#!/usr/bin/env python3

import time
from picamera2 import Picamera2
from datetime import datetime
import os

# Base directory for datasets
BASE_DIR = "/home/pi/dataset_image"
os.makedirs(BASE_DIR, exist_ok=True)

def capture_image():
    # Ask user for farm name
    farm_name = input("Enter the farm name: ").strip()
    if not farm_name:
        print("Invalid farm name. Exiting...")
        return

    # Create a folder for this farm
    farm_dir = os.path.join(BASE_DIR, farm_name)
    os.makedirs(farm_dir, exist_ok=True)

    # Initialize the camera
    picam2 = Picamera2()
    picam2.start()  # Start the camera
    time.sleep(2)  # Allow camera to warm up

    # Create timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(farm_dir, f"{timestamp}.jpg")

    # Capture the image
    picam2.capture_file(filename)
    print(f"Image saved to {filename}")

    picam2.stop()  # Stop the camera

if __name__ == "__main__":
    capture_image()