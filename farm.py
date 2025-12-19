#!/usr/bin/env python3
import time
from picamera2 import Picamera2
from libcamera import controls
from datetime import datetime
from pathlib import Path

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / "images"
FARM_IMAGE_DIR = IMAGE_DIR / "farms"


def ensure_directories():
    """Create all necessary directories"""
    IMAGE_DIR.mkdir(exist_ok=True)
    FARM_IMAGE_DIR.mkdir(exist_ok=True)


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
        print("Autofocus enabled (continuous mode)")
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
        print("\n" + "=" * 50)
        print("CAPTURE MODE ACTIVE")
        print("=" * 50)
        print("Press ENTER to capture an image")
        print("Type 'q' or 'quit' to exit")
        print("=" * 50 + "\n")

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
        picam2.stop()
        print(f"\nTotal images captured: {image_count}")
        print(f"Images saved in: {farm_dir}")
        print("Camera stopped. Goodbye!")


if __name__ == "__main__":
    capture_image()
