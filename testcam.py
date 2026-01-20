#!/usr/bin/env python3
# test_camera.py - Standalone camera focus test

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
    """Test camera with different focus distances"""
    
    print("=" * 60)
    print("🎥 CAMERA FOCUS TEST")
    print("=" * 60)
    
    # Ask user for focus distance
    print("\nFocus distance options:")
    print("  0.0 = Infinity (far away)")
    print("  0.1 = 10 meters")
    print("  0.2 = 5 meters")
    print("  0.5 = 2 meters")
    print("  1.0 = 1 meter")
    print("  None = Autofocus enabled")
    
    user_input = input("\nEnter focus distance (or press Enter for 0.2): ").strip()
    
    if user_input == "":
        focus_distance = 0.2
    elif user_input.lower() == "none":
        focus_distance = None
    else:
        try:
            focus_distance = float(user_input)
        except ValueError:
            print("Invalid input, using default 0.2")
            focus_distance = 0.2
    
    # Initialize camera with chosen focus
    print(f"\n🔧 Initializing camera with focus_distance={focus_distance}")
    try:
        camera = Camera(focus_distance=focus_distance)
        print("✓ Camera initialized successfully!")
    except Exception as e:
        print(f"❌ Failed to initialize camera: {e}")
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
            filename = f"focus_test_{focus_distance}_{timestamp}_{i}.jpg"
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
                time.sleep(0.5)  # Small delay between captures
                
        except Exception as e:
            print(f"  ❌ Error capturing image {i+1}: {e}")
    
    # Cleanup
    print("\n🛑 Closing camera...")
    camera.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ TEST COMPLETE!")
    print("=" * 60)
    print(f"Focus distance used: {focus_distance}")
    print(f"Images captured: {len(captured_files)}/{num_test_images}")
    print(f"Saved to: {test_dir}")
    print("\nCaptured files:")
    for f in captured_files:
        print(f"  - {f}")
    print("\n💡 Review the images to check if focus is good!")
    print("   If blurry, try a different focus distance.")
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