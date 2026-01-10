#!/usr/bin/env python3
# gimbal.py

import time
import math
from gpiozero import Servo
from mpu6050 import mpu6050

class CameraGimbal:
    """2-axis gimbal - Roll stabilization + Fixed 45° pitch"""
    
    def __init__(self, roll_pin=17, pitch_pin=27, target_pitch=-45.0, 
                 max_roll_compensation=20.0, use_mpu6050=True, mpu6050_address=0x68):
        
        # Configuration
        self.target_pitch = target_pitch  # -45° downward (FIXED position)
        self.max_roll = max_roll_compensation
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
        
        # Calculate fixed pitch servo position for 45° downward
        # Adjust this value based on your servo's physical range
        # Negative value = downward tilt
        self.pitch_servo_fixed_position = -0.8  # Adjust between -1.0 to 0.0 for 45° down
        
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
        
        # PID state (only for roll)
        self.roll_integral = 0
        self.roll_prev_error = 0
        
        # Center servos initially
        self.roll_servo.value = 0
        self.pitch_servo.value = 0
    
    def enable(self):
        """Enable gimbal stabilization"""
        self.enabled = True
        self.reset_pid()
        
        # Set pitch to fixed 45° downward position
        self.pitch_servo.value = self.pitch_servo_fixed_position
        
        print(f"Gimbal enabled - Pitch FIXED at {abs(self.target_pitch)}° down, Roll stabilization ACTIVE")
    
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
        Update gimbal stabilization
        - Roll: Active PID stabilization (EXACTLY like testgim.py)
        - Pitch: Fixed at 45° downward (no movement)
        
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
                
                # Complementary filter (EXACTLY like testgim.py)
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
        
        # --- PID correction for Roll ONLY (EXACTLY like testgim.py) ---
        roll_error = -self.roll_angle
        self.roll_integral += roll_error * dt
        roll_derivative = (roll_error - self.roll_prev_error) / dt if dt > 0 else 0
        self.roll_prev_error = roll_error
        roll_output = self.kp * roll_error + self.ki * self.roll_integral + self.kd * roll_derivative
        self.roll_servo.value = self._angle_to_servo(roll_output, self.max_roll)
        
        # --- Pitch: Keep FIXED at 45° downward (NO MOVEMENT) ---
        # Pitch servo doesn't move - it stays at the fixed position set during enable()
        # self.pitch_servo.value remains at self.pitch_servo_fixed_position
    
    def set_pitch_angle(self, servo_value):
        """
        Manually adjust the fixed pitch servo position
        servo_value: -1.0 to 0.0 (negative = downward)
        """
        self.pitch_servo_fixed_position = self._clamp(servo_value, -1.0, 0.0)
        if self.enabled:
            self.pitch_servo.value = self.pitch_servo_fixed_position
        print(f"Pitch servo fixed position set to: {self.pitch_servo_fixed_position:.2f}")
    
    def cleanup(self):
        """Clean up resources"""
        self.disable()
        self.roll_servo.close()
        self.pitch_servo.close()
        print("Gimbal cleanup complete")


# Standalone test mode
if __name__ == "__main__":
    print("=" * 60)
    print("GIMBAL TEST - Roll Stabilization + Fixed 45° Pitch")
    print("=" * 60)
    print("Pitch servo: FIXED at 45° downward (no movement)")
    print("Roll servo: Active stabilization (moves opposite to tilt)")
    print("=" * 60)
    print("\nCalibration mode: Find the right pitch servo value")
    print("Commands:")
    print("  Press ENTER to see current status")
    print("  Type servo value (-1.0 to 0.0) to adjust pitch angle")
    print("  Example: -0.5, -0.7, -0.9 (more negative = more downward)")
    print("  Type 'q' to start normal operation")
    print("=" * 60)
    
    gimbal = CameraGimbal(use_mpu6050=True)
    
    # Calibration loop
    try:
        while True:
            user_input = input("\nEnter pitch value or 'q' to start: ").strip().lower()
            
            if user_input == 'q':
                break
            elif user_input == '':
                print(f"Current pitch servo position: {gimbal.pitch_servo_fixed_position:.2f}")
                print("Adjust until camera points exactly 45° downward when level")
            else:
                try:
                    value = float(user_input)
                    gimbal.pitch_servo.value = gimbal._clamp(value, -1.0, 0.0)
                    gimbal.pitch_servo_fixed_position = gimbal._clamp(value, -1.0, 0.0)
                    print(f"Pitch servo set to: {gimbal.pitch_servo_fixed_position:.2f}")
                except ValueError:
                    print("Invalid input. Use number between -1.0 and 0.0")
    
    except KeyboardInterrupt:
        print("\nExiting calibration...")
        gimbal.cleanup()
        exit()
    
    # Normal operation
    print("\n" + "=" * 60)
    print("Starting normal operation...")
    print(f"Pitch: FIXED at {gimbal.pitch_servo_fixed_position:.2f}")
    print("Roll: Active stabilization")
    print("Press Ctrl+C to exit")
    print("=" * 60 + "\n")
    
    gimbal.enable()
    
    try:
        while True:
            gimbal.update()
            print(f"Roll: {gimbal.roll_angle:6.1f}° → servo: {gimbal.roll_servo.value:+.2f} | "
                  f"Pitch: FIXED at {gimbal.pitch_servo_fixed_position:+.2f}")
            time.sleep(0.02)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        print(f"\nSave this pitch value to your config:")
        print(f"  GIMBAL_PITCH_FIXED_POSITION = {gimbal.pitch_servo_fixed_position}")
        gimbal.cleanup()