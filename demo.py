#!/usr/bin/env python3
# contest_demo.py

"""
PinyaSuri Contest Demo - Auto Classification & Upload
- Manual image capture only
- AI classification happens automatically after capture
- Upload to website happens automatically after classification
"""

import logging
import sys
import time
import cv2
from datetime import datetime
from pathlib import Path

# Import your existing modules
import config
from camera import Camera
from classifier import PinyaSuriAI
import uploader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContestDemo:
    """
    Simple PinyaSuri demo:
    1. Capture image manually
    2. Classify automatically
    3. Upload automatically
    """
    
    def __init__(self):
        logger.info("=" * 70)
        logger.info("🌍 PINYASURI CONTEST DEMO")
        logger.info("=" * 70)
        logger.info("")
        
        # Ensure directories exist
        config.ensure_directories()
        
        # Initialize components
        logger.info("📦 Initializing system...")
        self.classifier = PinyaSuriAI()
        self.camera = Camera(classifier=self.classifier)
        
        # Demo metadata
        self.demo_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.flight_id = f"demo_{self.demo_id}"
        self.captures = []  # Track all captures and detections
        self.capture_count = 0
        
        # Test server connection
        uploader.test_server_connection()
        
        logger.info(f"✓ System ready!")
        logger.info(f"  Flight ID: {self.flight_id}")
        logger.info("")
    
    def capture_and_process(self):
        """
        Capture one image, then automatically:
        - Classify it
        - Show results
        - Upload to website
        """
        self.capture_count += 1
        
        logger.info("=" * 70)
        logger.info(f"📷 CAPTURE #{self.capture_count}")
        logger.info("=" * 70)
        
        try:
            # 1. CAPTURE IMAGE
            logger.info("📷 Capturing image...")
            image_path = self.camera.capture(
                waypoint=self.capture_count,
                flight_number=1,
                prefix="demo",
                burst_index=0
            )
            logger.info(f"✓ Image saved: {Path(image_path).name}")
            logger.info("")
            
            # 2. LOAD AND CLASSIFY (AUTOMATIC)
            logger.info("🤖 Running AI classification...")
            frame = cv2.imread(image_path)
            if frame is None:
                logger.error("❌ Failed to load image!")
                return False
            
            logger.info(f"✓ Image dimensions: {frame.shape[1]}x{frame.shape[0]}")
            
            # Run detection
            detections = self.classifier.detect_with_nms(
                frame,
                iou_threshold=config.NMS_IOU_THRESHOLD
            )
            logger.info("")
            
            # 3. SHOW RESULTS (AUTOMATIC)
            logger.info("=" * 70)
            logger.info("📊 DETECTION RESULTS")
            logger.info("=" * 70)
            
            if detections:
                summary = self.classifier.get_detection_summary(detections)
                logger.info(f"✓ Detected {summary['total_count']} pineapple(s)")
                logger.info(f"  Average confidence: {summary['avg_confidence']:.2%}")
                logger.info("")
                logger.info("  Class breakdown:")
                for class_name, count in summary['class_counts'].items():
                    logger.info(f"    • {class_name}: {count}")
            else:
                logger.info("ℹ️  No pineapples detected in this image")
            
            logger.info("=" * 70)
            logger.info("")
            
            # 4. SAVE DETECTION IMAGE WITH BBOXES (AUTOMATIC)
            cropped_frame = self.classifier.get_cropped_frame()
            
            if detections and cropped_frame is not None:
                logger.info("💾 Saving detection image with bounding boxes...")
                det_image_path = self.camera.save_detection_image(
                    cropped_frame=cropped_frame,
                    detections=detections,
                    waypoint=self.capture_count,
                    flight_number=1,
                    prefix="demo_det",
                    burst_index=0
                )
                if det_image_path:
                    logger.info(f"✓ Detection image saved: {Path(det_image_path).name}")
                logger.info("")
            
            # 5. UPLOAD TO WEBSITE (AUTOMATIC)
            logger.info("📤 Uploading to website...")
            
            try:
                # Use the direct upload function
                success = uploader.upload_image_directly(
                    image_file=Path(image_path),
                    flight_id=self.flight_id,
                    waypoint=f"WAYPOINT_{self.capture_count}"
                )
                
                if success:
                    logger.info("✓ Image uploaded to website!")
                else:
                    logger.warning("⚠️  Upload may have failed")
            
            except Exception as e:
                logger.warning(f"⚠️  Upload error: {e}")
            
            logger.info("")
            
            # Store capture data
            capture_data = {
                "capture_num": self.capture_count,
                "image_path": image_path,
                "total_detections": len(detections),
                "detections": detections,
                "summary": self.classifier.get_detection_summary(detections) if detections else {}
            }
            self.captures.append(capture_data)
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def show_all_captures(self):
        """Show summary of all captures and detections"""
        if not self.captures:
            logger.info("ℹ️  No captures yet")
            return
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 ALL CAPTURES SUMMARY")
        logger.info("=" * 70)
        
        total_images = len(self.captures)
        total_pineapples = sum(c['total_detections'] for c in self.captures)
        
        logger.info(f"Total captures: {total_images}")
        logger.info(f"Total pineapples detected: {total_pineapples}")
        logger.info("")
        
        for capture in self.captures:
            logger.info(f"Capture #{capture['capture_num']}: "
                       f"{capture['total_detections']} pineapples")
            if capture['summary']:
                for class_name, count in capture['summary'].get('class_counts', {}).items():
                    logger.info(f"  • {class_name}: {count}")
        
        logger.info("=" * 70)
        logger.info("")
    
    def interactive_mode(self):
        """Interactive demo mode"""
        logger.info("=" * 70)
        logger.info("🎮 DEMO MODE")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Commands:")
        logger.info("  c  - Capture image (auto classify & upload)")
        logger.info("  s  - Show all captures summary")
        logger.info("  q  - Quit")
        logger.info("")
        
        try:
            while True:
                cmd = input("\n> ").strip().lower()
                
                if not cmd:
                    continue
                
                # Capture (auto classify & upload)
                if cmd == 'c':
                    self.capture_and_process()
                
                # Show summary
                elif cmd == 's':
                    self.show_all_captures()
                
                # Quit
                elif cmd == 'q':
                    logger.info("Exiting...")
                    break
                
                else:
                    logger.warning("⚠️  Unknown command. Type 'c', 's', or 'q'")
        
        except KeyboardInterrupt:
            logger.info("\n\nInterrupted by user")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("")
        logger.info("=" * 70)
        logger.info("🧹 CLEANUP")
        logger.info("=" * 70)
        
        try:
            self.camera.close()
            logger.info("✓ Camera closed")
        except Exception as e:
            logger.warning(f"⚠ Error closing camera: {e}")
        
        logger.info("")
        logger.info("✅ Demo complete!")
        logger.info("=" * 70)


def main():
    try:
        demo = ContestDemo()
        demo.interactive_mode()
    
    except Exception as e:
        logger.error(f"⚠ Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()