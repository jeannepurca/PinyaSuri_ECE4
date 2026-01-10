#!/usr/bin/env python3
# simple_pid_gimbal_test.py
# MPU6050 + roll/pitch correction (mini PID)

import time
import math
from gpiozero import Servo
from mpu6050 import mpu6050

# -----------------------------
# CONFIGURATION
# -----------------------------
ROLL_SERVO_PIN = 17
PITCH_SERVO_PIN = 27

MAX_ROLL_ANGLE = 20.0   # max servo correction
MAX_PITCH_ANGLE = 20.0

UPDATE_DELAY = 0.02     # 50 Hz loop

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
# HELPER FUNCTIONS
# -----------------------------
def accel_to_angles(accel):
    roll = math.degrees(math.atan2(accel["y"], accel["z"]))
    pitch = math.degrees(math.atan2(-accel["x"], math.sqrt(accel["y"]**2 + accel["z"]**2)))
    return roll, pitch

def clamp(value, min_val, max_val):
    return max(min(value, max_val), min_val)

def angle_to_servo(angle, max_angle):
    angle = clamp(angle, -max_angle, max_angle)
    return angle / max_angle  # [-1, +1]

# -----------------------------
# MAIN LOOP
# -----------------------------
try:
    print("Simple PID gimbal test started. Tilt the IMU!")
    last_time = time.time()
    
    while True:
        current_time = time.time()
        dt = current_time - last_time
        last_time = current_time

        # Read IMU
        accel = imu.get_accel_data()
        roll, pitch = accel_to_angles(accel)

        # --- PID for roll ---
        roll_error = -roll  # goal: keep gimbal level
        roll_integral += roll_error * dt
        roll_derivative = (roll_error - roll_prev_error) / dt if dt > 0 else 0
        roll_prev_error = roll_error

        roll_output = KP*roll_error + KI*roll_integral + KD*roll_derivative
        roll_servo.value = angle_to_servo(roll_output, MAX_ROLL_ANGLE)

        # --- PID for pitch ---
        pitch_error = -pitch
        pitch_integral += pitch_error * dt
        pitch_derivative = (pitch_error - pitch_prev_error) / dt if dt > 0 else 0
        pitch_prev_error = pitch_error

        pitch_output = KP*pitch_error + KI*pitch_integral + KD*pitch_derivative
        pitch_servo.value = -angle_to_servo(pitch_output, MAX_PITCH_ANGLE)

        # Print status
        print(f"Roll: {roll:6.1f}° → {roll_output:6.1f}° | "
              f"Pitch: {pitch:6.1f}° → {pitch_output:6.1f}°")

        time.sleep(UPDATE_DELAY)

except KeyboardInterrupt:
    print("\nStopping test...")

finally:
    roll_servo.value = 0
    pitch_servo.value = 0
    roll_servo.close()
    pitch_servo.close()
    print("Servos centered. Test finished.")