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
from image_capture import ImageCapture
from flight_metrics import FlightMetricsLogger

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


class TestFlightSystem:
    """Test flight system for data gathering"""

    def __init__(self):
        self.pixhawk: Optional[PixhawkInterface] = None
        self.camera: Optional[ImageCapture] = None
        self.metrics_logger: Optional[FlightMetricsLogger] = None
        self.shutdown_event = asyncio.Event()

    async def initialize(self, max_retries: int = 3) -> bool:
        """Initialize system components with retry logic"""

        config.ensure_directories()
        
        # Initialize Pixhawk
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"》 Initializing Pixhawk (attempt {attempt}/{max_retries})...")
                self.pixhawk = PixhawkInterface(system_address=config.PIXHAWK_ADDRESS)
                await self.pixhawk.connect(timeout=config.CONNECTION_TIMEOUT)
                logger.info("✓ Pixhawk connected successfully")
                break
            except Exception as e:
                logger.error(f"✗ Pixhawk connection failed: {e}")
                if attempt == max_retries:
                    logger.error("⚠ Maximum retry attempts reached for Pixhawk.")
                    return False
                await asyncio.sleep(2)

        # Initialize Camera
        try:
            logger.info("》 Initializing Camera...")
            self.camera = ImageCapture(output_dir=str(config.RAW_IMG_DIR))
            logger.info("✓ Camera initialized successfully")
        except Exception as e:
            logger.error(f"✗ Camera initialization failed: {e}")
            return False
        
        # Initialize Image Capture Log CSV
        self._initialize_capture_log()

        # Initialize Flight Metrics Logger
        self.metrics_logger = FlightMetricsLogger(
            self.pixhawk,
            output_csv=str(config.FLIGHT_METRICS_CSV)
        )

        return True

    def _initialize_capture_log(self):
        """Create image capture log CSV with headers"""

        capture_log = config.LOG_DIR / "image_captures.csv"
        
        if not capture_log.exists():
            header = [
                "timestamp_utc", "image_path", "lat", "lon", 
                "abs_alt_m", "rel_alt_m", "waypoint_idx", "waypoint_total"
            ]
            
            with open(capture_log, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
            logger.info(f"》 Created image capture log: {capture_log}")

    async def run_mission(self):
        """Main mission loop: monitor progress and capture images at waypoints"""
        
        # Create Queues for Telemetry
        pos_queue = asyncio.Queue()
        prog_queue = asyncio.Queue()
        imu_queue = asyncio.Queue()
        battery_queue = asyncio.Queue()
        armed_queue = asyncio.Queue()
        in_air_queue = asyncio.Queue()
        
        # Start Telemetry Subscriptions
        pos_task = asyncio.create_task(self.pixhawk.subscribe_positions(pos_queue))
        prog_task = asyncio.create_task(self.pixhawk.subscribe_mission_progress(prog_queue))
        imu_task = asyncio.create_task(self.pixhawk.subscribe_imu_accel(imu_queue))
        batt_task = asyncio.create_task(self.pixhawk.subscribe_battery(battery_queue))
        armed_task = asyncio.create_task(self.pixhawk.subscribe_armed(armed_queue))
        in_air_task = asyncio.create_task(self.pixhawk.subscribe_in_air(in_air_queue))
        
        # Pass queues to metrics logger
        self.metrics_logger.pos_queue = pos_queue
        self.metrics_logger.imu_queue = imu_queue
        self.metrics_logger.battery_queue = battery_queue
        self.metrics_logger.armed_queue = armed_queue

        metrics_task = asyncio.create_task(self.metrics_logger.run())

        # Mission State Variables
        last_progress = -1
        captured_at_progress = 0  # Start from 1 (skip WP0 takeoff point)
        latest_pos = None
        mission_total = 0
        mission_started = False
        mission_completed = False
        has_landed = False
        
        logger.info("=" * 60)
        logger.info("🍍 PINYASURI TEST FLIGHT READY! 🚁")
        logger.info("Waiting for drone to take off...")
        logger.info("=" * 60)

        try:
            while not self.shutdown_event.is_set():

                # Process In-Air Status (Wait for takeoff)
                try:
                    while True:
                        in_air = in_air_queue.get_nowait()
                        if in_air and not mission_started:
                            mission_started = True
                            logger.info("=" * 60)
                            logger.info("🛫 DRONE IN AIR - Mission monitoring started.")
                            logger.info("=" * 60)
                        
                        # Check for landing after mission completion
                        if mission_completed and not in_air and not has_landed:
                            has_landed = True
                            logger.info("=" * 60)
                            logger.info("🛬 DRONE LANDED - Shutting down in 5 seconds...")
                            logger.info("=" * 60)
                            await asyncio.sleep(5)      # Grace period for final logs
                            self.shutdown_event.set()
                except asyncio.QueueEmpty:
                    pass

                # Only process mission if drone is airborne
                if not mission_started:
                    await asyncio.sleep(config.MAIN_LOOP_INTERVAL)
                    continue
                
                # Process Mission Progress Updates
                try:
                    while True:
                        prog = prog_queue.get_nowait()
                        last_progress = prog["current"]
                        mission_total = prog["total"]
                        logger.info(f"》 Mission Progress: Waypoint {last_progress}/{mission_total}")
                        
                        # Check if mission completed (reached last waypoint)
                        if mission_total > 0 and last_progress == mission_total:
                            if not mission_completed:
                                mission_completed = True
                                logger.info("=" * 60)
                                logger.info("🎯 MISSION COMPLETED - All waypoints visited")
                                logger.info("Waiting for drone to return and land...")
                                logger.info("=" * 60)
                except asyncio.QueueEmpty:
                    pass
                
                # Process Position Updates
                try:
                    while True:
                        latest_pos = pos_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                
                # Capture Image at New Waypoint (skip WP0)
                if last_progress > 0 and last_progress != captured_at_progress:
                    await self._capture_at_waypoint(
                        last_progress, 
                        mission_total, 
                        latest_pos
                    )
                    captured_at_progress = last_progress
                
                await asyncio.sleep(config.MAIN_LOOP_INTERVAL)
        
        finally:
            # Cleanup Tasks
            logger.info("》 Stopping mission tasks...")
            for task in [pos_task, prog_task, imu_task, batt_task, armed_task, in_air_task, metrics_task]:
                task.cancel()
            await asyncio.gather(
                pos_task, prog_task, imu_task, batt_task, armed_task, in_air_task, metrics_task, 
                return_exceptions=True
            )

    async def _capture_at_waypoint(self, waypoint_idx: int, mission_total: int, position: Optional[dict]):
        """Capture image at waypoint and log metadata"""

        logger.info("=" * 60)
        logger.info(f"📸 WAYPOINT {waypoint_idx} REACHED - Capturing Image")
        logger.info("=" * 60)
        
        try:
            # Capture Image
            image_path = self.camera.capture(prefix=f"wp{waypoint_idx}")
            logger.info(f"》 Image saved: {image_path}")
            
            # Log Capture Metadata
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
            
            logger.info(f"✓ Waypoint {waypoint_idx} data logged successfully")
            
        except Exception as e:
            logger.error(f"✗ Error at waypoint {waypoint_idx}: {e}", exc_info=True)

    async def shutdown(self):
        """Graceful shutdown of all components"""

        logger.info("=" * 60)
        logger.info("⚠ INITIATING SHUTDOWN ⚠")
        logger.info("=" * 60)
        
        self.shutdown_event.set()
        
        if self.camera:
            self.camera.close()
        
        logger.info("✓ Shutdown complete")


async def main():
    """Main entry point for test flight"""
    
    system = TestFlightSystem()
    
    # Initialize System
    logger.info("=" * 60)
    logger.info("🍍 PINYASURI TEST FLIGHT SYSTEM 🚁")
    logger.info("=" * 60)
    
    if not await system.initialize():
        logger.error("✗ System initialization failed. Exiting.")
        return 1
    
    logger.info("=" * 60)
    logger.info("✓ ALL SYSTEMS READY FOR TEST FLIGHT")
    logger.info("System will start monitoring once drone takes off")
    logger.info("Press Ctrl+C to stop manually at any time")
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