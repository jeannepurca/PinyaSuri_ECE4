#!/usr/bin/env python3
# camera.py

import logging
import pathlib
from datetime import datetime
import config
import cv2

logger = logging.getLogger(__name__)

class Camera:
    def __init__(self, classifier=None):
        config.ensure_directories()
        self.classifier = classifier

        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()
            
            cam_config = self.picam2.create_still_configuration(
                main={"size": (4056, 3040)},
                buffer_count=2
            )
            self.picam2.configure(cam_config)
            self.picam2.start()
            
            logger.info("✓ Camera started successfully!")
            
        except Exception as e:
            logger.error(f"⚠ Failed to initialize camera: {e} ⚠")
            raise

    def set_classifier(self, classifier):
        """Set the classifier instance for bounding box drawing"""
        self.classifier = classifier

    def capture(self, waypoint: int, flight_number: int = 1, prefix="img", burst_index=0):
        """Capture image and save to today's date folder"""

        # Get today's folder
        date_folder = config.get_image_day_dir()

        # Timestamp for filename
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]

        # Include burst index in filename
        filename = f"{prefix}_flight{flight_number}_wp{waypoint}_burst{burst_index}_{ts}.jpg"
        fullpath = date_folder / filename

        try:
            self.picam2.capture_file(str(fullpath))
            logger.debug(f"✓ Captured {filename}")
            return str(fullpath)
            
        except Exception as e:
            logger.error(f"⚠ Failed to capture {filename}: {e}")
            raise
    
    def save_cropped_image(self, cropped_frame, waypoint: int, 
                          flight_number: int = 1, prefix="cropped", burst_index=0):
        """Save the cropped square image (from classifier)"""
        try:
            # Get today's folder
            date_folder = config.get_image_day_dir()

            # Timestamp for filename
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
            
            # Create filename for cropped image
            filename = f"{prefix}_flight{flight_number}_wp{waypoint}_burst{burst_index}_{ts}.jpg"
            fullpath = date_folder / filename

            # Save cropped image
            success = cv2.imwrite(str(fullpath), cropped_frame)
            
            if success:
                logger.debug(f"✓ Saved cropped image: {filename}")
                return str(fullpath)
            else:
                logger.error(f"⚠ cv2.imwrite failed for: {filename}")
                return None
            
        except Exception as e:
            logger.error(f"⚠ Failed to save cropped image: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def save_detection_image(self, cropped_frame, detections, waypoint: int, 
                            flight_number: int = 1, prefix="detection", burst_index=0):
        """Draw bounding boxes on CROPPED frame and save"""
        try:
            if cropped_frame is None:
                logger.error(f"⚠ No cropped frame provided")
                return None

            logger.debug(f"Cropped frame shape: {cropped_frame.shape}")
            logger.debug(f"Number of detections: {len(detections)}")

            # Get today's folder
            date_folder = config.get_image_day_dir()

            # Timestamp for filename
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
            
            # Create filename for detection image
            filename = f"{prefix}_flight{flight_number}_wp{waypoint}_burst{burst_index}_{ts}.jpg"
            fullpath = date_folder / filename

            # Make a copy to draw on
            frame = cropped_frame.copy()

            # Draw bounding boxes if enabled and detections exist
            if config.DRAW_BBOXES and detections:
                logger.debug(f"Drawing {len(detections)} bounding boxes...")
                
                # Use classifier's draw_bounding_boxes method if available
                if self.classifier is not None:
                    frame = self.classifier.draw_bounding_boxes(frame, detections)
                else:
                    # Fallback to internal method
                    frame = self._draw_bounding_boxes(frame, detections)
                
                logger.debug("✓ Bounding boxes drawn")
            elif not config.DRAW_BBOXES:
                logger.debug("Bounding box drawing disabled in config")
            elif not detections:
                logger.debug("No detections to draw")
            
            # Save image
            success = cv2.imwrite(str(fullpath), frame)
            
            if success:
                logger.debug(f"✓ Saved detection image: {filename}")
                return str(fullpath)
            else:
                logger.error(f"⚠ cv2.imwrite failed for: {filename}")
                return None
            
        except Exception as e:
            logger.error(f"⚠ Failed to save detection image: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _draw_bounding_boxes(self, frame, detections):
        """Draw bounding boxes and labels on frame"""
        for det in detections:
            # Get bounding box in pixels
            x1, y1, x2, y2 = det['bbox_pixels']
            
            # Get class info
            class_idx = det['class_index']
            class_name = det['class_name']
            confidence = det['confidence']
            
            # Get color for this class
            color = config.get_class_color(class_idx)
            
            # Draw rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, config.BBOX_THICKNESS)
            
            # Prepare label text
            label = f"{class_name}: {confidence:.2f}"
            
            # Get text size for background rectangle
            (text_width, text_height), baseline = cv2.getTextSize(
                label, 
                cv2.FONT_HERSHEY_SIMPLEX, 
                config.FONT_SCALE, 
                1
            )
            
            # Draw label background (filled rectangle)
            label_y = y1 - 10 if y1 > text_height + 10 else y2 + text_height + 10
            cv2.rectangle(
                frame,
                (x1, label_y - text_height - baseline),
                (x1 + text_width, label_y + baseline),
                color,
                -1  # Filled
            )
            
            # Draw label text
            cv2.putText(
                frame,
                label,
                (x1, label_y - baseline),
                cv2.FONT_HERSHEY_SIMPLEX,
                config.FONT_SCALE,
                (255, 255, 255),  # White text
                1,
                cv2.LINE_AA
            )
        
        return frame

    def close(self):
        try:
            self.picam2.stop()
            logger.info("   ✓ Camera stopped successfully.")
        except Exception as e:
            logger.warning(f"⚠ Error stopping camera: {e} ⚠")