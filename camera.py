#!/usr/bin/env python3
# camera.py

import logging
import pathlib
from datetime import datetime
import config

logger = logging.getLogger(__name__)

class Camera:
    def __init__(self):
        config.ensure_directories()

        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()
            cam_config = self.picam2.create_still_configuration(main={"size": (4056, 3040)})
            self.picam2.configure(cam_config)
            self.picam2.start()
            logger.info("✓ Camera started successfully!")
        except Exception as e:
            logger.error(f"⚠ Failed to initialize camera: {e} ⚠")
            raise

    # Capture Image and Save to File
    def capture(self, waypoint: int, flight_number: int = 1, prefix="img", burst_index=0):
        """Capture image and save to today's date folder"""
        date_folder = config.get_image_day_dir()
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
        
        # Include burst_index in filename
        filename = f"{prefix}_flight{flight_number}_wp{waypoint}_burst{burst_index}_{ts}.jpg"
        fullpath = date_folder / filename

        self.picam2.capture_file(str(fullpath))
        logger.info(f"✓ Captured {filename} in folder {date_folder.name}")

        return str(fullpath)

    def close(self):
        try:
            self.picam2.stop()
            logger.info("✓ Camera closed.")
        except Exception as e:
            logger.warning(f"⚠ Error stopping camera: {e} ⚠")