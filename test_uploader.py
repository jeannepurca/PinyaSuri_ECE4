#!/usr/bin/env python3
# test_uploader.py - Test script for uploading existing JSON files

import json
import requests
from pathlib import Path
import logging
import time
import sys

# Import your config
try:
    import config
    logger = logging.getLogger(__name__)
    logger.info("✓ Using config.py settings")
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
# CONFIGURATION (from your config.py)
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
# UPLOAD FUNCTION
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
        
        logger.info(f"📤 Uploading: {json_file.name}")
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
        
        if response.status_code == 200:
            logger.info(f"✅ SUCCESS: {json_file.name}")
            try:
                response_data = response.json()
                logger.info(f"   Server response: {response_data}")
            except:
                logger.info(f"   Server response: {response.text[:200]}")
            return True
        else:
            logger.error(f"❌ FAILED: {json_file.name}")
            logger.error(f"   Status Code: {response.status_code}")
            logger.error(f"   Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Connection Error: Cannot reach server")
        logger.error(f"   Check if server is online: {SERVER_URL}")
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
    """Find all image files (for reference)"""
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
        # Try a simple request to check if server is up
        base_url = SERVER_URL.split('/api')[0] if '/api' in SERVER_URL else SERVER_URL
        response = requests.get(base_url, timeout=10)
        logger.info(f"✅ Server is reachable (Status: {response.status_code})")
        return True
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Cannot connect to server")
        logger.error(f"   The server might be offline or the URL is incorrect")
        return False
    except Exception as e:
        logger.warning(f"⚠️  Server test inconclusive: {e}")
        logger.info(f"   Will attempt upload anyway...")
        return True

def upload_all_json_files():
    """Find and upload all JSON files"""
    logger.info("="*60)
    logger.info("🚀 STARTING JSON UPLOAD TEST")
    logger.info("="*60)
    
    # Test server connection
    test_server_connection()
    
    # Find JSON files
    logger.info("="*60)
    logger.info("🔍 Scanning for JSON files...")
    json_files = find_json_files()
    
    if not json_files:
        logger.warning("⚠️  No JSON files found!")
        logger.info(f"   Searched in: {JSON_DIR}")
        logger.info("   Try creating a flight summary first or check the directory")
        return
    
    logger.info(f"📋 Found {len(json_files)} JSON files to upload")
    
    # Show list of files
    for i, f in enumerate(json_files, 1):
        logger.info(f"   [{i}] {f.relative_to(JSON_DIR)}")
    
    logger.info("="*60)
    
    # Confirm upload
    try:
        confirm = input(f"\n📤 Upload all {len(json_files)} files? (y/n) [y]: ").strip().lower()
        if confirm and confirm != 'y':
            logger.info("❌ Upload cancelled")
            return
    except KeyboardInterrupt:
        logger.info("\n❌ Upload cancelled")
        return
    
    # Upload each file
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
        
        # Small delay between uploads
        if i < len(json_files):
            time.sleep(0.5)
        
        print()  # Blank line for readability
    
    # Print summary
    logger.info("="*60)
    logger.info("📊 UPLOAD SUMMARY")
    logger.info(f"   ✅ Successful: {success_count}")
    logger.info(f"   ❌ Failed: {failed_count}")
    logger.info(f"   📁 Total: {len(json_files)}")
    logger.info("="*60)

def upload_specific_file(filepath):
    """Upload a specific JSON file"""
    logger.info("="*60)
    logger.info("📤 UPLOADING SPECIFIC FILE")
    logger.info("="*60)
    
    result = upload_json_file(filepath)
    
    if result:
        logger.info("="*60)
        logger.info("✅ Upload completed successfully!")
    else:
        logger.info("="*60)
        logger.info("❌ Upload failed!")
    logger.info("="*60)
    
    return result

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
    
    # List image files (just count)
    image_files = find_image_files()
    logger.info(f"\n🖼️  Images: {len(image_files)} files")
    
    logger.info("="*60)
    
    return json_files

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
            # Count files
            files = list(path.glob("*"))
            logger.info(f"      └─ {len(files)} items")
    
    logger.info("="*60)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 JSON UPLOADER TEST SCRIPT")
    print("="*60)
    print(f"\n📂 Using directories from config.py")
    print(f"   JSON: {JSON_DIR}")
    print(f"   Images: {IMAGE_DIR}")
    print(f"\n🌐 Server: {SERVER_URL}")
    print("="*60)
    print("\nAvailable test modes:")
    print("  1. Upload all JSON files (recommended)")
    print("  2. List available files")
    print("  3. Upload specific file")
    print("  4. Test server connection only")
    print("  5. Show directory information")
    print("="*60)
    
    try:
        choice = input("\nEnter choice (1-5) [default=1]: ").strip() or "1"
        print()
        
        if choice == "1":
            upload_all_json_files()
            
        elif choice == "2":
            files = list_available_files()
            if files:
                upload_choice = input("\n📤 Upload a file? Enter number or press Enter to skip: ").strip()
                if upload_choice.isdigit():
                    idx = int(upload_choice) - 1
                    if 0 <= idx < len(files):
                        print()
                        upload_specific_file(files[idx])
            
        elif choice == "3":
            filepath = input("Enter JSON file path: ").strip()
            print()
            upload_specific_file(filepath)
            
        elif choice == "4":
            test_server_connection()
            
        elif choice == "5":
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