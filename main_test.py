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
    
    # CRITICAL FIX: Add stabilization delay
    # Wait for drone to fully stabilize before capturing
    logger.info(">>> Waiting for drone to stabilize...")
    time.sleep(2.5)
    
    # Double-check we're still hovering after the delay
    pixhawk.update()
    if not pixhawk.is_hovering(threshold=0.3):
        logger.warning(f"⚠ Drone still moving after delay! Speed: {pixhawk.groundspeed:.2f} m/s")
        return False
    
    image_path = camera.capture(
        waypoint=waypoint,
        flight_number=flight_number,
        prefix="pinyasuri"
    )
    
    log_image_capture(flight_number, waypoint, pixhawk.position, image_path)
    
    logger.info(f"> Captured WP{waypoint} at {pixhawk.position['rel_alt']:.1f}m altitude")
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

def handle_arm_state_change(pixhawk, metrics, was_armed, flight_number, captured_wp, logger):
    """Detect and handle arm/disarm transitions"""
    if pixhawk.armed and not was_armed:
        # Just armed
        logger.info("=" * 60)
        logger.info(f"🛫 FLIGHT #{flight_number} - DRONE ARMED")
        logger.info("   Mission monitoring started.  ")
        logger.info("=" * 60)
        metrics.start_flight(True, pixhawk.battery_remaining)
        pixhawk.clear_waypoint_log()  # Clear old waypoint logs
        return True, flight_number
        
    elif not pixhawk.armed and was_armed:
        # Just disarmed
        logger.info(f"🛬 FLIGHT #{flight_number} - DRONE DISARMED")
        metrics.end_flight(True)
        captured_wp.clear()
        pixhawk.clear_waypoint_log()
        return False, flight_number + 1
    
    return was_armed, flight_number

def is_drone_in_air(pixhawk):
    if not pixhawk.position:
        return False
    
    return pixhawk.position["rel_alt"] >= config.MIN_ALTITUDE_FOR_CAPTURE

def should_capture_image(pixhawk, waypoint, captured_wp, logger):
    """Check if conditions are met for image capture"""

    # 1. Drone must be armed
    if not pixhawk.armed:
        return False
    
    # 2. Must have valid waypoint
    if not waypoint:
        return False
    
    # 3. Must have position data from GPS
    if not pixhawk.position:
        logger.debug("⚠ Cannot capture: no position data yet!")
        return False
    
    # 4. Must be in the air (altitude >= 2.0m)
    if not is_drone_in_air(pixhawk):
        return False
    
    # 5. Must have already captured this waypoint
    if waypoint in captured_wp:
        return False
    
    # IMPORTANT: Only capture at actual mapping waypoints (not takeoff/RTL)
    valid_capture_waypoints = [2, 3, 4]
    if waypoint not in valid_capture_waypoints:
        return False
    
    # CRITICAL FIX #1: Stricter hover detection
    # Use tighter threshold to ensure drone is truly stationary
    if not pixhawk.is_hovering(threshold=0.3):
        logger.debug(f"⚠ Still moving at {pixhawk.groundspeed:.2f} m/s")
        return False
    
    # CRITICAL FIX #2: Altitude stability check
    # Ensure altitude isn't changing rapidly (vertical stabilization)
    if not pixhawk.is_altitude_stable(threshold=0.5, window_size=7):
        logger.debug(f"⚠ Altitude not stable: {pixhawk.get_altitude_variation():.2f} m variation")
        return False
    
    # CRITICAL FIX #3: Verify waypoint was actually reached
    # Check if we received the MISSION_ITEM_REACHED event for this waypoint
    if waypoint not in pixhawk.wp_reached_log:
        logger.debug(f"⚠ WP{waypoint} not confirmed reached yet")
        return False
    
    # All checks passed!
    logger.info(f"✓ All capture conditions met for WP{waypoint}!")
    return True

def main_loop(pixhawk, camera, metrics, logger):
    captured_wp = set()
    flight_number = 1
    was_armed = False
    current_mode = "UNKNOWN"
    
    logger.info("=" * 60)
    logger.info("🍍 PINYASURI FLIGHT SYSTEM READY! 🚁")
    logger.info("System will run continuously. Press Ctrl+C to stop.")
    logger.info("=" * 60)

    while running:
        # Update pixhawk telemetry
        pixhawk.update()
        
        # Handle arm/disarm state changes
        was_armed, flight_number = handle_arm_state_change(
            pixhawk, metrics, was_armed, flight_number, captured_wp, logger
        )

        # Check for flight mode changes
        if pixhawk.mode != current_mode:
            current_mode = pixhawk.mode
            logger.info(f"> Flight Mode: {current_mode}")

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

def cleanup(camera, metrics, was_armed, logger):
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
    
    logger.info("✓ Shutdown complete.")

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