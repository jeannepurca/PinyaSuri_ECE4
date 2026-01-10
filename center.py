#!/usr/bin/env python3
# center.py

from gpiozero import Servo
import time

# CHANGE THIS TO YOUR GPIO PIN
SERVO_PIN = 17

# SG90 pulse widths (seconds)
MIN_PULSE = 0.0005   # 0.5 ms
MAX_PULSE = 0.0025   # 2.5 ms

servo = Servo(
    SERVO_PIN,
    min_pulse_width=MIN_PULSE,
    max_pulse_width=MAX_PULSE
)

print("Servo centered. Attach horn horizontally now.")
print("Press Ctrl+C when done.")

try:
    servo.value = 0.0   # EXACT CENTER
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Done.")
    servo.close()