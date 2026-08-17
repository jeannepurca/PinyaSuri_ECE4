#!/usr/bin/env python3
# contest_demo.py

"""
PinyaSuri Contest Demo - Simplified
- Manual image capture
- AI classification (YOLOv8n)
- Upload to website
"""

import logging
import sys
import json
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
    1. Capture images manually
    2. Classify with AI
    3. Upload to website
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
        self.captures = []  # Track all captures and detections
        
        # Start upload queue
        uploader.start_upload_queue()
        
        logger.info(f"✓ System ready!")
        logger.info(f"  Demo ID: {self.demo_id}")
        logger.info("")
    
    def capture_image(self, capture_num: int):
        """
        Capture one image and classify it
        """
        logger.info("=" * 70)
        logger.info(f"📷 CAPTURE #{capture_num}")
        logger.info("=" * 70)
        
        try:
            # 1. Capture image
            logger.info("📷 Capturing image...")
            image_path = self.camera.capture(
                waypoint=capture_num,  # Use capture number as identifier
                flight_number=1,
                prefix="demo",
                burst_index=0
            )
            logger.info(f"✓ Image saved: {Path(image_path).name}")
            
            # 2. Load for detection
            frame = cv2.imread(image_path)
            if frame is None:
                logger.error("❌ Failed to load image!")
                return None
            
            logger.info(f"✓ Image dimensions: {frame.shape[1]}x{frame.shape[0]}")
            
            # 3. Run AI detection
            logger.info("🤖 Running AI detection...")
            detections = self.classifier.detect_with_nms(
                frame,
                iou_threshold=config.NMS_IOU_THRESHOLD
            )
            
            # 4. Show results
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
            
            # 5. Get cropped frame
            cropped_frame = self.classifier.get_cropped_frame()
            
            # 6. Save detection image with bboxes
            if detections and cropped_frame is not None:
                logger.info("\n💾 Saving detection image...")
                det_image_path = self.camera.save_detection_image(
                    cropped_frame=cropped_frame,
                    detections=detections,
                    waypoint=capture_num,
                    flight_number=1,
                    prefix="demo_det",
                    burst_index=0
                )
                if det_image_path:
                    logger.info(f"✓ Detection image saved: {Path(det_image_path).name}")
            
            # 7. Queue image for upload
            logger.info("\n📤 Queueing for upload...")
            uploader.queue_image_upload(image_path)
            logger.info("✓ Queued")
            
            # Store capture data
            capture_data = {
                "capture_num": capture_num,
                "image_path": image_path,
                "total_detections": len(detections),
                "detections": detections,
                "summary": self.classifier.get_detection_summary(detections) if detections else {}
            }
            self.captures.append(capture_data)
            
            logger.info("")
            return capture_data
        
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def show_progress(self):
        """Show all captures and their results"""
        if not self.captures:
            logger.info("ℹ️  No captures yet")
            return
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 CAPTURE SUMMARY")
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
    
    def upload_to_website(self):
        """Upload all captured images to website"""
        if not self.captures:
            logger.warning("⚠️  No captures to upload!")
            return False
        
        logger.info("=" * 70)
        logger.info("📤 UPLOADING TO WEBSITE")
        logger.info("=" * 70)
        logger.info("")
        
        # Wait for images to upload
        logger.info("⏳ Waiting for images to upload...")
        max_wait = 60  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            stats = uploader.upload_queue.get_stats()
            
            elapsed = int(time.time() - start_time)
            logger.info(f"  [{elapsed}s] Uploaded: {stats['image_uploaded']}, "
                       f"Failed: {stats['image_failed']}, "
                       f"Queued: {stats['queue_size']}")
            
            if stats['queue_size'] == 0:
                if stats['image_uploaded'] > 0:
                    logger.info("✓ All images uploaded!")
                    break
                elif stats['image_failed'] > 0:
                    logger.error("❌ Upload failed!")
                    break
            
            time.sleep(2)
        
        # Final stats
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 UPLOAD RESULTS")
        logger.info("=" * 70)
        stats = uploader.upload_queue.get_stats()
        logger.info(f"✓ Images uploaded: {stats['image_uploaded']}")
        logger.info(f"❌ Images failed: {stats['image_failed']}")
        logger.info(f"⏳ Images remaining: {stats['queue_size']}")
        logger.info("=" * 70)
        logger.info("")
        
        return stats['image_uploaded'] > 0
    
    def interactive_mode(self):
        """Interactive demo mode"""
        logger.info("=" * 70)
        logger.info("🎮 DEMO MODE")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Commands:")
        logger.info("  c  - Capture and classify image")
        logger.info("  s  - Show capture summary")
        logger.info("  u  - Upload all to website")
        logger.info("  q  - Quit")
        logger.info("")
        
        capture_count = 0
        
        try:
            while True:
                cmd = input("\n> ").strip().lower()
                
                if not cmd:
                    continue
                
                # Capture
                if cmd == 'c':
                    capture_count += 1
                    result = self.capture_image(capture_count)
                    if result is None:
                        capture_count -= 1
                
                # Show summary
                elif cmd == 's':
                    self.show_progress()
                
                # Upload
                elif cmd == 'u':
                    self.upload_to_website()
                
                # Quit
                elif cmd == 'q':
                    logger.info("Exiting...")
                    break
                
                else:
                    logger.warning("⚠️  Unknown command. Type 'c', 's', 'u', or 'q'")
        
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
        
        try:
            uploader.stop_upload_queue()
            logger.info("✓ Upload queue stopped")
        except Exception as e:
            logger.warning(f"⚠ Error stopping upload: {e}")
        
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