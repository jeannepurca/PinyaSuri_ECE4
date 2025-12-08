from picamera2 import Picamera2
import time

picam2 = Picamera2()

# Enable preview or still capture mode
config = picam2.create_preview_configuration()
picam2.configure(config)

# Enable continuous autofocus
picam2.set_controls({"AfMode": 2})  # 2 = continuous autofocus

picam2.start()
time.sleep(5)  # let it focus

picam2.capture_file("test.jpg")
print("test.jpg")