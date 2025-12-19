#!/usr/bin/env python3
import time
from picamera2 import Picamera2
from datetime import datetime
from pathlib import Path

# Base Directories (based on config.py structure)
BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / "images"
FARM_IMAGE_DIR = IMAGE_DIR / "farms"  # Subfolder for farm images

def ensure_directories():
    """Create all necessary directories"""
    IMAGE_DIR.mkdir(exist_ok=True)
    FARM_IMAGE_DIR.mkdir(exist_ok=True)

def capture_image():
    # Ensure directories exist
    ensure_directories()
    
    # Ask user for farm name
    farm_name = input("Enter the farm name: ").strip()
    if not farm_name:
        print("Invalid farm name. Exiting...")
        return
    
    # Create a folder for this farm
    farm_dir = FARM_IMAGE_DIR / farm_name
    farm_dir.mkdir(exist_ok=True)
    
    # Initialize the camera with maximum resolution
    print("Initializing camera...")
    picam2 = Picamera2()
    
    # Configure for maximum still image resolution
    config = picam2.create_still_configuration()
    picam2.configure(config)
    
    picam2.start()  # Start the camera
    
    # Set autofocus mode to continuous (for Camera Module 3)
    try:
        picam2.set_controls({"AfMode": 2, "AfTrigger": 0})  # AfMode 2 = Continuous
        print("Autofocus enabled (continuous mode)")
    except Exception as e:
        print(f"Note: Autofocus not available on this camera ({e})")
    
    time.sleep(2)  # Allow camera to warm up and focus
    
    # Display camera info
    camera_props = picam2.camera_properties
    print(f"Camera: {camera_props.get('Model', 'Unknown')}")
    print(f"Max resolution: {config['main']['size']}")
    print("Camera ready!")
    
    try:
        image_count = 0
        print("\n" + "="*50)
        print("CAPTURE MODE ACTIVE - MAX RESOLUTION")
        print("="*50)
        print("Press ENTER to capture an image")
        print("Type 'q' or 'quit' and press ENTER to exit")
        print("="*50 + "\n")
        
        while True:
            # Wait for user input
            user_input = input("Ready to capture (or 'q' to quit): ").strip().lower()
            
            # Check if user wants to quit
            if user_input in ['q', 'quit', 'exit']:
                print("\nExiting capture mode...")
                break
            
            # Trigger autofocus before capture (for Camera Module 3)
            try:
                picam2.set_controls({"AfTrigger": 0})
                time.sleep(1)  # Wait for autofocus to complete
                print("Focusing...")
            except:
                pass
            
            # Capture the image (on Enter press or any other input)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = farm_dir / f"{timestamp}.jpg"
            
            picam2.capture_file(str(filename))
            image_count += 1
            print(f"✓ Image #{image_count} saved: {filename.name}")
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user (Ctrl+C)")
    
    finally:
        # Stop the camera
        picam2.stop()
        print(f"\nTotal images captured: {image_count}")
        print(f"Images saved in: {farm_dir}")
        print("Camera stopped. Goodbye!")

if __name__ == "__main__":
    capture_image()