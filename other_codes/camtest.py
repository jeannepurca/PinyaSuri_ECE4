from picamera2 import Picamera2
import time

picam2 = Picamera2()

config = picam2.create_still_configuration(
    main={"size": (640, 480)}
)

picam2.configure(config)
picam2.start()

time.sleep(2)

picam2.capture_file("camera_test.jpg")

picam2.stop()

print("Camera test successful!")
print("Saved: camera_test.jpg")