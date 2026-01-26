#!/usr/bin/env python3
# main_ai.py - FIXED: Proper indentation for cropped image saving

import time
import csv
import logging
import sys
from pathlib import Path
import json
import config
import uploader
from logging_config import setup_logging
from pixhawk import Pixhawk
from camera import Camera
from classifier import PinyaSuriAI
from metrics import get_next_daily_flight_number
from metrics import FlightMetricsLogger

running = True

# ----------------------------
# Image Selection
# ----------------------------
def select_best_frame_sequential(burst_results):
    """
    Sequential priority selection:
    1. FIRST: Frames with detections (if any exist)
    2. THEN: Among frames with detections, pick highest average confidence
    3. FALLBACK: If no detections in any frame, pick highest sharpness
    
    Priority Order:
    - Detection count > 0 (yes/no)
    - If yes → Highest average confidence wins
    - If no → Highest sharpness wins
    """
    if not burst_results:
        return None
    
    # Separate frames into those with detections vs without
    frames_with_detections = [r for r in burst_results if len(r['detections']) > 0]
    frames_without_detections = [r for r in burst_results if len(r['detections']) == 0]
    
    # PRIORITY 1: Do we have ANY frames with detections?
    if frames_with_detections:
        # YES - Select based on CONFIDENCE (among frames with detections)
        best_frame = None
        best_confidence = -1
        
        for result in frames_with_detections:
            # Calculate average confidence for this frame
            avg_confidence = sum(d['confidence'] for d in result['detections']) / len(result['detections'])
            
            if avg_confidence > best_confidence:
                best_confidence = avg_confidence
                best_frame = result
        
        return best_frame
    
    else:
        # NO detections in any frame - Select based on SHARPNESS
        best_frame = None
        best_sharpness = -1
        
        for result in frames_without_detections:
            if result['sharpness'] > best_sharpness:
                best_sharpness = result['sharpness']
                best_frame = result
        
        return best_frame
    
def rename_best_frame(image_path, logger):
    try:
        path = Path(image_path)
        
        new_name = f"{path.stem}_BEST{path.suffix}"
        new_path = path.parent / new_name
        
        path.rename(new_path)
        
        logger.info(f"  ✓ Renamed best frame: {path.name} -> {new_name}")
        
        return str(new_path)
    except Exception as e:
        logger.error(f"  ⚠️ Failed to rename best frame: {e}")
        return image_path 


# ----------------------------
# CSV Initialization
# ----------------------------
def initialize_image_log():
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
    
    if not config.CLASSIFICATION_CSV.exists():
        with open(config.CLASSIFICATION_CSV, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "flight_id",
                "flight_number",
                "waypoint",
                "burst_id",
                "burst_index",
                "image_path",
                "detection_count",
                "detections"
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

def log_detection_results(flight_id, flight_number, waypoint, burst_id, burst_index, image_path, detections, logger):
    """Log AI detection results to CSV and uploader"""
    try:
        detection_count = len(detections)
        detections_json = json.dumps([{
            'class': d['class_name'],
            'confidence': round(d['confidence'], 3),
            'bbox': [round(x, 4) for x in d['bbox']]
        } for d in detections])
        
        # Log to CSV
        with open(config.CLASSIFICATION_CSV, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                time.time(),
                flight_id,
                flight_number,
                waypoint,
                burst_id,
                burst_index,
                image_path,
                detection_count,
                detections_json
            ])
        
        uploader.add_detection_to_flight(flight_id, waypoint, image_path, detections)
        
    except Exception as e:
        logger.error(f"Failed to log detection results: {e}")


# ----------------------------
# Capture Handler
# ----------------------------
def handle_waypoint_capture(pixhawk, camera, classifier, metrics, waypoint, flight_number, captured_wp, logger):
    """Capture burst images at waypoint with AI detection and best frame selection
    
    Process:
    1. Capture FULL RESOLUTION image (4056x3040) - THIS IS WHAT GETS SAVED & UPLOADED
    2. Preprocess to square (3040x3040) in memory for AI analysis
    3. AI detects on cropped version (resized to 640x640 internally)
    4. Select best frame based on detections + sharpness
    5. Upload ORIGINAL FULL RESOLUTION image of best frame
    6. Optionally save detection visualization (cropped + bboxes)
    """
    if waypoint in captured_wp:
        return False
        
    wp_name = config.get_waypoint_name(waypoint)
    logger.info("=" * 60)
    logger.info(f">>> {wp_name} (WP{waypoint}) REACHED - Capturing burst images...")
    logger.info("=" * 60)
    
    # Wait for drone to fully stabilize WITH MODE CHECKING
    logger.info(f"⏳ Waiting {config.STABILIZATION_DELAY}s for drone to settle...")
    stabilization_start = time.time()
    
    while (time.time() - stabilization_start) < config.STABILIZATION_DELAY:
        pixhawk.update()
        
        if pixhawk.mode != "AUTO":
            logger.warning("=" * 60)
            logger.warning(f"⚠️ CAPTURE ABORTED - Mode changed to {pixhawk.mode}")
            logger.warning("=" * 60)
            return False
        
        time.sleep(0.1)

    pixhawk.update()
    
    if pixhawk.mode != "AUTO":
        logger.warning("=" * 60)
        logger.warning(f"⚠️ CAPTURE ABORTED - Not in AUTO mode ({pixhawk.mode})")
        logger.warning("=" * 60)
        return False
    
    # Burst capture WITH DETECTION AND SCORING
    num_captures = config.BURST_CAPTURE_COUNT
    burst_interval = config.BURST_INTERVAL
    burst_id = f"{metrics.flight_id}_wp{waypoint}_{int(time.time())}"
    burst_results = []  # Store all results for selection

    logger.info(f"📸 Starting burst capture with AI detection ({num_captures} frames)...")

    for i in range(num_captures):
        pixhawk.update()
        if pixhawk.mode != "AUTO":
            logger.warning("=" * 60)
            logger.warning(f"⚠️ BURST ABORTED at frame {i+1}/{num_captures} - Mode changed to {pixhawk.mode}")
            logger.warning(f"   Captured {len(burst_results)} images before abort")
            logger.warning("=" * 60)
            
            if burst_results:
                captured_wp.add(waypoint)
            return len(burst_results) > 0
        
        try:
            # ✅ STEP 1: Capture FULL RESOLUTION image (4056x3040)
            # This is the ORIGINAL that will be uploaded
            full_res_image_path = camera.capture(
                waypoint=waypoint,
                flight_number=flight_number,
                prefix="pinyasuri",
                burst_index=i
            )
            
            # Verify file
            if not Path(full_res_image_path).exists() or Path(full_res_image_path).stat().st_size < 1000:
                logger.error(f"⚠ Frame {i+1} file invalid or too small")
                continue
            
            logger.info(f"  ✓ Frame {i+1}/{num_captures} captured (4056x3040)")
            
            # ✅ STEP 2: Load FULL RESOLUTION image into memory
            try:
                import cv2
                
                full_res_frame = cv2.imread(full_res_image_path)
                
                if full_res_frame is None:
                    logger.error(f"  ⚠️ Failed to load image for detection")
                    continue
                
                # ✅ STEP 3: Run AI detection
                # The classifier.detect_with_nms() will internally:
                #   - Crop to square (3040x3040) via preprocess_frame()
                #   - Resize to 640x640 for AI model
                #   - Run detection
                #   - Store the cropped frame in classifier.last_cropped_frame
                detections = classifier.detect_with_nms(
                    full_res_frame, 
                    iou_threshold=config.NMS_IOU_THRESHOLD
                )
                
                # ✅ STEP 4: Get the cropped frame (for detection visualization later)
                cropped_frame = classifier.get_cropped_frame()
                
                if cropped_frame is None:
                    logger.error(f"  ⚠️ Failed to get cropped frame from classifier")
                    continue
                
                # ✅ STEP 5: Calculate sharpness on the cropped frame
                # (AI sees cropped, so we measure quality on what AI sees)
                gray = cv2.cvtColor(cropped_frame, cv2.COLOR_BGR2GRAY)
                sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
                
                # ✅ STEP 6: Log image capture with FULL RESOLUTION path
                log_image_capture(
                    metrics.flight_id, 
                    flight_number, 
                    waypoint, 
                    pixhawk.position,
                    burst_id,
                    i,
                    full_res_image_path,  # ← Original 4056x3040 image
                    logger
                )
                
                logger.info(f"     Full resolution saved: 4056x3040 ({Path(full_res_image_path).name})")
                logger.info(f"     AI analyzed: 3040x3040 (cropped) → 640x640 (model input)")
                
                # ✅ STEP 7: Store results for best frame selection
                burst_results.append({
                    'image_path': full_res_image_path,  # ← FULL RESOLUTION path
                    'detections': detections,
                    'sharpness': sharpness,
                    'frame_index': i,
                    'cropped_frame': cropped_frame  # Keep for detection viz only
                })
                
                # Log detailed detection summary for this frame
                logger.info(f"  🔍 Frame {i+1} Analysis:")
                logger.info(f"     └─ Detections: {len(detections)}")
                
                if detections:
                    # Show each detection with class and confidence
                    for idx, det in enumerate(detections, 1):
                        logger.info(f"        • Detection {idx}: {det['class_name']} "
                                  f"(confidence: {det['confidence']:.3f})")
                    
                    # Calculate and show average confidence
                    avg_conf = sum(d['confidence'] for d in detections) / len(detections)
                    logger.info(f"     └─ Avg Confidence: {avg_conf:.3f}")
                
                logger.info(f"     └─ Sharpness: {sharpness:.1f}")
                    
            except Exception as e:
                logger.error(f"  ⚠️ AI detection failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            if i < num_captures - 1:
                time.sleep(burst_interval)
                
        except Exception as e:
            logger.error(f"⚠ Burst frame {i+1} failed: {e}")

    # ============================================================
    # SELECT BEST FRAME AFTER BURST COMPLETE
    # ============================================================
    if burst_results:
        logger.info("=" * 60)
        logger.info("📊 SELECTING BEST FRAME FROM BURST...")
        
        best_result = select_best_frame_sequential(burst_results)
        
        if best_result:
            logger.info(f"  ✓ Selected Frame {best_result['frame_index']} as BEST:")
            logger.info(f"     └─ Detections: {len(best_result['detections'])}")
            
            if best_result['detections']:
                # Show individual detections
                for idx, det in enumerate(best_result['detections'], 1):
                    logger.info(f"        • Detection {idx}: {det['class_name']} "
                              f"(confidence: {det['confidence']:.3f})")
                
                # Show average confidence
                avg_conf = sum(d['confidence'] for d in best_result['detections']) / len(best_result['detections'])
                logger.info(f"     └─ Avg Confidence: {avg_conf:.3f}")
            
            logger.info(f"     └─ Sharpness: {best_result['sharpness']:.1f}")
            logger.info("=" * 60)
            
            # ✅ RENAME BEST FRAME (FULL RESOLUTION 4056x3040)
            original_path = best_result['image_path']
            best_image_path = rename_best_frame(original_path, logger)
            best_result['image_path'] = best_image_path
            
            # ✅ Queue FULL RESOLUTION image for upload
            logger.info(f"  ✓ Uploading: {Path(best_image_path).name} (4056x3040 - FULL RES)")
            uploader.queue_image_upload(best_image_path)
            
            # ✅ OPTIONAL: Save detection visualization (cropped + bboxes)
            # This is for debugging/verification - shows what AI saw
            if config.DRAW_BBOXES and best_result['detections']:
                detection_image_path = camera.save_detection_image(
                    best_result['cropped_frame'],  # Use cropped version
                    best_result['detections'],
                    waypoint,
                    flight_number,
                    prefix="detection",
                    burst_index=best_result['frame_index']
                )
                
                if detection_image_path:
                    logger.info(f"  ✓ Detection viz saved: {Path(detection_image_path).name} (3040x3040 cropped)")
                    uploader.queue_image_upload(detection_image_path)
            
            # Log detection results to CSV
            log_detection_results(
                metrics.flight_id,
                flight_number,
                waypoint,
                burst_id,
                best_result['frame_index'],
                best_image_path,  # Full resolution path
                best_result['detections'],
                logger
            )
            
            # ✅ DELETE NON-SELECTED FRAMES to save space
            for result in burst_results:
                if result['frame_index'] != best_result['frame_index']:
                    try:
                        Path(result['image_path']).unlink()
                        logger.debug(f"  ✓ Deleted non-selected frame {result['frame_index']}")
                    except Exception as e:
                        logger.debug(f"  ⚠️ Could not delete frame: {e}")
            
            captured_wp.add(waypoint)
            logger.info(f"✓ WAYPOINT {waypoint} CAPTURE COMPLETE")
            logger.info(f"  └─ Best frame: FULL RESOLUTION (4056x3040)")
            return True
        else:
            logger.error("⚠ No valid frames in burst")
            return False
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
    }

def handle_arm_state_change(pixhawk, metrics, was_armed, flight_number, captured_wp, logger):
    """Detect and handle arm/disarm transitions"""
    if pixhawk.armed and not was_armed:
        # Just armed - START NEW FLIGHT
        logger.info("=" * 60)
        logger.info(f"🛫 FLIGHT #{flight_number} - DRONE ARMED")
        logger.info("   Mission monitoring started.")
        logger.info("=" * 60)
        metrics.start_flight()
        
        # ✅ CRITICAL: Tell uploader about the new flight
        uploader.start_new_flight(metrics.flight_id)
        
        pixhawk.clear_waypoint_log()
        uploader.disable_uploads_during_flight()
        
        return True, flight_number
        
    elif not pixhawk.armed and was_armed:
        # Just disarmed - END CURRENT FLIGHT
        logger.info(f"🛬 FLIGHT #{flight_number} - DRONE DISARMED")
        
        # ✅ CRITICAL: Get flight_id BEFORE ending flight
        current_flight_id = metrics.flight_id
        
        metrics.end_flight()
        
        total_waypoints = pixhawk.get_last_waypoint() if pixhawk else 0
        logger.info(">>> Generating flight summary...")
        
        # ✅ Use the flight_id from WHEN THE FLIGHT WAS ACTIVE
        summary_path = uploader.finalize_flight_summary(current_flight_id, total_waypoints)
        
        if summary_path:
            logger.info(f"✓ Flight summary created.")
            logger.info(f"✓ All flight data queued for upload.")
        
        captured_wp.clear()
        pixhawk.clear_waypoint_log()
        
        return False, metrics.flight_number
    
    return was_armed, flight_number

def is_drone_in_air(pixhawk):
    """Check if drone altitude is within capture range"""
    if not pixhawk.position:
        return False
    
    alt = pixhawk.position["rel_alt"]
    
    # Check if altitude is within the acceptable range
    in_range = config.MIN_ALTITUDE_FOR_CAPTURE <= alt <= config.MAX_ALTITUDE_FOR_CAPTURE
    
    return in_range

def should_capture_image(pixhawk, waypoint, captured_wp, logger):

    # 1. Must be armed
    if not pixhawk.armed:
        logger.debug("❌ Check failed: Not armed")
        return False
    
    # 2. Must be in AUTO mode
    if pixhawk.mode != "AUTO":
        logger.debug(f"❌ Check failed: Not in AUTO mode (current: {pixhawk.mode})")
        return False
    
    # 3. Must have valid waypoint
    if not waypoint:
        logger.debug("❌ Check failed: No waypoint")
        return False
    
    # 4. Must have position data from GPS
    if not pixhawk.position:
        logger.debug("❌ Check failed: No position data")
        return False
    
    # 5. Must be in the air
    if not is_drone_in_air(pixhawk):
        alt = pixhawk.position['rel_alt'] if pixhawk.position else 0
        logger.debug(f"❌ Check failed: Altitude {alt:.2f}m not in range "
                    f"[{config.MIN_ALTITUDE_FOR_CAPTURE}m - {config.MAX_ALTITUDE_FOR_CAPTURE}m]")
        return False
    
    # 6. Must NOT have already captured this waypoint
    if waypoint in captured_wp:
        logger.debug(f"❌ Check failed: Already captured WP{waypoint}")
        return False
    
    # 7. Must capture only at survey/mapping waypoints (exclude last waypoint)
    last_wp = pixhawk.get_last_waypoint()
    if not config.is_mapping_waypoint(waypoint, last_wp):
        logger.debug(f"❌ Check failed: WP{waypoint} is not a mapping waypoint")
        return False

    # 8. Must have distance data
    if pixhawk.wp_dist is None:
        logger.debug(f"❌ Check failed: No distance data available yet")
        return False
    
    # 9. Must be hovering
    if pixhawk.groundspeed > config.HOVER_SPEED_THRESHOLD:
        logger.debug(f"❌ Check failed: Still moving at {pixhawk.groundspeed:.2f} m/s "
                    f"(threshold: {config.HOVER_SPEED_THRESHOLD} m/s)")
        return False
    
    # 10. Must be within capture distance
    if pixhawk.wp_dist > config.WAYPOINT_CAPTURE_DISTANCE:
        logger.debug(f"❌ Check failed: Too far from WP{waypoint} "
                    f"({pixhawk.wp_dist:.2f}m > {config.WAYPOINT_CAPTURE_DISTANCE}m)")
        return False

    # All checks passed!
    logger.info("=" * 60)
    logger.info(f"✅ ALL CHECKS PASSED - Triggering capture for WP{waypoint}!")
    logger.info(f"   Altitude: {pixhawk.position['rel_alt']:.2f}m")
    logger.info(f"   Distance to waypoint: {pixhawk.wp_dist:.2f}m")
    logger.info(f"   Groundspeed: {pixhawk.groundspeed:.2f} m/s")
    logger.info("=" * 60)
    return True


def main_loop(pixhawk, camera, classifier, metrics, logger):
    captured_wp = set()
    flight_number = metrics.flight_number
    was_armed = False
    current_mode = "UNKNOWN"
    current_waypoint = None
    last_debug_time = 0
    
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

        # Check for waypoint changes (only when armed and waypoint is valid)
        if pixhawk.armed and pixhawk.last_wp is not None and pixhawk.last_wp != current_waypoint:
            current_waypoint = pixhawk.last_wp
            wp_name = config.get_waypoint_name(current_waypoint)
            wp_type = config.get_waypoint_type(current_waypoint)
            
            logger.info(f"📍 Navigating to {wp_name} (WP{current_waypoint}) [{wp_type}]")

        # PERIODIC DEBUG OUTPUT (every 2 seconds when armed)
        if pixhawk.armed and (time.time() - last_debug_time) > 2.0:
            last_debug_time = time.time()
            dist_str = f"{pixhawk.wp_dist:.2f}m" if pixhawk.wp_dist else "N/A"
            
            if pixhawk.position:
                alt_str = f"{pixhawk.position['rel_alt']:.1f}m"
            else:
                alt_str = "N/A"
            
            logger.debug(f"[STATUS] Mode: {pixhawk.mode}, WP: {pixhawk.last_wp}, "
                        f"Alt: {alt_str}, "
                        f"Dist to WP: {dist_str}, "
                        f"Captured: {captured_wp}")

        # Safe Waypoint Guard
        wp = pixhawk.current_waypoint or {"lat": None, "lon": None, "alt": None}

        # Update metrics during flight
        if pixhawk.armed and pixhawk.position:
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
                "waypoint_lat": wp["lat"],
                "waypoint_lon": wp["lon"],
                "waypoint_alt": wp["alt"],
                "flight_mode": pixhawk.mode,
                "nav_state": pixhawk.nav_state,
                "is_hovering": pixhawk.is_hovering(threshold=config.HOVER_SPEED_THRESHOLD),
            }
            metrics.log_telemetry(telemetry)

        
        # Check for image capture
        if should_capture_image(pixhawk, pixhawk.last_wp, captured_wp, logger):
            handle_waypoint_capture(
                pixhawk, camera, classifier, metrics,
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
        
        # ✅ CRITICAL: Get flight_id BEFORE ending flight
        current_flight_id = metrics.flight_id
        
        metrics.end_flight()
        
        # Generate flight summary JSON
        total_waypoints = pixhawk.get_last_waypoint() if pixhawk else 0
        logger.info(">>> Generating flight summary...")
        
        # ✅ Use the flight_id from when flight was active
        summary_path = uploader.finalize_flight_summary(current_flight_id, total_waypoints)
        
        if summary_path:
            logger.info(f"✓ Flight summary created: {summary_path}")

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

    # STOP UPLOAD QUEUE AND PRINT STATS
    uploader.stop_upload_queue()
    logger.info("✓ Shutdown complete.")

def main():
    global running
    
    logger = setup_logging()
    logger.setLevel(logging.INFO)
    
    # START UPLOAD QUEUE
    uploader.start_upload_queue()
    
    # SCAN FOR UNUPLOADED FILES FROM PREVIOUS RUNS
    uploader.scan_and_queue_unuploaded_files()
    
    pixhawk = Pixhawk()
    camera = Camera()

    logger.info(">>> Initializing AI detector...")
    try:
        classifier = PinyaSuriAI()
        camera.set_classifier(classifier)  # Set classifier for camera
    except Exception as e:
        logger.error(f"⚠️ Failed to initialize AI detector: {e}")
        logger.error("   System will continue without AI detection")
        classifier = None

    next_flight_number = get_next_daily_flight_number()
    metrics = FlightMetricsLogger(flight_number=next_flight_number)

    logger.info("=" * 60)
    logger.info("🍍 PINYASURI FLIGHT SYSTEM 🚁")
    logger.info("=" * 60)
    
    # Wait for connection
    try:
        pixhawk.wait_for_connection()
        pixhawk.request_mission_count()
        pixhawk.request_mission_waypoints()
        initialize_image_log()
        was_armed = main_loop(pixhawk, camera, classifier, metrics, logger)
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