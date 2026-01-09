#!/usr/bin/env python3
# farmvidgim.py

import time
import threading
import logging
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput
from libcamera import controls
from datetime import datetime
from pathlib import Path

# Import gimbal controller
from gimbal import CameraGimbal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FarmVid")

BASE_DIR = Path(__file__).resolve().parent
VIDEO_DIR = BASE_DIR / "videos"
FARM_VIDEO_DIR = VIDEO_DIR / "farms"

def ensure_directories():
    VIDEO_DIR.mkdir(exist_ok=True)
    FARM_VIDEO_DIR.mkdir(exist_ok=True)


class GimbalStabilizer:
    """
    Handles gimbal stabilization in a separate thread
    Can work in two modes:
    1. Simulated mode - gentle drift simulation for testing
    2. Live mode - uses actual drone attitude data (requires MAVLink integration)
    """
    
    def __init__(self, roll_pin=17, pitch_pin=27, simulated=True):
        """
        Initialize gimbal stabilizer
        
        Args:
            roll_pin: GPIO pin for roll servo
            pitch_pin: GPIO pin for pitch servo
            simulated: If True, uses simulated gentle movements for testing
        """
        self.gimbal = CameraGimbal(roll_pin=roll_pin, pitch_pin=pitch_pin)
        self.simulated = simulated
        self.running = False
        self.thread = None
        
        # Simulated drift parameters (very gentle for smooth video)
        self.sim_drift = 0.0
        self.sim_drift_rate = 0.1  # degrees per second
        
    def start(self):
        """Start gimbal stabilization thread"""
        if not self.running:
            self.running = True
            self.gimbal.enable()
            self.thread = threading.Thread(target=self._stabilization_loop, daemon=True)
            self.thread.start()
            logger.info("✓ Gimbal stabilization started")
    
    def stop(self):
        """Stop gimbal stabilization"""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=2.0)
            self.gimbal.disable()
            logger.info("⚠ Gimbal stabilization stopped")
    
    def _stabilization_loop(self):
        """Main stabilization loop (runs in separate thread)"""
        last_time = time.time()
        
        while self.running:
            current_time = time.time()
            dt = current_time - last_time
            
            if self.simulated:
                # Simulate gentle drift/movement
                # In real use, this would be replaced with actual drone attitude data
                import math
                
                # Gentle sinusoidal movement (simulates minor corrections)
                self.sim_drift = 5 * math.sin(current_time * 0.5)
                
                # Update gimbal with simulated roll
                self.gimbal.update(self.sim_drift)
                
            else:
                # TODO: Get actual drone attitude from MAVLink/Pixhawk
                # For now, just maintain level
                self.gimbal.update(0.0)
            
            last_time = current_time
            time.sleep(0.02)  # 50Hz update rate
    
    def cleanup(self):
        """Clean shutdown"""
        self.stop()
        self.gimbal.cleanup()


def record_video_with_gimbal():
    """Main video recording function with gimbal stabilization"""
    ensure_directories()

    # Get farm name
    farm_name = input("Enter the farm name: ").strip()
    if not farm_name:
        print("Invalid farm name.")
        return

    farm_dir = FARM_VIDEO_DIR / farm_name
    farm_dir.mkdir(exist_ok=True)

    # Ask about gimbal mode
    print("\n=== GIMBAL CONFIGURATION ===")
    print("1. Simulated mode (gentle movement simulation)")
    print("2. Live mode (requires drone connection)")
    print("3. No gimbal (disabled)")
    
    gimbal_choice = input("Select mode [1]: ").strip() or "1"
    
    gimbal_stabilizer = None
    use_gimbal = gimbal_choice != "3"
    
    if use_gimbal:
        try:
            simulated_mode = gimbal_choice == "1"
            gimbal_stabilizer = GimbalStabilizer(
                roll_pin=17,    # Adjust these pins if needed
                pitch_pin=27,
                simulated=simulated_mode
            )
            logger.info("✓ Gimbal initialized successfully")
        except Exception as e:
            logger.error(f"⚠ Failed to initialize gimbal: {e}")
            logger.error("Continuing without gimbal stabilization...")
            use_gimbal = False

    # Initialize camera
    picam2 = Picamera2()

    video_config = picam2.create_video_configuration(
        main={"size": (1920, 1080)},
        controls={"FrameRate": 50}
    )
    picam2.configure(video_config)
    picam2.start()

    # Continuous AF (Camera Module v3)
    picam2.set_controls({
        "AfMode": controls.AfModeEnum.Continuous
    })

    time.sleep(2)

    encoder = H264Encoder(bitrate=10_000_000)
    recording = False
    video_count = 0

    print("\n" + "=" * 60)
    print("VIDEO RECORD MODE (MP4)")
    if use_gimbal:
        print("✓ Gimbal stabilization: ENABLED")
    else:
        print("⚠ Gimbal stabilization: DISABLED")
    print("=" * 60)
    print("Press ENTER to start/stop recording")
    print("Type 'q' to quit\n")

    try:
        while True:
            user_input = input("Ready: ").strip().lower()

            if user_input in ("q", "quit", "exit"):
                if recording:
                    picam2.stop_recording()
                    if gimbal_stabilizer:
                        gimbal_stabilizer.stop()
                break

            if not recording:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = farm_dir / f"{timestamp}.mp4"

                output = FfmpegOutput(str(filename))
                picam2.start_recording(encoder, output)
                
                # Start gimbal stabilization when recording starts
                if gimbal_stabilizer:
                    gimbal_stabilizer.start()

                recording = True
                video_count += 1
                print(f"● Recording started: {filename.name}")
                if use_gimbal:
                    print("  ↳ Gimbal stabilization active")

            else:
                picam2.stop_recording()
                
                # Stop gimbal when recording stops
                if gimbal_stabilizer:
                    gimbal_stabilizer.stop()
                
                recording = False
                print("■ Recording stopped")

    except KeyboardInterrupt:
        logger.info("\n⚠ Interrupted by user")
    
    finally:
        if recording:
            picam2.stop_recording()
        
        if gimbal_stabilizer:
            gimbal_stabilizer.cleanup()
        
        picam2.stop()

        print("\n" + "=" * 60)
        print(f"Total videos recorded: {video_count}")
        print(f"Saved in: {farm_dir}")
        print("Camera and gimbal stopped.")
        print("=" * 60)


if __name__ == "__main__":
    record_video_with_gimbal()