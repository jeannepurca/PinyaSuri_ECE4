#!/usr/bin/env python3
# test_uploader.py - Test script for uploading JSON files AND images

import json
import requests
from pathlib import Path
import logging
import time
import sys

try:
    import config
    logger = logging.getLogger(__name__)
except ImportError:
    print("❌ ERROR: config.py not found!")
    print("   Make sure config.py is in the same directory as this script")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ============================================================================
# CONFIGURATION
# ============================================================================

SERVER_URL = config.SERVER
JSON_DIR = config.JSON_DIR
IMAGE_DIR = config.IMAGE_DIR

# Ensure directories exist
config.ensure_directories()

logger.info(f"📂 JSON Directory: {JSON_DIR}")
logger.info(f"📂 Image Directory: {IMAGE_DIR}")
logger.info(f"🌐 Server URL: {SERVER_URL}")

# ============================================================================
# UPLOAD FUNCTIONS
# ============================================================================

def upload_json_file(json_path):
    """Upload a single JSON file to the server"""
    try:
        json_file = Path(json_path)
        
        if not json_file.exists():
            logger.error(f"❌ File not found: {json_path}")
            return False
        
        # Read JSON file
        with open(json_file, "r") as f:
            json_data = json.load(f)
        
        logger.info(f"📤 Uploading JSON: {json_file.name}")
        logger.debug(f"   Size: {json_file.stat().st_size} bytes")
        
        # Show preview of JSON structure
        preview = {
            "id": json_data.get("id", "N/A"),
            "type": json_data.get("type", "N/A"),
            "date": json_data.get("date", "N/A")
        }
        logger.debug(f"   Preview: {preview}")
        
        # Upload to server
        response = requests.post(
            SERVER_URL,
            json=json_data,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        # Success: 200 OK or 201 Created
        if response.status_code in [200, 201]:
            logger.info(f"✅ JSON SUCCESS: {json_file.name}")
            logger.info(f"   Status Code: {response.status_code}")
            try:
                response_data = response.json()
                logger.info(f"   Server response: {response_data}")
            except:
                logger.info(f"   Server response: {response.text[:200]}")
            return True
        else:
            logger.error(f"❌ JSON FAILED: {json_file.name}")
            logger.error(f"   Status Code: {response.status_code}")
            logger.error(f"   Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Connection Error: Cannot reach server")
        return False
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout: Server took too long to respond")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON file: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error uploading {json_file.name}: {e}")
        return False


def upload_image_file(image_path, test_mode=True):
    """Upload a single image file to the server"""
    try:
        image_file = Path(image_path)
        
        if not image_file.exists():
            logger.error(f"❌ File not found: {image_path}")
            return False, None
        
        file_size_mb = image_file.stat().st_size / (1024 * 1024)
        logger.info(f"📤 Uploading Image: {image_file.name} ({file_size_mb:.2f} MB)")
        
        if test_mode:
            # Try different methods to find what works
            logger.info("   🧪 Testing different upload methods...")
            
            # Method 1: multipart/form-data with field name "file"
            logger.info("   Testing: multipart with field 'file'")
            success, result = _try_upload_image(image_file, "file")
            if success:
                return True, result
            
            # Method 2: multipart/form-data with field name "image"
            logger.info("   Testing: multipart with field 'image'")
            success, result = _try_upload_image(image_file, "image")
            if success:
                return True, result
            
            # Method 3: Try as base64 in JSON
            logger.info("   Testing: base64 in JSON")
            success, result = _try_upload_image_base64(image_file)
            if success:
                return True, result
            
            logger.error(f"❌ IMAGE FAILED: All methods failed for {image_file.name}")
            return False, None
        else:
            # Use standard multipart upload
            return _try_upload_image(image_file, "file")
            
    except Exception as e:
        logger.error(f"❌ Error uploading image {image_file.name}: {e}")
        return False, None


def _try_upload_image(image_file, field_name):
    """Try uploading image as multipart/form-data"""
    try:
        with open(image_file, "rb") as f:
            files = {field_name: (image_file.name, f, "image/jpeg")}
            
            response = requests.post(
                SERVER_URL,
                files=files,
                timeout=60
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"   ✅ SUCCESS with field '{field_name}'")
                logger.info(f"      Status Code: {response.status_code}")
                
                try:
                    response_data = response.json()
                    logger.info(f"      Server response: {response_data}")
                    
                    # Look for image URL in response
                    url_fields = ["url", "image_url", "file_url", "path", "image_path", "location", "file_path"]
                    image_url = None
                    for url_field in url_fields:
                        if url_field in response_data:
                            image_url = response_data[url_field]
                            logger.info(f"      🎯 Image URL found in '{url_field}': {image_url}")
                            break
                    
                    return True, {"url": image_url, "response": response_data}
                except:
                    logger.info(f"      Server response (text): {response.text[:200]}")
                    return True, {"url": None, "response": response.text}
            else:
                logger.debug(f"      ❌ Failed with status {response.status_code}")
                return False, None
                
    except Exception as e:
        logger.debug(f"      ❌ Error: {e}")
        return False, None


def _try_upload_image_base64(image_file):
    """Try uploading image as base64 string in JSON"""
    try:
        import base64
        
        with open(image_file, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        json_data = {
            "type": "image_upload",
            "filename": image_file.name,
            "image": f"data:image/jpeg;base64,{image_base64}"
        }
        
        response = requests.post(
            SERVER_URL,
            json=json_data,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"   ✅ SUCCESS with base64 method")
            logger.info(f"      Status Code: {response.status_code}")
            
            try:
                response_data = response.json()
                logger.info(f"      Server response: {response_data}")
                return True, {"url": None, "response": response_data}
            except:
                logger.info(f"      Server response (text): {response.text[:200]}")
                return True, {"url": None, "response": response.text}
        else:
            logger.debug(f"      ❌ Failed with status {response.status_code}")
            return False, None
            
    except Exception as e:
        logger.debug(f"      ❌ Error: {e}")
        return False, None

# ============================================================================
# FILE SCANNING
# ============================================================================

def find_json_files():
    """Find all JSON files in your config directories"""
    json_files = []
    
    # Search in JSON_DIR (results directory)
    if JSON_DIR.exists():
        found = list(JSON_DIR.glob("**/*.json"))
        json_files.extend(found)
        logger.info(f"📁 Found {len(found)} JSON files in {JSON_DIR}")
    else:
        logger.warning(f"⚠️  JSON directory not found: {JSON_DIR}")
    
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
        logger.info(f"🖼️  Found {len(image_files)} images in {IMAGE_DIR}")
    else:
        logger.warning(f"⚠️  Image directory not found: {IMAGE_DIR}")
    
    return image_files

# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_server_connection():
    """Test if server is reachable"""
    logger.info("="*60)
    logger.info("🔍 Testing server connection...")
    logger.info(f"   Server URL: {SERVER_URL}")
    
    try:
        base_url = SERVER_URL.split('/api')[0] if '/api' in SERVER_URL else SERVER_URL
        response = requests.get(base_url, timeout=10)
        logger.info(f"✅ Server is reachable (Status: {response.status_code})")
        return True
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Cannot connect to server")
        return False
    except Exception as e:
        logger.warning(f"⚠️  Server test inconclusive: {e}")
        return True


def upload_all_json_files():
    """Find and upload all JSON files"""
    logger.info("="*60)
    logger.info("🚀 UPLOADING ALL JSON FILES")
    logger.info("="*60)
    
    test_server_connection()
    
    logger.info("="*60)
    logger.info("🔍 Scanning for JSON files...")
    json_files = find_json_files()
    
    if not json_files:
        logger.warning("⚠️  No JSON files found!")
        return
    
    logger.info(f"📋 Found {len(json_files)} JSON files to upload")
    
    for i, f in enumerate(json_files, 1):
        logger.info(f"   [{i}] {f.relative_to(JSON_DIR)}")
    
    logger.info("="*60)
    
    try:
        confirm = input(f"\n📤 Upload all {len(json_files)} files? (y/n) [y]: ").strip().lower()
        if confirm and confirm != 'y':
            logger.info("❌ Upload cancelled")
            return
    except KeyboardInterrupt:
        logger.info("\n❌ Upload cancelled")
        return
    
    success_count = 0
    failed_count = 0
    
    logger.info("\n" + "="*60)
    logger.info("📤 Starting uploads...")
    logger.info("="*60 + "\n")
    
    for i, json_file in enumerate(json_files, 1):
        logger.info(f"[{i}/{len(json_files)}] Processing: {json_file.name}")
        
        if upload_json_file(json_file):
            success_count += 1
        else:
            failed_count += 1
        
        if i < len(json_files):
            time.sleep(0.5)
        
        print()
    
    logger.info("="*60)
    logger.info("📊 UPLOAD SUMMARY")
    logger.info(f"   ✅ Successful: {success_count}")
    logger.info(f"   ❌ Failed: {failed_count}")
    logger.info(f"   📁 Total: {len(json_files)}")
    logger.info("="*60)


def upload_all_images():
    """Find and upload all images"""
    logger.info("="*60)
    logger.info("🚀 UPLOADING ALL IMAGES")
    logger.info("="*60)
    
    test_server_connection()
    
    logger.info("="*60)
    logger.info("🔍 Scanning for images...")
    image_files = find_image_files()
    
    if not image_files:
        logger.warning("⚠️  No images found!")
        return
    
    logger.info(f"🖼️  Found {len(image_files)} images to upload")
    
    # Show sample files
    for i, f in enumerate(image_files[:5], 1):
        logger.info(f"   [{i}] {f.name}")
    if len(image_files) > 5:
        logger.info(f"   ... and {len(image_files) - 5} more")
    
    logger.info("="*60)
    
    try:
        confirm = input(f"\n📤 Upload all {len(image_files)} images? (y/n) [y]: ").strip().lower()
        if confirm and confirm != 'y':
            logger.info("❌ Upload cancelled")
            return
    except KeyboardInterrupt:
        logger.info("\n❌ Upload cancelled")
        return
    
    success_count = 0
    failed_count = 0
    image_urls = []
    
    logger.info("\n" + "="*60)
    logger.info("📤 Starting image uploads...")
    logger.info("="*60 + "\n")
    
    for i, image_file in enumerate(image_files, 1):
        logger.info(f"[{i}/{len(image_files)}] Processing: {image_file.name}")
        
        success, result = upload_image_file(image_file, test_mode=True)
        
        if success:
            success_count += 1
            if result and result.get("url"):
                image_urls.append({
                    "filename": image_file.name,
                    "url": result["url"]
                })
        else:
            failed_count += 1
        
        if i < len(image_files):
            time.sleep(0.5)
        
        print()
    
    logger.info("="*60)
    logger.info("📊 IMAGE UPLOAD SUMMARY")
    logger.info(f"   ✅ Successful: {success_count}")
    logger.info(f"   ❌ Failed: {failed_count}")
    logger.info(f"   📁 Total: {len(image_files)}")
    logger.info("="*60)
    
    if image_urls:
        logger.info("\n📎 Image URLs received:")
        for item in image_urls[:5]:
            logger.info(f"   {item['filename']} -> {item['url']}")
        if len(image_urls) > 5:
            logger.info(f"   ... and {len(image_urls) - 5} more")


def upload_sample_image():
    """Upload just one sample image to test the endpoint"""
    logger.info("="*60)
    logger.info("🧪 UPLOADING SAMPLE IMAGE (TEST MODE)")
    logger.info("="*60)
    
    image_files = find_image_files()
    
    if not image_files:
        logger.warning("⚠️  No images found to test!")
        return
    
    # Use the first image as sample
    sample_image = image_files[0]
    
    logger.info(f"\n📸 Sample image: {sample_image.name}")
    logger.info(f"   Size: {sample_image.stat().st_size / (1024*1024):.2f} MB")
    logger.info(f"   Path: {sample_image}")
    logger.info("\n" + "="*60)
    
    try:
        confirm = input("\n📤 Upload this image? (y/n) [y]: ").strip().lower()
        if confirm and confirm != 'y':
            logger.info("❌ Upload cancelled")
            return
    except KeyboardInterrupt:
        logger.info("\n❌ Upload cancelled")
        return
    
    print()
    success, result = upload_image_file(sample_image, test_mode=True)
    
    print()
    if success:
        logger.info("="*60)
        logger.info("✅ SAMPLE IMAGE UPLOAD SUCCESSFUL!")
        if result and result.get("url"):
            logger.info(f"📎 Image URL: {result['url']}")
        logger.info("="*60)
        logger.info("\n💡 You can now use this same method for all images!")
    else:
        logger.info("="*60)
        logger.info("❌ SAMPLE IMAGE UPLOAD FAILED")
        logger.info("="*60)
        logger.info("\n💡 Contact your webdev team for the correct image upload method")


def upload_specific_file(filepath):
    """Upload a specific file (JSON or Image)"""
    logger.info("="*60)
    logger.info("📤 UPLOADING SPECIFIC FILE")
    logger.info("="*60)
    
    file_path = Path(filepath)
    
    if not file_path.exists():
        logger.error(f"❌ File not found: {filepath}")
        return
    
    # Determine file type
    if file_path.suffix.lower() == '.json':
        result = upload_json_file(file_path)
    elif file_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
        result, _ = upload_image_file(file_path, test_mode=True)
    else:
        logger.error(f"❌ Unsupported file type: {file_path.suffix}")
        return
    
    print()
    if result:
        logger.info("="*60)
        logger.info("✅ Upload completed successfully!")
    else:
        logger.info("="*60)
        logger.info("❌ Upload failed!")
    logger.info("="*60)


def list_available_files():
    """List all available JSON files and images"""
    logger.info("="*60)
    logger.info("📋 AVAILABLE FILES")
    logger.info("="*60)
    
    # List JSON files
    json_files = find_json_files()
    logger.info(f"\n📄 JSON Files ({len(json_files)}):")
    if json_files:
        for i, json_file in enumerate(json_files, 1):
            rel_path = json_file.relative_to(JSON_DIR) if json_file.is_relative_to(JSON_DIR) else json_file
            logger.info(f"   [{i}] {rel_path}")
    else:
        logger.info("   No JSON files found")
    
    # List image files
    image_files = find_image_files()
    logger.info(f"\n🖼️  Images ({len(image_files)}):")
    if image_files:
        for i, img_file in enumerate(image_files[:10], 1):
            logger.info(f"   [{i}] {img_file.name}")
        if len(image_files) > 10:
            logger.info(f"   ... and {len(image_files) - 10} more")
    else:
        logger.info("   No images found")
    
    logger.info("="*60)
    
    return json_files, image_files


def show_directory_info():
    """Show information about configured directories"""
    logger.info("="*60)
    logger.info("📂 DIRECTORY INFORMATION")
    logger.info("="*60)
    
    dirs = {
        "Base Directory": config.BASE_DIR,
        "JSON/Results": config.JSON_DIR,
        "Images": config.IMAGE_DIR,
        "Logs": config.LOG_DIR,
        "Models": config.MODEL_DIR
    }
    
    for name, path in dirs.items():
        exists = "✓" if path.exists() else "✗"
        logger.info(f"   {exists} {name}: {path}")
        if path.exists():
            files = list(path.glob("*"))
            logger.info(f"      └─ {len(files)} items")
    
    logger.info("="*60)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 FILE UPLOADER TEST SCRIPT")
    print("="*60)
    print(f"\n📂 Using directories from config.py")
    print(f"   JSON: {JSON_DIR}")
    print(f"   Images: {IMAGE_DIR}")
    print(f"\n🌐 Server: {SERVER_URL}")
    print("="*60)
    print("\nAvailable test modes:")
    print("  1. Upload all JSON files")
    print("  2. Upload all images")
    print("  3. Upload sample image (test mode)")
    print("  4. List available files")
    print("  5. Upload specific file")
    print("  6. Test server connection only")
    print("  7. Show directory information")
    print("="*60)
    
    try:
        choice = input("\nEnter choice (1-7) [default=3]: ").strip() or "3"
        print()
        
        if choice == "1":
            upload_all_json_files()
            
        elif choice == "2":
            upload_all_images()
            
        elif choice == "3":
            upload_sample_image()
            
        elif choice == "4":
            json_files, image_files = list_available_files()
            
        elif choice == "5":
            filepath = input("Enter file path (JSON or Image): ").strip()
            print()
            upload_specific_file(filepath)
            
        elif choice == "6":
            test_server_connection()
            
        elif choice == "7":
            show_directory_info()
            
        else:
            print("❌ Invalid choice!")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user")
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    
    print("\n" + "="*60)
    print("🏁 Test script completed")
    print("="*60 + "\n")