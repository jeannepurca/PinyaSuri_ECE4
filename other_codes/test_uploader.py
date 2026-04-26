#!/usr/bin/env python3
# test_uploader.py

"""
Upload existing files with detailed debugging
"""

import sys
import json
import logging
import re
from pathlib import Path
import config
import uploader
import time
import requests

logging.basicConfig(
    level=logging.DEBUG,  # More verbose
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_if_already_uploaded(json_file):
    """Check if JSON was already uploaded"""
    if str(json_file) in uploader.upload_queue.uploaded_files:
        return True
    return False


def upload_json_directly(json_file):
    """Upload JSON directly without queue for testing"""
    logger.info(f"📤 Direct JSON upload: {json_file.name}")
    
    try:
        with open(json_file, 'r') as f:
            json_data = json.load(f)
        
        logger.info(f"   Flight ID in JSON: {json_data.get('id')}")
        logger.info(f"   Waypoints: {[wp.get('waypoint_id') or wp.get('name') for wp in json_data.get('waypoints', [])]}")
        
        response = requests.post(
            config.FLIGHT_LOG_ENDPOINT,
            json=json_data,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        logger.info(f"   Response Status: {response.status_code}")
        logger.info(f"   Response: {response.text[:500]}")
        
        if response.status_code in [200, 201]:
            logger.info("   ✅ JSON uploaded successfully!")
            return True
        elif response.status_code == 409:
            logger.info("   ℹ️  Flight already exists (409 - this is OK)")
            return True
        else:
            logger.error(f"   ❌ Upload failed: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def upload_image_directly(image_file, flight_id, waypoint):
    """Upload image directly for testing"""
    logger.info(f"📤 Direct image upload: {image_file.name}")
    logger.info(f"   Flight ID: {flight_id}")
    logger.info(f"   Waypoint: {waypoint}")
    
    try:
        with open(image_file, 'rb') as f:
            files = {"image": (image_file.name, f, "image/jpeg")}
            data = {
                "flight_id": flight_id,
                "waypoint": waypoint
            }
            
            response = requests.post(
                config.IMAGE_UPLOAD_ENDPOINT,
                files=files,
                data=data,
                timeout=30
            )
        
        logger.info(f"   Response Status: {response.status_code}")
        logger.info(f"   Response: {response.text[:500]}")
        
        if response.status_code in [200, 201]:
            logger.info("   ✅ Image uploaded successfully!")
            return True
        else:
            logger.error(f"   ❌ Upload failed: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    logger.info("="*60)
    logger.info("📦 UPLOAD EXISTING FILES (DEBUG MODE)")
    logger.info("="*60)
    logger.info(f"Server: {config.SERVER_BASE}")
    logger.info("="*60)
    
    # Test server
    if not uploader.test_server_connection():
        logger.error("❌ Server not reachable!")
        return False
    
    # Find files
    json_files = list(config.JSON_DIR.glob("*_summary.json"))
    json_files = [f for f in json_files if 'upload_history' not in f.name]
    
    if not json_files:
        logger.error("❌ No JSON files found!")
        return False
    
    logger.info(f"\n📋 Found JSON files:")
    for jf in json_files:
        already_uploaded = check_if_already_uploaded(jf)
        status = "✅ (already uploaded)" if already_uploaded else "📤 (needs upload)"
        logger.info(f"   • {jf.name} {status}")
    
    # Get the JSON to upload
    json_file = json_files[0]
    
    logger.info(f"\n📄 Working with: {json_file.name}")
    
    # Read JSON to get flight info
    with open(json_file, 'r') as f:
        json_data = json.load(f)
    
    flight_id = json_data.get('id')
    waypoints = json_data.get('waypoints', [])
    
    logger.info(f"   Flight ID: {flight_id}")
    logger.info(f"   Waypoints: {len(waypoints)}")
    
    # Find images for this flight
    flight_num = re.search(r'F(\d+)', flight_id)
    if flight_num:
        pattern = f"*flight{flight_num.group(1)}*.jpg"
        images = list(config.IMAGE_DIR.glob(pattern))
        logger.info(f"   Images found: {len(images)}")
        for img in images:
            logger.info(f"      • {img.name}")
    else:
        logger.error("❌ Cannot extract flight number from flight ID")
        return False
    
    # Upload JSON
    logger.info(f"\n{'='*60}")
    logger.info("STEP 1: Upload JSON")
    logger.info("="*60)
    
    json_success = upload_json_directly(json_file)
    
    if not json_success:
        logger.error("❌ JSON upload failed - cannot proceed")
        return False
    
    # Wait for server to process
    logger.info("\n⏳ Waiting 3 seconds for server to process...")
    time.sleep(3)
    
    # Upload images
    logger.info(f"\n{'='*60}")
    logger.info("STEP 2: Upload Images")
    logger.info("="*60)
    
    if not images:
        logger.warning("⚠️  No images to upload")
        return True
    
    # Get waypoint from JSON
    if waypoints:
        waypoint = waypoints[0].get('waypoint_id') or waypoints[0].get('name')
    else:
        waypoint = "WAYPOINT_2"
    
    logger.info(f"Using waypoint: {waypoint}")
    
    success_count = 0
    for image in images:
        if upload_image_directly(image, flight_id, waypoint):
            success_count += 1
        time.sleep(1)  # Small delay between uploads
    
    # Results
    logger.info(f"\n{'='*60}")
    logger.info("📊 RESULTS")
    logger.info("="*60)
    logger.info(f"JSON uploaded: {'✅' if json_success else '❌'}")
    logger.info(f"Images uploaded: {success_count}/{len(images)}")
    logger.info("="*60)
    
    return success_count > 0


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)