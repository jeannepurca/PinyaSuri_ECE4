import time
from pixhawk_interface import PixhawkInterface
from image_capture import ImageCapture

def main():
    pixhawk = PixhawkInterface('/dev/serial0', 57600)                   # Connect to Pixhawk
    camera = ImageCapture("/home/ece4/PINYASURI/drone_images")          # Initialize camera

    while True:
        groundspeed = pixhawk.get_groundspeed()                         # Get current groundspeed
        if groundspeed is not None:                                     # Valid groundspeed
            print(f"[Main]  Speed: {groundspeed:.2f} m/s")              # Print speed
            if groundspeed < 0.5:                                       # Check if drone is stopped
                print("[Main] Drone stopped — capturing image...")      # Log event
                camera.capture_image()                                  # Capture image
                time.sleep(5)                                           # Avoid repeated captures

if __name__ == "__main__":
    main()