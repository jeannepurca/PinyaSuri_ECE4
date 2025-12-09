from picamera2 import Picamera2
import time

picam2 = Picamera2()

# Use STILL_CAPTURE configuration for maximum resolution
config = picam2.create_still_configuration(main={"size": (4056, 3040)})
picam2.configure(config)

# Enable continuous autofocus
picam2.set_controls({"AfMode": 0})

picam2.start()
time.sleep(2)  # give camera time to focus

# Capture the image at max resolution
picam2.capture_file("test_max.jpg")
print("Saved test_max.jpg")

picam2.stop()
