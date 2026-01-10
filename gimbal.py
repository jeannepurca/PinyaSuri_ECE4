#!/usr/bin/env python3
# gimbal.py

import time
import math
from gpiozero import Servo
from mpu6050 import mpu6050

class CameraGimbal:
    """2-axis gimbal stabilization - servo stabilizes to level, camera mounted at 45°"""
    
    def __init__(self, roll_pin=17, pitch_pin=27, target_pitch=-225.0, 
                 max_roll_compensation=20.0, use_mpu6050=True, mpu6050_address=0x68):
        
        # Configuration
        self.max_roll = max_roll_compensation
        self.max_pitch = max_roll_compensation
        self.use_mpu6050 = use_mpu6050
        
        # PID gains (same as testgim.py)
        self.kp = 0.6
        self.ki = 0.05
        self.kd = 0.03
        
        # Complementary filter
        self.alpha = 0.98
        
        # Initialize servos
        servo_min = 0.0005
        servo_max = 0.0025
        self.roll_servo = Servo(roll_pin, min_pulse_width=servo_min, max_pulse_width=servo_max)
        self.pitch_servo = Servo(pitch_pin, min_pulse_width=servo_min, max_pulse_width=servo_max)
        
        # Initialize IMU if enabled
        self.imu = None
        if self.use_mpu6050:
            try:
                self.imu = mpu6050(mpu6050_address)
            except Exception as e:
                print(f"Warning: Could not initialize MPU6050: {e}")
                self.use_mpu6050 = False
        
        # State variables
        self.enabled = False
        self.roll_angle = 0.0
        self.pitch_angle = 0.0
        self.last_time = time.time()
        
        # PID state
        self.roll_integral = 0
        self.roll_prev_error = 0
        self.pitch_integral = 0
        self.pitch_prev_error = 0
        
        # Center servos initially
        self.roll_servo.value = 0
        self.pitch_servo.value = 0
    
    def enable(self):
        """Enable gimbal stabilization"""
        self.enabled = True
        self.reset_pid()
        print("Gimbal enabled - stabilizing to level (camera mounted at 45° down)")
    
    def disable(self):
        """Disable gimbal and center servos"""
        self.enabled = False
        self.roll_servo.value = 0
        self.pitch_servo.value = 0
        self.reset_pid()
        print("Gimbal disabled and centered")
    
    def reset_pid(self):
        """Reset PID integrators"""
        self.roll_integral = 0
        self.roll_prev_error = 0
        self.pitch_integral = 0
        self.pitch_prev_error = 0
    
    def _clamp(self, value, min_val, max_val):
        """Clamp value between min and max"""
        return max(min(value, max_val), min_val)
    
    def _accel_to_angles(self, accel):
        """Convert accelerometer data to roll/pitch angles"""
        roll = math.degrees(math.atan2(accel["y"], accel["z"]))
        pitch = math.degrees(math.atan2(-accel["x"], math.sqrt(accel["y"]**2 + accel["z"]**2)))
        return roll, pitch
    
    def _angle_to_servo(self, angle, max_angle):
        """Convert angle to servo value [-1, +1]"""
        angle = self._clamp(angle, -max_angle, max_angle)
        return angle / max_angle
    
    def update(self, drone_roll=None, drone_pitch=None):
        """
        Update gimbal stabilization (EXACTLY like testgim.py)
        
        Args:
            drone_roll: Current drone roll angle (optional, uses IMU if not provided)
            drone_pitch: Current drone pitch angle (optional, uses IMU if not provided)
        """
        if not self.enabled:
            return
        
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time
        
        # Get current angles (from IMU or drone telemetry)
        if self.use_mpu6050 and self.imu and (drone_roll is None or drone_pitch is None):
            # Use IMU data
            try:
                accel = self.imu.get_accel_data()
                gyro = self.imu.get_gyro_data()
                accel_roll, accel_pitch = self._accel_to_angles(accel)
                
                # Complementary filter
                self.roll_angle = self.alpha * (self.roll_angle + gyro["x"] * dt) + (1 - self.alpha) * accel_roll
                self.pitch_angle = self.alpha * (self.pitch_angle + gyro["y"] * dt) + (1 - self.alpha) * accel_pitch
            except Exception as e:
                print(f"IMU read error: {e}")
                return
        else:
            # Use drone telemetry data
            if drone_roll is not None:
                self.roll_angle = drone_roll
            if drone_pitch is not None:
                self.pitch_angle = drone_pitch
        
        # --- PID correction for Roll (EXACTLY like testgim.py) ---
        roll_error = -self.roll_angle
        self.roll_integral += roll_error * dt
        roll_derivative = (roll_error - self.roll_prev_error) / dt if dt > 0 else 0
        self.roll_prev_error = roll_error
        roll_output = self.kp * roll_error + self.ki * self.roll_integral + self.kd * roll_derivative
        self.roll_servo.value = self._angle_to_servo(roll_output, self.max_roll)
        
        # --- PID correction for Pitch (EXACTLY like testgim.py) ---
        pitch_error = -self.pitch_angle
        self.pitch_integral += pitch_error * dt
        pitch_derivative = (pitch_error - self.pitch_prev_error) / dt if dt > 0 else 0
        self.pitch_prev_error = pitch_error
        pitch_output = self.kp * pitch_error + self.ki * self.pitch_integral + self.kd * pitch_derivative
        
        # EXACTLY like testgim.py: negated output
        self.pitch_servo.value = -self._angle_to_servo(pitch_output, self.max_pitch)
    
    def cleanup(self):
        """Clean up resources"""
        self.disable()
        self.roll_servo.close()
        self.pitch_servo.close()
        print("Gimbal cleanup complete")


# Standalone test mode
if __name__ == "__main__":
    print("=" * 60)
    print("GIMBAL TEST MODE (Same logic as testgim.py)")
    print("=" * 60)
    print("Servo stabilizes to keep IMU level (0°)")
    print("Mount camera at 45° angle on the servo for downward view")
    print("Press Ctrl+C to exit")
    print("=" * 60)
    
    gimbal = CameraGimbal(use_mpu6050=True)
    gimbal.enable()
    
    try:
        while True:
            gimbal.update()
            print(f"Roll: {gimbal.roll_angle:6.1f}° → servo: {gimbal.roll_servo.value:+.2f} | "
                  f"Pitch: {gimbal.pitch_angle:6.1f}° → servo: {gimbal.pitch_servo.value:+.2f}")
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        gimbal.cleanup()