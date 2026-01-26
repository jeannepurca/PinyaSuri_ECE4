#!/usr/bin/env python3
# test_uploader.py - Comprehensive test for uploader.py workflow

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
JSON_DIR = config.JSON_DIR
IMAGE_DIR = config.IMAGE_DIR

# Ensure directories exist
config.ensure_directories()

logger.info("=" * 60)
logger.info("📡 SERVER ENDPOINTS")
logger.info("=" * 60)
logger.info(f"📄 Flight Log (JSON): {FLIGHT_LOG_ENDPOINT}")
logger.info(f"🖼️  Image Upload: {IMAGE_UPLOAD_ENDPOINT}")
logger.info("=" * 60)
logger.info(f"📂 JSON Directory: {JSON_DIR}")
logger.info(f"📂 Image Directory: {IMAGE_DIR}")
logger.info("=" * 60)

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
                logger.info(f"   Response: {response.json()}")
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
        return False


def test_upload_image_direct(image_path):
    """Test image upload directly to server (bypassing uploader queue)"""
    try:
        image_file = Path(image_path)
        
        if not image_file.exists():
            logger.error(f"❌ File not found: {image_path}")
            return False, None
        
        file_size_mb = image_file.stat().st_size / (1024 * 1024)
        logger.info(f"📤 Testing direct image upload: {image_file.name} ({file_size_mb:.2f} MB)")
        logger.info(f"   → Endpoint: {IMAGE_UPLOAD_ENDPOINT}")
        
        with open(image_file, "rb") as f:
            files = {"file": (image_file.name, f, "image/jpeg")}
            response = requests.post(
                IMAGE_UPLOAD_ENDPOINT,
                files=files,
                timeout=60
            )
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ SUCCESS: {image_file.name}")
            logger.info(f"   Status: {response.status_code}")
            
            try:
                response_data = response.json()
                logger.info(f"   Response: {response_data}")
                
                # Look for URL in response
                url_fields = ["url", "image_url", "file_url", "path", "image_path", "location", "link", "src"]
                image_url = None
                for field in url_fields:
                    if field in response_data:
                        image_url = response_data[field]
                        logger.info(f"   🎯 Image URL found ({field}): {image_url}")
                        break
                
                if not image_url:
                    logger.warning(f"   ⚠️  No URL found in response. Available fields: {list(response_data.keys())}")
                
                return True, image_url
            except json.JSONDecodeError:
                response_text = response.text.strip()
                logger.info(f"   Response (text): {response_text[:200]}")
                # Check if response is a URL
                if response_text.startswith('http'):
                    logger.info(f"   🎯 URL in text response: {response_text}")
                    return True, response_text
                return True, None
        else:
            logger.error(f"❌ FAILED: {image_file.name}")
            logger.error(f"   Status: {response.status_code}")
            logger.error(f"   Response: {response.text[:500]}")
            return False, None
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False, None


# ============================================================================
# UPLOADER.PY TEST FUNCTIONS
# ============================================================================

def test_uploader_workflow():
    """Test the complete uploader.py workflow:
    1. Start upload queue
    2. Simulate flight with images
    3. Upload images (capture URLs)
    4. Generate JSON with URLs
    5. Upload JSON
    """
    logger.info("=" * 60)
    logger.info("🧪 TESTING COMPLETE UPLOADER WORKFLOW")
    logger.info("=" * 60)
    
    # Find test images
    image_files = list(IMAGE_DIR.glob("**/*.jpg"))[:3]  # Use max 3 images for testing
    
    if not image_files:
        logger.error("❌ No images found for testing!")
        logger.info(f"   Please add some .jpg files to: {IMAGE_DIR}")
        return
    
    logger.info(f"\n📸 Found {len(image_files)} test images:")
    for i, img in enumerate(image_files, 1):
        logger.info(f"   {i}. {img.name}")
    
    # Create test flight ID
    test_flight_id = f"TEST_FLIGHT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
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
        
        for i, image_path in enumerate(image_files, 1):
            waypoint = i
            
            # Simulate some detections for this image
            detections = [
                {
                    'class_name': 'healthy' if i % 2 == 0 else 'black_rot',
                    'confidence': 0.85 + (i * 0.03),
                    'bbox': [100, 100, 200, 200]
                }
            ]
            
            logger.info(f"\n   Waypoint {waypoint}:")
            logger.info(f"   └─ Image: {image_path.name}")
            logger.info(f"   └─ Detections: {len(detections)}")
            
            # Add detection data to flight aggregator
            uploader.add_detection_to_flight(
                test_flight_id,
                waypoint,
                image_path,
                detections
            )
            
            # Queue image for upload
            uploader.queue_image_upload(image_path)
            logger.info(f"   └─ Queued for upload")
        
        logger.info("\n✓ All waypoints captured and queued")
        
        # STEP 4: Finalize flight (this will upload images, capture URLs, generate JSON)
        logger.info("\n📋 STEP 4: Finalizing flight summary...")
        logger.info("   This will:")
        logger.info("   1. Enable uploading")
        logger.info("   2. Upload all images")
        logger.info("   3. Capture server URLs")
        logger.info("   4. Generate JSON with URLs")
        logger.info("   5. Upload JSON")
        logger.info("")
        
        summary_path = uploader.finalize_flight_summary(test_flight_id, len(image_files))
        
        if summary_path:
            logger.info(f"\n✓ Flight summary created: {summary_path}")
            
            # Verify JSON content
            logger.info("\n📋 STEP 5: Verifying JSON content...")
            with open(summary_path, 'r') as f:
                summary_data = json.load(f)
            
            logger.info(f"   Flight ID: {summary_data.get('id')}")
            logger.info(f"   Waypoints: {len(summary_data.get('waypoints', []))}")
            
            # Check for image URLs
            total_urls = 0
            for wp_data in summary_data.get('waypoints', []):
                urls = wp_data.get('images', [])
                total_urls += len(urls)
                
                logger.info(f"\n   Waypoint {wp_data.get('waypoint_id')}:")
                logger.info(f"   └─ Pineapples: {wp_data.get('num_pineapples', 0)}")
                logger.info(f"   └─ Image URLs: {len(urls)}")
                if urls:
                    for url in urls:
                        logger.info(f"      • {url}")
            
            if total_urls > 0:
                logger.info("\n" + "=" * 60)
                logger.info("✅ TEST PASSED!")
                logger.info(f"   {total_urls} image URLs successfully captured in JSON")
                logger.info("=" * 60)
            else:
                logger.warning("\n" + "=" * 60)
                logger.warning("⚠️  TEST INCOMPLETE!")
                logger.warning("   JSON was created but no image URLs were captured")
                logger.warning("   Check your server's image upload response format")
                logger.warning("=" * 60)
        else:
            logger.error("\n❌ TEST FAILED: Could not create flight summary")
        
        # STEP 6: Wait for all uploads to complete
        logger.info("\n📋 STEP 6: Waiting for uploads to complete...")
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
    
    # Find one test image
    image_files = list(IMAGE_DIR.glob("**/*.jpg"))
    
    if not image_files:
        logger.error("❌ No images found!")
        logger.info(f"   Please add a .jpg file to: {IMAGE_DIR}")
        return
    
    test_image = image_files[0]
    
    logger.info(f"\n📸 Test image: {test_image.name}")
    logger.info(f"   Size: {test_image.stat().st_size / (1024*1024):.2f} MB")
    
    # Upload directly and check response
    logger.info("\n📤 Uploading to test URL capture...")
    success, image_url = test_upload_image_direct(test_image)
    
    if success and image_url:
        logger.info("\n" + "=" * 60)
        logger.info("✅ URL CAPTURE TEST PASSED!")
        logger.info(f"   Server returned URL: {image_url}")
        logger.info("=" * 60)
        logger.info("\n💡 Your server is properly configured for URL capture!")
        logger.info("   The uploader.py system should work correctly.")
    elif success and not image_url:
        logger.warning("\n" + "=" * 60)
        logger.warning("⚠️  URL CAPTURE TEST INCOMPLETE")
        logger.warning("   Image uploaded successfully, but no URL was returned")
        logger.warning("=" * 60)
        logger.warning("\n💡 Action needed:")
        logger.warning("   1. Check your server's image upload response format")
        logger.warning("   2. Ensure it returns one of these fields:")
        logger.warning("      - url, image_url, file_url, path, image_path, location")
        logger.warning("   3. Or contact your webdev team")
    else:
        logger.error("\n" + "=" * 60)
        logger.error("❌ URL CAPTURE TEST FAILED")
        logger.error("   Image upload failed")
        logger.error("=" * 60)


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
            logger.info(f"   {i}. {f.name}")
    else:
        logger.info("   No JSON files found")
    
    image_files = find_image_files()
    logger.info(f"\n🖼️  Images ({len(image_files)}):")
    if image_files:
        for i, f in enumerate(image_files[:10], 1):
            logger.info(f"   {i}. {f.name}")
        if len(image_files) > 10:
            logger.info(f"   ... and {len(image_files) - 10} more")
    else:
        logger.info("   No images found")
    
    logger.info("=" * 60)


def test_server_connection():
    """Test if endpoints are reachable"""
    logger.info("=" * 60)
    logger.info("🔍 TESTING SERVER CONNECTION")
    logger.info("=" * 60)
    
    endpoints = {
        "Flight Log (JSON)": FLIGHT_LOG_ENDPOINT,
        "Image Upload": IMAGE_UPLOAD_ENDPOINT
    }
    
    all_ok = True
    
    for name, endpoint in endpoints.items():
        try:
            logger.info(f"\n📡 Testing: {name}")
            logger.info(f"   URL: {endpoint}")
            
            # Try to get the base URL
            base_url = endpoint.rsplit('/api', 1)[0] if '/api' in endpoint else endpoint.rsplit('/', 1)[0]
            response = requests.get(base_url, timeout=10)
            
            logger.info(f"   ✅ Reachable (Status: {response.status_code})")
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
        logger.info("✅ All endpoints reachable!")
    else:
        logger.warning("⚠️  Some endpoints unreachable - check configuration")
    logger.info("=" * 60)
    
    return all_ok


def show_config_info():
    """Show configuration information"""
    logger.info("=" * 60)
    logger.info("⚙️  CONFIGURATION INFORMATION")
    logger.info("=" * 60)
    
    logger.info("\n🌐 API Endpoints:")
    logger.info(f"   JSON:   {FLIGHT_LOG_ENDPOINT}")
    logger.info(f"   Images: {IMAGE_UPLOAD_ENDPOINT}")
    
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
    
    logger.info("=" * 60)


# ============================================================================
# MAIN MENU
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🧪 UPLOADER.PY TEST SCRIPT")
    print("=" * 60)
    print(f"\n📡 Configured Endpoints:")
    print(f"   JSON   → {FLIGHT_LOG_ENDPOINT}")
    print(f"   Images → {IMAGE_UPLOAD_ENDPOINT}")
    print(f"\n📂 Using directories from config.py")
    print(f"   JSON:   {JSON_DIR}")
    print(f"   Images: {IMAGE_DIR}")
    print("=" * 60)
    print("\n🎯 Recommended Test Order:")
    print("   1. Test server connection (option 6)")
    print("   2. Test image URL capture (option 2)")
    print("   3. Test complete workflow (option 1)")
    print("\n" + "=" * 60)
    print("Available options:")
    print("  1. 🚀 Test complete uploader workflow (RECOMMENDED)")
    print("  2. 🔍 Test image URL capture")
    print("  3. 📤 Test direct image upload")
    print("  4. 📄 Test direct JSON upload")
    print("  5. 📋 List available files")
    print("  6. 🌐 Test server connection")
    print("  7. ⚙️  Show configuration")
    print("=" * 60)
    
    try:
        choice = input("\nEnter choice (1-7) [default=1]: ").strip() or "1"
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
            
        elif choice == "4":
            json_files = find_json_files()
            if json_files:
                logger.info(f"Found {len(json_files)} JSON files")
                test_upload_json_direct(json_files[0])
            else:
                logger.error("No JSON files found!")
            
        elif choice == "5":
            list_available_files()
            
        elif choice == "6":
            test_server_connection()
            
        elif choice == "7":
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