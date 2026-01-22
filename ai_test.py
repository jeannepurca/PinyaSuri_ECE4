#!/usr/bin/env python3
# capture_detect.py - capture image and run PinyaSuriAI detection

import cv2
import logging
import config
from classifier import PinyaSuriAI

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def main():
    # Initialize AI detector
    ai = PinyaSuriAI()

    # Open default camera
    cap = cv2.VideoCapture(0)  # change index if you have multiple cameras
    if not cap.isOpened():
        logger.error("Cannot open camera")
        return

    logger.info("Camera opened. Press 'Enter' to capture an image...")

    while True:
        # Read a frame
        ret, frame = cap.read()
        if not ret:
            logger.error("Failed to read frame from camera")
            break

        # Show live preview (optional)
        cv2.imshow("Camera Preview", frame)
        key = cv2.waitKey(1)

        # Capture on Enter key
        if key == 13:  # Enter key
            logger.info("Capturing image...")
            detections = ai.detect_with_nms(frame)

            # Draw bounding boxes
            frame_with_boxes = ai.draw_bounding_boxes(frame.copy(), detections)

            # Save image
            output_file = config.IMAGE_OUTPUT_DIR / "captured_detection.jpg"
            cv2.imwrite(str(output_file), frame_with_boxes)
            logger.info(f"Image saved to {output_file}")

            # Print detection info
            if detections:
                logger.info("Detections:")
                for det in detections:
                    logger.info(f"  - {det['class_name']}: {det['confidence']:.2f}")
            else:
                logger.info("No objects detected.")

            break  # exit after one capture

    # Release resources
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
