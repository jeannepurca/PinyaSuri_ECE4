#!/usr/bin/env python3
# test_uploader.py

"""
Test uploader with existing images and JSON files
"""

import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime
import config
import uploader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_existing_files():
    """Find all existing images and JSON files"""
    logger.info("\n" + "="*60)
    logger.info("🔍 SCANNING FOR EXISTING FILES")
    logger.info("="*60)
    
    # Find images
    image_dir = config.IMAGE_DIR
    image_files = list(image_dir.glob("**/*.jpg"))
    
    # Separate by type
    raw_images = [f for f in image_files if 'pinyasuri_' in f.name or 'img_' in f.name]
    cropped_images = [f for f in image_files if 'cropped_' in f.name]
    detection_images = [f for f in image_files if 'detection_' in f.name]
    
    logger.info(f"\n📸 Found images in {image_dir}:")
    logger.info(f"   Raw images: {len(raw_images)}")
    logger.info(f"   Cropped images: {len(cropped_images)}")
    logger.info(f"   Detection images: {len(detection_images)}")
    logger.info(f"   Total: {len(image_files)}")
    
    # Find JSON files
    json_dir = config.JSON_DIR
    json_files = list(json_dir.glob("**/*.json"))
    
    # Filter out upload history
    flight_summaries = [f for f in json_files if 'summary' in f.name and 'upload_history' not in f.name]
    
    logger.info(f"\n📄 Found JSON files in {json_dir}:")
    logger.info(f"   Flight summaries: {len(flight_summaries)}")
    logger.info(f"   Total JSON: {len(json_files)}")
    
    if flight_summaries:
        logger.info("\n📋 Available flight summaries:")
        for json_file in flight_summaries:
            logger.info(f"   • {json_file.name}")
    
    if raw_images:
        logger.info(f"\n📋 Sample images (first 5):")
        for img in raw_images[:5]:
            logger.info(f"   • {img.name}")
        if len(raw_images) > 5:
            logger.info(f"   ... and {len(raw_images) - 5} more")
    
    return {
        'raw_images': raw_images,
        'cropped_images': cropped_images,
        'detection_images': detection_images,
        'flight_summaries': flight_summaries
    }


def test_json_upload_first(json_file):
    """Upload JSON file first to register flight with server"""
    logger.info(f"\n📤 Uploading JSON first: {json_file.name}")
    logger.info("   (This registers the flight/waypoints with the server)")
    
    try:
        with open(json_file, 'r') as f:
            json_data = json.load(f)
        
        logger.info(f"\n📋 JSON Summary:")
        logger.info(f"   Flight ID: {json_data.get('id', 'unknown')}")
        logger.info(f"   Date: {json_data.get('date', 'unknown')}")
        logger.info(f"   Waypoints: {json_data.get('summary', {}).get('captured_waypoints', 0)}")
        logger.info(f"   Pineapples: {json_data.get('summary', {}).get('pineapples_detected', 0)}")
        
        # Queue for upload
        uploader.upload_queue.add_json(json_file)
        
        # Wait for upload
        max_wait = 15
        waited = 0
        while waited < max_wait:
            stats = uploader.upload_queue.get_stats()
            if stats['json_uploaded'] > 0:
                logger.info("   ✅ JSON uploaded successfully!")
                return True
            elif stats['json_failed'] > 0:
                logger.error("   ❌ JSON upload failed!")
                return False
            time.sleep(1)
            waited += 1
        
        logger.warning("   ⚠️  Timeout waiting for JSON upload")
        return False
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def test_image_uploads(images, max_images=10):
    """Upload images (after JSON is uploaded)"""
    logger.info(f"\n📤 Testing image uploads...")
    logger.info(f"   Uploading first {max_images} images")
    
    images_to_upload = images[:max_images]
    
    for img in images_to_upload:
        uploader.upload_queue.add_image(img)
        logger.info(f"   Queued: {img.name}")
    
    # Wait for uploads
    logger.info(f"\n⏳ Waiting for {len(images_to_upload)} images to upload...")
    
    max_wait = 60
    waited = 0
    last_count = 0
    
    while waited < max_wait:
        stats = uploader.upload_queue.get_stats()
        current_count = stats['image_uploaded']
        
        if current_count != last_count:
            logger.info(f"   Progress: {current_count}/{len(images_to_upload)} uploaded")
            last_count = current_count
        
        if current_count >= len(images_to_upload):
            logger.info("   ✅ All images uploaded!")
            return True
        
        if stats['queue_size'] == 0 and waited > 10:
            break
        
        time.sleep(2)
        waited += 2
    
    stats = uploader.upload_queue.get_stats()
    logger.info(f"\n📊 Upload results:")
    logger.info(f"   Uploaded: {stats['image_uploaded']}/{len(images_to_upload)}")
    logger.info(f"   Failed: {stats['image_failed']}")
    
    return stats['image_uploaded'] > 0


def interactive_test():
    """Interactive test - let user choose what to upload"""
    files = find_existing_files()
    
    if not files['raw_images'] and not files['flight_summaries']:
        logger.error("\n❌ No files found to upload!")
        logger.info("\nPlease ensure you have:")
        logger.info(f"  • Images in: {config.IMAGE_DIR}")
        logger.info(f"  • JSON files in: {config.JSON_DIR}")
        return False
    
    # Test server connection
    logger.info("\n" + "="*60)
    logger.info("🔍 TESTING SERVER CONNECTION")
    logger.info("="*60)
    
    if not uploader.test_server_connection():
        logger.error("\n❌ Server not reachable!")
        logger.info(f"   Server: {config.SERVER_BASE}")
        return False
    
    logger.info("✅ Server is reachable!")
    
    # Start upload queue
    logger.info("\n🚀 Starting upload queue...")
    uploader.start_upload_queue()
    time.sleep(1)
    
    # Enable uploading
    uploader.upload_queue.enable_uploading("existing_files_test")
    
    # Ask user what to test
    logger.info("\n" + "="*60)
    logger.info("📋 UPLOAD OPTIONS")
    logger.info("="*60)
    logger.info("1. Upload JSON files only")
    logger.info("2. Upload images only (first 10)")
    logger.info("3. Upload JSON first, then images")
    logger.info("4. Upload all images")
    logger.info("5. Upload everything")
    
    try:
        choice = input("\nChoose option (1-5): ").strip()
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Cancelled by user")
        uploader.stop_upload_queue()
        return False
    
    success = False
    
    if choice == "1":
        # Upload JSON only
        if files['flight_summaries']:
            for json_file in files['flight_summaries']:
                test_json_upload_first(json_file)
            success = True
        else:
            logger.warning("No JSON files found!")
    
    elif choice == "2":
        # Upload images only
        if files['raw_images']:
            success = test_image_uploads(files['raw_images'], max_images=10)
        else:
            logger.warning("No images found!")
    
    elif choice == "3":
        # Upload JSON first, then images
        if files['flight_summaries'] and files['raw_images']:
            # Upload first JSON
            json_success = test_json_upload_first(files['flight_summaries'][0])
            
            if json_success:
                # Now upload images
                success = test_image_uploads(files['raw_images'], max_images=10)
            else:
                logger.error("❌ JSON upload failed - skipping images")
        else:
            logger.warning("Need both JSON and images!")
    
    elif choice == "4":
        # Upload all images
        if files['raw_images']:
            success = test_image_uploads(files['raw_images'], max_images=len(files['raw_images']))
        else:
            logger.warning("No images found!")
    
    elif choice == "5":
        # Upload everything
        logger.info("\n📤 Uploading all files...")
        
        # First upload all JSON files
        for json_file in files['flight_summaries']:
            uploader.upload_queue.add_json(json_file)
        
        # Then upload all images
        for img in files['raw_images']:
            uploader.upload_queue.add_image(img)
        
        if files['detection_images']:
            for img in files['detection_images']:
                uploader.upload_queue.add_image(img)
        
        # Wait for completion
        total_files = len(files['flight_summaries']) + len(files['raw_images']) + len(files['detection_images'])
        logger.info(f"   Queued {total_files} files")
        
        time.sleep(5)  # Give it time to start
        
        max_wait = 300  # 5 minutes for large batches
        waited = 0
        
        while waited < max_wait:
            stats = uploader.upload_queue.get_stats()
            total_uploaded = stats['json_uploaded'] + stats['image_uploaded']
            queue_size = stats['queue_size']
            
            logger.info(f"   Progress: {total_uploaded}/{total_files} uploaded, {queue_size} in queue")
            
            if queue_size == 0 and waited > 10:
                break
            
            time.sleep(5)
            waited += 5
        
        success = True
    
    else:
        logger.warning("Invalid choice!")
    
    # Wait a bit for final uploads
    time.sleep(3)
    
    # Print final stats
    logger.info("\n" + "="*60)
    logger.info("📊 FINAL STATISTICS")
    logger.info("="*60)
    
    stats = uploader.upload_queue.get_stats()
    
    logger.info(f"\n📸 Images:")
    logger.info(f"   Queued: {stats['image_queued']}")
    logger.info(f"   Uploaded: {stats['image_uploaded']}")
    logger.info(f"   Failed: {stats['image_failed']}")
    
    logger.info(f"\n📄 JSON Files:")
    logger.info(f"   Queued: {stats['json_queued']}")
    logger.info(f"   Uploaded: {stats['json_uploaded']}")
    logger.info(f"   Failed: {stats['json_failed']}")
    
    logger.info(f"\n📦 Queue Status:")
    logger.info(f"   Failed (will retry): {stats['failed_count']}")
    logger.info(f"   Total uploaded: {stats['uploaded_total']}")
    
    # Stop queue
    logger.info("\n🛑 Stopping upload queue...")
    uploader.stop_upload_queue()
    
    logger.info("\n" + "="*60)
    if success:
        logger.info("✅ TEST COMPLETED")
    else:
        logger.info("⚠️  TEST COMPLETED WITH ISSUES")
    logger.info("="*60)
    
    return success


def main():
    """Main test function"""
    logger.info("\n" + "="*60)
    logger.info("🧪 EXISTING FILES UPLOAD TEST")
    logger.info("="*60)
    logger.info(f"Server: {config.SERVER_BASE}")
    logger.info(f"Image directory: {config.IMAGE_DIR}")
    logger.info(f"JSON directory: {config.JSON_DIR}")
    logger.info("="*60)
    
    try:
        return interactive_test()
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Interrupted by user")
        uploader.stop_upload_queue()
        return False
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        uploader.stop_upload_queue()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)