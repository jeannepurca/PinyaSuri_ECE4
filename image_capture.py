import os
from picamera2 import Picamera2
from datetime import datetime
import logging
import pathlib

logger = logging.getLogger("ImageCapture")  # Create logger for ImageCapture

class ImageCapture:
    def __init__(self, output_dir="/home/ece4/PINYASURI/drone_images", keep_preview=False):     # Initialize camera
        self.output_dir = pathlib.Path(output_dir)              # Output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)      # Ensure directory exists
        self.picam2 = Picamera2()                               # Initialize Picamera2   

        config = self.picam2.create_still_configuration(main={"size": (4056, 3040)})    # Full V3 resolution
        self.picam2.configure(config)                           # Configure for still images
        self.picam2.start()                                     # Start the camera
        logger.info("Camera started.")                                  

    def capture(self, prefix="img"):                            # Capture an image
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]     # UTC timestamp for filename
        fname = f"{prefix}_{ts}.jpg"                            # Filename
        fpath = self.output_dir / fname                         # Full path
        self.picam2.capture_file(str(fpath))                    # Capture and save the image
        logger.info(f"Captured {fpath}")                        # Log the capture
        return str(fpath)                                       # Return the file path

    def close(self):
        try:                                                    # Try to stop the camera
            self.picam2.stop()                                  # Stop the camera
        except Exception:                                       # Ignore errors on stop
            pass                                                # Suppress exceptions on stop