#!/usr/bin/env python3

import asyncio
import logging
import csv
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path

import config
from pixhawk_mavlink import PixhawkMAVLink as PixhawkInterface
from flight_metrics import FlightMetrics
from image_capture import ImageCapture
from waypoint_detector import WaypointDetector
from mission_reader_mavlink import read_mission_waypoints_mavlink

# Ensure directories exist before logging
config.ensure_directories()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
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
        
        # Initialize Pixhawk via MAVLink UDP
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"》》》 Initializing Pixhawk MAVLink (attempt {attempt}/{max_retries})...")
                self.pixhawk = PixhawkInterface(connection_string=config.MAVLINK_CONNECTION)
                await self.pixhawk.connect(timeout=config.CONNECTION_TIMEOUT)
                logger.info("✓ Pixhawk MAVLink connected successfully.")
                break
            except Exception as e:
                logger.error(f"✗ Pixhawk connection failed: {e}")
                if attempt == max_retries:
                    logger.error("⚠ Maximum retry attempts reached for Pixhawk.")
                    return False
                await asyncio.sleep(2)

        # Download mission waypoints using direct MAVLink
        try:
            logger.info("》》》 Downloading mission waypoints via MAVLink...")
            
            waypoints = await read_mission_waypoints_mavlink(self.pixhawk)
            
            if len(waypoints) == 0:
                logger.warning("⚠ No waypoints found in mission!")
                logger.warning("⚠ System will run but won't capture images")
                self.waypoint_detector = None
            else:
                logger.info(f"✓ Loaded {len(waypoints)} waypoints for detection")
                self.waypoint_detector = WaypointDetector(waypoints, radius_meters=config.WAYPOINT_DETECTION_RADIUS)
                
                # Log all waypoints for debugging
                logger.info("=" * 60)
                logger.info("LOADED WAYPOINTS:")
                for idx, (lat, lon, alt) in enumerate(waypoints):
                    logger.info(f"  WP{idx+1}: ({lat:.7f}, {lon:.7f}, {alt:.1f}m)")
                logger.info("=" * 60)
                
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
                "abs_alt_m", "rel_alt_m", "waypoint_number", "total_waypoints",
                "flight_number"
            ]
            
            with open(capture_log, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
            logger.info(f"》 Created image capture log: {capture_log}")
    
    async def run_mission(self):
        """Main mission loop with continuous cycle support"""
        
        # Create Queues for Telemetry - Main Loop
        main_pos_queue = asyncio.Queue()
        main_imu_queue = asyncio.Queue()
        main_battery_queue = asyncio.Queue()
        main_armed_queue = asyncio.Queue()
        main_mode_queue = asyncio.Queue()
        main_in_air_queue = asyncio.Queue()
        
        # Create SEPARATE Queues for Metrics Logger
        metrics_pos_queue = asyncio.Queue()
        metrics_imu_queue = asyncio.Queue()
        metrics_battery_queue = asyncio.Queue()
        metrics_armed_queue = asyncio.Queue()
        
        # Start Telemetry Subscriptions - Main Loop
        pos_task = asyncio.create_task(self.pixhawk.subscribe_positions(main_pos_queue))
        imu_task = asyncio.create_task(self.pixhawk.subscribe_imu_accel(main_imu_queue))
        batt_task = asyncio.create_task(self.pixhawk.subscribe_battery(main_battery_queue))
        armed_task = asyncio.create_task(self.pixhawk.subscribe_armed(main_armed_queue))
        mode_task = asyncio.create_task(self.pixhawk.subscribe_flight_mode(main_mode_queue))
        in_air_task = asyncio.create_task(self.pixhawk.subscribe_in_air(main_in_air_queue))
        
        # Start SEPARATE Telemetry Subscriptions - Metrics Logger
        metrics_pos_task = asyncio.create_task(self.pixhawk.subscribe_positions(metrics_pos_queue))
        metrics_imu_task = asyncio.create_task(self.pixhawk.subscribe_imu_accel(metrics_imu_queue))
        metrics_batt_task = asyncio.create_task(self.pixhawk.subscribe_battery(metrics_battery_queue))
        metrics_armed_task = asyncio.create_task(self.pixhawk.subscribe_armed(metrics_armed_queue))

        # Pass SEPARATE queues to metrics logger
        self.metrics_logger.pos_queue = metrics_pos_queue
        self.metrics_logger.imu_queue = metrics_imu_queue
        self.metrics_logger.battery_queue = metrics_battery_queue
        self.metrics_logger.armed_queue = metrics_armed_queue

        metrics_task = asyncio.create_task(self.metrics_logger.run())

        # Mission State Variables
        latest_pos = None
        is_armed = False
        is_in_air = False
        mission_started = False
        was_armed_before = False
        current_flight_mode = "UNKNOWN"
        check_interval = 0.2
        last_check = 0
        flight_number = 0
        last_distance_log = 0

        # DEBUG: Counters
        position_update_count = 0
        mode_update_count = 0
        waypoint_check_count = 0
        
        logger.info("=" * 60)
        logger.info("🍍 PINYASURI TEST FLIGHT READY! 🚁")
        logger.info("System will run continuously. Press Ctrl+C to stop.")
        logger.info("=" * 60)

        try:
            while not self.shutdown_event.is_set():

                # Process Armed Status
                try:
                    while True:
                        armed_data = main_armed_queue.get_nowait()
                        new_armed = armed_data["armed"]
                        
                        # Detect ARM transition (start new flight)
                        if new_armed and not is_armed:
                            flight_number += 1
                            mission_started = True
                            was_armed_before = True
                            
                            # Reset waypoint detector for new flight
                            if self.waypoint_detector:
                                self.waypoint_detector.reset()
                            
                            logger.info("=" * 60)
                            logger.info(f"🛫 FLIGHT #{flight_number} - DRONE ARMED")
                            logger.info("   Mission monitoring started")
                            logger.info("=" * 60)

                        # Detect DISARM transition (end current flight)
                        if not new_armed and is_armed and was_armed_before:
                            logger.info("=" * 60)
                            logger.info(f"🛬 FLIGHT #{flight_number} - DRONE DISARMED")
                            logger.info(f"   Total position updates: {position_update_count}")
                            logger.info(f"   Total waypoint checks: {waypoint_check_count}")
                            if self.waypoint_detector:
                                captured = sorted([x+1 for x in self.waypoint_detector.captured])
                                logger.info(f"   Captured waypoints: {captured}")
                            logger.info("   Ready for next flight...")
                            logger.info("=" * 60)
                            
                            # Reset for next flight
                            mission_started = False
                            position_update_count = 0
                            waypoint_check_count = 0
                        
                        is_armed = new_armed
                        
                except asyncio.QueueEmpty:
                    pass
            
                # Process Position Updates
                try:
                    while True:
                        latest_pos = main_pos_queue.get_nowait()
                        position_update_count += 1
                except asyncio.QueueEmpty:
                    pass
            
                # Process Flight Mode Updates
                try:
                    while True:
                        mode = main_mode_queue.get_nowait()
                        mode_update_count += 1
                        if mode != current_flight_mode:
                            current_flight_mode = mode
                            logger.info(f"》 Flight Mode: {mode}")
                except asyncio.QueueEmpty:
                    pass
                
                # Process In-Air Status
                try:
                    while True:
                        new_in_air = main_in_air_queue.get_nowait()
                        
                        # Log transitions
                        if new_in_air and not is_in_air:
                            logger.info("》 Drone is now IN AIR - waypoint detection active")
                        elif not new_in_air and is_in_air:
                            logger.info("》 Drone is on GROUND - waypoint detection paused")
                        
                        is_in_air = new_in_air
                except asyncio.QueueEmpty:
                    pass

                # Check waypoints with periodic status logging
                current_time = asyncio.get_event_loop().time()
                
                # Log current status every 5 seconds when armed
                if mission_started and (current_time - last_distance_log >= 5.0):
                    last_distance_log = current_time
                    status = []
                    status.append(f"Armed={is_armed}")
                    status.append(f"InAir={is_in_air}")
                    status.append(f"HasPos={latest_pos is not None}")
                    status.append(f"HasWP={self.waypoint_detector is not None}")
                    
                    if latest_pos:
                        status.append(f"Pos=({latest_pos['lat']:.7f}, {latest_pos['lon']:.7f})")
                        status.append(f"Alt={latest_pos['rel_alt']:.1f}m")
                        
                        # Log distance to nearest waypoint
                        if self.waypoint_detector:
                            nearest_wp, nearest_dist = None, float('inf')
                            for idx, (wp_lat, wp_lon, wp_alt) in enumerate(self.waypoint_detector.waypoints):
                                if idx not in self.waypoint_detector.captured:
                                    dist = self.waypoint_detector.haversine_distance(
                                        latest_pos['lat'], latest_pos['lon'], wp_lat, wp_lon
                                    )
                                    if dist < nearest_dist:
                                        nearest_dist = dist
                                        nearest_wp = idx + 1
                            
                            if nearest_wp:
                                status.append(f"NearestWP={nearest_wp} ({nearest_dist:.1f}m)")
                    
                    logger.info(f"[STATUS] {' | '.join(status)}")

                # Check waypoints if we have position data
                if mission_started and latest_pos and self.waypoint_detector:
                    if current_time - last_check >= check_interval:
                        last_check = current_time
                        waypoint_check_count += 1
                        
                        # Check if near any waypoint
                        wp_idx, distance = self.waypoint_detector.check_position(
                            latest_pos["lat"],
                            latest_pos["lon"]
                        )
                        
                        if wp_idx is not None:
                            logger.info("=" * 60)
                            logger.info(f"📍 WAYPOINT {wp_idx + 1} DETECTED!")
                            logger.info(f"   Distance: {distance:.2f}m from waypoint")
                            logger.info(f"   In Air Status: {is_in_air}")
                            logger.info("=" * 60)
                            
                            await self._capture_at_waypoint(
                                wp_idx + 1,
                                len(self.waypoint_detector.waypoints),
                                latest_pos,
                                flight_number
                            )
                
                await asyncio.sleep(config.MAIN_LOOP_INTERVAL)
        
        except Exception as e:
            logger.error(f"✗ Error in mission loop: {e}", exc_info=True)
        
        finally:
            # Cleanup ALL Tasks (main + metrics)
            logger.info("》》》 Stopping mission tasks...")
            all_tasks = [
                pos_task, imu_task, batt_task, armed_task, mode_task, in_air_task,
                metrics_pos_task, metrics_imu_task, metrics_batt_task, metrics_armed_task,
                metrics_task
            ]
            for task in all_tasks:
                task.cancel()
            await asyncio.gather(*all_tasks, return_exceptions=True)

    async def _capture_at_waypoint(self, waypoint_idx: int, mission_total: int, 
                                   position: Optional[dict], flight_number: int):
        """Capture image at waypoint and log metadata"""

        logger.info("=" * 60)
        logger.info(f"📸 WAYPOINT {waypoint_idx} REACHED - Capturing image...")
        logger.info("=" * 60)  

        try:
            # Capture Image
            image_path = self.camera.capture(prefix=f"flight{flight_number}_wp{waypoint_idx}")
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
                    waypoint_idx, mission_total, flight_number
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
    logger.info("System ready for continuous flight cycles.")
    logger.info("Press Ctrl+C to stop.")
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