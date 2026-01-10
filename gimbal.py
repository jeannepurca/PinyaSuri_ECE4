#!/usr/bin/env python3
# gimbal.py

import time
import math
from gpiozero import Servo
from mpu6050 import mpu6050

class CameraGimbal:
    """2-axis gimbal stabilization maintaining 45° downward pitch"""
    
    def __init__(self, roll_pin=17, pitch_pin=27, target_pitch=-45.0, 
                 max_roll_compensation=20.0, use_mpu6050=True, mpu6050_address=0x68):
        
        # Configuration
        self.target_pitch = target_pitch  # -45° downward
        self.max_roll = max_roll_compensation
        self.use_mpu6050 = use_mpu6050
        
        # PID gains
        self.kp = 0.6
        self.ki = 0.05
        self.kd = 0.03
        
        # Complementary filter
        self.alpha = 0.98
        
        # SERVO OFFSET: This maps the desired camera angle to servo position
        # When IMU is at 0°, we want camera at -45°
        # Adjust this value based on your physical servo mounting
        self.pitch_servo_offset = -0.5  # Start at -0.5 (adjust as needed: -1.0 to +1.0)
        
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
        self.pitch_servo.value = self.pitch_servo_offset
    
    def enable(self):
        """Enable gimbal stabilization"""
        self.enabled = True
        self.reset_pid()
        self.pitch_servo.value = self.pitch_servo_offset
        print(f"Gimbal enabled - maintaining {abs(self.target_pitch)}° downward pitch")
    
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
        Update gimbal stabilization
        
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
        
        # --- PID correction for Roll (stabilize to 0°) ---
        roll_error = -self.roll_angle
        self.roll_integral += roll_error * dt
        roll_derivative = (roll_error - self.roll_prev_error) / dt if dt > 0 else 0
        self.roll_prev_error = roll_error
        roll_output = self.kp * roll_error + self.ki * self.roll_integral + self.kd * roll_derivative
        self.roll_servo.value = self._angle_to_servo(roll_output, self.max_roll)
        
        # --- PID correction for Pitch (maintain target angle) ---
        # Error = how much we deviate from target
        # If drone pitches down (-10°), we need servo to go UP (+10°) to compensate
        pitch_error = -self.pitch_angle  # Inverted: drone down → servo up
        
        self.pitch_integral += pitch_error * dt
        pitch_derivative = (pitch_error - self.pitch_prev_error) / dt if dt > 0 else 0
        self.pitch_prev_error = pitch_error
        pitch_output = self.kp * pitch_error + self.ki * self.pitch_integral + self.kd * pitch_derivative
        
        # Apply correction + base offset for 45° downward
        servo_position = self.pitch_servo_offset + self._angle_to_servo(pitch_output, self.max_roll)
        servo_position = self._clamp(servo_position, -1.0, 1.0)
        
        self.pitch_servo.value = servo_position
    
    def set_pitch_offset(self, offset):
        """
        Manually adjust pitch servo offset for calibration
        offset: -1.0 to +1.0 (negative = more downward)
        """
        self.pitch_servo_offset = self._clamp(offset, -1.0, 1.0)
        print(f"Pitch servo offset set to: {self.pitch_servo_offset:.2f}")
    
    def cleanup(self):
        """Clean up resources"""
        self.disable()
        self.roll_servo.close()
        self.pitch_servo.close()
        print("Gimbal cleanup complete")


# Standalone test mode with calibration
if __name__ == "__main__":
    print("=" * 60)
    print("GIMBAL CALIBRATION & TEST MODE")
    print("=" * 60)
    print("This will help you find the correct pitch servo offset")
    print("to achieve 45° downward camera angle when IMU is level")
    print("=" * 60)
    
    gimbal = CameraGimbal(use_mpu6050=True)
    gimbal.enable()
    
    print("\nCOMMANDS:")
    print("  Press ENTER to see current status")
    print("  Type offset value (-1.0 to +1.0) to adjust pitch")
    print("  Examples: -0.3, -0.5, -0.7 (more negative = more downward)")
    print("  Type 'q' to quit")
    print("\nCurrent offset:", gimbal.pitch_servo_offset)
    
    try:
        while True:
            gimbal.update()
            
            # Non-blocking input check
            import select
            import sys
            
            if select.select([sys.stdin], [], [], 0.02)[0]:
                user_input = input().strip().lower()
                
                if user_input == 'q':
                    break
                elif user_input == '':
                    print(f"\nStatus:")
                    print(f"  IMU Pitch: {gimbal.pitch_angle:6.1f}°")
                    print(f"  Servo offset: {gimbal.pitch_servo_offset:+.2f}")
                    print(f"  Servo position: {gimbal.pitch_servo.value:+.2f}")
                    print(f"  Roll: {gimbal.roll_angle:6.1f}°")
                else:
                    try:
                        offset = float(user_input)
                        gimbal.set_pitch_offset(offset)
                    except ValueError:
                        print("Invalid input. Use number between -1.0 and +1.0")
            
            time.sleep(0.02)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        print(f"\nFinal offset value: {gimbal.pitch_servo_offset}")
        print("Add this to your config.py:")
        print(f"  GIMBAL_PITCH_SERVO_OFFSET = {gimbal.pitch_servo_offset}")
        gimbal.cleanup()