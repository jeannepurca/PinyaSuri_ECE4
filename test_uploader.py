#!/usr/bin/env python3
# test_uploader.py

import json
import time
import sys
import logging
from pathlib import Path
from datetime import datetime
import shutil
import cv2
import numpy as np
import requests

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
# SERVER DIAGNOSTICS
# ============================================================================
class ServerDiagnostics:
    """Diagnose server API response format and requirements"""
    
    @staticmethod
    def test_flight_log_structure():
        """Test what structure the server expects for flight logs"""
        logger.info("=" * 60)
        logger.info("SERVER DIAGNOSTICS: Testing Flight Log Structure")
        logger.info("=" * 60)
        
        try:
            # Create a minimal flight log with EXACT waypoint naming
            test_flight_id = f"DIAGNOSTIC_{int(time.time())}"
            
            flight_log = {
                'id': test_flight_id,
                'type': 'flight',
                'date': datetime.now().strftime("%B %d, %Y"),
                'start_time': "10:00:00",
                'end_time': "10:15:00",
                'summary': {
                    'total_waypoints': 2,
                    'captured_waypoints': 2,
                    'mission_status': 'Test',
                    'pineapples_detected': 0,
                    'healthy_pineapples': 0,
                    'afflicted_pineapples': 0,
                    'most_common_affliction': None,
                    'avg_confidence': 0.0
                },
                'waypoints': [
                    {
                        'waypoint_id': 'WP_TEST_A',  # Test different naming patterns
                        'image': '',
                        'images': [],
                        'num_pineapples': 0,
                        'healthy': 0,
                        'afflicted': 0,
                        'afflictions': {}
                    },
                    {
                        'waypoint_id': 'WP_TEST_B',
                        'image': '',
                        'images': [],
                        'num_pineapples': 0,
                        'healthy': 0,
                        'afflicted': 0,
                        'afflictions': {}
                    }
                ]
            }
            
            logger.info("Uploading test flight log...")
            logger.info(f"  Flight ID: {test_flight_id}")
            logger.info(f"  Waypoints: WP_TEST_A, WP_TEST_B")
            
            response = requests.post(
                config.FLIGHT_LOG_ENDPOINT,
                json=flight_log,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            logger.info(f"Flight log upload status: {response.status_code}")
            logger.info(f"Response: {response.text}")
            
            if response.status_code in [200, 201]:
                logger.info("✓ Flight log accepted by server")
                
                # Now test image upload with MATCHING waypoint ID
                logger.info("")
                logger.info("Testing image upload with MATCHING waypoint ID...")
                
                test_img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
                test_path = Path("/tmp/diagnostic_test.jpg")
                cv2.imwrite(str(test_path), test_img)
                
                with open(test_path, "rb") as f:
                    files = {"image": ("diagnostic_test.jpg", f, "image/jpeg")}
                    data = {
                        "flight_id": test_flight_id,
                        "waypoint": "WP_TEST_A"  # EXACT match
                    }
                    
                    logger.info(f"  Uploading with: flight_id={data['flight_id']}, waypoint={data['waypoint']}")
                    
                    img_response = requests.post(
                        config.IMAGE_UPLOAD_ENDPOINT,
                        files=files,
                        data=data,
                        timeout=10
                    )
                    
                    logger.info(f"  Image upload status: {img_response.status_code}")
                    logger.info(f"  Response: {img_response.text}")
                
                test_path.unlink(missing_ok=True)
                
                if img_response.status_code in [200, 201]:
                    logger.info("✓ Image accepted with matching waypoint ID!")
                    
                    # Try to extract URL from response
                    try:
                        resp_data = img_response.json()
                        url = (resp_data.get('url') or 
                               resp_data.get('image_url') or 
                               resp_data.get('path') or
                               resp_data.get('file_url'))
                        if url:
                            logger.info(f"✓ Server returned image URL: {url}")
                            return test_flight_id, "WP_TEST_A", url
                        else:
                            logger.warning(f"⚠ Response has no URL field: {list(resp_data.keys())}")
                    except:
                        logger.info(f"  Response (non-JSON): {img_response.text}")
                    
                    return test_flight_id, "WP_TEST_A", None
                else:
                    logger.warning(f"⚠ Image rejected: {img_response.text}")
                    logger.warning("  Server may require different waypoint naming format")
                    return None, None, None
            else:
                logger.error(f"✗ Flight log rejected: {response.text}")
                return None, None, None
                
        except Exception as e:
            logger.error(f"Diagnostic failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, None, None
    
    @staticmethod
    def inspect_server_requirements():
        """Try to understand server's exact requirements"""
        logger.info("=" * 60)
        logger.info("SERVER DIAGNOSTICS: Inspecting Server Requirements")
        logger.info("=" * 60)
        
        # Test different waypoint naming patterns
        test_patterns = [
            "WAYPOINT_2",
            "WP_2", 
            "WP2",
            "waypoint_2",
            "2"
        ]
        
        test_flight_id = f"PATTERN_TEST_{int(time.time())}"
        
        for pattern in test_patterns:
            logger.info(f"\nTesting waypoint pattern: '{pattern}'")
            
            flight_log = {
                'id': test_flight_id,
                'type': 'flight',
                'date': datetime.now().strftime("%B %d, %Y"),
                'start_time': "10:00:00",
                'end_time': "10:00:10",
                'summary': {
                    'total_waypoints': 1,
                    'captured_waypoints': 1,
                    'mission_status': 'Test',
                    'pineapples_detected': 0,
                    'healthy_pineapples': 0,
                    'afflicted_pineapples': 0,
                    'most_common_affliction': None,
                    'avg_confidence': 0.0
                },
                'waypoints': [
                    {
                        'waypoint_id': pattern,
                        'image': '',
                        'images': [],
                        'num_pineapples': 0,
                        'healthy': 0,
                        'afflicted': 0,
                        'afflictions': {}
                    }
                ]
            }
            
            try:
                # Upload flight log
                response = requests.post(
                    config.FLIGHT_LOG_ENDPOINT,
                    json=flight_log,
                    timeout=5
                )
                
                if response.status_code not in [200, 201]:
                    logger.warning(f"  ✗ Flight log rejected for pattern '{pattern}'")
                    continue
                
                # Try image upload
                test_img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
                test_path = Path(f"/tmp/test_{pattern}.jpg")
                cv2.imwrite(str(test_path), test_img)
                
                with open(test_path, "rb") as f:
                    files = {"image": (f"test_{pattern}.jpg", f, "image/jpeg")}
                    data = {
                        "flight_id": test_flight_id,
                        "waypoint": pattern
                    }
                    
                    img_resp = requests.post(
                        config.IMAGE_UPLOAD_ENDPOINT,
                        files=files,
                        data=data,
                        timeout=5
                    )
                
                test_path.unlink(missing_ok=True)
                
                if img_resp.status_code in [200, 201]:
                    logger.info(f"  ✓ SUCCESS with pattern: '{pattern}'")
                    logger.info(f"    Response: {img_resp.text[:100]}")
                    return pattern  # Return successful pattern
                else:
                    logger.warning(f"  ✗ Image rejected for pattern '{pattern}'")
                    logger.warning(f"    Error: {img_resp.text[:100]}")
                    
            except Exception as e:
                logger.warning(f"  ✗ Error testing pattern '{pattern}': {e}")
            
            time.sleep(0.5)  # Brief delay between tests
        
        logger.warning("\n⚠ No waypoint pattern worked!")
        return None


# ============================================================================
# IMPROVED TEST DATA GENERATOR
# ============================================================================
class ImprovedTestDataGenerator:
    """Generate test data matching server requirements"""
    
    def __init__(self, waypoint_pattern="WAYPOINT_{}"):
        self.test_dir = Path("test_data")
        self.test_images_dir = self.test_dir / "images"
        self.test_json_dir = self.test_dir / "json"
        self.flight_id = f"TEST_FLIGHT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.created_files = []
        self.waypoint_pattern = waypoint_pattern  # Configurable pattern
    
    def setup(self):
        """Create test directories"""
        logger.info("=" * 60)
        logger.info("SETTING UP TEST ENVIRONMENT")
        logger.info("=" * 60)
        
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        
        self.test_images_dir.mkdir(parents=True)
        self.test_json_dir.mkdir(parents=True)
        
        logger.info(f"✓ Created test directories")
        logger.info(f"  Waypoint pattern: {self.waypoint_pattern}")
    
    def get_waypoint_id(self, wp_num):
        """Get waypoint ID using configured pattern"""
        return self.waypoint_pattern.format(wp_num)
    
    def create_test_image(self, waypoint_num, burst_index=0):
        """Create a test image"""
        img = np.random.randint(50, 200, (640, 640, 3), dtype=np.uint8)
        cv2.rectangle(img, (100, 100), (540, 540), (0, 255, 0), 2)
        
        waypoint_id = self.get_waypoint_id(waypoint_num)
        text = f"{waypoint_id} - Frame {burst_index}"
        
        cv2.putText(img, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.7, (255, 255, 255), 2)
        cv2.putText(img, self.flight_id, (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, (200, 200, 200), 1)
        
        timestamp = int(time.time() * 1000)
        filename = f"pinyasuri_{self.flight_id}_wp{waypoint_num}_{timestamp}_f{burst_index}.jpg"
        filepath = self.test_images_dir / filename
        
        cv2.imwrite(str(filepath), img)
        self.created_files.append(filepath)
        
        return filepath, waypoint_id
    
    def create_complete_test_flight(self, num_waypoints=2):
        """Create complete test flight with proper waypoint matching"""
        logger.info("=" * 60)
        logger.info(f"GENERATING TEST FLIGHT")
        logger.info(f"Flight ID: {self.flight_id}")
        logger.info("=" * 60)
        
        # Create waypoints and images
        waypoint_list = []
        image_paths = []
        
        for wp_num in range(2, 2 + num_waypoints):
            waypoint_id = self.get_waypoint_id(wp_num)
            
            waypoint_entry = {
                'waypoint_id': waypoint_id,  # Use consistent naming
                'image': '',
                'images': [],
                'num_pineapples': 2,
                'healthy': 1,
                'afflicted': 1,
                'afflictions': {'Crown Rot Disease': 1}
            }
            waypoint_list.append(waypoint_entry)
            
            # Create image for this waypoint
            img_path, _ = self.create_test_image(wp_num, 0)
            image_paths.append((img_path, waypoint_id))
        
        # Create flight log
        flight_log = {
            'id': self.flight_id,
            'type': 'flight',
            'date': datetime.now().strftime("%B %d, %Y"),
            'start_time': datetime.now().strftime("%H:%M:%S"),
            'end_time': datetime.now().strftime("%H:%M:%S"),
            'summary': {
                'total_waypoints': num_waypoints,
                'captured_waypoints': num_waypoints,
                'mission_status': 'Completed',
                'pineapples_detected': num_waypoints * 2,
                'healthy_pineapples': num_waypoints,
                'afflicted_pineapples': num_waypoints,
                'most_common_affliction': 'Crown Rot Disease',
                'avg_confidence': 90.0
            },
            'waypoints': waypoint_list
        }
        
        # Save flight log
        log_filename = f"{self.flight_id}_summary.json"
        log_path = self.test_json_dir / log_filename
        
        with open(log_path, 'w') as f:
            json.dump(flight_log, f, indent=4)
        
        self.created_files.append(log_path)
        logger.info(f"✓ Created flight log with {num_waypoints} waypoints")
        logger.info(f"✓ Created {len(image_paths)} test images")
        
        return log_path, image_paths, flight_log
    
    def cleanup(self):
        """Remove test data"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            logger.info(f"✓ Cleaned up test data")


# ============================================================================
# REALISTIC WORKFLOW TEST
# ============================================================================
class RealisticWorkflowTest:
    """Test that mimics actual flight workflow"""
    
    def __init__(self, waypoint_pattern="WAYPOINT_{}"):
        self.generator = ImprovedTestDataGenerator(waypoint_pattern)
        self.uploaded_image_urls = []
    
    def run(self):
        """Run realistic upload test"""
        logger.info("=" * 60)
        logger.info("REALISTIC WORKFLOW TEST")
        logger.info("=" * 60)
        
        try:
            # Setup
            self.generator.setup()
            
            # Create test data
            log_path, image_paths, flight_data = self.generator.create_complete_test_flight(num_waypoints=2)
            
            # STEP 1: Upload flight log FIRST
            logger.info("")
            logger.info("STEP 1: Uploading flight log...")
            logger.info("-" * 60)
            
            try:
                response = requests.post(
                    config.FLIGHT_LOG_ENDPOINT,
                    json=flight_data,
                    timeout=10,
                    headers={"Content-Type": "application/json"}
                )
                
                logger.info(f"Status: {response.status_code}")
                logger.info(f"Response: {response.text[:200]}")
                
                if response.status_code not in [200, 201]:
                    logger.error(f"✗ Flight log rejected")
                    return False
                
                logger.info("✓ Flight log accepted")
                    
            except Exception as e:
                logger.error(f"✗ Flight log upload failed: {e}")
                return False
            
            # Small delay to ensure server processes the log
            time.sleep(1)
            
            # STEP 2: Upload images with MATCHING waypoint IDs
            logger.info("")
            logger.info("STEP 2: Uploading images...")
            logger.info("-" * 60)
            
            uploaded_count = 0
            failed_count = 0
            
            for img_path, waypoint_id in image_paths:
                try:
                    logger.info(f"Uploading: {Path(img_path).name}")
                    logger.info(f"  flight_id: {self.generator.flight_id}")
                    logger.info(f"  waypoint: {waypoint_id}")
                    
                    with open(img_path, "rb") as f:
                        files = {"image": (Path(img_path).name, f, "image/jpeg")}
                        data = {
                            "flight_id": self.generator.flight_id,
                            "waypoint": waypoint_id  # EXACT match with flight log
                        }
                        
                        response = requests.post(
                            config.IMAGE_UPLOAD_ENDPOINT,
                            files=files,
                            data=data,
                            timeout=10
                        )
                    
                    logger.info(f"  Status: {response.status_code}")
                    
                    if response.status_code in [200, 201]:
                        logger.info(f"  ✓ Upload successful")
                        logger.info(f"  Response: {response.text[:200]}")
                        
                        # Try to extract URL
                        try:
                            json_resp = response.json()
                            url = (json_resp.get('url') or 
                                  json_resp.get('image_url') or 
                                  json_resp.get('path') or
                                  json_resp.get('file_url'))
                            if url:
                                logger.info(f"  📎 Image URL: {url}")
                                self.uploaded_image_urls.append({
                                    'waypoint': waypoint_id,
                                    'url': url,
                                    'filename': Path(img_path).name
                                })
                        except:
                            pass
                        
                        uploaded_count += 1
                    else:
                        logger.warning(f"  ✗ Upload failed")
                        logger.warning(f"  Response: {response.text}")
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"  ✗ Error: {e}")
                    failed_count += 1
            
            # Summary
            logger.info("")
            logger.info("=" * 60)
            logger.info("TEST RESULTS")
            logger.info("=" * 60)
            logger.info(f"Flight Log: ✓ Uploaded")
            logger.info(f"Images: {uploaded_count} uploaded, {failed_count} failed")
            logger.info(f"Image URLs captured: {len(self.uploaded_image_urls)}")
            
            if self.uploaded_image_urls:
                logger.info("\nCaptured Image URLs:")
                for item in self.uploaded_image_urls:
                    logger.info(f"  {item['waypoint']}: {item['url']}")
            
            success = uploaded_count > 0 and failed_count == 0
            
            if success:
                logger.info("\n✓ ALL TESTS PASSED!")
            else:
                logger.info("\n⚠ TESTS COMPLETED WITH ISSUES")
            
            return success
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        finally:
            time.sleep(1)
            self.generator.cleanup()


# ============================================================================
# MAIN
# ============================================================================
def main():
    """Main test entry point"""
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 58 + "║")
    logger.info("║" + "  PINYASURI UPLOADER DIAGNOSTIC SUITE v2".center(58) + "║")
    logger.info("║" + " " * 58 + "║")
    logger.info("╚" + "=" * 58 + "╝")
    logger.info("")
    
    try:
        # Diagnostic 1: Test basic structure
        logger.info("\n")
        flight_id, waypoint, url = ServerDiagnostics.test_flight_log_structure()
        time.sleep(2)
        
        # Diagnostic 2: Find working waypoint pattern
        logger.info("\n")
        working_pattern = ServerDiagnostics.inspect_server_requirements()
        time.sleep(2)
        
        # Use discovered pattern or default
        if working_pattern:
            # Convert discovered pattern to format string
            if "WAYPOINT_" in working_pattern:
                pattern = "WAYPOINT_{}"
            elif "WP_" in working_pattern:
                pattern = "WP_{}"
            elif "WP" in working_pattern and "_" not in working_pattern:
                pattern = "WP{}"
            else:
                pattern = "{}"  # Just the number
                
            logger.info(f"\n✓ Using waypoint pattern: {pattern}")
        else:
            pattern = "WAYPOINT_{}"  # Default from your config
            logger.info(f"\n⚠ Using default pattern: {pattern}")
        
        # Test 3: Realistic workflow with correct pattern
        logger.info("\n")
        workflow_test = RealisticWorkflowTest(waypoint_pattern=pattern)
        success = workflow_test.run()
        
        # Final summary
        logger.info("")
        logger.info("╔" + "=" * 58 + "╗")
        if success:
            logger.info("║" + "  ✓ ALL DIAGNOSTICS PASSED".center(58) + "║")
        else:
            logger.info("║" + "  ⚠ DIAGNOSTICS FOUND ISSUES - See above".center(58) + "║")
        logger.info("╚" + "=" * 58 + "╝")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.info("")
        logger.warning("⚠ Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"⚠ Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())