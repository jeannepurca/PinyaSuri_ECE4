#!/usr/bin/env python3
# farmvidgim.py

import time
import threading
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput
from libcamera import controls
from datetime import datetime
from pathlib import Path

import config

# Import gimbal
try:
    from gimbal import CameraGimbal
    GIMBAL_AVAILABLE = True
except ImportError:
    GIMBAL_AVAILABLE = False
    print("Warning: gimbal.py not found. Running without stabilization.")

# Video Directory
VIDEO_DIR = config.BASE_DIR / "videos"
FARM_VIDEO_DIR = VIDEO_DIR / "farms"


def ensure_directories():
    VIDEO_DIR.mkdir(exist_ok=True)
    FARM_VIDEO_DIR.mkdir(exist_ok=True)


def gimbal_update_thread(gimbal, stop_event):
    """Background thread to continuously update gimbal"""
    while not stop_event.is_set():
        try:
            gimbal.update()
            time.sleep(0.02)  # 50 Hz update rate
        except Exception as e:
            print(f"Gimbal update error: {e}")
            break


def record_video():
    ensure_directories()

    farm_name = input("Enter the farm name: ").strip()
    if not farm_name:
        print("Invalid farm name.")
        return

    farm_dir = FARM_VIDEO_DIR / farm_name
    farm_dir.mkdir(exist_ok=True)

    # Initialize gimbal
    gimbal = None
    gimbal_thread = None
    stop_gimbal = None
    
    if config.GIMBAL_ENABLED and GIMBAL_AVAILABLE:
        try:
            gimbal = CameraGimbal(
                roll_pin=config.GIMBAL_ROLL_PIN,
                use_mpu6050=config.USE_MPU6050,
                mpu6050_address=config.MPU6050_I2C_ADDRESS
            )
            gimbal.enable()
            
            # Start gimbal update thread
            stop_gimbal = threading.Event()
            gimbal_thread = threading.Thread(
                target=gimbal_update_thread,
                args=(gimbal, stop_gimbal),
                daemon=True
            )
            gimbal_thread.start()
            
            print("✓ Gimbal stabilization ENABLED (roll only, pitch physically fixed at 45°)")
        except Exception as e:
            print(f"⚠ Gimbal initialization failed: {e}")
            print("  Continuing without gimbal stabilization")
            gimbal = None

    # Initialize camera
    picam2 = Picamera2()

    video_config = picam2.create_video_configuration(
        main={"size": (1920, 1080)},
        controls={"FrameRate": 50}
    )
    picam2.configure(video_config)
    picam2.start()

    # Continuous AF (Camera Module v3)
    try:
        picam2.set_controls({
            "AfMode": controls.AfModeEnum.Continuous
        })
        print("✓ Autofocus enabled (continuous mode)")
    except Exception as e:
        print(f"Autofocus not available: {e}")

    time.sleep(2)

    encoder = H264Encoder(bitrate=10_000_000)
    recording = False
    video_count = 0

    print("\n" + "=" * 60)
    print("VIDEO RECORD MODE (MP4)")
    if gimbal:
        print("🎥 Gimbal: ACTIVE - Roll stabilization enabled")
        print("    (Pitch physically fixed at 45° downward)")
    print("=" * 60)
    print("Press ENTER to start/stop recording")
    print("Type 'q' to quit")
    print("=" * 60 + "\n")

    try:
        while True:
            user_input = input("Ready: ").strip().lower()

            if user_input in ("q", "quit", "exit"):
                if recording:
                    picam2.stop_recording()
                break

            if not recording:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = farm_dir / f"{timestamp}.mp4"

                output = FfmpegOutput(str(filename))
                picam2.start_recording(encoder, output)

                recording = True
                video_count += 1
                print(f"● Recording started: {filename.name}")

            else:
                picam2.stop_recording()
                recording = False
                print("■ Recording stopped")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user (Ctrl+C)")

    finally:
        # Stop recording if active
        if recording:
            picam2.stop_recording()
        
        # Stop camera
        picam2.stop()
        
        # Stop gimbal
        if gimbal:
            if stop_gimbal:
                stop_gimbal.set()
            if gimbal_thread:
                gimbal_thread.join(timeout=1.0)
            gimbal.cleanup()

        print(f"\nTotal videos recorded: {video_count}")
        print(f"Saved in: {farm_dir}")
        print("Camera and gimbal stopped.")


if __name__ == "__main__":
    record_video()