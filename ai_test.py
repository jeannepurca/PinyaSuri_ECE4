#!/usr/bin/env python3
# ai_test.py

import logging
import sys
import cv2
from datetime import datetime
from pathlib import Path

# Import your existing modules
import config
from camera import Camera
from classifier import PinyaSuriAI

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DetectionTester:
    def __init__(self):
        """Initialize camera and AI classifier"""
        logger.info("=" * 60)
        logger.info("PINEAPPLE DETECTION TESTING SYSTEM")
        logger.info("=" * 60)
        
        try:
            # Initialize AI classifier first
            logger.info("Loading AI model...")
            self.classifier = PinyaSuriAI()
            
            # Initialize camera with classifier reference
            logger.info("Initializing camera...")
            self.camera = Camera(classifier=self.classifier)
            
            # Test counter
            self.test_count = 0
            
            logger.info("✓ System ready!")
            logger.info("")
            
        except Exception as e:
            logger.error(f"⚠ Initialization failed: {e}")
            raise
    
    def run_test(self):
        """Capture image and run detection"""
        self.test_count += 1
        
        logger.info("=" * 60)
        logger.info(f"TEST #{self.test_count}")
        logger.info("=" * 60)
        
        try:
            # 1. Capture image
            logger.info("📷 Capturing image...")
            image_path = self.camera.capture(
                waypoint=999,  # Test waypoint
                flight_number=0,  # Test flight
                prefix="test",
                burst_index=self.test_count
            )
            logger.info(f"✓ Image captured: {image_path}")
            
            # 2. Load image for detection
            logger.info("🔍 Loading image for detection...")
            frame = cv2.imread(image_path)
            
            if frame is None:
                logger.error("⚠ Failed to load captured image!")
                return
            
            logger.info(f"✓ Image loaded: {frame.shape[1]}x{frame.shape[0]} pixels")
            
            # 3. Run detection with NMS
            logger.info("🤖 Running AI detection...")
            detections = self.classifier.detect_with_nms(
                frame, 
                iou_threshold=config.NMS_IOU_THRESHOLD
            )
            
            # 4. Display results
            self._display_results(detections)
            
            # 5. Save detection image with bounding boxes
            if detections:
                logger.info("💾 Saving detection image with bounding boxes...")
                detection_image_path = self.camera.save_detection_image(
                    image_path=image_path,
                    detections=detections,
                    waypoint=999,
                    flight_number=0,
                    prefix="test_detection",
                    burst_index=self.test_count
                )
                
                if detection_image_path:
                    logger.info(f"✓ Detection image saved: {detection_image_path}")
            else:
                logger.info("ℹ No detections to save")
            
            logger.info("")
            logger.info("Test completed successfully!")
            logger.info("")
            
        except Exception as e:
            logger.error(f"⚠ Test failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _display_results(self, detections):
        """Display detection results in a formatted way"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("DETECTION RESULTS")
        logger.info("=" * 60)
        
        if not detections:
            logger.info("❌ No pineapples detected")
            logger.info("=" * 60)
            return
        
        # Get summary
        summary = self.classifier.get_detection_summary(detections)
        
        logger.info(f"✓ Total detections: {summary['total_count']}")
        logger.info(f"✓ Average confidence: {summary['avg_confidence']:.2%}")
        logger.info("")
        
        # Class breakdown
        logger.info("Class Breakdown:")
        for class_name, count in summary['class_counts'].items():
            logger.info(f"  • {class_name}: {count}")
        logger.info("")
        
        # Individual detections
        logger.info("Individual Detections:")
        logger.info("-" * 60)
        
        for i, det in enumerate(detections, 1):
            class_name = det['class_name']
            confidence = det['confidence']
            bbox = det['bbox_pixels']
            
            logger.info(f"Detection #{i}:")
            logger.info(f"  Class: {class_name}")
            logger.info(f"  Confidence: {confidence:.2%}")
            logger.info(f"  BBox (pixels): ({bbox[0]}, {bbox[1]}) to ({bbox[2]}, {bbox[3]})")
            logger.info("")
        
        logger.info("=" * 60)
        logger.info("")
    
    def interactive_mode(self):
        """Run interactive testing mode"""
        logger.info("=" * 60)
        logger.info("INTERACTIVE MODE")
        logger.info("=" * 60)
        logger.info("Press ENTER to capture and detect")
        logger.info("Type 'q' or 'quit' to exit")
        logger.info("=" * 60)
        logger.info("")
        
        try:
            while True:
                user_input = input("Press ENTER to test (or 'q' to quit): ").strip().lower()
                
                if user_input in ['q', 'quit', 'exit']:
                    logger.info("Exiting...")
                    break
                
                # Run test on Enter
                self.run_test()
                
        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("CLEANUP")
        logger.info("=" * 60)
        
        try:
            self.camera.close()
            logger.info("✓ Camera closed")
        except Exception as e:
            logger.warning(f"⚠ Error during cleanup: {e}")
        
        logger.info("")
        logger.info(f"Total tests run: {self.test_count}")
        logger.info("Goodbye!")
        logger.info("=" * 60)


def main():
    try:
        # Ensure directories exist
        config.ensure_directories()
        
        # Create tester
        tester = DetectionTester()
        
        # Run interactive mode
        tester.interactive_mode()
        
    except Exception as e:
        logger.error(f"⚠ Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()