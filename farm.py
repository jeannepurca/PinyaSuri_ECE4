#!/usr/bin/env python3
"""
Simple camera capture script for Raspberry Pi Camera Module v3
Requires: picamera2 library (pre-installed on Raspberry Pi OS Bookworm)
"""

from picamera2 import Picamera2
from libcamera import controls
import time
from datetime import datetime

# Initialize the camera
picam2 = Picamera2()

# Configure camera for preview and capture
# This creates a configuration with a preview stream and main capture stream
config = picam2.create_preview_configuration(
    main={"size": (4608, 2592)},  # Full resolution for Camera Module v3
    lores={"size": (640, 480)},   # Lower resolution for preview
    display="lores"
)
picam2.configure(config)

# Optional: Set autofocus mode (Camera Module v3 has autofocus)
picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})

# Start the camera
picam2.start()

print("Camera started. Preview window should appear.")
print("Press Ctrl+C to exit")
print()

try:
    # Let camera warm up and adjust
    time.sleep(2)
    
    while True:
        # Wait for user input
        input("Press Enter to capture an image (or Ctrl+C to exit)...")
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"image_{timestamp}.jpg"
        
        # Capture image
        picam2.capture_file(filename)
        print(f"Image saved as: {filename}")
        print()

except KeyboardInterrupt:
    print("\nExiting...")

finally:
    # Clean up
    picam2.stop()
    print("Camera stopped.")