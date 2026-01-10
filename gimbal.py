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
    """
    Camera gimbal with roll stabilization and fixed pitch angle.
    Uses complementary filter + PID control for smooth stabilization.
    """
    
    def __init__(self, roll_pin, pitch_pin, use_mpu6050=True, mpu6050_address=0x68):
        """
        Initialize gimbal servos and IMU
        
        Args:
            roll_pin: GPIO pin for roll servo
            pitch_pin: GPIO pin for pitch servo
            use_mpu6050: Use MPU6050 IMU for stabilization
            mpu6050_address: I2C address of MPU6050
        """
        self.use_mpu6050 = use_mpu6050
        self.enabled = False
        
        # Convert pulse widths from microseconds to seconds
        servo_min = config.GIMBAL_SERVO_MIN_PULSE / 1_000_000
        servo_max = config.GIMBAL_SERVO_MAX_PULSE / 1_000_000
        
        # Initialize servos
        self.roll_servo = Servo(
            roll_pin, 
            min_pulse_width=servo_min, 
            max_pulse_width=servo_max
        )
        self.pitch_servo = Servo(
            pitch_pin,
            min_pulse_width=servo_min,
            max_pulse_width=servo_max
        )
        
        # Set pitch to fixed 45° downward position
        self.pitch_servo.value = config.GIMBAL_PITCH_FIXED_POSITION
        logger.info(f"Pitch servo set to fixed position: {config.GIMBAL_PITCH_FIXED_POSITION}")
        
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
        
        # Maximum roll correction angle (degrees)
        self.max_roll_angle = 20.0
        
        logger.info("Gimbal initialized - Roll stabilization ACTIVE, Pitch FIXED at 45°")
    
    def _clamp(self, value, min_val, max_val):
        """Clamp value between min and max"""
        return max(min(value, max_val), min_val)
    
    def _accel_to_roll(self, accel):
        """Calculate roll angle from accelerometer data"""
        roll = math.degrees(math.atan2(accel["y"], accel["z"]))
        return roll
    
    def _angle_to_servo(self, angle, max_angle):
        """Convert angle to servo value [-1, +1]"""
        angle = self._clamp(angle, -max_angle, max_angle)
        return angle / max_angle
    
    def update(self, drone_roll=None, drone_pitch=None):
        """
        Update gimbal stabilization
        
        Args:
            drone_roll: Drone's roll angle (degrees) - used if MPU6050 unavailable
            drone_pitch: Drone's pitch angle (degrees) - ignored (pitch is fixed)
        """
        if not self.enabled:
            return
        
        # Calculate delta time
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time
        
        if dt <= 0:
            return
        
        # Get roll angle from MPU6050 or fallback to drone telemetry
        if self.use_mpu6050 and self.imu:
            try:
                # Read IMU data
                accel = self.imu.get_accel_data()
                gyro = self.imu.get_gyro_data()  # degrees/sec
                
                # Calculate roll from accelerometer
                accel_roll = self._accel_to_roll(accel)
                
                # Complementary filter
                self.roll_angle = (
                    config.MPU6050_ALPHA * (self.roll_angle + gyro["x"] * dt) + 
                    (1 - config.MPU6050_ALPHA) * accel_roll
                )
                
            except Exception as e:
                logger.debug(f"IMU read error: {e}")
                # Fallback to drone telemetry
                if drone_roll is not None:
                    self.roll_angle = drone_roll
        else:
            # Use drone telemetry
            if drone_roll is not None:
                self.roll_angle = drone_roll
        
        # PID control for roll stabilization
        roll_error = -self.roll_angle  # Negative to oppose the tilt
        self.roll_integral += roll_error * dt
        roll_derivative = (roll_error - self.roll_prev_error) / dt
        self.roll_prev_error = roll_error
        
        # Calculate PID output
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
        """Disable gimbal stabilization and center servos"""
        self.enabled = False
        self.roll_servo.value = 0  # Center roll
        self.pitch_servo.value = config.GIMBAL_PITCH_FIXED_POSITION  # Keep pitch fixed
        logger.info("Gimbal stabilization DISABLED - servos centered")
    
    def cleanup(self):
        """Clean up resources"""
        self.disable()
        self.roll_servo.close()
        self.pitch_servo.close()
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
    
    # Initialize gimbal
    gimbal = CameraGimbal(
        roll_pin=config.GIMBAL_ROLL_PIN,
        pitch_pin=config.GIMBAL_PITCH_PIN,
        use_mpu6050=config.USE_MPU6050,
        mpu6050_address=config.MPU6050_I2C_ADDRESS
    )
    
    print(f"✓ Roll servo on GPIO {config.GIMBAL_ROLL_PIN}")
    print(f"✓ Pitch servo on GPIO {config.GIMBAL_PITCH_PIN} (FIXED at 45°)")
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
        print("✓ Test complete. Servos centered.")


def test_pitch_calibration():
    """
    Interactive pitch servo calibration tool.
    Helps find the correct value for 45° downward angle.
    """
    print("=" * 60)
    print("🎯 PITCH SERVO CALIBRATION MODE")
    print("=" * 60)
    print("This tool helps you find the correct pitch servo value.")
    print()
    
    # Convert pulse widths from microseconds to seconds
    servo_min = config.GIMBAL_SERVO_MIN_PULSE / 1_000_000
    servo_max = config.GIMBAL_SERVO_MAX_PULSE / 1_000_000
    
    # Initialize only pitch servo
    pitch_servo = Servo(
        config.GIMBAL_PITCH_PIN,
        min_pulse_width=servo_min,
        max_pulse_width=servo_max
    )
    
    print(f"Pitch servo initialized on GPIO {config.GIMBAL_PITCH_PIN}")
    print()
    print("Commands:")
    print("  Enter a value between -1.0 and +1.0")
    print("  'q' to quit")
    print()
    print("Typical values:")
    print("  -1.0 = Maximum down")
    print("  -0.5 = 45° down (typical)")
    print("   0.0 = Center (90°)")
    print("  +0.5 = 45° up")
    print("  +1.0 = Maximum up")
    print("=" * 60)
    
    try:
        # Start at current config value
        current_value = config.GIMBAL_PITCH_FIXED_POSITION
        pitch_servo.value = current_value
        print(f"\nCurrent value: {current_value:+.2f}")
        
        while True:
            user_input = input("\nEnter servo value (-1.0 to +1.0): ").strip()
            
            if user_input.lower() == 'q':
                break
            
            try:
                value = float(user_input)
                if -1.0 <= value <= 1.0:
                    pitch_servo.value = value
                    print(f"✓ Pitch servo set to: {value:+.2f}")
                    print(f"  Update config.py: GIMBAL_PITCH_FIXED_POSITION = {value}")
                else:
                    print("⚠ Value must be between -1.0 and +1.0")
            except ValueError:
                print("⚠ Invalid input. Enter a number or 'q' to quit.")
    
    except KeyboardInterrupt:
        print("\n⚠ Calibration interrupted")
    
    finally:
        print("\nCentering servo...")
        pitch_servo.value = 0
        pitch_servo.close()
        print("✓ Calibration complete.")


if __name__ == "__main__":
    import sys
    
    # Check for calibration mode
    if len(sys.argv) > 1 and sys.argv[1] == "calibrate":
        test_pitch_calibration()
    else:
        # Run standalone test when executed directly
        test_gimbal()