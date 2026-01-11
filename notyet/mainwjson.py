#!/usr/bin/env python3
# main.py - Updated with proper JSON handling and upload

import time
import csv
import logging
import sys

import config
from logging_config import setup_logging
from pixhawk import Pixhawk
from notyet.gimbal import CameraGimbal
from camera import Camera
from metrics import FlightMetrics
from data_uploader import (
    save_json, 
    queue_image_upload,
    start_upload_queue,
    stop_upload_queue,
    scan_and_queue_unuploaded_files
)

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
    max_wait_time = 6.0
    check_interval = 0.4
    stable_checks_needed = 2
    speed_threshold = 0.6
    altitude_threshold = 0.8
    
    logger.info(">>> Waiting for drone to stabilize...")
    
    stable_count = 0
    elapsed = 0.0
    
    while elapsed < max_wait_time:
        time.sleep(check_interval)
        elapsed += check_interval
        
        pixhawk.update()
        
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
            if stable_count > 0:
                logger.debug(f"  ○ Lost stability - rechecking... "
                           f"(speed: {pixhawk.groundspeed:.2f} m/s)")
            stable_count = 0
    
    if stable_count < stable_checks_needed:
        logger.warning(f"⚠ Could not achieve stable hover after {elapsed:.1f}s")
        logger.warning(f"  Current speed: {pixhawk.groundspeed:.2f} m/s")
        logger.warning(f"  Altitude variation: {pixhawk.get_altitude_variation():.2f} m")
        logger.warning(f"  Mission Planner will hold for {10 - elapsed:.1f}s more")
        logger.warning("  Skipping capture this attempt")
        return False
    
    # Capture image
    try:
        image_path = camera.capture(
            waypoint=waypoint,
            flight_number=flight_number,
            prefix="pinyasuri"
        )
        
        # Save JSON locally and queue for upload
        json_path = save_json(
            flight_number=flight_number,
            waypoint=waypoint,
            image_path=image_path,
            class_name="",  # Will be filled by AI classification later
            prediction=""
        )
        
        # Queue image for upload
        full_image_path = config.IMAGE_DIR / image_path
        queue_image_upload(full_image_path)

        # Log to CSV
        log_image_capture(flight_number, waypoint, pixhawk.position, image_path)
        
        logger.info(f"✓ CAPTURED {wp_name} at {pixhawk.position['rel_alt']:.1f}m altitude")
        logger.info(f"  Image: {image_path}")
        logger.info(f"  JSON: {json_path.name if json_path else 'FAILED'}")
        
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
        logger.info("=" * 60)
        logger.info(f"🛫 FLIGHT #{flight_number} - DRONE ARMED")
        logger.info("   Mission monitoring started.")
        logger.info("=" * 60)
        metrics.start_flight(True, pixhawk.battery_remaining)
        pixhawk.clear_waypoint_log()
        
        if gimbal:
            gimbal.enable()
        
        return True, flight_number
        
    elif not pixhawk.armed and was_armed:
        logger.info(f"🛬 FLIGHT #{flight_number} - DRONE DISARMED")
        metrics.end_flight(True)
        captured_wp.clear()
        pixhawk.clear_waypoint_log()
        
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
    
    if not pixhawk.armed:
        return False
    
    if not waypoint:
        return False
    
    if not pixhawk.position:
        logger.debug("⚠ Cannot capture: no position data yet!")
        return False
    
    if not is_drone_in_air(pixhawk):
        return False
    
    if waypoint in captured_wp:
        return False
    
    if not config.is_mapping_waypoint(waypoint):
        logger.debug(f"⚠ {config.get_waypoint_name(waypoint)} is not a mapping waypoint")
        return False
    
    if not pixhawk.is_hovering(threshold=0.6):
        logger.debug(f"⚠ Still moving at {pixhawk.groundspeed:.2f} m/s")
        return False
    
    if not pixhawk.is_altitude_stable(threshold=0.8, window_size=5):
        logger.debug(f"⚠ Altitude not stable: {pixhawk.get_altitude_variation():.2f} m variation")
        return False
    
    if waypoint not in pixhawk.wp_reached_log:
        logger.debug(f"⚠ {config.get_waypoint_name(waypoint)} not confirmed reached yet")
        return False
    
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
        pixhawk.update()
        
        if gimbal and gimbal.enabled:
            drone_roll = pixhawk.get_roll()
            drone_pitch = pixhawk.get_pitch()
            gimbal.update(drone_roll, drone_pitch)
        
        was_armed, flight_number = handle_arm_state_change(
            pixhawk, metrics, gimbal, was_armed, flight_number, captured_wp, logger
        )

        if pixhawk.mode != current_mode:
            current_mode = pixhawk.mode
            logger.info(f"> Flight Mode: {current_mode}")

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

def cleanup(camera, metrics, gimbal, was_armed, logger):
    """Clean up resources before exit"""
    logger.info("=" * 60)
    logger.info("⚠ INITIATING SHUTDOWN ⚠")
    logger.info("=" * 60)
    logger.info(">>> Stopping mission tasks...")

    if was_armed:
        logger.info(">>> Finalizing flight metrics...")
        metrics.end_flight(True)
    
    # Upload all mission data to server
    try:
        logger.info(">>> Uploading mission data to server...")
        stop_upload_queue()  # This will finish all queued uploads and print stats
        logger.info("✓ Mission data upload complete")
    except Exception as e:
        logger.warning(f"⚠ Mission upload failed: {e}")

    if gimbal:
        try:
            gimbal.cleanup()
        except Exception as e:
            logger.warning(f"⚠ Error cleaning up gimbal: {e}")

    try:
        camera.close()
    except Exception as e:
        logger.info(f"⚠ Error closing camera: {e} ⚠")
    
    logger.info("✓ Shutdown complete.")

def main():
    global running
    
    logger = setup_logging()
    
    pixhawk = Pixhawk()
    camera = Camera()
    metrics = FlightMetrics()
    
    gimbal = None
    try:
        gimbal = CameraGimbal(
            roll_pin=17,
            pitch_pin=27,
            target_pitch=-45,
            max_roll_compensation=30,
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
    
    try:
        pixhawk.wait_for_connection()
        initialize_csv()
        
        # Start upload queue worker
        logger.info(">>> Starting upload queue...")
        start_upload_queue()
        
        # Queue any unuploaded files from previous sessions
        scan_and_queue_unuploaded_files()
        
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