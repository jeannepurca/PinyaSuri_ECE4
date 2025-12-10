#!/usr/bin/env python3

import asyncio
import logging
import csv
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path

import config
from pixhawk_interface import PixhawkInterface
from flight_metrics import FlightMetrics
from image_capture import ImageCapture

# Ensure directories exist before logging
config.ensure_directories()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_DIR / "test_flight.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TestFlight")


class TestFlight:
    """Test flight system for data gathering (no AI classification)"""

    def __init__(self):
        self.pixhawk: Optional[PixhawkInterface] = None
        self.camera: Optional[ImageCapture] = None
        self.metrics_logger: Optional[FlightMetrics] = None
        self.shutdown_event = asyncio.Event()
        self._capture_lock = asyncio.Lock()

    async def initialize(self, max_retries: int = 3) -> bool:
        """Initialize system components (Pixhawk, Camera, CSV, Metrics)""" 

        config.ensure_directories()
        
        # Initialize Pixhawk
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"》》》 Initializing Pixhawk (attempt {attempt}/{max_retries})...")
                self.pixhawk = PixhawkInterface(system_address=config.PIXHAWK_ADDRESS)
                await self.pixhawk.connect(timeout=config.CONNECTION_TIMEOUT)
                logger.info("✓ Pixhawk connected successfully.")
                break
            except Exception as e:
                logger.error(f"✗ Pixhawk connection failed: {e}")
                if attempt == max_retries:
                    logger.error("⚠ Maximum retry attempts reached for Pixhawk.")
                    return False
                await asyncio.sleep(2)

        # Initialize Camera
        try:
            logger.info("》》》 Initializing Camera...")
            self.camera = ImageCapture(
                output_dir=str(config.TEST_IMAGE_DIR)
            )
            logger.info("✓ Camera initialized successfully.")
        except Exception as e:
            logger.error(f"✗ Camera initialization failed: {e}")
            return False

        # Initialize CSV for Image Capture Logs
        self._initialize_capture_log()

        # Initialize Flight Metrics Logger
        self.metrics_logger = FlightMetrics(
            self.pixhawk,
            output_csv=str(config.FLIGHT_METRICS_CSV)
        )

        # Request mission count from Pixhawk (for Mission Planner missions)
        await self.pixhawk.request_mission_count()
        await asyncio.sleep(1)

        return True

    def _initialize_capture_log(self):
        """Create CSV for image capture logs"""
        capture_log = config.LOG_DIR / "image_captures.csv"
        
        if not capture_log.exists():
            header = [
                "timestamp_utc", "image_path", "lat", "lon", 
                "abs_alt_m", "rel_alt_m", "mission_item_current", "mission_item_total"
            ]
            
            with open(capture_log, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
            logger.info(f"》 Created image capture log: {capture_log}")
    
    async def run_mission(self):
        """Main mission loop: monitor progress and capture images"""
        
        # Create Queues for Telemetry
        pos_queue = asyncio.Queue()
        prog_queue = asyncio.Queue()
        imu_queue = asyncio.Queue()
        battery_queue = asyncio.Queue()
        armed_queue = asyncio.Queue()
        mode_queue = asyncio.Queue()
        
        # Start Telemetry Subscriptions
        pos_task = asyncio.create_task(self.pixhawk.subscribe_positions(pos_queue))
        prog_task = asyncio.create_task(self.pixhawk.subscribe_mission_progress(prog_queue))
        imu_task = asyncio.create_task(self.pixhawk.subscribe_imu_accel(imu_queue))
        batt_task = asyncio.create_task(self.pixhawk.subscribe_battery(battery_queue))
        armed_task = asyncio.create_task(self.pixhawk.subscribe_armed(armed_queue))
        mode_task = asyncio.create_task(self.pixhawk.subscribe_flight_mode(mode_queue))

        # Pass queues to metrics logger
        self.metrics_logger.pos_queue = pos_queue
        self.metrics_logger.imu_queue = imu_queue
        self.metrics_logger.battery_queue = battery_queue
        self.metrics_logger.armed_queue = armed_queue

        metrics_task = asyncio.create_task(self.metrics_logger.run())

        # Mission State Variables
        last_progress = -1
        captured_waypoints = set()
        latest_pos = None
        mission_total = 0
        is_armed = False
        mission_started = False
        was_armed_before = False
        current_flight_mode = "UNKNOWN"

        # DEBUG: Counters
        progress_update_count = 0
        position_update_count = 0
        mode_update_count = 0
        
        logger.info("=" * 60)
        logger.info("🍍 PINYASURI TEST FLIGHT READY! 🚁")
        logger.info("Waiting for drone to arm...")
        logger.info("=" * 60)

        try:
            while not self.shutdown_event.is_set():

                # Process Armed Status
                try:
                    while True:
                        armed_data = armed_queue.get_nowait()
                        is_armed = armed_data["armed"]
                        logger.debug(f"🔧 DEBUG: Armed status - {is_armed}")
                        
                        # Start monitoring when armed
                        if is_armed and not mission_started:
                            mission_started = True
                            was_armed_before = True
                            logger.info("=" * 60)
                            logger.info("🛫 DRONE ARMED - Mission monitoring started.")
                            logger.info("=" * 60)

                        # Detect disarm after mission (landing)
                        if was_armed_before and not is_armed:
                            logger.info("=" * 60)
                            logger.info("🛬 DRONE DISARMED - Mission complete.")
                            logger.info(f"》 DEBUG: Total progress updates: {progress_update_count}")
                            logger.info(f"》 DEBUG: Total position updates: {position_update_count}")
                            logger.info(f"》 DEBUG: Captured waypoints: {sorted(captured_waypoints)}")
                            logger.info("》》》 Shutting down in 5 seconds...")
                            logger.info("=" * 60)
                            await asyncio.sleep(5)
                            self.shutdown_event.set()
                except asyncio.QueueEmpty:
                    pass
            
                # Process Position Updates
                try:
                    while True:
                        latest_pos = pos_queue.get_nowait()
                        position_update_count += 1
                except asyncio.QueueEmpty:
                    pass
            
                # Process Flight Mode Updates
                try:
                    while True:
                        mode = mode_queue.get_nowait()
                        mode_update_count += 1
                        if mode != current_flight_mode:
                            current_flight_mode = mode
                            logger.info(f"》 Flight Mode: {mode}")
                except asyncio.QueueEmpty:
                    pass

                # Only process mission if armed
                if not mission_started:
                    await asyncio.sleep(config.MAIN_LOOP_INTERVAL)
                    continue

                # Process Mission Progress Updates
                try:
                    while True:
                        prog = prog_queue.get_nowait()
                        progress_update_count += 1
                        current_waypoint = prog["current"]
                        mission_total = prog["total"]
                        
                        # Only process if waypoint changed
                        if current_waypoint != last_progress:
                            logger.info(f"》 Mission Progress: Waypoint {current_waypoint}/{mission_total}")
                            last_progress = current_waypoint
                            
                            # Capture image if this waypoint hasn't been processed yet
                            if current_waypoint > 0 and current_waypoint not in captured_waypoints:
                                # Use lock to prevent duplicate captures
                                async with self._capture_lock:
                                    if current_waypoint not in captured_waypoints:
                                        logger.info(f"》 NEW WAYPOINT: {current_waypoint} - Capturing")
                                        
                                        # Wait briefly for position to stabilize
                                        await asyncio.sleep(0.2)
                                        
                                        # Get most recent position
                                        capture_pos = latest_pos
                                        
                                        await self._capture_at_waypoint(
                                            current_waypoint,
                                            mission_total,
                                            capture_pos
                                        )
                                        captured_waypoints.add(current_waypoint)
                            else:
                                logger.debug(f"🔧 Waypoint {current_waypoint} already captured")
                        
                except asyncio.QueueEmpty:
                    pass
                
                await asyncio.sleep(config.MAIN_LOOP_INTERVAL)
        
        except Exception as e:
            logger.error(f"✗ Error in mission loop: {e}", exc_info=True)
        
        finally:
            # Cleanup Tasks
            logger.info("》》》 Stopping mission tasks...")
            for task in [pos_task, prog_task, imu_task, batt_task, armed_task, mode_task, metrics_task]:
                task.cancel()
            await asyncio.gather(
                pos_task, prog_task, imu_task, batt_task, armed_task, mode_task, metrics_task, 
                return_exceptions=True
            )

    async def _capture_at_waypoint(self, waypoint_idx: int, mission_total: int, position: Optional[dict]):
        """Capture image at waypoint and log metadata"""

        logger.info("=" * 60)
        logger.info(f"📸 WAYPOINT {waypoint_idx} REACHED - Capturing image...")
        logger.info("=" * 60)  

        try:
            # Capture Image
            image_path = self.camera.capture(prefix=f"wp{waypoint_idx}")
            logger.info(f"✓ Image captured: {image_path}")
            
            # Log to CSV
            timestamp = datetime.utcnow().isoformat()
            lat = position["lat"] if position else ""
            lon = position["lon"] if position else ""
            abs_alt = position["abs_alt"] if position else ""
            rel_alt = position["rel_alt"] if position else ""
            
            capture_log = config.LOG_DIR / "image_captures.csv"
            
            with open(capture_log, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp, image_path, lat, lon, abs_alt, rel_alt,
                    waypoint_idx, mission_total
                ])
            
            # Display Position Info
            if position:
                logger.info(f"  Location: {lat:.6f}°, {lon:.6f}°")
                logger.info(f"  Altitude: {rel_alt:.1f}m (relative), {abs_alt:.1f}m (absolute)")
            
            logger.info(f"✓ Waypoint {waypoint_idx} data logged successfully.")
            
        except Exception as e:
            logger.error(f"✗ Error capturing at waypoint {waypoint_idx}: {e}", exc_info=True)

    async def shutdown(self):
        """Graceful shutdown of all components"""

        logger.info("=" * 60)
        logger.info("⚠ INITIATING SHUTDOWN ⚠")
        logger.info("=" * 60)
        
        self.shutdown_event.set()
        
        if self.camera:
            self.camera.close()
        
        logger.info("✓ Shutdown complete.")


async def main():
    """Main entry point"""
    
    system = TestFlight()
    
    # Initialize system
    logger.info("=" * 60)
    logger.info("🍍 PINYASURI TEST FLIGHT 🚁")
    logger.info("=" * 60)

    if not await system.initialize():
        logger.error("✗ System initialization failed. Exiting.")
        return 1
    
    logger.info("=" * 60)
    logger.info("✓ ALL SYSTEMS INITIALIZED SUCCESSFULLY!")
    logger.info("System will start monitoring once drone is armed.")
    logger.info("Press Ctrl+C to stop manually at any time.")
    logger.info("=" * 60)
    
    # Run Mission
    try:
        await system.run_mission()
    except KeyboardInterrupt:
        logger.info("=" * 60)
        logger.info("⚠ MANUAL STOP - Interrupted by user! ⚠")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}", exc_info=True)
        return 1
    finally:
        await system.shutdown()
    
    logger.info("=" * 60)
    logger.info("⚠ PINYASURI TEST FLIGHT STOPPED ⚠")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))