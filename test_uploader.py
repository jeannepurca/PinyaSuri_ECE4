#!/usr/bin/env python3
# test_uploader.py

"""
Test script for uploader.py
Tests JSON and image upload functionality
"""

import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np

# Import the modules to test
import config
import uploader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_image(filename, width=640, height=480):
    """Create a simple test image"""
    # Create a random colored image
    img = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    
    # Add some text
    cv2.putText(
        img,
        f"Test Image: {filename}",
        (50, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2
    )
    
    return img


def create_test_flight_data():
    """Create mock flight data for testing"""
    test_flight_id = f"flight_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    logger.info("="*60)
    logger.info("🧪 CREATING TEST FLIGHT DATA")
    logger.info(f"   Flight ID: {test_flight_id}")
    logger.info("="*60)
    
    # Ensure directories exist
    config.ensure_directories()
    image_dir = config.get_image_day_dir()
    
    # Start flight tracking
    uploader.start_new_flight(test_flight_id)
    
    # Create test data for 3 waypoints
    test_images = []
    test_detections = []
    
    for waypoint in [2, 3, 4]:  # Skip HOME and TAKEOFF
        logger.info(f"\n📍 Creating data for Waypoint {waypoint}...")
        
        # Create 2 images per waypoint
        for burst in range(2):
            # Create test image
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
            filename = f"pinyasuri_flight1_wp{waypoint}_burst{burst}_{ts}.jpg"
            filepath = image_dir / filename
            
            # Generate and save image
            img = create_test_image(filename)
            cv2.imwrite(str(filepath), img)
            
            logger.info(f"   ✓ Created: {filename}")
            test_images.append(filepath)
            
            # Create mock detections
            detections = []
            num_detections = np.random.randint(1, 4)  # 1-3 detections per image
            
            for i in range(num_detections):
                # Random class (Healthy or some disease)
                class_idx = np.random.choice([0, 1, 2, 3, 4, 5, 6])
                class_name = config.get_class_name(class_idx)
                confidence = np.random.uniform(0.5, 0.95)
                
                detection = {
                    'class_index': class_idx,
                    'class_name': class_name,
                    'confidence': confidence,
                    'bbox_pixels': [100, 100, 200, 200]  # Dummy bbox
                }
                detections.append(detection)
            
            # Add to flight aggregator
            uploader.add_detection_to_flight(
                test_flight_id,
                waypoint,
                str(filepath),
                detections
            )
            
            logger.info(f"      └─ Added {len(detections)} detections")
            
            test_detections.append((filepath, detections))
    
    logger.info(f"\n✓ Test data created:")
    logger.info(f"   - {len(test_images)} images")
    logger.info(f"   - 3 waypoints")
    
    return test_flight_id, test_images, test_detections


def test_server_connection():
    """Test if server is reachable"""
    logger.info("\n" + "="*60)
    logger.info("🔍 TESTING SERVER CONNECTION")
    logger.info("="*60)
    
    result = uploader.test_server_connection()
    
    if result:
        logger.info("✓ Server is reachable!")
        return True
    else:
        logger.error("❌ Cannot connect to server!")
        logger.error(f"   Server URL: {config.SERVER_BASE}")
        logger.error("\n   Please check:")
        logger.error("   1. Server is running")
        logger.error("   2. IP address in config.py is correct")
        logger.error("   3. Both devices are on same network")
        return False


def test_image_upload(image_path, flight_id):
    """Test uploading a single image"""
    logger.info(f"\n📤 Testing image upload: {Path(image_path).name}")
    
    # Queue the image
    uploader.queue_image_upload(image_path)
    
    # Wait a bit for upload to process
    time.sleep(3)
    
    # Check stats
    stats = uploader.upload_queue.get_stats()
    logger.info(f"   Stats: {stats['image_uploaded']} uploaded, {stats['image_failed']} failed")
    
    return stats['image_uploaded'] > 0


def test_json_upload(test_flight_id):
    """Test creating and uploading flight summary JSON"""
    logger.info("\n" + "="*60)
    logger.info("📝 TESTING JSON CREATION AND UPLOAD")
    logger.info("="*60)
    
    # Finalize flight (this creates JSON and uploads everything)
    total_waypoints = 5  # HOME, TAKEOFF, WP2, WP3, WP4
    
    summary_path = uploader.finalize_flight_summary(test_flight_id, total_waypoints)
    
    if summary_path:
        logger.info(f"\n✓ Flight summary created: {summary_path}")
        
        # Show the JSON content
        with open(summary_path, 'r') as f:
            summary = json.load(f)
        
        logger.info("\n📄 Flight Summary Content:")
        logger.info(f"   Flight ID: {summary['id']}")
        logger.info(f"   Date: {summary['date']}")
        logger.info(f"   Waypoints captured: {summary['summary']['captured_waypoints']}/{summary['summary']['total_waypoints']}")
        logger.info(f"   Pineapples detected: {summary['summary']['pineapples_detected']}")
        logger.info(f"   Healthy: {summary['summary']['healthy_pineapples']}")
        logger.info(f"   Afflicted: {summary['summary']['afflicted_pineapples']}")
        
        return True
    else:
        logger.error("❌ Failed to create flight summary")
        return False


def wait_for_uploads(timeout=60):
    """Wait for all uploads to complete"""
    logger.info("\n⏳ Waiting for uploads to complete...")
    logger.info(f"   Timeout: {timeout} seconds")
    
    start_time = time.time()
    last_stats = None
    
    while time.time() - start_time < timeout:
        stats = uploader.upload_queue.get_stats()
        
        # Print progress if stats changed
        if stats != last_stats:
            logger.info(f"   Progress: Images {stats['image_uploaded']}/{stats['image_queued']}, "
                       f"JSON {stats['json_uploaded']}/{stats['json_queued']}, "
                       f"Queue: {stats['queue_size']}")
            last_stats = stats.copy()
        
        # Check if done
        if stats['queue_size'] == 0 and stats['pending_count'] == 0:
            logger.info("✓ All uploads complete!")
            return True
        
        time.sleep(2)
    
    logger.warning("⚠ Timeout waiting for uploads")
    return False


def print_final_stats():
    """Print final upload statistics"""
    logger.info("\n" + "="*60)
    logger.info("📊 FINAL UPLOAD STATISTICS")
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
    logger.info(f"   In queue: {stats['queue_size']}")
    logger.info(f"   Pending: {stats['pending_count']}")
    logger.info(f"   Failed (will retry): {stats['failed_count']}")
    logger.info(f"   Total uploaded: {stats['uploaded_total']}")
    
    logger.info("\n" + "="*60)
    
    # Success/failure summary
    total_attempted = stats['image_queued'] + stats['json_queued']
    total_uploaded = stats['image_uploaded'] + stats['json_uploaded']
    total_failed = stats['image_failed'] + stats['json_failed']
    
    if total_attempted > 0:
        success_rate = (total_uploaded / total_attempted) * 100
        logger.info(f"📈 Success Rate: {success_rate:.1f}% ({total_uploaded}/{total_attempted})")
    
    if total_failed == 0:
        logger.info("✅ ALL UPLOADS SUCCESSFUL!")
    else:
        logger.warning(f"⚠️  {total_failed} uploads failed")
    
    logger.info("="*60)


def main():
    """Main test function"""
    logger.info("\n" + "="*60)
    logger.info("🧪 UPLOADER TEST SCRIPT")
    logger.info("="*60)
    logger.info(f"Server: {config.SERVER_BASE}")
    logger.info(f"Flight Log Endpoint: {config.FLIGHT_LOG_ENDPOINT}")
    logger.info(f"Image Upload Endpoint: {config.IMAGE_UPLOAD_ENDPOINT}")
    logger.info("="*60)
    
    # Step 1: Test server connection
    if not test_server_connection():
        logger.error("\n❌ Test aborted - server not reachable")
        logger.info("\nTo fix:")
        logger.info("1. Start your server")
        logger.info("2. Update SERVER_BASE in config.py with correct IP")
        logger.info("3. Ensure both devices are on same network")
        return False
    
    # Step 2: Start upload queue
    logger.info("\n🚀 Starting upload queue...")
    uploader.start_upload_queue()
    time.sleep(1)
    
    # Step 3: Create test data
    test_flight_id, test_images, test_detections = create_test_flight_data()
    
    # Step 4: Enable uploading (simulates flight completion)
    logger.info("\n🎬 Simulating flight completion...")
    uploader.upload_queue.enable_uploading(test_flight_id)
    
    # Step 5: Test JSON creation and upload
    json_success = test_json_upload(test_flight_id)
    
    # Step 6: Wait for all uploads
    wait_for_uploads(timeout=120)
    
    # Step 7: Print final statistics
    print_final_stats()
    
    # Step 8: Stop upload queue
    logger.info("\n🛑 Stopping upload queue...")
    uploader.stop_upload_queue()
    
    # Final result
    logger.info("\n" + "="*60)
    if json_success:
        logger.info("✅ TEST COMPLETED SUCCESSFULLY!")
    else:
        logger.info("⚠️  TEST COMPLETED WITH ISSUES")
    logger.info("="*60)
    
    logger.info("\n📁 Check the following directories:")
    logger.info(f"   Images: {config.IMAGE_DIR}")
    logger.info(f"   JSON summaries: {config.JSON_DIR}")
    logger.info(f"   Upload history: {config.JSON_DIR / 'upload_history.json'}")
    
    return json_success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Test interrupted by user")
        uploader.stop_upload_queue()
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        uploader.stop_upload_queue()
        sys.exit(1)