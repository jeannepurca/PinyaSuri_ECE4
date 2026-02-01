#!/usr/bin/env python3
# quick_test.py

"""
Quick test script - just tests server connection and basic upload
"""

import logging
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import config
import uploader

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def main():
    print("\n" + "="*60)
    print("🚀 QUICK UPLOADER TEST")
    print("="*60)
    
    # 1. Test connection
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
    
    # 2. Create a test image
    print("\n2️⃣  Creating test image...")
    config.ensure_directories()
    image_dir = config.get_image_day_dir()
    
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    test_image_path = image_dir / f"test_image_{ts}.jpg"
    
    # Create simple test image
    img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    cv2.putText(img, "TEST IMAGE", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
    cv2.imwrite(str(test_image_path), img)
    
    print(f"   ✅ Created: {test_image_path.name}")
    
    # 3. Start upload queue
    print("\n3️⃣  Starting upload queue...")
    uploader.start_upload_queue()
    
    # Create test flight
    test_flight_id = f"test_{ts}"
    uploader.start_new_flight(test_flight_id)
    
    # Enable uploading
    uploader.upload_queue.enable_uploading(test_flight_id)
    print("   ✅ Upload queue ready")
    
    # 4. Upload the image
    print("\n4️⃣  Uploading test image...")
    uploader.queue_image_upload(test_image_path)
    
    # Wait for upload
    import time
    max_wait = 30
    waited = 0
    
    while waited < max_wait:
        stats = uploader.upload_queue.get_stats()
        
        if stats['image_uploaded'] > 0:
            print(f"   ✅ Image uploaded successfully!")
            break
        elif stats['image_failed'] > 0:
            print(f"   ❌ Image upload failed!")
            break
        
        print(f"   ⏳ Waiting... ({waited}s)")
        time.sleep(2)
        waited += 2
    
    if waited >= max_wait:
        print(f"   ⚠️  Timeout after {max_wait}s")
    
    # 5. Show stats
    print("\n5️⃣  Upload Statistics:")
    stats = uploader.upload_queue.get_stats()
    print(f"   • Images uploaded: {stats['image_uploaded']}")
    print(f"   • Images failed: {stats['image_failed']}")
    print(f"   • Queue size: {stats['queue_size']}")
    
    # Stop queue
    uploader.stop_upload_queue()
    
    print("\n" + "="*60)
    if stats['image_uploaded'] > 0:
        print("✅ TEST PASSED - Upload working!")
    else:
        print("❌ TEST FAILED - Check logs above")
    print("="*60)
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