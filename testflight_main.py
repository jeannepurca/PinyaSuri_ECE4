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
from waypoint_detector import WaypointDetector

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
        self.waypoint_detector: Optional[WaypointDetector] = None
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

        # Download mission waypoints for distance-based detection
        try:
            logger.info("》》》 Downloading mission waypoints...")
            mission_plan = await self.pixhawk.drone.mission.download_mission()
            
            # Extract waypoint coordinates (skip home/takeoff/land commands)
            waypoints = []
            for idx, item in enumerate(mission_plan.mission_items):
                # Command 16 = WAYPOINT, skip others (22=TAKEOFF, 20=LAND, etc.)
                if item.command == 16 and idx > 0:  # Skip home (idx 0)
                    waypoints.append((item.latitude_deg, item.longitude_deg, item.altitude_m))
                    logger.info(f"  WP{len(waypoints)}: ({item.latitude_deg:.7f}, {item.longitude_deg:.7f})")
            
            if len(waypoints) == 0:
                logger.warning("⚠ No waypoints found in mission!")
                logger.warning("⚠ System will run but won't capture images")
                self.waypoint_detector = None
            else:
                logger.info(f"✓ Loaded {len(waypoints)} waypoints for detection")
                # Initialize waypoint detector with 5m radius
                self.waypoint_detector = WaypointDetector(waypoints, radius_meters=5.0)
                
        except Exception as e:
            logger.warning(f"⚠ Could not download mission: {e}")
            logger.warning("⚠ Distance-based detection disabled")
            self.waypoint_detector = None

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

        return True

    def _initialize_capture_log(self):
        """Create CSV for image capture logs"""
        capture_log = config.LOG_DIR / "image_captures.csv"
        
        if not capture_log.exists():
            header = [
                "timestamp_utc", "image_path", "lat", "lon", 
                "abs_alt_m", "rel_alt_m", "waypoint_number", "total_waypoints"
            ]
            
            with open(capture_log, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
            logger.info(f"》 Created image capture log: {capture_log}")
    
    async def run_mission(self):
        """Main mission loop with distance-based waypoint detection"""
        
        # Create Queues for Telemetry
        pos_queue = asyncio.Queue()
        imu_queue = asyncio.Queue()
        battery_queue = asyncio.Queue()
        armed_queue = asyncio.Queue()
        mode_queue = asyncio.Queue()
        
        # Start Telemetry Subscriptions
        pos_task = asyncio.create_task(self.pixhawk.subscribe_positions(pos_queue))
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
        latest_pos = None
        is_armed = False
        mission_started = False
        was_armed_before = False
        current_flight_mode = "UNKNOWN"
        check_interval = 0.5  # Check position every 500ms
        last_check = 0

        # DEBUG: Counters
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
                            logger.info(f"》 DEBUG: Total position updates: {position_update_count}")
                            if self.waypoint_detector:
                                logger.info(f"》 DEBUG: Captured waypoints: {sorted([x+1 for x in self.waypoint_detector.captured])}")
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

                # Only check waypoints if armed and we have position data
                if mission_started and latest_pos and self.waypoint_detector:
                    current_time = asyncio.get_event_loop().time()
                    
                    if current_time - last_check >= check_interval:
                        last_check = current_time
                        
                        # Check if near any waypoint
                        wp_idx, distance = self.waypoint_detector.check_position(
                            latest_pos["lat"],
                            latest_pos["lon"]
                        )
                        
                        if wp_idx is not None:
                            logger.info("=" * 60)
                            logger.info(f"📍 WAYPOINT {wp_idx + 1} DETECTED!")
                            logger.info(f"   Distance: {distance:.2f}m from waypoint")
                            logger.info("=" * 60)
                            
                            await self._capture_at_waypoint(
                                wp_idx + 1,  # Human-readable numbering (1-indexed)
                                len(self.waypoint_detector.waypoints),
                                latest_pos
                            )
                
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