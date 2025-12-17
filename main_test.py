#!/usr/bin/env python3
# main_test.py

import time
import csv
import logging
import sys

import config
from pixhawk import Pixhawk
from camera import Camera
from metrics import FlightMetrics

# Global flag for graceful shutdown
running = True

def setup_logging():
    """Configure logging system"""
    config.ensure_directories()
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s',
        handlers=[
            logging.FileHandler(config.LOG_DIR / "test_flight.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("TestFlight")

def initialize_csv():
    """Create image log CSV with headers"""
    with open(config.IMAGE_LOG_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "flight", "waypoint", "lat", "lon", "rel_alt", "image"])

def log_image_capture(flight_number, waypoint, position, image_path):
    """Write image capture data to CSV"""
    with open(config.IMAGE_LOG_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            time.time(),
            flight_number,
            waypoint,
            position["lat"],
            position["lon"],
            position["rel_alt"],
            image_path
        ])

def handle_waypoint_capture(pixhawk, camera, metrics, waypoint, flight_number, captured_wp, logger):
    """Capture image at waypoint and log data"""
    if waypoint in captured_wp:
        return False
    
    logger.info("=" * 60)
    logger.info(f">>> WAYPOINT {waypoint} REACHED - Capturing image...")
    logger.info("=" * 60)
    time.sleep(1.5)
    
    image_path = camera.capture(
        waypoint=waypoint,
        flight_number=flight_number,
        prefix="pinyasuri"
    )
    
    log_image_capture(flight_number, waypoint, pixhawk.position, image_path)
    
    logger.info(f">>> Captured WP{waypoint} at {pixhawk.position['rel_alt']:.1f}m altitude")
    captured_wp.add(waypoint)
    metrics.increment_waypoint()
    
    return True

def get_telemetry_dict(pixhawk):
    """Build telemetry dictionary for metrics"""
    if not pixhawk.position:
        return None
    
    return {
        "rel_alt": pixhawk.position["rel_alt"],
        "lat": pixhawk.position["lat"],
        "lon": pixhawk.position["lon"],
        "imu_accel": pixhawk.imu_accel,
        "battery_remaining": pixhawk.battery_remaining
    }

def handle_arm_state_change(pixhawk, metrics, was_armed, flight_number, captured_wp):
    """Detect and handle arm/disarm transitions"""
    if pixhawk.armed and not was_armed:
        # Just armed
        logger.info("=" * 60)
        logger.info(f"🛫 FLIGHT #{flight_number} - DRONE ARMED")
        logger.info("   Mission monitoring started.  ")
        logger.info("=" * 60)
        metrics.start_flight(True, pixhawk.battery_remaining)
        return True, flight_number
        
    elif not pixhawk.armed and was_armed:
        # Just disarmed
        logger.info(f"🛬 FLIGHT #{flight_number} - DRONE DISARMED")
        metrics.end_flight(True)
        captured_wp.clear()
        return False, flight_number + 1
    
    return was_armed, flight_number

def is_drone_in_air(pixhawk):
    if not pixhawk.position:
        return False
    
    return pixhawk.position["rel_alt"] >= config.MIN_ALTITUDE_FOR_CAPTURE

def should_capture_image(pixhawk, waypoint, captured_wp, logger):
    """Check if conditions are met for image capture"""

    # Basic checks
    if not pixhawk.armed:
        return False
    
    if not waypoint:
        return False
    
    if not pixhawk.position:
        return False
    
    if not is_drone_in_air(pixhawk):
        logger.debug(f"⚠ Drone too low: {pixhawk.position['rel_alt']:.2f}m < {config.MIN_ALTITUDE_FOR_CAPTURE}m⚠")
        return False
    
    if waypoint in captured_wp:
        return False
    
    # All failsafes passed!
    return True

def main_loop(pixhawk, camera, metrics, logger):
    captured_wp = set()
    flight_number = 1
    was_armed = False
    current_mode = "UNKNOWN"
    was_in_air = False
    last_waypoint = None
    
    logger.info("=" * 60)
    logger.info("🍍 PINYASURI FLIGHT SYSTEM READY! 🚁")
    logger.info("System will run continuously. Press Ctrl+C to stop.")
    logger.info("=" * 60)

    while running:
        # Update pixhawk telemetry
        pixhawk.update()
        
        # Handle arm/disarm state changes
        was_armed, flight_number = handle_arm_state_change(
            pixhawk, metrics, was_armed, flight_number, captured_wp
        )

        # Check for flight mode changes
        if pixhawk.mode != current_mode:
            current_mode = pixhawk.mode
            logger.info(f">>> Flight Mode: {current_mode}")

        # Update metrics during flight
        if pixhawk.armed:
            telemetry = get_telemetry_dict(pixhawk)
            if telemetry:
                metrics.update(telemetry)
        
        # Check for image capture
        if should_capture_image(pixhawk, pixhawk.last_wp, captured_wp, logger):
            handle_waypoint_capture(
                pixhawk, camera, metrics, 
                pixhawk.last_wp, flight_number, captured_wp, logger
            )
        
        time.sleep(config.MAIN_LOOP_INTERVAL)
    
    return was_armed

def cleanup(camera, metrics, was_armed,):
    """Clean up resources before exit"""
    logger.info("=" * 60)
    logger.info("⚠ INITIATING SHUTDOWN ⚠")
    logger.info("=" * 60)
    logger.info(">>> Stopping mission tasks...")

    if was_armed:
        logger.info(">>> Finalizing flight metrics...")
        metrics.end_flight(True)
    
    try:
        camera.close()
    except Exception as e:
        logger.info(f"⚠ Error closing camera: {e} ⚠")
    
    logger.info("✓ Shutdown complete")

def main():
    global running
    
    # Setup
    logger = setup_logging()
    
    # Initialize components
    pixhawk = Pixhawk()
    camera = Camera()
    metrics = FlightMetrics()

    logger.info("=" * 60)
    logger.info("🍍 PINYASURI FLIGHT SYSTEM 🚁")
    logger.info("=" * 60)
    
    # Wait for connection
    try:
        pixhawk.wait_for_connection()
        initialize_csv()
        
        # Run main loop
        was_armed = main_loop(pixhawk, camera, metrics, logger)
        
    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 60)
        logger.info("⚠ MANUAL STOP - Interrupted by user! ⚠")
        logger.info("=" * 60)
        running = False

        time.sleep(0.5)
        was_armed = pixhawk.armed if pixhawk else False
    except Exception as e:
        logger.error(f"⚠ Fatal error: {e} ⚠", exc_info=True)
        was_armed = False
    finally:
        cleanup(camera, metrics, was_armed, logger)

if __name__ == "__main__":
    main()