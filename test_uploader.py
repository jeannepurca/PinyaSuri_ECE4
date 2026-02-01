#!/usr/bin/env python3
# test_uploader.py

import json
import requests
from pathlib import Path
import logging
import time
import sys
from datetime import datetime

try:
    import config
    import uploader
    logger = logging.getLogger(__name__)
except ImportError as e:
    print(f"❌ ERROR: Required module not found: {e}")
    print("   Make sure config.py and uploader.py are in the same directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# ============================================================================
# CONFIGURATION
# ============================================================================
FLIGHT_LOG_ENDPOINT = config.FLIGHT_LOG_ENDPOINT
IMAGE_UPLOAD_ENDPOINT = config.IMAGE_UPLOAD_ENDPOINT
SERVER_BASE = config.SERVER_BASE
JSON_DIR = config.JSON_DIR
IMAGE_DIR = config.IMAGE_DIR

# Ensure directories exist
config.ensure_directories()

logger.info("=" * 60)
logger.info("📡 SERVER CONFIGURATION")
logger.info("=" * 60)
logger.info(f"🌐 Server Base: {SERVER_BASE}")
logger.info(f"📄 Flight Log (JSON): {FLIGHT_LOG_ENDPOINT}")
logger.info(f"🖼️  Image Upload: {IMAGE_UPLOAD_ENDPOINT}")
logger.info("=" * 60)
logger.info(f"📂 JSON Directory: {JSON_DIR}")
logger.info(f"📂 Image Directory: {IMAGE_DIR}")
logger.info("=" * 60)

# Detect if using local or cloud server
is_local_server = "192.168" in SERVER_BASE or "localhost" in SERVER_BASE or "127.0.0.1" in SERVER_BASE
if is_local_server:
    logger.info("🏠 Using LOCAL SERVER - ensure server is running and reachable")
else:
    logger.info("☁️  Using CLOUD SERVER")
logger.info("=" * 60)


# ============================================================================
# SERVER CONNECTION TEST
# ============================================================================
def test_server_connection():
    """Test if endpoints are reachable"""
    logger.info("=" * 60)
    logger.info("🔍 TESTING SERVER CONNECTION")
    logger.info("=" * 60)
    
    # Test base server first
    logger.info(f"\n🌐 Testing Base Server: {SERVER_BASE}")
    try:
        response = requests.get(SERVER_BASE, timeout=5)
        logger.info(f"   ✅ Server reachable (Status: {response.status_code})")
        base_ok = True
    except requests.exceptions.ConnectionError:
        logger.error(f"   ❌ Cannot connect to server")
        if is_local_server:
            logger.error("   💡 Local server troubleshooting:")
            logger.error("      1. Is the server running?")
            logger.error("      2. Check IP address in config.py")
            logger.error("      3. Are both devices on same network?")
            logger.error("      4. Try: ping " + SERVER_BASE.split("://")[1].split(":")[0])
        base_ok = False
    except requests.exceptions.Timeout:
        logger.error(f"   ❌ Connection timeout")
        base_ok = False
    except Exception as e:
        logger.warning(f"   ⚠️  Test inconclusive: {e}")
        base_ok = False
    
    # Test specific endpoints
    endpoints = {
        "Flight Log (JSON)": FLIGHT_LOG_ENDPOINT,
        "Image Upload": IMAGE_UPLOAD_ENDPOINT
    }
    
    all_ok = base_ok
    
    for name, endpoint in endpoints.items():
        try:
            logger.info(f"\n📡 Testing: {name}")
            logger.info(f"   URL: {endpoint}")
            
            # Try a simple HEAD or GET request
            response = requests.head(endpoint, timeout=10)
            
            # Some servers don't support HEAD, so try GET if HEAD fails
            if response.status_code == 405:
                response = requests.get(endpoint, timeout=10)
            
            # For POST endpoints, 405 (Method Not Allowed) is actually OK
            if response.status_code in [200, 201, 404, 405]:
                logger.info(f"   ✅ Endpoint reachable (Status: {response.status_code})")
            else:
                logger.warning(f"   ⚠️  Unexpected status: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            logger.error(f"   ❌ Cannot connect - check network/server")
            all_ok = False
        except requests.exceptions.Timeout:
            logger.error(f"   ❌ Connection timeout")
            all_ok = False
        except Exception as e:
            logger.warning(f"   ⚠️  Test inconclusive: {e}")
    
    logger.info("\n" + "=" * 60)
    if all_ok:
        logger.info("✅ ALL TESTS PASSED - Server is reachable!")
        logger.info("   You can proceed with testing uploads.")
    else:
        logger.warning("⚠️  CONNECTION ISSUES DETECTED")
        logger.warning("   Fix connection issues before testing uploads.")
        if is_local_server:
            logger.warning("\n   Local Server Checklist:")
            logger.warning("   □ Server is running")
            logger.warning("   □ IP address is correct in config.py")
            logger.warning("   □ Both devices on same WiFi/network")
            logger.warning("   □ Firewall allows connections")
    logger.info("=" * 60)
    
    return all_ok


# ============================================================================
# DIRECT UPLOAD FUNCTIONS (for testing server endpoints)
# ============================================================================
def test_upload_json_direct(json_path):
    """Test JSON upload directly to server (bypassing uploader queue)"""
    try:
        json_file = Path(json_path)
        
        if not json_file.exists():
            logger.error(f"❌ File not found: {json_path}")
            return False
        
        with open(json_file, "r") as f:
            json_data = json.load(f)
        
        logger.info(f"📤 Testing direct JSON upload: {json_file.name}")
        logger.info(f"   → Endpoint: {FLIGHT_LOG_ENDPOINT}")
        logger.info(f"   → Data size: {len(json.dumps(json_data))} bytes")
        
        response = requests.post(
            FLIGHT_LOG_ENDPOINT,
            json=json_data,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ SUCCESS: {json_file.name}")
            logger.info(f"   Status: {response.status_code}")
            try:
                response_json = response.json()
                logger.info(f"   Response: {response_json}")
            except:
                logger.info(f"   Response: {response.text[:200]}")
            return True
        else:
            logger.error(f"❌ FAILED: {json_file.name}")
            logger.error(f"   Status: {response.status_code}")
            logger.error(f"   Response: {response.text[:500]}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_upload_image_direct(image_path):
    try:
        image_file = Path(image_path)
        
        if not image_file.exists():
            logger.error(f"❌ File not found: {image_path}")
            return False, None
        
        file_size_mb = image_file.stat().st_size / (1024 * 1024)
        logger.info(f"📤 Testing direct image upload: {image_file.name} ({file_size_mb:.2f} MB)")
        logger.info(f"   → Endpoint: {IMAGE_UPLOAD_ENDPOINT}")
        
        # Extract waypoint from filename if possible
        import re
        waypoint_match = re.search(r'_wp(\d+)_', image_file.name)
        if waypoint_match:
            waypoint_num = int(waypoint_match.group(1))
            waypoint = config.get_waypoint_name(waypoint_num) if hasattr(config, 'get_waypoint_name') else f"WP{waypoint_num}"
        else:
            waypoint = "WP1"  # Default for testing
        
        # Test flight ID
        test_flight_id = f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"   → Flight ID: {test_flight_id}")
        logger.info(f"   → Waypoint: {waypoint}")
        
        # Match server's expected field name
        with open(image_file, "rb") as f:
            files = {"image": (image_file.name, f, "image/jpeg")}
            
            # Include required data fields
            data = {
                "flight_id": test_flight_id,
                "waypoint": waypoint
            }
            
            response = requests.post(
                IMAGE_UPLOAD_ENDPOINT,
                files=files,
                data=data,
                timeout=60
            )
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ SUCCESS: {image_file.name}")
            logger.info(f"   Status: {response.status_code}")
            
            try:
                response_data = response.json()
                logger.info(f"   Response (JSON): {response_data}")
                
                # Look for URL in response - try multiple common field names
                url_fields = [
                    "url", "image_url", "file_url", "path", "image_path", 
                    "filepath", "location", "link", "src", "imageUrl"
                ]
                
                image_url = None
                found_field = None
                
                for field in url_fields:
                    if field in response_data:
                        image_url = response_data[field]
                        found_field = field
                        break
                
                if image_url:
                    logger.info(f"   🎯 Image URL found in field '{found_field}': {image_url}")
                    return True, image_url
                else:
                    logger.warning(f"   ⚠️  No URL found in response")
                    logger.warning(f"   Available fields: {list(response_data.keys())}")
                    logger.warning(f"   💡 You may need to update uploader.py to match your server's response format")
                    return True, None
                    
            except json.JSONDecodeError:
                # Response might be plain text (just the URL)
                response_text = response.text.strip()
                logger.info(f"   Response (text): {response_text[:200]}")
                
                if response_text.startswith('http'):
                    logger.info(f"   🎯 URL found in text response: {response_text}")
                    return True, response_text
                else:
                    logger.warning(f"   ⚠️  Response is not JSON and doesn't look like a URL")
                    return True, None
        else:
            logger.error(f"❌ FAILED: {image_file.name}")
            logger.error(f"   Status: {response.status_code}")
            logger.error(f"   Response: {response.text[:500]}")
            return False, None
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False, None


# ============================================================================
# WAYPOINT-IMAGE RELATIONSHIP VALIDATOR
# ============================================================================
def validate_waypoint_image_relationships(json_path):
    """Validate that waypoints in JSON are properly linked to image URLs"""
    logger.info("=" * 60)
    logger.info("🔍 VALIDATING WAYPOINT-IMAGE RELATIONSHIPS")
    logger.info("=" * 60)
    
    try:
        json_file = Path(json_path)
        
        if not json_file.exists():
            logger.error(f"❌ File not found: {json_path}")
            return False
        
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        logger.info(f"\n📄 Analyzing: {json_file.name}")
        logger.info(f"   Flight ID: {data.get('id', 'N/A')}")
        
        waypoints = data.get('waypoints', [])
        logger.info(f"   Waypoints: {len(waypoints)}")
        
        if not waypoints:
            logger.warning("   ⚠️  No waypoints found in JSON")
            return False
        
        # Analyze each waypoint
        all_valid = True
        total_images = 0
        waypoints_with_images = 0
        waypoints_without_images = 0
        
        logger.info("\n📊 Waypoint Analysis:")
        logger.info("-" * 60)
        
        for i, wp in enumerate(waypoints, 1):
            wp_id = wp.get('waypoint_id', f'WP{i}')
            
            # Get image data
            primary_image = wp.get('image', '')
            all_images = wp.get('images', [])
            
            # Get detection data
            num_pineapples = wp.get('num_pineapples', 0)
            healthy = wp.get('healthy', 0)
            afflicted = wp.get('afflicted', 0)
            
            logger.info(f"\n{wp_id}:")
            logger.info(f"  Detections: {num_pineapples} pineapples ({healthy} healthy, {afflicted} afflicted)")
            
            # Check for images
            if all_images and len(all_images) > 0:
                waypoints_with_images += 1
                total_images += len(all_images)
                logger.info(f"  ✅ Images: {len(all_images)} URL(s)")
                
                for idx, url in enumerate(all_images, 1):
                    # Validate URL format
                    is_valid_url = url.startswith('http://') or url.startswith('https://')
                    status = "✅" if is_valid_url else "⚠️"
                    logger.info(f"     {status} Image {idx}: {url}")
                    
                    if not is_valid_url:
                        all_valid = False
                        logger.warning(f"        ⚠️  Not a valid URL!")
            else:
                waypoints_without_images += 1
                logger.warning(f"  ❌ No images linked")
                all_valid = False
            
            # Check consistency
            if primary_image and primary_image not in all_images:
                logger.warning(f"  ⚠️  Primary image not in images array!")
                all_valid = False
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 VALIDATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total waypoints: {len(waypoints)}")
        logger.info(f"Waypoints with images: {waypoints_with_images}")
        logger.info(f"Waypoints without images: {waypoints_without_images}")
        logger.info(f"Total image URLs: {total_images}")
        logger.info(f"Average images per waypoint: {total_images / len(waypoints):.1f}")
        
        # Image metadata check
        img_metadata = data.get('image_metadata', {})
        if img_metadata:
            logger.info(f"\nImage Metadata:")
            logger.info(f"  Total images: {img_metadata.get('total_images', 0)}")
            logger.info(f"  Images per waypoint: {img_metadata.get('images_per_waypoint', {})}")
        
        logger.info("\n" + "=" * 60)
        if all_valid and waypoints_without_images == 0:
            logger.info("✅ VALIDATION PASSED")
            logger.info("   All waypoints have properly linked image URLs!")
        elif waypoints_with_images > 0:
            logger.warning("⚠️  VALIDATION INCOMPLETE")
            logger.warning(f"   {waypoints_without_images} waypoint(s) missing images")
        else:
            logger.error("❌ VALIDATION FAILED")
            logger.error("   No waypoints have linked images!")
        logger.info("=" * 60)
        
        return all_valid and waypoints_without_images == 0
        
    except Exception as e:
        logger.error(f"❌ Validation error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# ============================================================================
# UPLOADER.PY WORKFLOW TEST
# ============================================================================
def test_uploader_workflow():
    """Test the complete uploader.py workflow:
    1. Start upload queue
    2. Simulate flight with images
    3. Upload images (capture URLs)
    4. Generate JSON with URLs
    5. Upload JSON
    6. Validate waypoint-image relationships
    """
    logger.info("=" * 60)
    logger.info("🧪 TESTING COMPLETE UPLOADER WORKFLOW")
    logger.info("=" * 60)
    
    # Find test images
    image_files = list(IMAGE_DIR.glob("**/*.jpg"))[:3]  # Use max 3 images for testing
    
    if not image_files:
        logger.error("❌ No images found for testing!")
        logger.info(f"   Please add some .jpg files to: {IMAGE_DIR}")
        logger.info("\n💡 You can:")
        logger.info("   1. Copy some test images to the images directory")
        logger.info("   2. Or run a real flight to capture images")
        return
    
    logger.info(f"\n📸 Found {len(image_files)} test images:")
    for i, img in enumerate(image_files, 1):
        size_mb = img.stat().st_size / (1024 * 1024)
        logger.info(f"   {i}. {img.name} ({size_mb:.2f} MB)")
    
    # Create test flight ID
    test_flight_id = f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    logger.info(f"\n🛫 Simulating flight: {test_flight_id}")
    logger.info("=" * 60)
    
    try:
        # STEP 1: Start upload queue
        logger.info("\n📋 STEP 1: Starting upload queue...")
        uploader.start_upload_queue()
        logger.info("✓ Upload queue started")
        time.sleep(1)
        
        # STEP 2: Initialize flight in aggregator
        logger.info("\n📋 STEP 2: Initializing flight in aggregator...")
        uploader.start_new_flight(test_flight_id)
        logger.info(f"✓ Flight {test_flight_id} initialized")
        
        # STEP 3: Simulate image captures with detections
        logger.info("\n📋 STEP 3: Simulating waypoint captures...")
        logger.info("   (This simulates what happens during a real flight)")
        
        for i, image_path in enumerate(image_files, 1):
            waypoint = i
            
            # Simulate varied detections for testing
            detections = []
            
            if i == 1:
                # First waypoint: healthy pineapples
                detections = [
                    {
                        'class_name': 'Healthy',
                        'confidence': 0.92,
                        'bbox': [100, 100, 200, 200]
                    },
                    {
                        'class_name': 'Healthy',
                        'confidence': 0.88,
                        'bbox': [300, 150, 400, 250]
                    }
                ]
            elif i == 2:
                # Second waypoint: diseased pineapples
                detections = [
                    {
                        'class_name': 'Crown Rot Disease',
                        'confidence': 0.85,
                        'bbox': [120, 120, 220, 220]
                    }
                ]
            else:
                # Third waypoint: mix
                detections = [
                    {
                        'class_name': 'Healthy',
                        'confidence': 0.90,
                        'bbox': [100, 100, 200, 200]
                    },
                    {
                        'class_name': 'Fruit Rot Disease',
                        'confidence': 0.78,
                        'bbox': [250, 200, 350, 300]
                    }
                ]
            
            logger.info(f"\n   Waypoint {waypoint} ({config.get_waypoint_name(waypoint)}):")
            logger.info(f"   └─ Image: {image_path.name}")
            logger.info(f"   └─ Detections: {len(detections)}")
            for det in detections:
                logger.info(f"      • {det['class_name']} (confidence: {det['confidence']:.2f})")
            
            # Add detection data to flight aggregator
            uploader.add_detection_to_flight(
                test_flight_id,
                waypoint,
                image_path,
                detections
            )
            
            # Queue image for upload
            uploader.queue_image_upload(image_path)
            logger.info(f"   └─ ✓ Queued for upload")
        
        logger.info("\n✓ All waypoints captured and queued")
        
        # STEP 4: Finalize flight
        logger.info("\n📋 STEP 4: Finalizing flight summary...")
        logger.info("   This will:")
        logger.info("   1. Enable uploading")
        logger.info("   2. Upload all images to server")
        logger.info("   3. Capture image URLs from server responses")
        logger.info("   4. Generate JSON with waypoint-image links")
        logger.info("   5. Upload JSON to server")
        logger.info("")
        
        summary_path = uploader.finalize_flight_summary(test_flight_id, len(image_files))
        
        if summary_path:
            logger.info(f"\n✓ Flight summary created: {summary_path}")
            
            # STEP 5: Verify JSON content
            logger.info("\n📋 STEP 5: Verifying JSON content...")
            with open(summary_path, 'r') as f:
                summary_data = json.load(f)
            
            logger.info(f"   Flight ID: {summary_data.get('id')}")
            logger.info(f"   Flight Type: {summary_data.get('type')}")
            logger.info(f"   Date: {summary_data.get('date')}")
            logger.info(f"   Time: {summary_data.get('start_time')} - {summary_data.get('end_time')}")
            
            # Summary stats
            summary = summary_data.get('summary', {})
            logger.info(f"\n   📊 Summary:")
            logger.info(f"      Total waypoints: {summary.get('total_waypoints')}")
            logger.info(f"      Captured waypoints: {summary.get('captured_waypoints')}")
            logger.info(f"      Mission status: {summary.get('mission_status')}")
            logger.info(f"      Pineapples detected: {summary.get('pineapples_detected')}")
            logger.info(f"      Healthy: {summary.get('healthy_pineapples')}")
            logger.info(f"      Afflicted: {summary.get('afflicted_pineapples')}")
            
            # Check for image URLs in waypoints
            logger.info(f"\n   🖼️  Waypoint Image URLs:")
            total_urls = 0
            waypoints = summary_data.get('waypoints', [])
            
            for wp_data in waypoints:
                urls = wp_data.get('images', [])
                total_urls += len(urls)
                
                logger.info(f"\n      {wp_data.get('waypoint_id')}:")
                logger.info(f"      └─ Pineapples: {wp_data.get('num_pineapples', 0)} "
                          f"({wp_data.get('healthy', 0)} healthy, {wp_data.get('afflicted', 0)} afflicted)")
                logger.info(f"      └─ Image URLs: {len(urls)}")
                
                if urls:
                    for idx, url in enumerate(urls, 1):
                        logger.info(f"         {idx}. {url}")
                else:
                    logger.warning(f"         ⚠️  No image URLs!")
            
            # Final assessment
            logger.info("\n" + "=" * 60)
            if total_urls == len(image_files):
                logger.info("✅ TEST PASSED!")
                logger.info(f"   All {total_urls} images successfully linked to waypoints")
                logger.info("   Waypoint-image relationships are correct!")
            elif total_urls > 0:
                logger.warning("⚠️  TEST INCOMPLETE!")
                logger.warning(f"   Only {total_urls}/{len(image_files)} images captured")
                logger.warning("   Some images may not have uploaded successfully")
            else:
                logger.error("❌ TEST FAILED!")
                logger.error("   No image URLs were captured")
                logger.error("   Check your server's image upload response format")
            logger.info("=" * 60)
            
            # STEP 6: Detailed validation
            logger.info("\n📋 STEP 6: Running detailed validation...")
            validate_waypoint_image_relationships(summary_path)
            
        else:
            logger.error("\n❌ TEST FAILED: Could not create flight summary")
        
        # STEP 7: Wait for all uploads to complete
        logger.info("\n📋 STEP 7: Waiting for uploads to complete...")
        time.sleep(5)
        
        # Print final stats
        logger.info("\n" + "=" * 60)
        uploader.upload_queue.print_stats()
        
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Test cancelled by user")
    except Exception as e:
        logger.error(f"\n❌ Test error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Cleanup
        logger.info("\n📋 Cleaning up...")
        uploader.stop_upload_queue()
        logger.info("✓ Test complete")


def test_image_url_capture():
    """Test if image upload returns a URL that can be captured"""
    logger.info("=" * 60)
    logger.info("🧪 TESTING IMAGE URL CAPTURE")
    logger.info("=" * 60)
    logger.info("\nThis test checks if your server returns image URLs")
    logger.info("that the uploader can capture and link to waypoints.")
    
    # Find one test image
    image_files = list(IMAGE_DIR.glob("**/*.jpg"))
    
    if not image_files:
        logger.error("\n❌ No images found!")
        logger.info(f"   Please add a .jpg file to: {IMAGE_DIR}")
        return
    
    test_image = image_files[0]
    
    logger.info(f"\n📸 Test image: {test_image.name}")
    logger.info(f"   Size: {test_image.stat().st_size / (1024*1024):.2f} MB")
    logger.info(f"   Path: {test_image}")
    
    # Upload directly and check response
    logger.info("\n📤 Uploading to test URL capture...")
    success, image_url = test_upload_image_direct(test_image)
    
    if success and image_url:
        logger.info("\n" + "=" * 60)
        logger.info("✅ URL CAPTURE TEST PASSED!")
        logger.info(f"   Server returned URL: {image_url}")
        logger.info("=" * 60)
        logger.info("\n💡 Your server is properly configured!")
        logger.info("   The uploader.py system will work correctly.")
        logger.info("   Waypoint-image linking should function as expected.")
    elif success and not image_url:
        logger.warning("\n" + "=" * 60)
        logger.warning("⚠️  URL CAPTURE TEST INCOMPLETE")
        logger.warning("   Image uploaded successfully, but no URL was returned")
        logger.warning("=" * 60)
        logger.warning("\n💡 Action needed:")
        logger.warning("   Your server needs to return the image URL in the response.")
        logger.warning("\n   Expected response format (JSON):")
        logger.warning("   {")
        logger.warning('     "url": "http://192.168.1.16:5000/uploads/image123.jpg"')
        logger.warning("   }")
        logger.warning("\n   Or one of these field names:")
        logger.warning("   - url, image_url, file_url, path, filepath")
        logger.warning("\n   Without URLs, waypoint-image linking will fail!")
    else:
        logger.error("\n" + "=" * 60)
        logger.error("❌ URL CAPTURE TEST FAILED")
        logger.error("   Image upload failed")
        logger.error("=" * 60)
        logger.error("\n💡 Check:")
        logger.error("   1. Server is running")
        logger.error("   2. Endpoint URL is correct")
        logger.error("   3. Network connection")


# ============================================================================
# FILE SCANNING
# ============================================================================

def find_json_files():
    """Find all JSON files"""
    json_files = []
    
    if JSON_DIR.exists():
        found = list(JSON_DIR.glob("**/*.json"))
        json_files.extend(found)
    
    # Filter out upload_history.json
    unique_files = [f for f in json_files if f.name != "upload_history.json"]
    
    return unique_files


def find_image_files():
    """Find all image files"""
    image_files = []
    
    if IMAGE_DIR.exists():
        jpg_files = list(IMAGE_DIR.glob("**/*.jpg"))
        png_files = list(IMAGE_DIR.glob("**/*.png"))
        image_files = jpg_files + png_files
    
    return image_files


def list_available_files():
    """List all available files"""
    logger.info("=" * 60)
    logger.info("📋 AVAILABLE FILES")
    logger.info("=" * 60)
    
    json_files = find_json_files()
    logger.info(f"\n📄 JSON Files ({len(json_files)}):")
    if json_files:
        for i, f in enumerate(json_files, 1):
            size_kb = f.stat().st_size / 1024
            logger.info(f"   {i}. {f.name} ({size_kb:.1f} KB)")
    else:
        logger.info("   No JSON files found")
        logger.info(f"   Location: {JSON_DIR}")
    
    image_files = find_image_files()
    logger.info(f"\n🖼️  Images ({len(image_files)}):")
    if image_files:
        total_size_mb = sum(f.stat().st_size for f in image_files) / (1024 * 1024)
        logger.info(f"   Total size: {total_size_mb:.2f} MB")
        
        for i, f in enumerate(image_files[:10], 1):
            size_mb = f.stat().st_size / (1024 * 1024)
            logger.info(f"   {i}. {f.name} ({size_mb:.2f} MB)")
        
        if len(image_files) > 10:
            logger.info(f"   ... and {len(image_files) - 10} more")
    else:
        logger.info("   No images found")
        logger.info(f"   Location: {IMAGE_DIR}")
    
    logger.info("=" * 60)


def show_config_info():
    """Show configuration information"""
    logger.info("=" * 60)
    logger.info("⚙️  CONFIGURATION INFORMATION")
    logger.info("=" * 60)
    
    logger.info("\n🌐 Server Type:")
    if is_local_server:
        logger.info("   🏠 LOCAL SERVER")
        logger.info(f"      Base URL: {SERVER_BASE}")
        logger.info("\n   📝 Local Server Requirements:")
        logger.info("      □ Server must be running")
        logger.info("      □ Both devices on same network")
        logger.info("      □ Firewall allows connections")
    else:
        logger.info("   ☁️  CLOUD SERVER")
        logger.info(f"      Base URL: {SERVER_BASE}")
    
    logger.info("\n🌐 API Endpoints:")
    logger.info(f"   JSON Upload:   {FLIGHT_LOG_ENDPOINT}")
    logger.info(f"   Image Upload:  {IMAGE_UPLOAD_ENDPOINT}")
    
    logger.info("\n📂 Directories:")
    dirs = {
        "Base": config.BASE_DIR,
        "JSON": config.JSON_DIR,
        "Images": config.IMAGE_DIR,
        "Logs": config.LOG_DIR,
    }
    
    for name, path in dirs.items():
        exists = "✓" if path.exists() else "✗"
        logger.info(f"   {exists} {name}: {path}")
        if path.exists():
            files = list(path.glob("*"))
            logger.info(f"      └─ {len(files)} items")
    
    logger.info("\n🔧 AI Configuration:")
    logger.info(f"   Model: {config.MODEL_PATH.name if hasattr(config, 'MODEL_PATH') else 'N/A'}")
    logger.info(f"   Detection threshold: {config.DETECTION_THRESHOLD if hasattr(config, 'DETECTION_THRESHOLD') else 'N/A'}")
    logger.info(f"   Classes: {len(config.CLASS_NAMES) if hasattr(config, 'CLASS_NAMES') else 'N/A'}")
    
    logger.info("=" * 60)


# ============================================================================
# MAIN MENU
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🧪 PINYASURI UPLOADER TEST SCRIPT")
    print("=" * 60)
    
    # Show current configuration
    if is_local_server:
        print(f"\n🏠 LOCAL SERVER MODE")
        print(f"   Server: {SERVER_BASE}")
        print(f"   ⚠️  Ensure server is running and reachable!")
    else:
        print(f"\n☁️  CLOUD SERVER MODE")
        print(f"   Server: {SERVER_BASE}")
    
    print(f"\n📡 Configured Endpoints:")
    print(f"   JSON   → {FLIGHT_LOG_ENDPOINT}")
    print(f"   Images → {IMAGE_UPLOAD_ENDPOINT}")
    
    print(f"\n📂 Using directories from config.py:")
    print(f"   JSON:   {JSON_DIR}")
    print(f"   Images: {IMAGE_DIR}")
    
    print("\n" + "=" * 60)
    print("🎯 RECOMMENDED TEST ORDER:")
    print("   1. Test server connection (option 7)")
    print("   2. Test image URL capture (option 2)")
    print("   3. Test complete workflow (option 1)")
    print("   4. Validate existing JSON files (option 6)")
    print("\n" + "=" * 60)
    print("Available options:")
    print("  1. 🚀 Test complete uploader workflow (RECOMMENDED)")
    print("  2. 🔍 Test image URL capture")
    print("  3. 📤 Test direct image upload")
    print("  4. 📄 Test direct JSON upload")
    print("  5. 📋 List available files")
    print("  6. ✅ Validate waypoint-image relationships in JSON")
    print("  7. 🌐 Test server connection")
    print("  8. ⚙️  Show configuration")
    print("=" * 60)
    
    try:
        choice = input("\nEnter choice (1-8) [default=7]: ").strip() or "7"
        print()
        
        if choice == "1":
            test_uploader_workflow()
            
        elif choice == "2":
            test_image_url_capture()
            
        elif choice == "3":
            image_files = find_image_files()
            if image_files:
                logger.info(f"Found {len(image_files)} images")
                test_upload_image_direct(image_files[0])
            else:
                logger.error("No images found!")
                logger.info(f"Add .jpg files to: {IMAGE_DIR}")
            
        elif choice == "4":
            json_files = find_json_files()
            if json_files:
                logger.info(f"Found {len(json_files)} JSON files")
                test_upload_json_direct(json_files[0])
            else:
                logger.error("No JSON files found!")
                logger.info(f"Add .json files to: {JSON_DIR}")
            
        elif choice == "5":
            list_available_files()
            
        elif choice == "6":
            json_files = find_json_files()
            if json_files:
                logger.info(f"\nFound {len(json_files)} JSON file(s)")
                
                if len(json_files) == 1:
                    validate_waypoint_image_relationships(json_files[0])
                else:
                    print("\nWhich file to validate?")
                    for i, f in enumerate(json_files, 1):
                        print(f"  {i}. {f.name}")
                    
                    try:
                        file_choice = int(input("\nEnter number [1]: ").strip() or "1")
                        if 1 <= file_choice <= len(json_files):
                            validate_waypoint_image_relationships(json_files[file_choice - 1])
                        else:
                            logger.error("Invalid choice!")
                    except ValueError:
                        logger.error("Invalid input!")
            else:
                logger.error("No JSON files found!")
                logger.info(f"Add .json files to: {JSON_DIR}")
            
        elif choice == "7":
            test_server_connection()
            
        elif choice == "8":
            show_config_info()
            
        else:
            print("❌ Invalid choice!")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user")
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    
    print("\n" + "=" * 60)
    print("🏁 Test script completed")
    print("=" * 60 + "\n")