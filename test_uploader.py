#!/usr/bin/env python3
# test_uploader.py

"""
Upload existing files with proper flight ID matching
"""

import sys
import json
import logging
import re
from pathlib import Path
import config
import uploader
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_flight_id_from_filename(filename):
    """Extract flight number from filename like 'pinyasuri_flight93_wp2...'"""
    match = re.search(r'flight(\d+)', filename)
    if match:
        flight_num = match.group(1)
        # Match the format used in JSON files
        return f"20260201_F{flight_num}"
    return None


def organize_files_by_flight():
    """Organize existing images and JSONs by flight ID"""
    logger.info("🔍 Scanning and organizing files...")
    
    # Find all JSON files
    json_files = list(config.JSON_DIR.glob("*_summary.json"))
    json_files = [f for f in json_files if 'upload_history' not in f.name]
    
    # Find all images
    image_files = list(config.IMAGE_DIR.glob("*.jpg"))
    
    # Organize by flight
    flights = {}
    
    # Process JSONs first
    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)
            flight_id = data.get('id')
            
            if flight_id:
                flights[flight_id] = {
                    'json': json_file,
                    'images': [],
                    'waypoints': [wp.get('waypoint_id') or wp.get('name') for wp in data.get('waypoints', [])]
                }
    
    # Match images to flights
    for image_file in image_files:
        flight_id = extract_flight_id_from_filename(image_file.name)
        
        if flight_id and flight_id in flights:
            flights[flight_id]['images'].append(image_file)
        else:
            # Orphan image - no matching JSON
            logger.debug(f"Orphan image (no JSON): {image_file.name}")
    
    return flights


def upload_flight(flight_id, flight_data):
    """Upload a single flight's JSON and images"""
    logger.info(f"\n{'='*60}")
    logger.info(f"📤 Uploading Flight: {flight_id}")
    logger.info(f"{'='*60}")
    
    json_file = flight_data['json']
    images = flight_data['images']
    waypoints = flight_data['waypoints']
    
    logger.info(f"   JSON: {json_file.name}")
    logger.info(f"   Images: {len(images)}")
    logger.info(f"   Waypoints: {', '.join(waypoints)}")
    
    # Step 1: Upload JSON first
    logger.info(f"\n1️⃣  Uploading JSON to register flight...")
    uploader.upload_queue.add_json(json_file)
    
    # Wait for JSON to upload
    max_wait = 15
    waited = 0
    json_uploaded = False
    
    while waited < max_wait:
        stats = uploader.upload_queue.get_stats()
        if stats['json_uploaded'] > 0:
            logger.info("   ✅ JSON uploaded successfully!")
            json_uploaded = True
            break
        time.sleep(1)
        waited += 1
    
    if not json_uploaded:
        logger.error("   ❌ JSON upload failed - skipping images")
        return False
    
    # Wait a bit for server to process
    time.sleep(2)
    
    # Step 2: Upload images with correct flight_id
    logger.info(f"\n2️⃣  Uploading {len(images)} images...")
    
    # IMPORTANT: Set the current flight ID so images use the right one
    uploader.upload_queue.current_flight_id = flight_id
    
    for image in images:
        uploader.upload_queue.add_image(image)
    
    # Wait for images to upload
    max_wait = 60
    waited = 0
    initial_count = stats['image_uploaded']
    
    while waited < max_wait:
        stats = uploader.upload_queue.get_stats()
        uploaded_count = stats['image_uploaded'] - initial_count
        
        if uploaded_count >= len(images):
            logger.info(f"   ✅ All {len(images)} images uploaded!")
            break
        
        if stats['queue_size'] == 0 and waited > 10:
            logger.info(f"   ⚠️  Uploaded {uploaded_count}/{len(images)} images")
            break
        
        time.sleep(2)
        waited += 2
    
    logger.info(f"✅ Flight {flight_id} upload complete")
    return True


def main():
    logger.info("="*60)
    logger.info("📦 UPLOAD EXISTING FILES")
    logger.info("="*60)
    logger.info(f"Server: {config.SERVER_BASE}")
    logger.info("="*60)
    
    # Test server
    if not uploader.test_server_connection():
        logger.error("❌ Server not reachable!")
        return False
    
    # Organize files
    flights = organize_files_by_flight()
    
    if not flights:
        logger.error("❌ No flight data found!")
        logger.info("\nMake sure you have:")
        logger.info(f"  • JSON files in: {config.JSON_DIR}")
        logger.info(f"  • Images in: {config.IMAGE_DIR}")
        return False
    
    logger.info(f"\n✅ Found {len(flights)} flight(s) to upload:")
    for flight_id, data in flights.items():
        logger.info(f"   • {flight_id}: {data['json'].name} + {len(data['images'])} images")
    
    # Start upload queue
    logger.info("\n🚀 Starting upload queue...")
    uploader.start_upload_queue()
    uploader.upload_queue.enable_uploading("batch_upload")
    time.sleep(1)
    
    # Upload each flight
    success_count = 0
    for flight_id, flight_data in flights.items():
        if upload_flight(flight_id, flight_data):
            success_count += 1
    
    # Wait for any remaining uploads
    logger.info("\n⏳ Waiting for all uploads to complete...")
    time.sleep(5)
    
    # Show final stats
    logger.info("\n" + "="*60)
    logger.info("📊 FINAL STATISTICS")
    logger.info("="*60)
    
    stats = uploader.upload_queue.get_stats()
    logger.info(f"JSON uploaded: {stats['json_uploaded']}")
    logger.info(f"JSON failed: {stats['json_failed']}")
    logger.info(f"Images uploaded: {stats['image_uploaded']}")
    logger.info(f"Images failed: {stats['image_failed']}")
    logger.info(f"Failed (will retry): {stats['failed_count']}")
    
    # Stop queue
    uploader.stop_upload_queue()
    
    logger.info("\n" + "="*60)
    if success_count == len(flights):
        logger.info("✅ ALL FLIGHTS UPLOADED SUCCESSFULLY!")
    else:
        logger.info(f"⚠️  {success_count}/{len(flights)} flights uploaded")
    logger.info("="*60)
    
    return success_count > 0


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        uploader.stop_upload_queue()
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        uploader.stop_upload_queue()
        sys.exit(1)