#!/usr/bin/env python3
# camera.py

import logging
import pathlib
from datetime import datetime
import config

logger = logging.getLogger(__name__)

class Camera:
    def __init__(self, focus_distance=None, shutter_speed_us=None):
        """
        Initialize camera with optional fixed focus and shutter speed
        
        Args:
            focus_distance: Focus distance in diopters (1/meters)
                          - 0.0 = infinity focus
                          - 0.2 = 5 meters
                          - 1.0 = 1 meter
                          None = autofocus enabled
            shutter_speed_us: Shutter speed in microseconds
                          - 500 = 1/2000s (very fast, good for motion)
                          - 1000 = 1/1000s (fast)
                          - 2000 = 1/500s (moderate)
                          None = auto exposure
        """
        config.ensure_directories()

        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()
            
            # Use faster configuration optimized for burst capture
            cam_config = self.picam2.create_still_configuration(
                main={"size": (4056, 3040)},
                buffer_count=2  # Double buffering for faster captures
            )
            self.picam2.configure(cam_config)
            
            # Build controls dictionary
            controls = {}
            
            # Set fixed focus if specified
            if focus_distance is not None:
                controls["AfMode"] = 0  # Manual focus
                controls["LensPosition"] = focus_distance
                logger.info(f"✓ Fixed focus set to {focus_distance} diopters")
            else:
                controls["AfMode"] = 2  # Continuous autofocus
                logger.info("✓ Autofocus enabled")
            
            # Set shutter speed if specified (critical for motion blur)
            if shutter_speed_us is not None:
                controls["ExposureTime"] = shutter_speed_us
                # Also disable auto exposure to maintain fixed shutter
                controls["AeEnable"] = False
                # Set reasonable ISO to compensate for fast shutter
                controls["AnalogueGain"] = 4.0  # ISO 400 equivalent
                logger.info(f"✓ Shutter speed set to {shutter_speed_us}µs (1/{1000000//shutter_speed_us}s)")
            else:
                controls["AeEnable"] = True  # Auto exposure
                logger.info("✓ Auto exposure enabled")
            
            # Apply all controls
            self.picam2.set_controls(controls)
            
            self.picam2.start()
            
            logger.info("✓ Camera started successfully!")
            
        except Exception as e:
            logger.error(f"⚠ Failed to initialize camera: {e} ⚠")
            raise

    def capture(self, waypoint: int, flight_number: int = 1, prefix="img", burst_index=0):
        """Capture image and save to today's date folder"""

        # Get today's folder
        date_folder = config.get_image_day_dir()

        # Timestamp for filename
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
        
        # Include burst index in filename
        filename = f"{prefix}_flight{flight_number}_wp{waypoint}_burst{burst_index}_{ts}.jpg"
        fullpath = date_folder / filename

        try:
            self.picam2.capture_file(str(fullpath))
            logger.debug(f"✓ Captured {filename}")
            return str(fullpath)
            
        except Exception as e:
            logger.error(f"⚠ Failed to capture {filename}: {e}")
            raise

    def close(self):
        try:
            self.picam2.stop()
            logger.info("✓ Camera stopped successfully.")
        except Exception as e:
            logger.warning(f"⚠ Error stopping camera: {e} ⚠")