#!/usr/bin/env python3

import time
from picamera2 import Picamera2
from datetime import datetime
import os

# Directory to save captured images
SAVE_DIR = "/home/pi/captured_images"
os.makedirs(SAVE_DIR, exist_ok=True)

def capture_image():
    # Initialize the camera
    picam2 = Picamera2()
    picam2.start()  # Start the camera

    time.sleep(2)  # Allow camera to warm up

    # Create a timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(SAVE_DIR, f"image_{timestamp}.jpg")

    # Capture the image
    picam2.capture_file(filename)
    print(f"Image saved to {filename}")

    picam2.stop()  # Stop the camera

if __name__ == "__main__":
    capture_image()
