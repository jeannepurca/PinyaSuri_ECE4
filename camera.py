#!/usr/bin/env python3
# camera.py

import logging
import pathlib
from datetime import datetime
import time
import config

logger = logging.getLogger(__name__)

class Camera:
    def __init__(self, focus_mode="auto_lock"):
        """
        Initialize camera with intelligent focus handling
        
        Args:
            focus_mode: 
                - "auto_lock" (default): Autofocus once at startup, then lock (best for drones)
                - "infinity": Lock focus at infinity (good for high altitude)
                - "fixed_1m": Lock focus at 1 meter
                - "fixed_5m": Lock focus at 5 meters
                - "continuous": Continuous autofocus (not recommended for flight)
        """
        config.ensure_directories()

        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()
            
            # Use faster configuration optimized for burst capture
            cam_config = self.picam2.create_still_configuration(
                main={"size": (4056, 3040)},
                buffer_count=2
            )
            self.picam2.configure(cam_config)
            
            # Start camera first
            self.picam2.start()
            time.sleep(0.5)  # Let camera warm up
            
            # Handle different focus modes
            if focus_mode == "auto_lock":
                self._auto_focus_and_lock()
                
            elif focus_mode == "infinity":
                self._set_fixed_focus(0.0, "infinity")
                
            elif focus_mode == "fixed_1m":
                self._set_fixed_focus(1.0, "1 meter")
                
            elif focus_mode == "fixed_5m":
                self._set_fixed_focus(0.2, "5 meters")
                
            elif focus_mode == "continuous":
                self.picam2.set_controls({"AfMode": 2})
                logger.warning("⚠ Continuous autofocus enabled - may struggle with drone vibration")
                
            else:
                logger.warning(f"Unknown focus mode '{focus_mode}', using auto_lock")
                self._auto_focus_and_lock()
            
            # Set optimized exposure for aerial photography
            self.picam2.set_controls({
                "AeEnable": True,  # Auto exposure
                "AeExposureMode": 0,  # Normal exposure mode
                "AwbEnable": True,  # Auto white balance
            })
            
            logger.info("✓ Camera ready for flight!")
            
        except Exception as e:
            logger.error(f"⚠ Failed to initialize camera: {e} ⚠")
            raise

    def _auto_focus_and_lock(self):
        """Automatically focus once, then lock the position"""
        logger.info("🎯 Auto-calibrating focus...")
        
        try:
            # Enable autofocus temporarily
            self.picam2.set_controls({"AfMode": 2})
            time.sleep(0.3)
            
            # Trigger autofocus
            self.picam2.set_controls({"AfTrigger": 0})
            
            # Wait for autofocus to complete
            max_wait = 3.0
            start_time = time.time()
            focused = False
            
            while (time.time() - start_time) < max_wait:
                metadata = self.picam2.capture_metadata()
                af_state = metadata.get("AfState", None)
                
                # AfState: 0=Idle, 1=Scanning, 2=Focused, 3=Failed
                if af_state == 2:
                    focused = True
                    break
                    
                time.sleep(0.1)
            
            # Get the lens position
            metadata = self.picam2.capture_metadata()
            lens_position = metadata.get("LensPosition", 0.0)
            
            if focused:
                logger.info(f"✓ Focus locked at lens position: {lens_position:.2f}")
            else:
                logger.warning(f"⚠ Focus timeout, locking at position: {lens_position:.2f}")
            
            # Switch to manual mode to lock this position
            self.picam2.set_controls({
                "AfMode": 0,  # Manual mode
                "LensPosition": lens_position
            })
            
            time.sleep(0.2)
            logger.info("✓ Focus locked - ready for flight")
            
        except Exception as e:
            logger.error(f"⚠ Auto-focus failed: {e}, using infinity focus as fallback")
            self._set_fixed_focus(0.0, "infinity (fallback)")

    def _set_fixed_focus(self, diopters, description):
        """Set fixed focus at specified distance"""
        self.picam2.set_controls({
            "AfMode": 0,  # Manual mode
            "LensPosition": diopters
        })
        time.sleep(0.2)
        logger.info(f"✓ Fixed focus set to {description} ({diopters} diopters)")

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