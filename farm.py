#!/usr/bin/env python3

import time
from picamera2 import Picamera2
from datetime import datetime
from pathlib import Path

# Base Directories (based on config.py structure)
BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / "images"
FARM_IMAGE_DIR = IMAGE_DIR / "farms"  # Subfolder for farm images

def ensure_directories():
    """Create all necessary directories"""
    IMAGE_DIR.mkdir(exist_ok=True)
    FARM_IMAGE_DIR.mkdir(exist_ok=True)

def capture_image():
    # Ensure directories exist
    ensure_directories()
    
    # Ask user for farm name
    farm_name = input("Enter the farm name: ").strip()
    if not farm_name:
        print("Invalid farm name. Exiting...")
        return

    # Create a folder for this farm
    farm_dir = FARM_IMAGE_DIR / farm_name
    farm_dir.mkdir(exist_ok=True)

    # Initialize the camera
    picam2 = Picamera2()
    picam2.start()  # Start the camera
    time.sleep(2)  # Allow camera to warm up

    # Create timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = farm_dir / f"{timestamp}.jpg"

    # Capture the image
    picam2.capture_file(str(filename))
    print(f"Image saved to {filename}")

    picam2.stop()  # Stop the camera

if __name__ == "__main__":
    capture_image()