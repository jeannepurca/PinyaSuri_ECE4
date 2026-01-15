#!/usr/bin/env python3
# main.py

import time
import csv
import logging
import sys
from pathlib import Path

import config

from logging_config import setup_logging
from pixhawk import Pixhawk
from camera import Camera
from metrics import get_next_daily_flight_number
from metrics import FlightMetricsLogger

running = True

# ----------------------------
# CSV Initialization
# ----------------------------
def initialize_csv():
    """Create image log CSV with headers if file doesn't exist"""
    if not config.IMAGE_LOG_CSV.exists():
        with open(config.IMAGE_LOG_CSV, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "flight_id",
                "flight_number",
                "waypoint",
                "lat_deg",
                "lon_deg",
                "rel_alt_m",
                "burst_id",
                "burst_index",
                "image_path"
            ])

def log_image_capture(flight_id, flight_number, waypoint, position, burst_id, burst_index, image_path, logger):
    """Append image capture record to CSV with error handling"""
    try:
        with open(config.IMAGE_LOG_CSV, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                time.time(),
                flight_id,
                flight_number,
                waypoint,
                position["lat"],
                position["lon"],
                position["rel_alt"],
                burst_id,
                burst_index,
                image_path
            ])
    except Exception as e:
        logger.error(f"Failed to log image capture to CSV: {e}")

# ----------------------------
# Capture handler
# ----------------------------
def handle_waypoint_capture(pixhawk, camera, metrics, waypoint, flight_number, captured_wp, logger):
    """Capture burst images at waypoint with stability monitoring"""
    if waypoint in captured_wp:
        return False
        
    wp_name = config.get_waypoint_name(waypoint)
    logger.info("=" * 60)
    logger.info(f">>> {wp_name} (WP{waypoint}) REACHED - Capturing burst images...")
    logger.info("=" * 60)

    # Wait until drone stabilizes
    stable_count = 0
    elapsed = 0.0
    
    logger.info(">>> Waiting for drone to stabilize...")
    
    while elapsed < config.STABILITY_WAIT_TIME:
        time.sleep(config.STABILITY_CHECK_INTERVAL)
        elapsed += config.STABILITY_CHECK_INTERVAL
        pixhawk.update()

        # Check if drone is stable
        is_hovering = pixhawk.is_hovering(threshold=config.HOVER_SPEED_THRESHOLD)
        is_alt_stable = pixhawk.is_altitude_stable(threshold=config.ALTITUDE_STABILITY_THRESHOLD, window_size=5)

        if is_hovering and is_alt_stable:
            stable_count += 1
            logger.info(f"  ✓ Stable check {stable_count}/{config.STABILITY_CHECKS_NEEDED} "
                       f"(speed: {pixhawk.groundspeed:.2f} m/s, "
                       f"alt var: {pixhawk.get_altitude_variation():.2f} m)")
            
            if stable_count >= config.STABILITY_CHECKS_NEEDED:
                logger.info(f"✓ Drone stabilized after {elapsed:.1f}s - Capturing now!")
                break
        else:
            # Reset counter if drone becomes unstable
            if stable_count > 0:
                logger.debug(f"  ○ Lost stability - rechecking... "
                           f"(speed: {pixhawk.groundspeed:.2f} m/s)")
            stable_count = 0

    # Check if we achieved stability
    if stable_count < config.STABILITY_CHECKS_NEEDED:
        logger.warning(f"⚠ Could not achieve stable hover after {elapsed:.1f}s")
        logger.warning(f"  Current speed: {pixhawk.groundspeed:.2f} m/s")
        logger.warning(f"  Altitude variation: {pixhawk.get_altitude_variation():.2f} m")
        logger.warning(f"  Mission Planner will hold for {config.STABILITY_WAIT_TIME - elapsed:.1f}s more")
        logger.warning("  Skipping capture this attempt.")
        return False

    # Burst capture with stability monitoring
    num_captures = config.BURST_CAPTURE_COUNT
    burst_interval = config.BURST_INTERVAL
    captured_images = []
    burst_id = f"{metrics.flight_id}_wp{waypoint}_{int(time.time())}"

    logger.info(f"📸 Starting burst capture ({num_captures} frames)...")

    for i in range(num_captures):
        # Quick stability check between frames (except first)
        if i > 0:
            pixhawk.update()  # Get latest telemetry
            
            if not pixhawk.is_hovering(threshold=0.6):
                logger.warning(f"⚠ Instability detected at frame {i+1} (speed: {pixhawk.groundspeed:.2f} m/s)")
                # Add extra settling time
                time.sleep(config.BURST_STABILIZATION_DELAY)
        
        try:
            image_path = camera.capture(
                waypoint=waypoint,
                flight_number=flight_number,
                prefix="pinyasuri",
                burst_index=i
            )
            
            # Verify file was written and has valid size
            if Path(image_path).exists() and Path(image_path).stat().st_size > 1000:
                captured_images.append(image_path)
                
                # Log with burst metadata
                log_image_capture(
                    metrics.flight_id, 
                    flight_number, 
                    waypoint, 
                    pixhawk.position,
                    burst_id,
                    i,
                    image_path, 
                    logger
                )
                
                logger.info(f"  ✓ Frame {i+1}/{num_captures} captured "
                           f"(speed: {pixhawk.groundspeed:.2f} m/s, "
                           f"size: {Path(image_path).stat().st_size / 1024:.1f} KB)")
            else:
                logger.error(f"⚠ Frame {i+1} file invalid or too small")
            
            if i < num_captures - 1:  # Don't wait after last image
                time.sleep(burst_interval)
                
        except Exception as e:
            logger.error(f"⚠ Burst frame {i+1} failed: {e}")

    if captured_images:
        logger.info(f"✓ CAPTURED {len(captured_images)}/{num_captures} images at {wp_name}")
        logger.info(f"  Burst ID: {burst_id}")
        captured_wp.add(waypoint)
        return True
    else:
        logger.error("⚠ Burst capture completely failed - no valid images")
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

def handle_arm_state_change(pixhawk, metrics, was_armed, flight_number, captured_wp, logger):
    """Detect and handle arm/disarm transitions"""
    if pixhawk.armed and not was_armed:
        # Just armed
        logger.info("=" * 60)
        logger.info(f"🛫 FLIGHT #{flight_number} - DRONE ARMED")
        logger.info("   Mission monitoring started.")
        logger.info("=" * 60)
        metrics.start_flight()
        pixhawk.clear_waypoint_log()
        
        return True, flight_number
        
    elif not pixhawk.armed and was_armed:
        # Just disarmed
        logger.info(f"🛬 FLIGHT #{flight_number} - DRONE DISARMED")
        metrics.end_flight()
        captured_wp.clear()
        pixhawk.clear_waypoint_log()
        
        return False, metrics.flight_number
    
    return was_armed, flight_number

def is_drone_in_air(pixhawk):
    if not pixhawk.position:
        return False
    
    return pixhawk.position["rel_alt"] >= config.MIN_ALTITUDE_FOR_CAPTURE

def should_capture_image(pixhawk, waypoint, captured_wp, logger):
    """Check if conditions are met for image capture"""

    # 1. Must be armed
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
    
    # 6. Must capture only at survey/mapping waypoints
    if not config.is_mapping_waypoint(waypoint):
        return False

    # 7. RELAXED hover detection for outdoor conditions
    if not pixhawk.is_hovering(threshold=config.HOVER_SPEED_THRESHOLD):
        logger.debug(f"⚠ Still moving at {pixhawk.groundspeed:.2f} m/s")
        return False
    
    # 8. RELAXED altitude stability check
    if not pixhawk.is_altitude_stable(threshold=config.ALTITUDE_STABILITY_THRESHOLD, window_size=5):
        logger.debug(f"⚠ Altitude not stable: {pixhawk.get_altitude_variation():.2f} m variation")
        return False

    # 9. Must reached the verified waypoint
    if waypoint not in pixhawk.wp_reached_log:
        logger.debug(f"⚠ {config.get_waypoint_name(waypoint)} not confirmed reached yet")
        return False

    # All checks passed!
    logger.info(f"✓ All capture conditions met for {config.get_waypoint_name(waypoint)}!")
    return True

def main_loop(pixhawk, camera, metrics, logger):
    captured_wp = set()
    flight_number = metrics.flight_number
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
            telemetry = {
                "attitude": {
                    "roll": getattr(pixhawk, "roll", 0.0),
                    "pitch": getattr(pixhawk, "pitch", 0.0),
                    "yaw": getattr(pixhawk, "yaw", 0.0)
                },
                "imu_accel": pixhawk.imu_accel,
                "gps": {
                    "lat": pixhawk.position["lat"],
                    "lon": pixhawk.position["lon"],
                    "alt": pixhawk.position["rel_alt"],
                    "groundspeed": pixhawk.groundspeed
                },
                "waypoint_index": pixhawk.last_wp,
                "waypoint_lat": pixhawk.get_waypoint_lat(pixhawk.last_wp),
                "waypoint_lon": pixhawk.get_waypoint_lon(pixhawk.last_wp),
                "waypoint_alt": pixhawk.get_waypoint_alt(pixhawk.last_wp),
                "flight_mode": pixhawk.mode,
                "nav_state": pixhawk.nav_state,
                "is_hovering": pixhawk.is_hovering(threshold=config.HOVER_SPEED_THRESHOLD),
                "battery": {
                    "voltage": pixhawk.battery_voltage,
                    "current": pixhawk.battery_current,
                    "percentage": pixhawk.battery_remaining
                }
            }
            metrics.log_telemetry(telemetry)

        
        # Check for image capture
        if should_capture_image(pixhawk, pixhawk.last_wp, captured_wp, logger):
            handle_waypoint_capture(
                pixhawk, camera, metrics, 
                pixhawk.last_wp, flight_number, captured_wp, logger
            )
        time.sleep(config.MAIN_LOOP_INTERVAL)
    return was_armed

def cleanup(camera, pixhawk, metrics, was_armed, logger):
    """Clean up resources before exit"""
    logger.info("=" * 60)
    logger.info("⚠ INITIATING SHUTDOWN ⚠")
    logger.info("=" * 60)
    logger.info(">>> Stopping mission tasks...")

    if was_armed:
        logger.info(">>> Finalizing flight metrics...")
        metrics.end_flight()

    # Cleanup camera
    try:
        camera.close()
    except Exception as e:
        logger.info(f"⚠ Error closing camera: {e} ⚠")

    # Cleanup pixhawk
    try:
        if pixhawk and pixhawk.master:
            pixhawk.master.close()
            logger.info("✓ Pixhawk connection closed.")
    except Exception as e:
        logger.warning(f"⚠ Error closing Pixhawk: {e} ⚠")
    
    logger.info("✓ Shutdown complete.")

def main():
    global running
    
    logger = setup_logging()
    pixhawk = Pixhawk()
    camera = Camera()
    next_flight_number = get_next_daily_flight_number()
    metrics = FlightMetricsLogger(flight_number=next_flight_number)

    logger.info("=" * 60)
    logger.info("🍍 PINYASURI FLIGHT SYSTEM 🚁")
    logger.info("=" * 60)
    
    # Wait for connection
    try:
        pixhawk.wait_for_connection()
        initialize_csv()
        was_armed = main_loop(pixhawk, camera, metrics, logger)
    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 60)
        logger.info("⚠ MANUAL STOP - Interrupted by user! ⚠")
        logger.info("=" * 60)
        time.sleep(0.5)
        was_armed = pixhawk.armed if pixhawk else False
    except Exception as e:
        logger.error(f"⚠ Fatal error: {e} ⚠", exc_info=True)
        was_armed = False
    finally:
        cleanup(camera, pixhawk, metrics, was_armed, logger)

if __name__ == "__main__":
    main()