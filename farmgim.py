#!/usr/bin/env python3
# farmgim.py

import time
import threading
from picamera2 import Picamera2
from libcamera import controls
from datetime import datetime
from pathlib import Path

import config

# Import gimbal
try:
    from gimbal import CameraGimbal
    GIMBAL_AVAILABLE = True
except ImportError:
    GIMBAL_AVAILABLE = False
    print("Warning: gimbal.py not found. Running without stabilization.")

# Base Directories
FARM_IMAGE_DIR = config.IMAGE_DIR / "farms"


def ensure_directories():
    """Create all necessary directories"""
    config.ensure_directories()
    FARM_IMAGE_DIR.mkdir(exist_ok=True)


def gimbal_update_thread(gimbal, stop_event):
    """Background thread to continuously update gimbal"""
    while not stop_event.is_set():
        try:
            gimbal.update()
            time.sleep(0.02)  # 50 Hz update rate
        except Exception as e:
            print(f"Gimbal update error: {e}")
            break


def capture_image():
    ensure_directories()

    # Ask user for farm name
    farm_name = input("Enter the farm name: ").strip()
    if not farm_name:
        print("Invalid farm name. Exiting...")
        return

    # Create a folder for this farm
    farm_dir = FARM_IMAGE_DIR / farm_name
    farm_dir.mkdir(exist_ok=True)

    # Initialize gimbal
    gimbal = None
    gimbal_thread = None
    stop_gimbal = None
    
    if config.GIMBAL_ENABLED and GIMBAL_AVAILABLE:
        try:
            print("Initializing gimbal...")
            gimbal = CameraGimbal(
                roll_pin=config.GIMBAL_ROLL_PIN,
                pitch_pin=config.GIMBAL_PITCH_PIN,
                use_mpu6050=config.USE_MPU6050,
                mpu6050_address=config.MPU6050_I2C_ADDRESS
            )
            gimbal.enable()
            
            # Start gimbal update thread
            stop_gimbal = threading.Event()
            gimbal_thread = threading.Thread(
                target=gimbal_update_thread,
                args=(gimbal, stop_gimbal),
                daemon=True
            )
            gimbal_thread.start()
            
            print("✓ Gimbal stabilization ENABLED (45° downward pitch)")
        except Exception as e:
            print(f"⚠ Gimbal initialization failed: {e}")
            print("  Continuing without gimbal stabilization")
            gimbal = None

    # Initialize camera
    print("Initializing camera...")
    picam2 = Picamera2()

    # Configure for maximum still resolution
    still_config = picam2.create_still_configuration()
    picam2.configure(still_config)

    picam2.start()

    # Enable Continuous Autofocus (Camera Module v3)
    try:
        picam2.set_controls({
            "AfMode": controls.AfModeEnum.Continuous
        })
        print("✓ Autofocus enabled (continuous mode)")
    except Exception as e:
        print(f"Autofocus not available: {e}")

    # Allow sensor + AF to settle
    time.sleep(2)

    # Display camera info
    camera_props = picam2.camera_properties
    print(f"Camera model: {camera_props.get('Model', 'Unknown')}")
    print(f"Resolution: {still_config['main']['size']}")
    print("Camera ready!")

    image_count = 0

    try:
        print("\n" + "=" * 60)
        print("CAPTURE MODE ACTIVE")
        if gimbal:
            print("🎥 Gimbal: ACTIVE - Camera stabilized at 45° downward")
        print("=" * 60)
        print("Press ENTER to capture an image")
        print("Type 'q' or 'quit' to exit")
        print("=" * 60 + "\n")

        while True:
            user_input = input("Ready to capture (or 'q' to quit): ").strip().lower()

            if user_input in ("q", "quit", "exit"):
                print("\nExiting capture mode...")
                break

            # Give AF a brief moment before capture
            time.sleep(0.3)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = farm_dir / f"{timestamp}.jpg"

            picam2.capture_file(str(filename))
            image_count += 1

            print(f"✓ Image #{image_count} saved: {filename.name}")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user (Ctrl+C)")

    finally:
        # Stop camera
        picam2.stop()
        
        # Stop gimbal
        if gimbal:
            if stop_gimbal:
                stop_gimbal.set()
            if gimbal_thread:
                gimbal_thread.join(timeout=1.0)
            gimbal.cleanup()
        
        print(f"\nTotal images captured: {image_count}")
        print(f"Images saved in: {farm_dir}")
        print("Camera and gimbal stopped. Goodbye!")


if __name__ == "__main__":
    capture_image()