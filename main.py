#!/usr/bin/env python3
# main.py - Integrated with gimbal stabilization

import time
import csv
import logging
import sys

import config
from logging_config import setup_logging
from pixhawk import Pixhawk
from gimbal import CameraGimbal
from camera import Camera
from metrics import FlightMetrics

running = True

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
    
    wp_name = config.get_waypoint_name(waypoint)
    
    logger.info("=" * 60)
    logger.info(f">>> {wp_name} (WP{waypoint}) REACHED - Capturing image...")
    logger.info("=" * 60)
    
    # Configuration
    max_wait_time = 6.0  # Max wait (Mission Planner handles the 10s hover)
    check_interval = 0.4  # Check every 0.4 seconds
    stable_checks_needed = 2  # Need 2 consecutive stable readings
    
    # Relaxed thresholds for outdoor conditions
    speed_threshold = 0.6  # m/s (forgiving for wind)
    altitude_threshold = 0.8  # m (forgiving for air turbulence)
    
    logger.info(">>> Waiting for drone to stabilize...")
    
    stable_count = 0
    elapsed = 0.0
    
    while elapsed < max_wait_time:
        time.sleep(check_interval)
        elapsed += check_interval
        
        # Update telemetry
        pixhawk.update()
        
        # Check if drone is stable
        is_hovering = pixhawk.is_hovering(threshold=speed_threshold)
        is_alt_stable = pixhawk.is_altitude_stable(
            threshold=altitude_threshold, 
            window_size=5
        )
        
        if is_hovering and is_alt_stable:
            stable_count += 1
            logger.info(f"  ✓ Stable check {stable_count}/{stable_checks_needed} "
                       f"(speed: {pixhawk.groundspeed:.2f} m/s, "
                       f"alt var: {pixhawk.get_altitude_variation():.2f} m)")
            
            if stable_count >= stable_checks_needed:
                logger.info(f"✓ Drone stabilized after {elapsed:.1f}s - Capturing now!")
                break
        else:
            # Reset counter if drone becomes unstable
            if stable_count > 0:
                logger.debug(f"  ○ Lost stability - rechecking... "
                           f"(speed: {pixhawk.groundspeed:.2f} m/s)")
            stable_count = 0
    
    # Check if we achieved stability
    if stable_count < stable_checks_needed:
        logger.warning(f"⚠ Could not achieve stable hover after {elapsed:.1f}s")
        logger.warning(f"  Current speed: {pixhawk.groundspeed:.2f} m/s")
        logger.warning(f"  Altitude variation: {pixhawk.get_altitude_variation():.2f} m")
        logger.warning(f"  Mission Planner will hold for {10 - elapsed:.1f}s more")
        logger.warning("  Skipping capture this attempt")
        return False
    
    # Capture image immediately after stability confirmed
    try:
        image_path = camera.capture(
            waypoint=waypoint,
            flight_number=flight_number,
            prefix="pinyasuri"
        )

        # Log CSV
        log_image_capture(flight_number, waypoint, pixhawk.position, image_path)
        
        logger.info(f"✓ CAPTURED {wp_name} at {pixhawk.position['rel_alt']:.1f}m altitude")
        logger.info(f"  Image: {image_path}")
        captured_wp.add(waypoint)
        metrics.increment_waypoint()
        
        return True
        
    except Exception as e:
        logger.error(f"⚠ Camera capture failed: {e}")
        return False

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

def handle_arm_state_change(pixhawk, metrics, gimbal, was_armed, flight_number, captured_wp, logger):
    """Detect and handle arm/disarm transitions"""
    if pixhawk.armed and not was_armed:
        # Just armed
        logger.info("=" * 60)
        logger.info(f"🛫 FLIGHT #{flight_number} - DRONE ARMED")
        logger.info("   Mission monitoring started.  ")
        logger.info("=" * 60)
        metrics.start_flight(True, pixhawk.battery_remaining)
        pixhawk.clear_waypoint_log()  # Clear old waypoint logs
        
        # Enable gimbal stabilization
        if gimbal:
            gimbal.enable()
        
        return True, flight_number
        
    elif not pixhawk.armed and was_armed:
        # Just disarmed
        logger.info(f"🛬 FLIGHT #{flight_number} - DRONE DISARMED")
        metrics.end_flight(True)
        captured_wp.clear()
        pixhawk.clear_waypoint_log()
        
        # Disable gimbal and center servos
        if gimbal:
            gimbal.disable()
        
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
    
    # 4. Must be in the air (altitude >= MIN_ALTITUDE_FOR_CAPTURE)
    if not is_drone_in_air(pixhawk):
        return False
    
    # 5. Must NOT have already captured this waypoint
    if waypoint in captured_wp:
        return False
    
    # 6. Only capture at survey/mapping waypoints (not HOME, TAKEOFF, or RTL)
    if not config.is_mapping_waypoint(waypoint):
        logger.debug(f"⚠ {config.get_waypoint_name(waypoint)} is not a mapping waypoint")
        return False
    
    # 7. RELAXED hover detection for outdoor conditions
    # Mission Planner holds for 10s, so we can be more forgiving
    if not pixhawk.is_hovering(threshold=0.6):  # Relaxed for wind
        logger.debug(f"⚠ Still moving at {pixhawk.groundspeed:.2f} m/s")
        return False
    
    # 8. RELAXED altitude stability check
    # More forgiving since Mission Planner handles the hover
    if not pixhawk.is_altitude_stable(threshold=0.8, window_size=5):  # Very forgiving
        logger.debug(f"⚠ Altitude not stable: {pixhawk.get_altitude_variation():.2f} m variation")
        return False
    
    # 9. Verify waypoint was actually reached
    # Check if we received the MISSION_ITEM_REACHED event for this waypoint
    if waypoint not in pixhawk.wp_reached_log:
        logger.debug(f"⚠ {config.get_waypoint_name(waypoint)} not confirmed reached yet")
        return False
    
    # All checks passed!
    logger.info(f"✓ All capture conditions met for {config.get_waypoint_name(waypoint)}!")
    return True

def main_loop(pixhawk, camera, metrics, gimbal, logger):
    captured_wp = set()
    flight_number = 1
    was_armed = False
    current_mode = "UNKNOWN"
    
    logger.info("=" * 60)
    logger.info("🍍 PINYASURI FLIGHT SYSTEM READY! 🚁")
    if gimbal:
        logger.info("🎥 Gimbal stabilization: ENABLED")
    logger.info("System will run continuously. Press Ctrl+C to stop.")
    logger.info("=" * 60)

    while running:
        # Update pixhawk telemetry
        pixhawk.update()
        
        # Update gimbal stabilization (if enabled)
        if gimbal and gimbal.enabled:
            # Get current drone attitude
            drone_roll = pixhawk.get_roll()
            drone_pitch = pixhawk.get_pitch()
            
            # Update gimbal to compensate for roll
            gimbal.update(drone_roll, drone_pitch)
        
        # Handle arm/disarm state changes
        was_armed, flight_number = handle_arm_state_change(
            pixhawk, metrics, gimbal, was_armed, flight_number, captured_wp, logger
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

def cleanup(camera, metrics, gimbal, was_armed, logger):
    """Clean up resources before exit"""
    logger.info("=" * 60)
    logger.info("⚠ INITIATING SHUTDOWN ⚠")
    logger.info("=" * 60)
    logger.info(">>> Stopping mission tasks...")

    if was_armed:
        logger.info(">>> Finalizing flight metrics...")
        metrics.end_flight(True)

    # Cleanup gimbal
    if gimbal:
        try:
            gimbal.cleanup()
        except Exception as e:
            logger.warning(f"⚠ Error cleaning up gimbal: {e}")

    # Cleanup camera
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
    
    # Initialize gimbal (optional - set to None to disable)
    gimbal = None
    try:
        gimbal = CameraGimbal(
            roll_pin=config.GIMBAL_ROLL_PIN,
            pitch_pin=config.GIMBAL_PITCH_PIN,
            use_mpu6050=config.USE_MPU6050,
            mpu6050_address=config.MPU6050_I2C_ADDRESS
        )
        logger.info("✓ Gimbal initialized successfully")
    except Exception as e:
        logger.warning(f"⚠ Gimbal initialization failed: {e}")
        gimbal = None

    logger.info("=" * 60)
    logger.info("🍍 PINYASURI FLIGHT SYSTEM 🚁")
    logger.info("=" * 60)
    
    # Wait for connection
    try:
        pixhawk.wait_for_connection()
        initialize_csv()
        
        # Run main loop
        was_armed = main_loop(pixhawk, camera, metrics, gimbal, logger)
        
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
        cleanup(camera, metrics, gimbal, was_armed, logger)

if __name__ == "__main__":
    main()