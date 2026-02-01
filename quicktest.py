#!/usr/bin/env python3
# quick_test_fixed.py

"""
Quick test script - uploads JSON first, then images
(Fixed to work with servers that require flight registration)
"""

import logging
import cv2
import numpy as np
import json
from pathlib import Path
from datetime import datetime
import config
import uploader
import time

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def create_minimal_flight_json(flight_id, waypoint="WAYPOINT_2"):
    """Create a minimal flight summary JSON to register with server"""
    return {
        "id": flight_id,
        "type": "flight",
        "date": datetime.now().strftime("%B %d, %Y"),
        "start_time": datetime.now().strftime("%H:%M:%S"),
        "end_time": datetime.now().strftime("%H:%M:%S"),
        "summary": {
            "total_waypoints": 5,
            "captured_waypoints": 1,
            "mission_status": "Test",
            "pineapples_detected": 0,
            "healthy_pineapples": 0,
            "afflicted_pineapples": 0,
            "most_common_affliction": None,
            "avg_confidence": 0
        },
        "waypoints": [
            {
                "waypoint_id": waypoint,
                "image": "",
                "images": [],
                "num_pineapples": 0,
                "healthy": 0,
                "afflicted": 0,
                "afflictions": {}
            }
        ],
        "image_metadata": {
            "total_images": 1,
            "images_per_waypoint": {waypoint: 1}
        }
    }


def main():
    print("\n" + "="*60)
    print("🚀 QUICK UPLOADER TEST (FIXED)")
    print("="*60)
    
    # Test 1: Server connection
    print("\n1️⃣  Testing server connection...")
    print(f"   Server: {config.SERVER_BASE}")
    
    if not uploader.test_server_connection():
        print("   ❌ Server not reachable!")
        print("\n   Fix this first:")
        print(f"   • Check SERVER_BASE in config.py: {config.SERVER_BASE}")
        print("   • Make sure server is running")
        print("   • Verify network connection")
        return
    
    print("   ✅ Server is reachable!")
    
    # Test 2: Create test flight ID
    print("\n2️⃣  Creating test flight...")
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    test_flight_id = f"test_{ts}"
    test_waypoint = "WAYPOINT_2"
    
    print(f"   Flight ID: {test_flight_id}")
    print(f"   Waypoint: {test_waypoint}")
    
    # Test 3: Create and save minimal JSON
    print("\n3️⃣  Creating flight registration JSON...")
    config.ensure_directories()
    
    flight_json = create_minimal_flight_json(test_flight_id, test_waypoint)
    json_path = config.JSON_DIR / f"{test_flight_id}_summary.json"
    
    with open(json_path, 'w') as f:
        json.dump(flight_json, f, indent=2)
    
    print(f"   ✅ Created: {json_path.name}")
    
    # Test 4: Start upload queue
    print("\n4️⃣  Starting upload queue...")
    uploader.start_upload_queue()
    uploader.upload_queue.enable_uploading(test_flight_id)
    time.sleep(1)
    print("   ✅ Upload queue ready")
    
    # Test 5: Upload JSON FIRST (register flight with server)
    print("\n5️⃣  Uploading JSON to register flight with server...")
    print("   (This tells the server about the flight)")
    
    uploader.upload_queue.add_json(json_path)
    
    # Wait for JSON upload
    max_wait = 15
    waited = 0
    json_uploaded = False
    
    while waited < max_wait:
        stats = uploader.upload_queue.get_stats()
        
        if stats['json_uploaded'] > 0:
            print("   ✅ JSON uploaded - flight registered with server!")
            json_uploaded = True
            break
        elif stats['json_failed'] > 0:
            print("   ❌ JSON upload failed!")
            break
        
        time.sleep(1)
        waited += 1
    
    if not json_uploaded:
        print("   ⚠️  JSON upload failed or timed out")
        print("   Cannot proceed with image upload")
        uploader.stop_upload_queue()
        return
    
    # Test 6: Create test image
    print("\n6️⃣  Creating test image...")
    image_dir = config.get_image_day_dir()
    
    # Create filename that matches the waypoint we registered
    test_image_path = image_dir / f"pinyasuri_flight1_wp2_burst0_{ts}.jpg"
    
    # Create simple test image
    img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    cv2.putText(img, "TEST IMAGE", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
    cv2.imwrite(str(test_image_path), img)
    
    print(f"   ✅ Created: {test_image_path.name}")
    
    # Test 7: Upload image (after JSON is registered)
    print("\n7️⃣  Uploading test image...")
    print("   (Server now knows about the flight, so this should work)")
    
    uploader.queue_image_upload(test_image_path)
    
    # Wait for upload
    max_wait = 30
    waited = 0
    
    while waited < max_wait:
        stats = uploader.upload_queue.get_stats()
        
        if stats['image_uploaded'] > 0:
            print(f"   ✅ Image uploaded successfully!")
            break
        elif stats['image_failed'] > 0:
            print(f"   ❌ Image upload failed!")
            print(f"   Check server logs for details")
            break
        
        time.sleep(2)
        waited += 2
    
    if waited >= max_wait:
        print(f"   ⚠️  Timeout after {max_wait}s")
    
    # Test 8: Show final stats
    print("\n8️⃣  Upload Statistics:")
    stats = uploader.upload_queue.get_stats()
    print(f"   • JSON uploaded: {stats['json_uploaded']}")
    print(f"   • JSON failed: {stats['json_failed']}")
    print(f"   • Images uploaded: {stats['image_uploaded']}")
    print(f"   • Images failed: {stats['image_failed']}")
    print(f"   • Queue size: {stats['queue_size']}")
    
    # Stop queue
    uploader.stop_upload_queue()
    
    print("\n" + "="*60)
    if stats['json_uploaded'] > 0 and stats['image_uploaded'] > 0:
        print("✅ TEST PASSED - Both JSON and image uploaded!")
    elif stats['json_uploaded'] > 0:
        print("⚠️  PARTIAL SUCCESS - JSON uploaded, image failed")
        print("   Check server logs to see why image failed")
    else:
        print("❌ TEST FAILED - Check logs above")
    print("="*60)
    
    print(f"\n📁 Files created:")
    print(f"   JSON: {json_path}")
    print(f"   Image: {test_image_path}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
        uploader.stop_upload_queue()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        uploader.stop_upload_queue()