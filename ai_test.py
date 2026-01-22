#!/usr/bin/env python3
# ai_test.py - Test AI classifier without drone

import logging
import sys
from pathlib import Path
import cv2
import time
import argparse
from classifier import PinyaSuriAI
import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class ClassifierTester:
    def __init__(self):
        """Initialize the classifier tester"""
        logger.info("=" * 60)
        logger.info("🍍 PINYASURI AI CLASSIFIER TESTER")
        logger.info("=" * 60)
        
        try:
            self.classifier = PinyaSuriAI()
            logger.info("✓ Classifier loaded successfully!")
        except Exception as e:
            logger.error(f"⚠ Failed to initialize classifier: {e}")
            raise
    
    def test_single_image(self, image_path, save_output=True, show_image=False):
        """
        Test classifier on a single image
        
        Args:
            image_path: Path to test image
            save_output: Whether to save annotated image
            show_image: Whether to display image (requires display)
        """
        logger.info("-" * 60)
        logger.info(f"Testing image: {Path(image_path).name}")
        logger.info("-" * 60)
        
        # Load image
        frame = cv2.imread(str(image_path))
        if frame is None:
            logger.error(f"⚠ Failed to load image: {image_path}")
            return None
        
        logger.info(f"Image size: {frame.shape[1]}x{frame.shape[0]} pixels")
        
        # Run detection
        start_time = time.time()
        detections = self.classifier.detect_with_nms(
            frame, 
            iou_threshold=config.NMS_IOU_THRESHOLD
        )
        inference_time = time.time() - start_time
        
        # Display results
        logger.info(f"⏱️  Inference time: {inference_time*1000:.1f}ms")
        logger.info(f"🔍 Detected {len(detections)} object(s)")
        
        if detections:
            # Get summary
            summary = self.classifier.get_detection_summary(detections)
            logger.info(f"📊 Detection Summary:")
            logger.info(f"   Total count: {summary['total_count']}")
            logger.info(f"   Average confidence: {summary['avg_confidence']:.3f}")
            logger.info(f"   Class breakdown:")
            for class_name, count in summary['class_counts'].items():
                logger.info(f"      - {class_name}: {count}")
            
            # Detailed detections
            logger.info(f"📋 Detailed Detections:")
            for i, det in enumerate(detections, 1):
                logger.info(f"   [{i}] {det['class_name']}")
                logger.info(f"       Confidence: {det['confidence']:.3f}")
                x1, y1, x2, y2 = det['bbox_pixels']
                logger.info(f"       BBox: ({x1}, {y1}) → ({x2}, {y2})")
        else:
            logger.info("ℹ️  No objects detected")
        
        # Save annotated image
        if save_output and config.DRAW_BBOXES:
            output_path = self._save_annotated_image(image_path, frame, detections)
            if output_path:
                logger.info(f"✓ Saved annotated image: {output_path}")
        
        # Show image
        if show_image:
            self._show_image(frame, detections)
        
        logger.info("-" * 60)
        return detections
    
    def test_directory(self, directory_path, save_output=True):
        """
        Test classifier on all images in a directory
        
        Args:
            directory_path: Path to directory containing images
            save_output: Whether to save annotated images
        """
        directory = Path(directory_path)
        
        if not directory.exists():
            logger.error(f"⚠ Directory not found: {directory_path}")
            return
        
        # Find all image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        image_files = [
            f for f in directory.iterdir() 
            if f.suffix.lower() in image_extensions
        ]
        
        if not image_files:
            logger.warning(f"⚠ No images found in {directory_path}")
            return
        
        logger.info("=" * 60)
        logger.info(f"📁 Testing {len(image_files)} images from: {directory}")
        logger.info("=" * 60)
        
        # Statistics
        total_detections = 0
        total_inference_time = 0
        class_counts = {}
        images_with_detections = 0
        
        for i, image_file in enumerate(image_files, 1):
            logger.info(f"\n[{i}/{len(image_files)}]")
            
            start_time = time.time()
            detections = self.test_single_image(
                image_file, 
                save_output=save_output, 
                show_image=False
            )
            inference_time = time.time() - start_time
            
            if detections:
                total_detections += len(detections)
                images_with_detections += 1
                
                # Aggregate class counts
                for det in detections:
                    class_name = det['class_name']
                    class_counts[class_name] = class_counts.get(class_name, 0) + 1
            
            total_inference_time += inference_time
        
        # Print overall statistics
        logger.info("\n" + "=" * 60)
        logger.info("📊 OVERALL STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total images processed: {len(image_files)}")
        logger.info(f"Images with detections: {images_with_detections}/{len(image_files)}")
        logger.info(f"Total objects detected: {total_detections}")
        logger.info(f"Average detections per image: {total_detections/len(image_files):.2f}")
        logger.info(f"Average inference time: {(total_inference_time/len(image_files))*1000:.1f}ms")
        
        if class_counts:
            logger.info(f"\nClass Distribution:")
            for class_name, count in sorted(class_counts.items()):
                percentage = (count / total_detections) * 100
                logger.info(f"   {class_name}: {count} ({percentage:.1f}%)")
        
        logger.info("=" * 60)
    
    def test_video_stream(self, video_path=None, camera_index=0):
        """
        Test classifier on video stream or camera feed
        
        Args:
            video_path: Path to video file (None for camera)
            camera_index: Camera index if using camera
        """
        if video_path:
            cap = cv2.VideoCapture(str(video_path))
            source_name = Path(video_path).name
        else:
            cap = cv2.VideoCapture(camera_index)
            source_name = f"Camera {camera_index}"
        
        if not cap.isOpened():
            logger.error(f"⚠ Failed to open video source: {source_name}")
            return
        
        logger.info("=" * 60)
        logger.info(f"🎥 Testing video stream: {source_name}")
        logger.info("Press 'q' to quit, 's' to save current frame")
        logger.info("=" * 60)
        
        frame_count = 0
        total_inference_time = 0
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.info("End of video stream")
                    break
                
                frame_count += 1
                
                # Run detection
                start_time = time.time()
                detections = self.classifier.detect_with_nms(
                    frame, 
                    iou_threshold=config.NMS_IOU_THRESHOLD
                )
                inference_time = time.time() - start_time
                total_inference_time += inference_time
                
                # Draw bounding boxes using classifier's method
                if config.DRAW_BBOXES and detections:
                    frame = self.classifier.draw_bounding_boxes(frame, detections)
                
                # Add info overlay
                fps = 1.0 / inference_time if inference_time > 0 else 0
                info_text = f"Frame: {frame_count} | FPS: {fps:.1f} | Detections: {len(detections)}"
                cv2.putText(
                    frame, info_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
                )
                
                # Display frame
                cv2.imshow('Classifier Test - Press Q to quit', frame)
                
                # Handle key press
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    # Save current frame
                    output_path = Path("test_output") / f"frame_{frame_count}.jpg"
                    output_path.parent.mkdir(exist_ok=True)
                    cv2.imwrite(str(output_path), frame)
                    logger.info(f"✓ Saved frame to {output_path}")
        
        finally:
            cap.release()
            cv2.destroyAllWindows()
            
            avg_fps = frame_count / total_inference_time if total_inference_time > 0 else 0
            logger.info(f"\nProcessed {frame_count} frames")
            logger.info(f"Average FPS: {avg_fps:.2f}")
    
    def benchmark_performance(self, test_image_path, num_iterations=100):
        """
        Benchmark inference performance
        
        Args:
            test_image_path: Path to test image
            num_iterations: Number of iterations to run
        """
        logger.info("=" * 60)
        logger.info(f"⚡ PERFORMANCE BENCHMARK ({num_iterations} iterations)")
        logger.info("=" * 60)
        
        # Load image
        frame = cv2.imread(str(test_image_path))
        if frame is None:
            logger.error(f"⚠ Failed to load image: {test_image_path}")
            return
        
        logger.info(f"Image: {Path(test_image_path).name}")
        logger.info(f"Size: {frame.shape[1]}x{frame.shape[0]} pixels")
        logger.info(f"Running {num_iterations} inference iterations...\n")
        
        inference_times = []
        
        for i in range(num_iterations):
            start_time = time.time()
            detections = self.classifier.detect_with_nms(
                frame, 
                iou_threshold=config.NMS_IOU_THRESHOLD
            )
            inference_time = time.time() - start_time
            inference_times.append(inference_time)
            
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{num_iterations}")
        
        # Calculate statistics
        import statistics
        avg_time = statistics.mean(inference_times)
        min_time = min(inference_times)
        max_time = max(inference_times)
        median_time = statistics.median(inference_times)
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 BENCHMARK RESULTS")
        logger.info("=" * 60)
        logger.info(f"Average inference time: {avg_time*1000:.2f}ms ({1/avg_time:.1f} FPS)")
        logger.info(f"Minimum inference time: {min_time*1000:.2f}ms ({1/min_time:.1f} FPS)")
        logger.info(f"Maximum inference time: {max_time*1000:.2f}ms ({1/max_time:.1f} FPS)")
        logger.info(f"Median inference time: {median_time*1000:.2f}ms ({1/median_time:.1f} FPS)")
        logger.info("=" * 60)
    
    def _save_annotated_image(self, original_path, frame, detections):
        """Save annotated image to output directory"""
        try:
            output_dir = Path("test_output")
            output_dir.mkdir(exist_ok=True)
            
            # Create output filename
            original_name = Path(original_path).stem
            output_path = output_dir / f"{original_name}_annotated.jpg"
            
            # Draw bounding boxes using classifier's method
            if detections:
                annotated_frame = self.classifier.draw_bounding_boxes(frame.copy(), detections)
            else:
                annotated_frame = frame
            
            # Save image
            cv2.imwrite(str(output_path), annotated_frame)
            return output_path
            
        except Exception as e:
            logger.error(f"⚠ Failed to save annotated image: {e}")
            return None
    
    def _show_image(self, frame, detections):
        """Display image with bounding boxes"""
        try:
            # Draw bounding boxes using classifier's method
            if detections:
                display_frame = self.classifier.draw_bounding_boxes(frame.copy(), detections)
            else:
                display_frame = frame
            
            # Resize if image is too large
            max_display_width = 1280
            max_display_height = 720
            h, w = display_frame.shape[:2]
            
            if w > max_display_width or h > max_display_height:
                scale = min(max_display_width / w, max_display_height / h)
                new_w = int(w * scale)
                new_h = int(h * scale)
                display_frame = cv2.resize(display_frame, (new_w, new_h))
            
            cv2.imshow('Detection Result - Press any key to continue', display_frame)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            
        except Exception as e:
            logger.error(f"⚠ Failed to display image: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Test PinyaSuri AI Classifier without drone"
    )
    
    parser.add_argument(
        'mode',
        choices=['image', 'directory', 'video', 'camera', 'benchmark'],
        help='Testing mode'
    )
    
    parser.add_argument(
        'path',
        nargs='?',
        help='Path to image, directory, or video file'
    )
    
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save annotated images'
    )
    
    parser.add_argument(
        '--show',
        action='store_true',
        help='Display images (only for single image mode)'
    )
    
    parser.add_argument(
        '--camera-index',
        type=int,
        default=0,
        help='Camera index for camera mode (default: 0)'
    )
    
    parser.add_argument(
        '--iterations',
        type=int,
        default=100,
        help='Number of iterations for benchmark (default: 100)'
    )
    
    args = parser.parse_args()
    
    # Initialize tester
    try:
        tester = ClassifierTester()
    except Exception as e:
        logger.error(f"Failed to initialize tester: {e}")
        sys.exit(1)
    
    # Run appropriate test
    try:
        if args.mode == 'image':
            if not args.path:
                logger.error("Error: Image path required for 'image' mode")
                sys.exit(1)
            tester.test_single_image(
                args.path, 
                save_output=not args.no_save,
                show_image=args.show
            )
        
        elif args.mode == 'directory':
            if not args.path:
                logger.error("Error: Directory path required for 'directory' mode")
                sys.exit(1)
            tester.test_directory(args.path, save_output=not args.no_save)
        
        elif args.mode == 'video':
            if not args.path:
                logger.error("Error: Video path required for 'video' mode")
                sys.exit(1)
            tester.test_video_stream(video_path=args.path)
        
        elif args.mode == 'camera':
            tester.test_video_stream(camera_index=args.camera_index)
        
        elif args.mode == 'benchmark':
            if not args.path:
                logger.error("Error: Image path required for 'benchmark' mode")
                sys.exit(1)
            tester.benchmark_performance(args.path, num_iterations=args.iterations)
    
    except KeyboardInterrupt:
        logger.info("\n⚠ Interrupted by user")
    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()