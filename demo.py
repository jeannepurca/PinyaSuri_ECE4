#!/usr/bin/env python3
# contest_demo.py

"""
PinyaSuri Contest Demo - JSON Per Capture
- Manual image capture only
- Generate JSON for each capture (1, 2, 3, etc.)
- AI classification happens automatically after capture
- Upload JSON then image to website automatically
"""

import logging
import sys
import time
import cv2
import json
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
    Simple PinyaSuri demo with per-capture JSON:
    1. Capture image manually
    2. Generate JSON for this capture
    3. Upload JSON to server
    4. Classify with AI
    5. Show results
    6. Upload image to server
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
        self.capture_count = 0
        
        # Test server connection
        uploader.test_server_connection()
        
        logger.info(f"✓ System ready!")
        logger.info(f"  Demo ID: {self.demo_id}")
        logger.info("")
    
    def create_flight_json(self, capture_num, detections):
        """Create flight JSON for this specific capture"""
        flight_id = f"demo_{self.demo_id}_capture{capture_num}"
        
        # Calculate detection summary
        total_pineapples = len(detections)
        healthy_count = sum(1 for d in detections if d['class_name'] == 'Healthy')
        afflicted_count = total_pineapples - healthy_count
        
        # Get afflictions
        afflictions = {}
        for det in detections:
            if det['class_name'] != 'Healthy':
                afflictions[det['class_name']] = afflictions.get(det['class_name'], 0) + 1
        
        # Get average confidence
        avg_confidence = sum(d['confidence'] for d in detections) / len(detections) if detections else 0
        
        # Most common affliction
        most_common = max(afflictions.items(), key=lambda x: x[1])[0] if afflictions else None
        
        # Create JSON
        flight_summary = {
            "id": flight_id,
            "type": "flight",
            "date": datetime.now().strftime("%B %d, %Y"),
            "start_time": datetime.now().strftime("%H:%M:%S"),
            "end_time": datetime.now().strftime("%H:%M:%S"),
            "summary": {
                "total_waypoints": 1,
                "captured_waypoints": 1,
                "mission_status": "Demo - Capture {}".format(capture_num),
                "pineapples_detected": total_pineapples,
                "healthy_pineapples": healthy_count,
                "afflicted_pineapples": afflicted_count,
                "most_common_affliction": most_common,
                "avg_confidence": round(avg_confidence, 4)
            },
            "waypoints": [
                {
                    "waypoint_id": f"CAPTURE_{capture_num}",
                    "images": [],
                    "num_pineapples": total_pineapples,
                    "healthy": healthy_count,
                    "afflicted": afflicted_count,
                    "afflictions": afflictions
                }
            ],
            "image_metadata": {
                "total_images": 1,
                "images_per_waypoint": {f"CAPTURE_{capture_num}": 1}
            }
        }
        
        return flight_id, flight_summary
    
    def capture_and_process(self):
        """
        Capture one image, then automatically:
        1. Generate JSON for this capture
        2. Upload JSON to server
        3. Classify image
        4. Show results
        5. Upload image to server
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
            
            # 5. CREATE AND UPLOAD JSON FOR THIS CAPTURE
            logger.info("📄 Creating flight JSON for this capture...")
            flight_id, flight_summary = self.create_flight_json(self.capture_count, detections)
            logger.info(f"  Flight ID: {flight_id}")
            logger.info(f"  Pineapples detected: {flight_summary['summary']['pineapples_detected']}")
            
            # Save JSON to disk
            json_path = config.JSON_DIR / f"{flight_id}_summary.json"
            with open(json_path, 'w') as f:
                json.dump(flight_summary, f, indent=2)
            logger.info(f"✓ JSON created: {json_path.name}")
            logger.info("")
            
            # Upload JSON first
            logger.info("📤 Uploading JSON to website...")
            try:
                json_success = uploader.upload_json_directly(json_path)
                if json_success:
                    logger.info("✓ JSON uploaded to website!")
                else:
                    logger.warning("⚠️  JSON upload may have failed")
                logger.info("")
            except Exception as e:
                logger.warning(f"⚠️  JSON upload error: {e}")
                logger.info("")
            
            # 6. UPLOAD IMAGE TO WEBSITE
            logger.info("📤 Uploading image to website...")
            
            try:
                # Use the direct upload function
                img_success = uploader.upload_image_directly(
                    image_file=Path(image_path),
                    flight_id=flight_id,
                    waypoint=f"CAPTURE_{self.capture_count}"
                )
                
                if img_success:
                    logger.info("✓ Image uploaded to website!")
                else:
                    logger.warning("⚠️  Image upload may have failed")
            
            except Exception as e:
                logger.warning(f"⚠️  Image upload error: {e}")
            
            logger.info("")
            
            # Store capture data
            capture_data = {
                "capture_num": self.capture_count,
                "flight_id": flight_id,
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
            logger.info(f"Capture #{capture['capture_num']} ({capture['flight_id']}): "
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
        logger.info("  c  - Capture image (auto classify, create JSON & upload)")
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