#!/usr/bin/env python3
# gimbal.py

import time
import math
import logging
from gpiozero import Servo
from mpu6050 import mpu6050

import config

logger = logging.getLogger(__name__)

class CameraGimbal:    
    def __init__(self, roll_pin, use_mpu6050=True, mpu6050_address=0x68):
        """
        Initialize gimbal servo and IMU
        """
        self.use_mpu6050 = use_mpu6050
        self.enabled = False
        
        # Add filtered sensor values
        self.filtered_gyro_x = 0.0
        self.filtered_accel_roll = 0.0
        self.filter_alpha = 0.1  # Lower = smoother but slower response

        # Convert pulse widths from microseconds to seconds
        servo_min = config.GIMBAL_SERVO_MIN_PULSE / 1_000_000
        servo_max = config.GIMBAL_SERVO_MAX_PULSE / 1_000_000
        
        # Initialize roll servo only
        self.roll_servo = Servo(
            roll_pin, 
            min_pulse_width=servo_min, 
            max_pulse_width=servo_max
        )
        
        # Initialize MPU6050 if enabled
        self.imu = None
        if self.use_mpu6050:
            try:
                self.imu = mpu6050(mpu6050_address)
                logger.info(f"MPU6050 initialized at address 0x{mpu6050_address:02X}")
            except Exception as e:
                logger.warning(f"MPU6050 initialization failed: {e}")
                self.use_mpu6050 = False
        
        # PID state for roll only
        self.roll_integral = 0
        self.roll_prev_error = 0
        
        # Complementary filter state
        self.roll_angle = 0.0
        self.last_time = time.time()
        
        # INCREASE maximum roll correction angle
        self.max_roll_angle = 45.0  # Was 20.0 - increase servo authority
        
        # Reduce integral limit to prevent aggressive windup
        self.max_integral = 5.0  # Was 10.0
        
        # Add deadband threshold
        self.deadband = 0.5  # degrees

        logger.info("Gimbal initialized - Roll stabilization ACTIVE (pitch is physically fixed)")

    def _low_pass_filter(self, new_value, old_value, alpha):
        """Simple low-pass filter"""
        return alpha * new_value + (1 - alpha) * old_value

    def _clamp(self, value, min_val, max_val):
        """Clamp value between min and max"""
        return max(min(value, max_val), min_val)
    
    def _accel_to_roll(self, accel):
        """Calculate roll angle from accelerometer data"""
        return math.degrees(math.atan2(accel["y"], accel["z"]))
    
    def _angle_to_servo(self, angle, max_angle):
        """Convert angle to servo value [-1, +1]"""
        angle = self._clamp(angle, -max_angle, max_angle)
        return angle / max_angle
    
    def update(self):
        """
        Update gimbal stabilization
        """
        if not self.enabled:
            return
        
        # Calculate delta time
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time
        
        if dt <= 0:
            return
        
        if self.use_mpu6050 and self.imu:
            try:
                # Read IMU data
                accel = self.imu.get_accel_data()
                gyro = self.imu.get_gyro_data()  # degrees/sec
                
                # Calculate roll from accelerometer
                accel_roll = self._accel_to_roll(accel)
                
                # Low-pass filter raw sensor readings
                self.filtered_gyro_x = self._low_pass_filter(
                    gyro["x"], self.filtered_gyro_x, self.filter_alpha
                )
                
                self.filtered_accel_roll = self._low_pass_filter(
                    accel_roll, self.filtered_accel_roll, self.filter_alpha
                )
                
                # Complementary filter
                roll_angle_new = (
                    config.MPU6050_ALPHA * (self.roll_angle + self.filtered_gyro_x * dt) + 
                    (1 - config.MPU6050_ALPHA) * self.filtered_accel_roll
                )

                # ADDITIONAL LOW-PASS FILTER on final roll angle
                self.roll_angle = self._low_pass_filter(roll_angle_new, self.roll_angle, self.filter_alpha)

            except Exception as e:
                logger.debug(f"IMU read error: {e}")
                return  # keep last valid roll_angle

        # PID control for roll stabilization
        roll_error = -self.roll_angle

        # Apply deadband
        if abs(roll_error) < self.deadband:
            roll_error = 0
            self.roll_integral *= 0.95

        # Anti-windup integral
        self.roll_integral = self._clamp(
            self.roll_integral + roll_error * dt,
            -self.max_integral,
            self.max_integral
        )

        # Derivative
        roll_derivative = (roll_error - self.roll_prev_error) / dt if roll_error != 0 else 0
        self.roll_prev_error = roll_error

        # PID output
        roll_output = (
            config.GIMBAL_PID_KP * roll_error + 
            config.GIMBAL_PID_KI * self.roll_integral + 
            config.GIMBAL_PID_KD * roll_derivative
        )

        # Apply to servo
        self.roll_servo.value = self._angle_to_servo(roll_output, self.max_roll_angle)

    
    def enable(self):
        """Enable gimbal stabilization"""
        self.enabled = True
        self.roll_integral = 0
        self.roll_prev_error = 0
        self.last_time = time.time()
        logger.info("Gimbal stabilization ENABLED")
    
    def disable(self):
        """Disable gimbal stabilization and center servo"""
        self.enabled = False
        self.roll_servo.value = 0  # Center roll
        logger.info("Gimbal stabilization DISABLED - servo centered")
    
    def cleanup(self):
        """Clean up resources"""
        self.disable()
        self.roll_servo.close()
        logger.info("Gimbal cleanup complete")


# ============================================================================
# STANDALONE TEST MODE
# ============================================================================

def test_gimbal():
    """
    Standalone test mode for gimbal stabilization.
    Runs independently without drone connection.
    """
    print("=" * 60)
    print("🎥 GIMBAL STANDALONE TEST MODE")
    print("=" * 60)
    print("Initializing gimbal system...")
    
    # Initialize gimbal (roll only)
    gimbal = CameraGimbal(
        roll_pin=config.GIMBAL_ROLL_PIN,
        use_mpu6050=config.USE_MPU6050,
        mpu6050_address=config.MPU6050_I2C_ADDRESS
    )
    
    print(f"✓ Roll servo on GPIO {config.GIMBAL_ROLL_PIN}")
    print(f"✓ Pitch: Physically fixed at 45° downward")
    print(f"✓ MPU6050 at 0x{config.MPU6050_I2C_ADDRESS:02X}")
    print(f"✓ Update rate: 50 Hz")
    print(f"✓ PID gains: Kp={config.GIMBAL_PID_KP}, Ki={config.GIMBAL_PID_KI}, Kd={config.GIMBAL_PID_KD}")
    print("=" * 60)
    print("Gimbal stabilization starting... Tilt the IMU!")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    # Enable stabilization
    gimbal.enable()
    
    try:
        while True:
            # Update gimbal (no drone data in test mode, uses only IMU)
            gimbal.update()
            
            # Print current state
            print(f"Roll: {gimbal.roll_angle:6.1f}° | "
                  f"Servo: {gimbal.roll_servo.value:+.3f} | "
                  f"Integral: {gimbal.roll_integral:6.2f}")
            
            time.sleep(0.02)  # 50 Hz update rate
            
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("⚠ Test stopped by user")
        print("=" * 60)
    
    finally:
        print("Cleaning up...")
        gimbal.cleanup()
        print("✓ Test complete. Servo centered.")


if __name__ == "__main__":
    # Run standalone test when executed directly
    test_gimbal()