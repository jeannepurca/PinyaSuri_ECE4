#!/usr/bin/env python3
# testgim.py

import time
import math
from gpiozero import Servo
from mpu6050 import mpu6050

# -----------------------------
# CONFIGURATION
# -----------------------------
ROLL_SERVO_PIN = 17
PITCH_SERVO_PIN = 18

MAX_ROLL_ANGLE = 20.0
MAX_PITCH_ANGLE = 20.0

UPDATE_DELAY = 0.02    # 50 Hz
ALPHA = 0.98           # complementary filter

# PID gains
KP = 0.6
KI = 0.05
KD = 0.03

SERVO_MIN = 0.0005
SERVO_MAX = 0.0025

# -----------------------------
# INITIALIZE HARDWARE
# -----------------------------
imu = mpu6050(0x68)
roll_servo = Servo(ROLL_SERVO_PIN, min_pulse_width=SERVO_MIN, max_pulse_width=SERVO_MAX)
pitch_servo = Servo(PITCH_SERVO_PIN, min_pulse_width=SERVO_MIN, max_pulse_width=SERVO_MAX)

# -----------------------------
# PID STATE
# -----------------------------
roll_integral = 0
roll_prev_error = 0
pitch_integral = 0
pitch_prev_error = 0

# -----------------------------
# FILTER STATE
# -----------------------------
roll_angle = 0.0
pitch_angle = 0.0
last_time = time.time()

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def clamp(value, min_val, max_val):
    return max(min(value, max_val), min_val)

def accel_to_angles(accel):
    roll = math.degrees(math.atan2(accel["y"], accel["z"]))
    pitch = math.degrees(math.atan2(-accel["x"], math.sqrt(accel["y"]**2 + accel["z"]**2)))
    return roll, pitch

def angle_to_servo(angle, max_angle):
    angle = clamp(angle, -max_angle, max_angle)
    return angle / max_angle  # [-1, +1]

# -----------------------------
# MAIN LOOP
# -----------------------------
try:
    print("Mini gimbal test started (complementary filter). Tilt the IMU!")
    
    while True:
        current_time = time.time()
        dt = current_time - last_time
        last_time = current_time

        # --- IMU readings ---
        accel = imu.get_accel_data()
        gyro = imu.get_gyro_data()  # degrees/sec
        accel_roll, accel_pitch = accel_to_angles(accel)

        # --- Complementary filter ---
        roll_angle = ALPHA * (roll_angle + gyro["x"] * dt) + (1 - ALPHA) * accel_roll
        pitch_angle = ALPHA * (pitch_angle + gyro["y"] * dt) + (1 - ALPHA) * accel_pitch

        # --- PID correction ---
        # Roll
        roll_error = -roll_angle
        roll_integral += roll_error * dt
        roll_derivative = (roll_error - roll_prev_error) / dt if dt > 0 else 0
        roll_prev_error = roll_error
        roll_output = KP*roll_error + KI*roll_integral + KD*roll_derivative
        roll_servo.value = angle_to_servo(roll_output, MAX_ROLL_ANGLE)

        # Pitch
        pitch_error = -pitch_angle
        pitch_integral += pitch_error * dt
        pitch_derivative = (pitch_error - pitch_prev_error) / dt if dt > 0 else 0
        pitch_prev_error = pitch_error
        pitch_output = KP*pitch_error + KI*pitch_integral + KD*pitch_derivative
        pitch_servo.value = -angle_to_servo(pitch_output, MAX_PITCH_ANGLE)

        print(f"Roll: {roll_angle:6.1f}° → {roll_output:6.1f} | "
              f"Pitch: {pitch_angle:6.1f}° → {pitch_output:6.1f}°")

        time.sleep(UPDATE_DELAY)

except KeyboardInterrupt:
    print("\nStopping test...")

finally:
    roll_servo.value = 0
    pitch_servo.value = 0
    roll_servo.close()
    pitch_servo.close()
    print("Servos centered. Test finished.")