from picamera2 import Picamera2
import time
import os

class ImageCapture:
    def __init__(self, save_dir="/home/ece4/PINYASURI/drone_images"):
        self.save_dir = save_dir                                        # Save directory for images
        os.makedirs(self.save_dir, exist_ok=True)                       # Ensure directory exists
        self.picam = Picamera2()                                        # Initialize Picamera2
        self.picam.configure(self.picam.create_still_configuration())   # Configure for still images
        self.picam.start()                                              # Start the camera
    
    def capture_image(self):
        filename = f"{self.save_dir}/image_{int(time.time())}.jpg"      # Create a unique filename
        self.picam.capture_file(filename)                               # Capture and save the image
        print(f"[Camera] Image captured: {filename}")                   # Log the capture
        return filename                                                 # Return the filename