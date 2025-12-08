from picamera2 import Picamera2, Preview
import time

picam2 = Picamera2()

# Configure preview mode
config = picam2.create_preview_configuration()
picam2.configure(config)

# Enable continuous autofocus
picam2.set_controls({"AfMode": 2})  # 2 = Continuous autofocus

# Start preview window
picam2.start_preview(Preview.QTGL)

# Start camera
picam2.start()

print("Camera preview with autofocus running... Press Ctrl+C to exit.")
try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    picam2.stop()
    print("Preview stopped.")