#!/usr/bin/env python3
# test_camera.py - Test auto-lock focus system

import time
import logging
from pathlib import Path
from camera import Camera
import config

# Setup simple logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_camera_focus():
    """Test camera with different focus modes"""
    
    print("=" * 60)
    print("🎥 CAMERA AUTO-LOCK FOCUS TEST")
    print("=" * 60)
    
    # Ask user for focus mode
    print("\nFocus mode options:")
    print("  1. auto_lock   - Autofocus once, then lock (RECOMMENDED)")
    print("  2. infinity    - Lock at infinity (far distance)")
    print("  3. fixed_1m    - Lock at 1 meter")
    print("  4. fixed_5m    - Lock at 5 meters")
    print("  5. continuous  - Continuous autofocus (not for drones)")
    
    user_input = input("\nEnter choice (1-5, or press Enter for auto_lock): ").strip()
    
    focus_modes = {
        "1": "auto_lock",
        "2": "infinity",
        "3": "fixed_1m",
        "4": "fixed_5m",
        "5": "continuous",
        "": "auto_lock"
    }
    
    focus_mode = focus_modes.get(user_input, "auto_lock")
    
    # Initialize camera with chosen focus mode
    print(f"\n🔧 Initializing camera with focus_mode='{focus_mode}'")
    print("=" * 60)
    
    try:
        camera = Camera(focus_mode=focus_mode)
        print("=" * 60)
        print("✓ Camera initialized successfully!")
    except Exception as e:
        print(f"❌ Failed to initialize camera: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Countdown
    print("\n📸 Preparing to capture test images...")
    for i in range(3, 0, -1):
        print(f"   {i}...")
        time.sleep(1)
    
    # Capture multiple test images
    num_test_images = 5
    print(f"\n📷 Capturing {num_test_images} test images...")
    
    test_dir = config.get_image_day_dir() / "focus_test"
    test_dir.mkdir(exist_ok=True)
    
    captured_files = []
    
    for i in range(num_test_images):
        try:
            timestamp = time.strftime("%Y%m%dT%H%M%S")
            filename = f"test_{focus_mode}_{timestamp}_{i}.jpg"
            filepath = test_dir / filename
            
            camera.picam2.capture_file(str(filepath))
            
            # Check file size
            if filepath.exists():
                size_kb = filepath.stat().st_size / 1024
                print(f"  ✓ Image {i+1}/{num_test_images}: {filename} ({size_kb:.1f} KB)")
                captured_files.append(str(filepath))
            else:
                print(f"  ❌ Image {i+1} failed to save")
            
            if i < num_test_images - 1:
                time.sleep(0.3)  # Small delay between captures
                
        except Exception as e:
            print(f"  ❌ Error capturing image {i+1}: {e}")
    
    # Cleanup
    print("\n🛑 Closing camera...")
    camera.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ TEST COMPLETE!")
    print("=" * 60)
    print(f"Focus mode used: {focus_mode}")
    print(f"Images captured: {len(captured_files)}/{num_test_images}")
    print(f"Saved to: {test_dir}")
    print("\nCaptured files:")
    for f in captured_files:
        print(f"  - {Path(f).name}")
    print("\n💡 NEXT STEPS:")
    print("   1. Review the images to check sharpness")
    print("   2. If images are sharp and clear → SUCCESS! Use this mode")
    print("   3. If blurry:")
    print("      - Try 'infinity' mode for high altitude flights")
    print("      - Try 'fixed_5m' for medium altitude (2-10m)")
    print("      - Ensure drone is stable when hovering")
    print("\n   Note: Motion blur during flight means drone vibration")
    print("         is too high - increase STABILIZATION_DELAY in config")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_camera_focus()
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()