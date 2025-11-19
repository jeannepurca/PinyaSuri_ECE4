import os
from picamera2 import Picamera2, Preview
from datetime import datetime
import logging
import pathlib

logger = logging.getLogger("ImageCapture")

class ImageCapture:
    def __init__(self, out_dir="/home/ece4/PINYASURI/drone_images", keep_preview=False):
        self.out_dir = pathlib.Path(out_dir)                           # Output directory
        self.out_dir.mkdir(parents=True, exist_ok=True)                # Ensure directory exists
        self.picam2 = Picamera2()                                      # Initialize Picamera2   

        config = self.picam2.create_still_configuration(main={"size": (4056, 3040)})  # full V3 resolution; adjust if needed
        self.picam2.configure(config)                                  # Configure for still images
        self.picam2.start()                                            # Start the camera
        logger.info("Camera started")                                  

    def capture(self, prefix="img"):
        """
        Capture a single file and return path.
        Using capture_file is convenient for one-shot captures.
        """
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]        # UTC timestamp
        fname = f"{prefix}_{ts}.jpg"                                   # Filename
        fpath = self.out_dir / fname                                   # Full path
        self.picam2.capture_file(str(fpath))                           # Capture and save the image
        logger.info(f"Captured {fpath}")                               # Log the capture
        return str(fpath)                                              # Return the file path

    def close(self):
        try:                                                           # Try to stop the camera
            self.picam2.stop()                                         # Stop the camera
        except Exception:                                              # Ignore errors on stop
            pass                                                       # Suppress exceptions on stop