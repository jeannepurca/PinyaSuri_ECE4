#!/usr/bin/env python3
# gimbal.py - Optimized with reduced IMU read frequency

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
        
        # IMU read rate limiting (read every N updates)
        self.imu_update_interval = 2  # Read IMU every 2 updates (25Hz instead of 50Hz)
        self.update_counter = 0
        
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
        self.last_imu_time = time.time()
        
        # Cached IMU values (used between reads)
        self.last_gyro_x = 0.0
        self.last_accel_roll = 0.0
        
        # Maximum roll correction angle
        self.max_roll_angle = 45.0
        
        # Integral limit
        self.max_integral = 5.0
        
        # Deadband threshold
        self.deadband = 0.5  # degrees

        logger.info("Gimbal initialized - Roll stabilization ACTIVE (pitch is physically fixed)")

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
        Only reads IMU every N cycles to reduce I2C overhead
        """
        if not self.enabled:
            return
        
        # Calculate ACTUAL delta time
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time
        
        # Sanity check: reject unrealistic dt values
        if dt <= 0 or dt > 0.1:
            logger.debug(f"Skipping update - invalid dt: {dt}")
            return
        
        # Only read IMU periodically (not every update)
        self.update_counter += 1
        if self.update_counter >= self.imu_update_interval:
            self.update_counter = 0
            
            if self.use_mpu6050 and self.imu:
                try:
                    # Read IMU data
                    accel = self.imu.get_accel_data()
                    gyro = self.imu.get_gyro_data()
                    
                    # Cache values
                    self.last_gyro_x = gyro["x"]
                    self.last_accel_roll = self._accel_to_roll(accel)
                    self.last_imu_time = current_time

                except Exception as e:
                    logger.debug(f"IMU read error: {e}")
                    # Continue with last known values
        
        # Calculate dt since last IMU read
        imu_dt = current_time - self.last_imu_time
        
        # Complementary filter using cached IMU values
        self.roll_angle = (
            config.MPU6050_ALPHA * (self.roll_angle + self.last_gyro_x * dt) + 
            (1 - config.MPU6050_ALPHA) * self.last_accel_roll
        )

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
        roll_derivative = (roll_error - self.roll_prev_error) / dt
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
        self.last_imu_time = time.time()
        self.update_counter = 0
        logger.info("Gimbal stabilization ENABLED")
    
    def disable(self):
        """Disable gimbal stabilization and center servo"""
        self.enabled = False
        self.roll_servo.value = 0
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
    """
    print("=" * 60)
    print("🎥 GIMBAL STANDALONE TEST MODE (OPTIMIZED)")
    print("=" * 60)
    print("Initializing gimbal system...")
    
    gimbal = CameraGimbal(
        roll_pin=config.GIMBAL_ROLL_PIN,
        use_mpu6050=config.USE_MPU6050,
        mpu6050_address=config.MPU6050_I2C_ADDRESS
    )
    
    print(f"✓ Roll servo on GPIO {config.GIMBAL_ROLL_PIN}")
    print(f"✓ Pitch: Physically fixed at 45° downward")
    print(f"✓ MPU6050 at 0x{config.MPU6050_I2C_ADDRESS:02X}")
    print(f"✓ Servo update rate: 50 Hz")
    print(f"✓ IMU read rate: {50/gimbal.imu_update_interval:.0f} Hz")
    print(f"✓ PID gains: Kp={config.GIMBAL_PID_KP}, Ki={config.GIMBAL_PID_KI}, Kd={config.GIMBAL_PID_KD}")
    print("=" * 60)
    print("Gimbal stabilization starting... Tilt the IMU!")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    gimbal.enable()
    
    try:
        while True:
            gimbal.update()
            
            # Print current state occasionally
            if gimbal.update_counter == 0:  # Only when IMU was just read
                print(f"Roll: {gimbal.roll_angle:6.1f}° | "
                      f"Servo: {gimbal.roll_servo.value:+.3f} | "
                      f"Integral: {gimbal.roll_integral:6.2f}")
            
            time.sleep(0.02)  # 50 Hz
            
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("⚠ Test stopped by user")
        print("=" * 60)
    
    finally:
        print("Cleaning up...")
        gimbal.cleanup()
        print("✓ Test complete. Servo centered.")


if __name__ == "__main__":
    test_gimbal()