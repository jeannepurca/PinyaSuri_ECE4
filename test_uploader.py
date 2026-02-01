#!/usr/bin/env python3
# test_uploader.py - Comprehensive Uploader Testing Script

"""
Test script for validating the uploader.py functionality.

This script will:
1. Create test flight data (images + JSON)
2. Test the upload queue system
3. Validate JSON-to-image relationships
4. Test server connectivity
5. Verify flight summary generation
6. Check upload success/failure tracking

Usage:
    python test_uploader.py
"""

import json
import time
import sys
import logging
from pathlib import Path
from datetime import datetime
import shutil
import cv2
import numpy as np

# Import your modules
import config
import uploader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# TEST DATA GENERATOR
# ============================================================================
class TestDataGenerator:
    """Generate realistic test data for upload testing"""
    
    def __init__(self):
        self.test_dir = Path("test_data")
        self.test_images_dir = self.test_dir / "images"
        self.test_json_dir = self.test_dir / "json"
        self.flight_id = f"TEST_FLIGHT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.created_files = []
    
    def setup(self):
        """Create test directories"""
        logger.info("=" * 60)
        logger.info("SETTING UP TEST ENVIRONMENT")
        logger.info("=" * 60)
        
        # Clean up old test data
        if self.test_dir.exists():
            logger.info(f"Removing old test data: {self.test_dir}")
            shutil.rmtree(self.test_dir)
        
        # Create fresh directories
        self.test_images_dir.mkdir(parents=True)
        self.test_json_dir.mkdir(parents=True)
        
        logger.info(f"✓ Created test directories:")
        logger.info(f"  - Images: {self.test_images_dir}")
        logger.info(f"  - JSON: {self.test_json_dir}")
    
    def create_test_image(self, waypoint, burst_index=0, is_best=False):
        """Create a realistic test image with text overlay"""
        # Create a colored image (simulating pineapple field)
        img = np.random.randint(50, 200, (640, 640, 3), dtype=np.uint8)
        
        # Add some visual elements
        cv2.rectangle(img, (100, 100), (540, 540), (0, 255, 0), 2)
        
        # Add text overlay
        text = f"WP{waypoint} - Frame {burst_index}"
        if is_best:
            text += " [BEST]"
        
        cv2.putText(img, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.7, (255, 255, 255), 2)
        cv2.putText(img, self.flight_id, (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, (200, 200, 200), 1)
        
        # Generate filename matching your naming convention
        timestamp = int(time.time() * 1000)
        best_suffix = "_BEST" if is_best else ""
        filename = f"pinyasuri_{self.flight_id}_wp{waypoint}_{timestamp}_f{burst_index}{best_suffix}.jpg"
        filepath = self.test_images_dir / filename
        
        # Save image
        cv2.imwrite(str(filepath), img)
        self.created_files.append(filepath)
        
        logger.debug(f"  Created image: {filename}")
        return filepath
    
    def create_detection_image(self, waypoint, burst_index=0):
        """Create a detection visualization image"""
        # Create image with bounding boxes
        img = np.random.randint(50, 200, (640, 640, 3), dtype=np.uint8)
        
        # Draw some fake bounding boxes
        cv2.rectangle(img, (150, 150), (300, 300), (0, 255, 0), 3)
        cv2.putText(img, "Healthy (0.95)", (150, 140), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        cv2.rectangle(img, (350, 200), (500, 400), (0, 0, 255), 3)
        cv2.putText(img, "Crown Rot (0.87)", (350, 190), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        # Generate filename
        timestamp = int(time.time() * 1000)
        filename = f"detection_{self.flight_id}_wp{waypoint}_{timestamp}_f{burst_index}_BEST.jpg"
        filepath = self.test_images_dir / filename
        
        cv2.imwrite(str(filepath), img)
        self.created_files.append(filepath)
        
        logger.debug(f"  Created detection: {filename}")
        return filepath
    
    def create_test_flight_data(self, num_waypoints=3):
        """Create a complete test flight with images and detections"""
        logger.info("=" * 60)
        logger.info(f"GENERATING TEST FLIGHT DATA")
        logger.info(f"Flight ID: {self.flight_id}")
        logger.info(f"Waypoints: {num_waypoints}")
        logger.info("=" * 60)
        
        flight_images = []
        flight_detections = {}
        
        for wp in range(2, 2 + num_waypoints):  # Start from WP2 (skip HOME and TAKEOFF)
            logger.info(f"Generating data for Waypoint {wp}...")
            
            # Create burst images (3 frames)
            burst_images = []
            for frame_idx in range(3):
                is_best = (frame_idx == 1)  # Frame 1 is the best
                img_path = self.create_test_image(wp, frame_idx, is_best)
                burst_images.append(img_path)
                
                if is_best:
                    flight_images.append(str(img_path))
            
            # Create detection image for best frame
            det_path = self.create_detection_image(wp, 1)
            
            # Generate mock detections for this waypoint
            detections = [
                {
                    'class_name': 'Healthy',
                    'confidence': 0.95,
                    'bbox': [150, 150, 300, 300]
                },
                {
                    'class_name': 'Crown Rot Disease',
                    'confidence': 0.87,
                    'bbox': [350, 200, 500, 400]
                }
            ]
            
            flight_detections[wp] = {
                'image_path': str(burst_images[1]),  # Best frame
                'detections': detections
            }
            
            logger.info(f"  ✓ Created {len(burst_images)} images + 1 detection visualization")
        
        logger.info(f"✓ Generated {len(flight_images)} best frame images")
        logger.info(f"✓ Generated {len(flight_detections)} waypoint detection sets")
        
        return flight_images, flight_detections
    
    def create_flight_summary_json(self, flight_images, flight_detections):
        """Create a mock flight summary JSON matching your format"""
        logger.info("=" * 60)
        logger.info("GENERATING FLIGHT SUMMARY JSON")
        logger.info("=" * 60)
        
        waypoint_list = []
        total_detections = 0
        healthy_count = 0
        afflicted_count = 0
        
        for wp_num, det_data in flight_detections.items():
            detections = det_data['detections']
            
            wp_healthy = sum(1 for d in detections if d['class_name'] == 'Healthy')
            wp_afflicted = len(detections) - wp_healthy
            
            healthy_count += wp_healthy
            afflicted_count += wp_afflicted
            total_detections += len(detections)
            
            waypoint_entry = {
                'waypoint_id': f'WAYPOINT_{wp_num}',
                'image': f"http://placeholder.url/image_wp{wp_num}.jpg",  # Will be replaced by actual upload
                'images': [f"http://placeholder.url/image_wp{wp_num}.jpg"],
                'num_pineapples': len(detections),
                'healthy': wp_healthy,
                'afflicted': wp_afflicted,
                'afflictions': {
                    d['class_name']: 1 for d in detections if d['class_name'] != 'Healthy'
                }
            }
            
            waypoint_list.append(waypoint_entry)
        
        summary = {
            'id': self.flight_id,
            'type': 'flight',
            'date': datetime.now().strftime("%B %d, %Y"),
            'start_time': "10:30:00",
            'end_time': "10:45:00",
            'summary': {
                'total_waypoints': len(flight_detections) + 2,  # +2 for HOME and TAKEOFF
                'captured_waypoints': len(flight_detections),
                'mission_status': 'Completed',
                'pineapples_detected': total_detections,
                'healthy_pineapples': healthy_count,
                'afflicted_pineapples': afflicted_count,
                'most_common_affliction': 'Crown Rot Disease',
                'avg_confidence': 91.0
            },
            'waypoints': waypoint_list,
            'image_metadata': {
                'total_images': len(flight_images),
                'images_per_waypoint': {
                    f'WAYPOINT_{wp}': 1 for wp in flight_detections.keys()
                }
            }
        }
        
        # Save JSON
        summary_filename = f"{self.flight_id}_summary.json"
        summary_path = self.test_json_dir / summary_filename
        
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=4)
        
        self.created_files.append(summary_path)
        
        logger.info(f"✓ Created flight summary: {summary_filename}")
        logger.info(f"  - Total waypoints: {summary['summary']['total_waypoints']}")
        logger.info(f"  - Captured waypoints: {summary['summary']['captured_waypoints']}")
        logger.info(f"  - Total detections: {total_detections}")
        
        return summary_path
    
    def cleanup(self):
        """Remove all test data"""
        logger.info("=" * 60)
        logger.info("CLEANING UP TEST DATA")
        logger.info("=" * 60)
        
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            logger.info(f"✓ Removed test directory: {self.test_dir}")


# ============================================================================
# TEST SUITE
# ============================================================================
class UploaderTestSuite:
    """Comprehensive test suite for uploader functionality"""
    
    def __init__(self):
        self.generator = TestDataGenerator()
        self.test_results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }
    
    def log_result(self, test_name, passed, message=""):
        """Log test result"""
        if passed:
            self.test_results['passed'].append(test_name)
            logger.info(f"✓ PASS: {test_name}")
            if message:
                logger.info(f"  {message}")
        else:
            self.test_results['failed'].append(test_name)
            logger.error(f"✗ FAIL: {test_name}")
            if message:
                logger.error(f"  {message}")
    
    def test_server_connection(self):
        """Test 1: Server connectivity"""
        logger.info("=" * 60)
        logger.info("TEST 1: Server Connection")
        logger.info("=" * 60)
        
        try:
            result = uploader.test_server_connection()
            
            if result:
                self.log_result("Server Connection", True, 
                               f"Connected to {config.SERVER_BASE}")
            else:
                self.log_result("Server Connection", False, 
                               f"Cannot reach {config.SERVER_BASE}")
                logger.warning("  This may cause upload failures in subsequent tests")
        except Exception as e:
            self.log_result("Server Connection", False, str(e))
    
    def test_flight_aggregator(self):
        """Test 2: Flight aggregator functionality"""
        logger.info("=" * 60)
        logger.info("TEST 2: Flight Aggregator")
        logger.info("=" * 60)
        
        try:
            test_flight_id = "TEST_AGGREGATOR_001"
            
            # Start flight
            uploader.start_new_flight(test_flight_id)
            
            # Check if flight was initialized
            has_data = uploader.flight_aggregator.has_flight_data(test_flight_id)
            
            if has_data:
                self.log_result("Flight Aggregator Init", True, 
                               f"Flight {test_flight_id} initialized")
            else:
                self.log_result("Flight Aggregator Init", False, 
                               "Flight not properly initialized")
            
            # Add mock detection data
            mock_detections = [
                {'class_name': 'Healthy', 'confidence': 0.95, 'bbox': [0, 0, 100, 100]}
            ]
            
            uploader.add_detection_to_flight(
                test_flight_id, 
                waypoint=2,
                image_path="/tmp/test_image.jpg",
                detections=mock_detections
            )
            
            # Verify data was added
            flight_info = uploader.flight_aggregator.get_flight_info(test_flight_id)
            
            if flight_info['waypoints'] > 0:
                self.log_result("Flight Aggregator Add Data", True, 
                               f"Data added: {flight_info}")
            else:
                self.log_result("Flight Aggregator Add Data", False, 
                               "No waypoints tracked")
                
        except Exception as e:
            self.log_result("Flight Aggregator", False, str(e))
    
    def test_upload_queue(self):
        """Test 3: Upload queue system"""
        logger.info("=" * 60)
        logger.info("TEST 3: Upload Queue System")
        logger.info("=" * 60)
        
        try:
            # Create test image
            test_img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            test_img_path = Path("/tmp/test_queue_image.jpg")
            cv2.imwrite(str(test_img_path), test_img)
            
            # Queue image
            initial_stats = uploader.upload_queue.get_stats()
            uploader.queue_image_upload(test_img_path)
            
            after_stats = uploader.upload_queue.get_stats()
            
            # Check if item was queued
            pending_increased = (
                after_stats['pending_count'] > initial_stats['pending_count'] or
                after_stats['image_queued'] > initial_stats['image_queued']
            )
            
            if pending_increased:
                self.log_result("Upload Queue", True, 
                               f"Image queued successfully. Stats: {after_stats}")
            else:
                self.log_result("Upload Queue", False, 
                               f"Image not queued. Stats: {after_stats}")
            
            # Cleanup
            test_img_path.unlink(missing_ok=True)
            
        except Exception as e:
            self.log_result("Upload Queue", False, str(e))
    
    def test_full_upload_workflow(self):
        """Test 4: Full upload workflow with real data"""
        logger.info("=" * 60)
        logger.info("TEST 4: Full Upload Workflow")
        logger.info("=" * 60)
        
        try:
            # Generate test data
            self.generator.setup()
            flight_images, flight_detections = self.generator.create_test_flight_data(num_waypoints=3)
            summary_path = self.generator.create_flight_summary_json(flight_images, flight_detections)
            
            # Initialize flight in aggregator
            uploader.start_new_flight(self.generator.flight_id)
            
            # Add detection data to aggregator
            for wp_num, det_data in flight_detections.items():
                uploader.add_detection_to_flight(
                    self.generator.flight_id,
                    waypoint=wp_num,
                    image_path=det_data['image_path'],
                    detections=det_data['detections']
                )
            
            logger.info("✓ Added all detection data to flight aggregator")
            
            # Queue all images for upload
            logger.info("Queueing images for upload...")
            for img_path in self.generator.created_files:
                if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    uploader.queue_image_upload(img_path)
            
            # Queue JSON for upload
            logger.info("Queueing JSON for upload...")
            uploader.upload_queue.add_json(summary_path)
            
            # Enable uploading (simulate flight completion)
            logger.info("Enabling uploads (simulating flight completion)...")
            uploader.upload_queue.enable_uploading(self.generator.flight_id)
            
            # Wait for uploads to process
            logger.info("Waiting for upload queue to process...")
            max_wait = 30  # seconds
            waited = 0
            
            while waited < max_wait:
                stats = uploader.upload_queue.get_stats()
                queue_size = stats['queue_size']
                
                logger.info(f"  Queue status: {stats}")
                
                if queue_size == 0:
                    logger.info("  ✓ Queue empty - uploads complete!")
                    break
                
                time.sleep(2)
                waited += 2
            
            # Check final stats
            final_stats = uploader.upload_queue.get_stats()
            
            total_uploaded = final_stats['image_uploaded'] + final_stats['json_uploaded']
            total_failed = final_stats['image_failed'] + final_stats['json_failed']
            
            logger.info(f"Final Upload Statistics:")
            logger.info(f"  Images uploaded: {final_stats['image_uploaded']}")
            logger.info(f"  JSON uploaded: {final_stats['json_uploaded']}")
            logger.info(f"  Total uploaded: {total_uploaded}")
            logger.info(f"  Total failed: {total_failed}")
            
            if total_uploaded > 0 and total_failed == 0:
                self.log_result("Full Upload Workflow", True, 
                               f"All uploads successful ({total_uploaded} files)")
            elif total_uploaded > 0:
                self.log_result("Full Upload Workflow", True, 
                               f"Partial success: {total_uploaded} uploaded, {total_failed} failed")
                self.test_results['warnings'].append(
                    f"Some uploads failed: {total_failed} files"
                )
            else:
                self.log_result("Full Upload Workflow", False, 
                               f"No successful uploads. Failed: {total_failed}")
            
        except Exception as e:
            self.log_result("Full Upload Workflow", False, str(e))
            import traceback
            logger.error(traceback.format_exc())
    
    def test_json_image_relationship(self):
        """Test 5: Verify JSON references match uploaded images"""
        logger.info("=" * 60)
        logger.info("TEST 5: JSON-Image Relationship Validation")
        logger.info("=" * 60)
        
        try:
            # This test verifies that the flight summary JSON contains
            # references to the images that were uploaded
            
            flight_id = self.generator.flight_id
            flight_data = uploader.flight_aggregator.flights.get(flight_id)
            
            if not flight_data:
                self.log_result("JSON-Image Relationship", False, 
                               "No flight data found in aggregator")
                return
            
            # Check if image URLs were captured
            image_url_map = flight_data.get('image_url_map', {})
            waypoint_images = flight_data.get('waypoint_images', {})
            
            if image_url_map:
                self.log_result("JSON-Image Relationship", True, 
                               f"Image URLs captured: {len(image_url_map)} mappings")
                
                logger.info("Image URL Mappings:")
                for local_path, url in list(image_url_map.items())[:3]:
                    logger.info(f"  {Path(local_path).name} → {url}")
                
                if len(image_url_map) > 3:
                    logger.info(f"  ... and {len(image_url_map) - 3} more")
            else:
                self.log_result("JSON-Image Relationship", False, 
                               "No image URLs captured - check server response format")
                self.test_results['warnings'].append(
                    "Server may not be returning image URLs in expected format"
                )
            
            # Verify waypoint-to-image linkage
            if waypoint_images:
                logger.info(f"Waypoint Image Linkages:")
                for wp, urls in waypoint_images.items():
                    logger.info(f"  WP{wp}: {len(urls)} images")
            
        except Exception as e:
            self.log_result("JSON-Image Relationship", False, str(e))
    
    def test_directory_structure(self):
        """Test 6: Verify directory structure compliance"""
        logger.info("=" * 60)
        logger.info("TEST 6: Directory Structure Validation")
        logger.info("=" * 60)
        
        try:
            required_dirs = [
                config.IMAGE_DIR,
                config.JSON_DIR,
                config.LOG_DIR,
                config.MODEL_DIR
            ]
            
            missing_dirs = []
            existing_dirs = []
            
            for directory in required_dirs:
                if directory.exists():
                    existing_dirs.append(directory)
                else:
                    missing_dirs.append(directory)
            
            if not missing_dirs:
                self.log_result("Directory Structure", True, 
                               f"All {len(required_dirs)} required directories exist")
            else:
                self.log_result("Directory Structure", False, 
                               f"Missing directories: {missing_dirs}")
            
            # Show directory contents summary
            logger.info("Directory Contents:")
            for directory in existing_dirs:
                try:
                    file_count = len(list(directory.rglob('*')))
                    logger.info(f"  {directory.name}: {file_count} items")
                except Exception as e:
                    logger.warning(f"  {directory.name}: Cannot read ({e})")
            
        except Exception as e:
            self.log_result("Directory Structure", False, str(e))
    
    def run_all_tests(self):
        """Run complete test suite"""
        logger.info("╔" + "=" * 58 + "╗")
        logger.info("║" + " " * 58 + "║")
        logger.info("║" + "  PINYASURI UPLOADER TEST SUITE".center(58) + "║")
        logger.info("║" + " " * 58 + "║")
        logger.info("╚" + "=" * 58 + "╝")
        logger.info("")
        
        # Start upload queue
        uploader.start_upload_queue()
        
        try:
            # Run tests
            self.test_server_connection()
            self.test_directory_structure()
            self.test_flight_aggregator()
            self.test_upload_queue()
            self.test_full_upload_workflow()
            self.test_json_image_relationship()
            
        finally:
            # Stop upload queue
            uploader.stop_upload_queue()
            
            # Cleanup test data
            self.generator.cleanup()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test results summary"""
        logger.info("")
        logger.info("╔" + "=" * 58 + "╗")
        logger.info("║" + " " * 58 + "║")
        logger.info("║" + "  TEST RESULTS SUMMARY".center(58) + "║")
        logger.info("║" + " " * 58 + "║")
        logger.info("╚" + "=" * 58 + "╝")
        logger.info("")
        
        total_tests = len(self.test_results['passed']) + len(self.test_results['failed'])
        pass_rate = (len(self.test_results['passed']) / total_tests * 100) if total_tests > 0 else 0
        
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {len(self.test_results['passed'])} ✓")
        logger.info(f"Failed: {len(self.test_results['failed'])} ✗")
        logger.info(f"Pass Rate: {pass_rate:.1f}%")
        logger.info("")
        
        if self.test_results['passed']:
            logger.info("✓ PASSED TESTS:")
            for test in self.test_results['passed']:
                logger.info(f"  ✓ {test}")
            logger.info("")
        
        if self.test_results['failed']:
            logger.info("✗ FAILED TESTS:")
            for test in self.test_results['failed']:
                logger.info(f"  ✗ {test}")
            logger.info("")
        
        if self.test_results['warnings']:
            logger.info("⚠ WARNINGS:")
            for warning in self.test_results['warnings']:
                logger.info(f"  ⚠ {warning}")
            logger.info("")
        
        # Overall result
        if len(self.test_results['failed']) == 0:
            logger.info("╔" + "=" * 58 + "╗")
            logger.info("║" + "  ✓ ALL TESTS PASSED!".center(58) + "║")
            logger.info("╚" + "=" * 58 + "╝")
        else:
            logger.info("╔" + "=" * 58 + "╗")
            logger.info("║" + "  ⚠ SOME TESTS FAILED - Review above".center(58) + "║")
            logger.info("╚" + "=" * 58 + "╝")


# ============================================================================
# MAIN
# ============================================================================
def main():
    """Main test entry point"""
    try:
        # Ensure config directories exist
        config.ensure_directories()
        
        # Create and run test suite
        test_suite = UploaderTestSuite()
        test_suite.run_all_tests()
        
        # Exit code based on results
        if len(test_suite.test_results['failed']) == 0:
            sys.exit(0)  # Success
        else:
            sys.exit(1)  # Failure
        
    except KeyboardInterrupt:
        logger.info("")
        logger.warning("⚠ Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"⚠ Fatal error in test suite: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()