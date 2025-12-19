#!/usr/bin/env python3
import time
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput
from libcamera import controls
from datetime import datetime
from pathlib import Path

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
VIDEO_DIR = BASE_DIR / "videos"
FARM_VIDEO_DIR = VIDEO_DIR / "farms"


def ensure_directories():
    VIDEO_DIR.mkdir(exist_ok=True)
    FARM_VIDEO_DIR.mkdir(exist_ok=True)


def record_video():
    ensure_directories()

    farm_name = input("Enter the farm name: ").strip()
    if not farm_name:
        print("Invalid farm name. Exiting...")
        return

    farm_dir = FARM_VIDEO_DIR / farm_name
    farm_dir.mkdir(exist_ok=True)

    print("Initializing camera...")
    picam2 = Picamera2()

    # ✅ Recommended mode: 1080p50
    video_config = picam2.create_video_configuration(
        main={"size": (1920, 1080)},
        controls={"FrameRate": 50}
    )
    picam2.configure(video_config)
    picam2.start()

    # Continuous autofocus (Camera Module v3)
    picam2.set_controls({
        "AfMode": controls.AfModeEnum.Continuous
    })

    time.sleep(2)

    encoder = H264Encoder(bitrate=10_000_000)  # 10 Mbps
    recording = False
    video_count = 0

    print("\nVIDEO RECORD MODE (MP4)")
    print("Press ENTER to start/stop recording")
    print("Type 'q' to quit\n")

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

                output = FfmpegOutput(
                    str(filename),
                    audio=False,
                    video_codec="copy"  # no re-encoding
                )

                picam2.start_recording(encoder, output)

                recording = True
                video_count += 1
                print(f"● Recording started: {filename.name}")

            else:
                picam2.stop_recording()
                recording = False
                print("■ Recording stopped")

    finally:
        if recording:
            picam2.stop_recording()

        picam2.stop()
        print(f"\nTotal videos recorded: {video_count}")
        print(f"Saved in: {farm_dir}")
        print("Camera stopped.")


if __name__ == "__main__":
    record_video()
