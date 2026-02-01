#!/usr/bin/env python3
# test_uploader_v2.py - Improved Uploader Testing with Server Compatibility

"""
Enhanced test script that accounts for server requirements:
- Server needs flight logs before accepting images
- Better diagnostics for server response format
- More realistic test workflow
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
    """Diagnose server API response format"""
    
    @staticmethod
    def test_image_upload_response():
        """Test what the server returns when uploading an image"""
        logger.info("=" * 60)
        logger.info("SERVER DIAGNOSTICS: Testing Image Upload Response Format")
        logger.info("=" * 60)
        
        try:
            # Create a minimal test image
            test_img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            test_path = Path("/tmp/diagnostic_test.jpg")
            cv2.imwrite(str(test_path), test_img)
            
            # Try uploading to the server
            with open(test_path, "rb") as f:
                files = {"image": ("diagnostic_test.jpg", f, "image/jpeg")}
                data = {
                    "flight_id": "DIAGNOSTIC_TEST",
                    "waypoint": "TEST_WP"
                }
                
                logger.info(f"Uploading test image to: {config.IMAGE_UPLOAD_ENDPOINT}")
                logger.info(f"Data: {data}")
                
                response = requests.post(
                    config.IMAGE_UPLOAD_ENDPOINT,
                    files=files,
                    data=data,
                    timeout=10
                )
                
                logger.info(f"Response Status: {response.status_code}")
                logger.info(f"Response Headers: {dict(response.headers)}")
                logger.info(f"Response Body: {response.text}")
                
                # Try to parse as JSON
                try:
                    json_response = response.json()
                    logger.info(f"Parsed JSON: {json.dumps(json_response, indent=2)}")
                    
                    # Look for URL fields
                    url_fields = ['url', 'image_url', 'path', 'file_url', 'link', 'src', 'filepath', 'location']
                    found_urls = {}
                    
                    for field in url_fields:
                        if field in json_response:
                            found_urls[field] = json_response[field]
                    
                    if found_urls:
                        logger.info(f"✓ Found URL fields: {found_urls}")
                    else:
                        logger.warning("⚠ No URL fields found in response")
                        logger.warning(f"  Available fields: {list(json_response.keys())}")
                        
                except json.JSONDecodeError:
                    logger.info("Response is not JSON format")
                    if response.text.startswith('http'):
                        logger.info(f"✓ Response appears to be a direct URL: {response.text}")
            
            # Cleanup
            test_path.unlink(missing_ok=True)
            
        except Exception as e:
            logger.error(f"Diagnostic failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    @staticmethod
    def test_flight_log_requirement():
        """Test if server requires flight log before image upload"""
        logger.info("=" * 60)
        logger.info("SERVER DIAGNOSTICS: Testing Flight Log Requirement")
        logger.info("=" * 60)
        
        try:
            # Create a minimal flight log
            test_flight_id = "DIAGNOSTIC_FLIGHT_001"
            
            flight_log = {
                'id': test_flight_id,
                'type': 'flight',
                'date': datetime.now().strftime("%B %d, %Y"),
                'start_time': "10:00:00",
                'end_time': "10:15:00",
                'summary': {
                    'total_waypoints': 2,
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
                        'waypoint_id': 'DIAGNOSTIC_WP',
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
            response = requests.post(
                config.FLIGHT_LOG_ENDPOINT,
                json=flight_log,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            logger.info(f"Flight log upload status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                logger.info("✓ Flight log accepted by server")
                
                # Now try uploading an image
                logger.info("Now testing image upload with existing flight log...")
                
                test_img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
                test_path = Path("/tmp/diagnostic_test2.jpg")
                cv2.imwrite(str(test_path), test_img)
                
                with open(test_path, "rb") as f:
                    files = {"image": ("diagnostic_test2.jpg", f, "image/jpeg")}
                    data = {
                        "flight_id": test_flight_id,
                        "waypoint": "DIAGNOSTIC_WP"
                    }
                    
                    img_response = requests.post(
                        config.IMAGE_UPLOAD_ENDPOINT,
                        files=files,
                        data=data,
                        timeout=10
                    )
                    
                    logger.info(f"Image upload status: {img_response.status_code}")
                    logger.info(f"Image upload response: {img_response.text}")
                
                test_path.unlink(missing_ok=True)
                
                if img_response.status_code in [200, 201]:
                    logger.info("✓ Image accepted after flight log exists")
                else:
                    logger.warning("⚠ Image still rejected even with flight log")
            else:
                logger.warning(f"⚠ Flight log rejected: {response.text}")
                
        except Exception as e:
            logger.error(f"Diagnostic failed: {e}")
            import traceback
            logger.error(traceback.format_exc())


# ============================================================================
# IMPROVED TEST DATA GENERATOR
# ============================================================================
class ImprovedTestDataGenerator:
    """Generate test data that follows server requirements"""
    
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
        
        if self.test_dir.exists():
            logger.info(f"Removing old test data: {self.test_dir}")
            shutil.rmtree(self.test_dir)
        
        self.test_images_dir.mkdir(parents=True)
        self.test_json_dir.mkdir(parents=True)
        
        logger.info(f"✓ Created test directories:")
        logger.info(f"  - Images: {self.test_images_dir}")
        logger.info(f"  - JSON: {self.test_json_dir}")
    
    def create_test_image(self, waypoint, burst_index=0, is_best=False):
        """Create a test image"""
        img = np.random.randint(50, 200, (640, 640, 3), dtype=np.uint8)
        
        cv2.rectangle(img, (100, 100), (540, 540), (0, 255, 0), 2)
        
        text = f"WP{waypoint} - Frame {burst_index}"
        if is_best:
            text += " [BEST]"
        
        cv2.putText(img, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.7, (255, 255, 255), 2)
        cv2.putText(img, self.flight_id, (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, (200, 200, 200), 1)
        
        timestamp = int(time.time() * 1000)
        best_suffix = "_BEST" if is_best else ""
        filename = f"pinyasuri_{self.flight_id}_wp{waypoint}_{timestamp}_f{burst_index}{best_suffix}.jpg"
        filepath = self.test_images_dir / filename
        
        cv2.imwrite(str(filepath), img)
        self.created_files.append(filepath)
        
        return filepath
    
    def create_complete_test_flight(self, num_waypoints=2):
        """Create complete test flight - FLIGHT LOG FIRST, then images"""
        logger.info("=" * 60)
        logger.info(f"GENERATING COMPLETE TEST FLIGHT")
        logger.info(f"Flight ID: {self.flight_id}")
        logger.info(f"Strategy: Flight log FIRST, then images")
        logger.info("=" * 60)
        
        # Step 1: Create flight log FIRST (to satisfy server requirements)
        waypoint_list = []
        
        for wp in range(2, 2 + num_waypoints):
            waypoint_entry = {
                'waypoint_id': f'WAYPOINT_{wp}',
                'image': '',  # Will be updated after image upload
                'images': [],  # Will be updated after image upload
                'num_pineapples': 2,
                'healthy': 1,
                'afflicted': 1,
                'afflictions': {'Crown Rot Disease': 1}
            }
            waypoint_list.append(waypoint_entry)
        
        flight_log = {
            'id': self.flight_id,
            'type': 'flight',
            'date': datetime.now().strftime("%B %d, %Y"),
            'start_time': "10:00:00",
            'end_time': "10:15:00",
            'summary': {
                'total_waypoints': num_waypoints + 2,
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
        logger.info(f"✓ Created flight log: {log_filename}")
        
        # Step 2: Now create images
        flight_images = []
        
        for wp in range(2, 2 + num_waypoints):
            logger.info(f"Creating image for Waypoint {wp}...")
            img_path = self.create_test_image(wp, 0, is_best=True)
            flight_images.append(str(img_path))
        
        logger.info(f"✓ Created {len(flight_images)} test images")
        
        return log_path, flight_images
    
    def cleanup(self):
        """Remove test data"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            logger.info(f"✓ Cleaned up: {self.test_dir}")


# ============================================================================
# REALISTIC WORKFLOW TEST
# ============================================================================
class RealisticWorkflowTest:
    """Test that mimics actual flight workflow"""
    
    def __init__(self):
        self.generator = ImprovedTestDataGenerator()
    
    def run(self):
        """Run realistic upload test"""
        logger.info("=" * 60)
        logger.info("REALISTIC WORKFLOW TEST")
        logger.info("Simulating actual flight upload sequence")
        logger.info("=" * 60)
        
        try:
            # Setup
            self.generator.setup()
            
            # Create test data
            log_path, image_paths = self.generator.create_complete_test_flight(num_waypoints=2)
            
            # STEP 1: Upload flight log FIRST
            logger.info("")
            logger.info("STEP 1: Uploading flight log to server...")
            logger.info("-" * 60)
            
            with open(log_path, 'r') as f:
                flight_data = json.load(f)
            
            try:
                response = requests.post(
                    config.FLIGHT_LOG_ENDPOINT,
                    json=flight_data,
                    timeout=10,
                    headers={"Content-Type": "application/json"}
                )
                
                logger.info(f"Flight log upload status: {response.status_code}")
                
                if response.status_code in [200, 201]:
                    logger.info("✓ Flight log accepted by server")
                    logger.info(f"  Response: {response.text[:200]}")
                else:
                    logger.error(f"✗ Flight log rejected: {response.text}")
                    return False
                    
            except Exception as e:
                logger.error(f"✗ Flight log upload failed: {e}")
                return False
            
            # STEP 2: Now upload images
            logger.info("")
            logger.info("STEP 2: Uploading images to server...")
            logger.info("-" * 60)
            
            uploaded_count = 0
            failed_count = 0
            image_urls = []
            
            for img_path in image_paths:
                try:
                    # Extract waypoint from filename
                    import re
                    wp_match = re.search(r'_wp(\d+)_', Path(img_path).name)
                    if wp_match:
                        waypoint_num = int(wp_match.group(1))
                        waypoint_id = f"WAYPOINT_{waypoint_num}"
                    else:
                        waypoint_id = "UNKNOWN"
                    
                    with open(img_path, "rb") as f:
                        files = {"image": (Path(img_path).name, f, "image/jpeg")}
                        data = {
                            "flight_id": self.generator.flight_id,
                            "waypoint": waypoint_id
                        }
                        
                        logger.info(f"Uploading: {Path(img_path).name}")
                        logger.info(f"  Data: flight_id={data['flight_id']}, waypoint={data['waypoint']}")
                        
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
                                      json_resp.get('path'))
                                if url:
                                    logger.info(f"  📎 Image URL: {url}")
                                    image_urls.append(url)
                            except:
                                pass
                            
                            uploaded_count += 1
                        else:
                            logger.warning(f"  ✗ Upload failed: {response.text[:200]}")
                            failed_count += 1
                            
                except Exception as e:
                    logger.error(f"  ✗ Error uploading {Path(img_path).name}: {e}")
                    failed_count += 1
            
            # Summary
            logger.info("")
            logger.info("=" * 60)
            logger.info("WORKFLOW TEST RESULTS")
            logger.info("=" * 60)
            logger.info(f"Flight Log: ✓ Uploaded")
            logger.info(f"Images: {uploaded_count} uploaded, {failed_count} failed")
            logger.info(f"Image URLs captured: {len(image_urls)}")
            
            if image_urls:
                logger.info("Sample URLs:")
                for url in image_urls[:3]:
                    logger.info(f"  - {url}")
            
            success = uploaded_count > 0 and failed_count == 0
            
            if success:
                logger.info("")
                logger.info("✓ WORKFLOW TEST PASSED!")
            else:
                logger.info("")
                logger.info("⚠ WORKFLOW TEST COMPLETED WITH ISSUES")
            
            return success
            
        except Exception as e:
            logger.error(f"Workflow test failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        finally:
            # Cleanup
            time.sleep(1)
            self.generator.cleanup()


# ============================================================================
# MAIN
# ============================================================================
def main():
    """Main test entry point"""
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 58 + "║")
    logger.info("║" + "  PINYASURI UPLOADER DIAGNOSTIC SUITE".center(58) + "║")
    logger.info("║" + " " * 58 + "║")
    logger.info("╚" + "=" * 58 + "╝")
    logger.info("")
    
    try:
        # Test 1: Server diagnostics
        ServerDiagnostics.test_image_upload_response()
        time.sleep(1)
        
        ServerDiagnostics.test_flight_log_requirement()
        time.sleep(1)
        
        # Test 2: Realistic workflow
        workflow_test = RealisticWorkflowTest()
        success = workflow_test.run()
        
        # Final summary
        logger.info("")
        logger.info("╔" + "=" * 58 + "╗")
        if success:
            logger.info("║" + "  ✓ DIAGNOSTICS COMPLETE - All systems working!".center(58) + "║")
        else:
            logger.info("║" + "  ⚠ DIAGNOSTICS COMPLETE - Review issues above".center(58) + "║")
        logger.info("╚" + "=" * 58 + "╝")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.info("")
        logger.warning("⚠ Diagnostics interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"⚠ Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())