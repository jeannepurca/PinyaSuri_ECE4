#!/usr/bin/env python3
# main_test.py

import time
import csv
import logging
import signal
import sys

import config
from pixhawk import Pixhawk
from camera import Camera
from metrics import FlightMetrics

# Global flag for graceful shutdown
running = True

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global running
    print("\n⚠ Shutdown requested...")
    running = False

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
    
    logger.info(f">>> Preparing to capture WP{waypoint}...")
    time.sleep(1.5)
    
    image_path = camera.capture(
        waypoint=waypoint,
        flight_number=flight_number,
        prefix="pinyasuri"
    )
    
    log_image_capture(flight_number, waypoint, pixhawk.position, image_path)
    
    print(f">>> Captured WP{waypoint} at {pixhawk.position['rel_alt']:.1f}m altitude")
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
        metrics.start_flight(True, pixhawk.battery_remaining)
        return True, flight_number
        
    elif not pixhawk.armed and was_armed:
        # Just disarmed
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

    if pixhawk.mode != "AUTO":
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
    
    print("🚁 Mission monitoring started.")

    while running:
        # Update pixhawk telemetry
        pixhawk.update()
        
        # Handle arm/disarm state changes
        was_armed, flight_number = handle_arm_state_change(
            pixhawk, metrics, was_armed, flight_number, captured_wp
        )
        
        # Update metrics during flight
        if pixhawk.armed:
            telemetry = get_telemetry_dict(pixhawk)
            if telemetry:
                metrics.update(telemetry)
        
        if should_capture_image(pixhawk, pixhawk.last_wp, captured_wp, logger):
            handle_waypoint_capture(
                pixhawk, camera, metrics, 
                pixhawk.last_wp, flight_number, captured_wp, logger
            )
        
        time.sleep(config.MAIN_LOOP_INTERVAL)
    
    return was_armed

def cleanup(camera, metrics, was_armed):
    """Clean up resources before exit"""
    print("\n>>> Cleaning up...")
    
    if was_armed:
        print(">>> Finalizing flight metrics...")
        metrics.end_flight(True)
    
    try:
        camera.close()
    except Exception as e:
        print(f"⚠ Error closing camera: {e} ⚠")
    
    print("✓ Cleanup complete")

def main():
    # Setup
    logger = setup_logging()
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize components
    pixhawk = Pixhawk()
    camera = Camera()
    metrics = FlightMetrics()
    
    pixhawk.wait_for_connection()
    initialize_csv()
    
    # Run main loop
    was_armed = False
    try:
        was_armed = main_loop(pixhawk, camera, metrics, logger)
    except Exception as e:
        logger.error(f"⚠ Fatal error: {e} ⚠", exc_info=True)
    finally:
        cleanup(camera, metrics, was_armed)

if __name__ == "__main__":
    main()