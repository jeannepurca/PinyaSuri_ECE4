#!/usr/bin/env python3
# ai_test.py - Headless ENTER-to-capture AI test

import time
import logging
from pathlib import Path
import cv2
from classifier import PinyaSuriAI
import config

# Try Picamera2
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ----------------------------
# Output directory
# ----------------------------
OUTPUT_DIR = Path("test_output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ----------------------------
# Camera helpers
# ----------------------------
def open_picamera2(width=640, height=480):
    if not PICAMERA2_AVAILABLE:
        return None

    try:
        logger.info("Trying Picamera2...")
        picam2 = Picamera2()
        cfg = picam2.create_preview_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        picam2.configure(cfg)
        picam2.start()
        time.sleep(1)
        logger.info("✓ Picamera2 started")
        return picam2
    except Exception as e:
        logger.warning(f"Picamera2 failed: {e}")
        return None


def open_opencv_camera(index=0):
    logger.info(f"Trying OpenCV camera {index}...")
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        time.sleep(0.5)
        logger.info("✓ OpenCV camera opened")
        return cap
    cap.release()
    return None


# ----------------------------
# Main
# ----------------------------
def main():
    logger.info("=" * 60)
    logger.info("🍍 PINYASURI AI – PRESS ENTER TO CAPTURE")
    logger.info("=" * 60)

    # Load classifier
    classifier = PinyaSuriAI()

    # Open camera
    picam2 = open_picamera2()
    cap = None

    if picam2 is None:
        cap = open_opencv_camera()

    if picam2 is None and cap is None:
        logger.error("❌ Failed to open any camera")
        return

    logger.info("📸 Camera ready")
    logger.info("👉 Press ENTER to capture image")
    logger.info("👉 Press CTRL+C to exit")
    logger.info("=" * 60)

    frame_count = 0

    try:
        while True:
            input()  # WAIT FOR ENTER

            # Capture frame
            if picam2:
                frame = picam2.capture_array()
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            else:
                ret, frame = cap.read()
                if not ret:
                    logger.error("Failed to read frame")
                    break

            frame_count += 1

            logger.info(f"📷 Capturing frame {frame_count}...")

            # Run detection
            t0 = time.time()
            detections = classifier.detect_with_nms(
                frame,
                iou_threshold=config.NMS_IOU_THRESHOLD
            )
            infer_time = time.time() - t0

            # Draw bounding boxes
            if detections:
                frame = classifier.draw_bounding_boxes(frame, detections)

            # Save image
            output_path = OUTPUT_DIR / f"capture_{frame_count:04d}.jpg"
            cv2.imwrite(str(output_path), frame)

            logger.info(
                f"✓ Saved {output_path.name} | "
                f"Detections: {len(detections)} | "
                f"Inference: {infer_time*1000:.1f} ms"
            )
            logger.info("👉 Press ENTER to capture again")

    except KeyboardInterrupt:
        logger.info("\n🛑 Exiting...")

    finally:
        if picam2:
            picam2.stop()
        if cap:
            cap.release()

        logger.info("Camera closed")


if __name__ == "__main__":
    main()