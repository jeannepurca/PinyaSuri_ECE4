import os
from picamera2 import Picamera2
from datetime import datetime
import logging
import pathlib

# Create logger for ImageCapture
logger = logging.getLogger("ImageCapture")

class ImageCapture:
    def __init__(self, output_dir=None, keep_preview=False):
        if output_dir is None:
            import config
            output_dir = str(config.IMAGE_DIR)
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.picam2 = Picamera2()
            cam_config = self.picam2.create_still_configuration(main={"size": (4056, 3040)})
            self.picam2.configure(cam_config)
            self.picam2.start()
            logger.info("Camera started successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            raise

    # Capture Image and Save to File
    def capture(self, prefix="img"):
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
        filename = f"{prefix}_{ts}.jpg"
        fullpath = self.output_dir / filename
        self.picam2.capture_file(str(fullpath))
        logger.info(f"Captured {fullpath}")
        return str(fullpath)                                       

    def close(self):
        try:
            self.picam2.stop()
            logger.info("Camera stopped successfully.")
        except Exception as e:
            logger.warning(f"Error stopping camera: {e}")
