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
from old_files.image_capture import ImageCapture
from ai_classifier import Classifier
from old_files.waypoint_detector import WaypointDetector
from mission_reader_mavsdk import read_mission_waypoints_mavsdk

# Ensure directories exist before logging
config.ensure_directories()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    handlers=[
        logging.FileHandler(config.LOG_DIR / "flight.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PinyaSuri")


class PinyaSuri:
    """Main system coordinator for PinyaSuri with continuous cycle support"""

    def __init__(self):
        self.pixhawk: Optional[PixhawkInterface] = None
        self.camera: Optional[ImageCapture] = None
        self.classifier: Optional[Classifier] = None
        self.metrics_logger: Optional[FlightMetrics] = None
        self.waypoint_detector: Optional[WaypointDetector] = None
        self.shutdown_event = asyncio.Event()
        self._capture_lock = asyncio.Lock()

    async def initialize(self, max_retries: int = 3) -> bool:
        """Initialize system components (Pixhawk, Camera, AI, CSV, Metrics)""" 

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

        # Download mission waypoints using MAVSDK
        try:
            logger.info("》》》 Downloading mission waypoints via MAVSDK...")
            
            waypoints = await read_mission_waypoints_mavsdk(self.pixhawk)
            
            if len(waypoints) == 0:
                logger.warning("⚠ No waypoints found in mission!")
                logger.warning("⚠ System will run but won't capture images")
                self.waypoint_detector = None
            else:
                logger.info(f"✓ Loaded {len(waypoints)} waypoints for detection")
                self.waypoint_detector = WaypointDetector(waypoints, radius_meters=config.WAYPOINT_DETECTION_RADIUS)
                
        except Exception as e:
            logger.warning(f"⚠ Could not download mission: {e}")
            logger.warning("⚠ Distance-based detection disabled")
            self.waypoint_detector = None

        # Initialize Camera
        try:
            logger.info("》》》 Initializing Camera...")
            self.camera = ImageCapture(
                output_dir=str(config.IMAGE_DIR)
            )
            logger.info("✓ Camera initialized successfully.")
        except Exception as e:
            logger.error(f"✗ Camera initialization failed: {e}")
            return False
        
        # Initialize AI Classifier
        try:
            logger.info("》》》 Loading AI Model...")
            self.classifier = Classifier(
                model_path=str(config.MODEL_PATH),
                input_size=config.MODEL_INPUT_SIZE
            )
            logger.info("✓ AI Model loaded successfully.")
        except Exception as e:
            logger.error(f"✗ AI Model loading failed: {e}")
            return False

        # Initialize CSV for Classification Results
        self._initialize_classification_csv()

        # Initialize Flight Metrics Logger
        self.metrics_logger = FlightMetrics(
            self.pixhawk,
            output_csv=str(config.FLIGHT_METRICS_CSV)
        )

        return True

    def _initialize_classification_csv(self):
        """Create CSV for AI outputs"""

        if not config.CLASSIFICATION_CSV.exists():
            header = [
                "timestamp_utc", "image_path", "lat", "lon", "abs_alt_m", "rel_alt_m",
                "waypoint_number", "total_waypoints", "pred_idx", "pred_label",
                "confidence", "flight_number"  # ADDED: Track which flight
            ]
            
            with open(config.CLASSIFICATION_CSV, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
            logger.info(f"》 Created classification log: {config.CLASSIFICATION_CSV}")
    
    async def run_mission(self):
        """Main mission loop with continuous cycle support"""
        
        # Create Queues for Telemetry
        pos_queue = asyncio.Queue()
        imu_queue = asyncio.Queue()
        battery_queue = asyncio.Queue()
        armed_queue = asyncio.Queue()
        mode_queue = asyncio.Queue()
        in_air_queue = asyncio.Queue()
        
        # Start Telemetry Subscriptions
        pos_task = asyncio.create_task(self.pixhawk.subscribe_positions(pos_queue))
        imu_task = asyncio.create_task(self.pixhawk.subscribe_imu_accel(imu_queue))
        batt_task = asyncio.create_task(self.pixhawk.subscribe_battery(battery_queue))
        armed_task = asyncio.create_task(self.pixhawk.subscribe_armed(armed_queue))
        mode_task = asyncio.create_task(self.pixhawk.subscribe_flight_mode(mode_queue))
        in_air_task = asyncio.create_task(self.pixhawk.subscribe_in_air(in_air_queue))

        # Pass queues to metrics logger (FIXED)
        self.metrics_logger.pos_queue = pos_queue
        self.metrics_logger.imu_queue = imu_queue
        self.metrics_logger.battery_queue = battery_queue
        self.metrics_logger.armed_queue = armed_queue

        metrics_task = asyncio.create_task(self.metrics_logger.run())

        # Mission State Variables
        latest_pos = None
        is_armed = False
        is_in_air = False
        mission_started = False
        was_armed_before = False
        current_flight_mode = "UNKNOWN"
        check_interval = 0.5
        last_check = 0
        flight_number = 0  # Track flight cycles

        # DEBUG: Counters
        position_update_count = 0
        mode_update_count = 0
        
        logger.info("=" * 60)
        logger.info("🍍 PINYASURI SYSTEM READY! 🚁")
        logger.info("System will run continuously. Press Ctrl+C to stop.")
        logger.info("=" * 60)

        try:
            while not self.shutdown_event.is_set():

                # Process Armed Status
                try:
                    while True:
                        armed_data = armed_queue.get_nowait()
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
                            if self.waypoint_detector:
                                captured = sorted([x+1 for x in self.waypoint_detector.captured])
                                logger.info(f"   Captured waypoints: {captured}")
                            logger.info("   Ready for next flight...")
                            logger.info("=" * 60)
                            
                            # Reset for next flight
                            mission_started = False
                            position_update_count = 0
                        
                        is_armed = new_armed
                        
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
                
                # Process In-Air Status
                try:
                    while True:
                        new_in_air = in_air_queue.get_nowait()
                        
                        # Log transitions
                        if new_in_air and not is_in_air:
                            logger.info("》 Drone is now IN AIR - waypoint detection active")
                        elif not new_in_air and is_in_air:
                            logger.info("》 Drone is on GROUND - waypoint detection paused")
                        
                        is_in_air = new_in_air
                except asyncio.QueueEmpty:
                    pass

                # Only check waypoints if armed, in air, and we have position data
                if mission_started and is_in_air and latest_pos and self.waypoint_detector:
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
                            
                            await self._process_waypoint(
                                wp_idx + 1,
                                len(self.waypoint_detector.waypoints),
                                latest_pos,
                                flight_number
                            )
                
                await asyncio.sleep(config.MAIN_LOOP_INTERVAL)
        
        except Exception as e:
            logger.error(f"✗ Error in mission loop: {e}", exc_info=True)
        
        finally:
            # Cleanup Tasks
            logger.info("》》》 Stopping mission tasks...")
            for task in [pos_task, imu_task, batt_task, armed_task, mode_task, in_air_task, metrics_task]:
                task.cancel()
            await asyncio.gather(
                pos_task, imu_task, batt_task, armed_task, mode_task, in_air_task, metrics_task, 
                return_exceptions=True
            )

    async def _process_waypoint(self, waypoint_idx: int, mission_total: int, 
                               position: Optional[dict], flight_number: int):
        """Capture image and run classification at a waypoint"""

        logger.info("=" * 60)
        logger.info(f"📸 WAYPOINT {waypoint_idx} REACHED - Processing...")
        logger.info("=" * 60)  

        try:
            # Capture Image
            image_path = self.camera.capture(prefix=f"flight{flight_number}_wp{waypoint_idx}")
            logger.info(f"✓ Image captured: {image_path}")
            
            # Run AI Classification
            result = self.classifier.predict(image_path)
            pred_label = config.get_class_name(result["index"])
            logger.info(f"》 Classification: {pred_label} (confidence: {result['confidence']:.2%})")
            
            # Log to CSV
            timestamp = datetime.utcnow().isoformat()
            lat = position["lat"] if position else ""
            lon = position["lon"] if position else ""
            abs_alt = position["abs_alt"] if position else ""
            rel_alt = position["rel_alt"] if position else ""
            
            with open(config.CLASSIFICATION_CSV, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp, image_path, lat, lon, abs_alt, rel_alt,
                    waypoint_idx, mission_total, result["index"], pred_label,
                    result["confidence"], flight_number
                ])
            
            # Display Position Info
            if position:
                logger.info(f"  Location: {lat:.6f}°, {lon:.6f}°")
                logger.info(f"  Altitude: {rel_alt:.1f}m (relative), {abs_alt:.1f}m (absolute)")
            
            logger.info(f"✓ Waypoint {waypoint_idx} processed successfully.")
            
        except Exception as e:
            logger.error(f"✗ Error processing waypoint {waypoint_idx}: {e}", exc_info=True)

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
    
    system = PinyaSuri()
    
    # Initialize system
    logger.info("=" * 60)
    logger.info("🍍 WELCOME TO PINYASURI SYSTEM 🚁")
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
    logger.info("⚠ PINYASURI SYSTEM STOPPED ⚠")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))