#!/usr/bin/env python3
# gimbal.py - Debug version to identify jitter source

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
        
        # Performance tracking
        self.update_count = 0
        self.slow_updates = 0
        self.imu_errors = 0
        
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
        Update gimbal stabilization with performance monitoring
        """
        if not self.enabled:
            return
        
        update_start = time.time()
        
        # Calculate ACTUAL delta time
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time
        
        # Track performance
        self.update_count += 1
        
        # Sanity check: reject unrealistic dt values
        if dt <= 0 or dt > 0.1:
            logger.warning(f"⚠ INVALID dt: {dt:.4f}s - Skipping update #{self.update_count}")
            return
        
        # Warn about slow updates (>30ms = <33Hz)
        if dt > 0.030:
            self.slow_updates += 1
            if self.slow_updates % 10 == 0:
                logger.warning(f"⚠ Slow update rate: {1/dt:.1f}Hz (dt={dt*1000:.1f}ms) - Count: {self.slow_updates}")
        
        if self.use_mpu6050 and self.imu:
            imu_start = time.time()
            try:
                # Read IMU data
                accel = self.imu.get_accel_data()
                gyro = self.imu.get_gyro_data()
                
                imu_duration = (time.time() - imu_start) * 1000  # ms
                
                # Warn about slow I2C reads
                if imu_duration > 5.0:
                    logger.warning(f"⚠ Slow IMU read: {imu_duration:.1f}ms")
                
                # Calculate roll from accelerometer
                accel_roll = self._accel_to_roll(accel)
                
                # Complementary filter
                self.roll_angle = (
                    config.MPU6050_ALPHA * (self.roll_angle + gyro["x"] * dt) + 
                    (1 - config.MPU6050_ALPHA) * accel_roll
                )

            except Exception as e:
                self.imu_errors += 1
                if self.imu_errors % 10 == 0:
                    logger.error(f"⚠ IMU read error #{self.imu_errors}: {e}")
                return

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
        servo_start = time.time()
        self.roll_servo.value = self._angle_to_servo(roll_output, self.max_roll_angle)
        servo_duration = (time.time() - servo_start) * 1000  # ms
        
        # Warn about slow servo writes
        if servo_duration > 5.0:
            logger.warning(f"⚠ Slow servo write: {servo_duration:.1f}ms")
        
        # Total update time
        total_duration = (time.time() - update_start) * 1000  # ms
        
        # Print diagnostics every 100 updates
        if self.update_count % 100 == 0:
            logger.info(f"📊 Stats (last 100 updates): "
                       f"Avg rate: {1/dt:.1f}Hz | "
                       f"Slow updates: {self.slow_updates} | "
                       f"IMU errors: {self.imu_errors} | "
                       f"Update time: {total_duration:.1f}ms")
    
    def enable(self):
        """Enable gimbal stabilization"""
        self.enabled = True
        self.roll_integral = 0
        self.roll_prev_error = 0
        self.last_time = time.time()
        
        # Reset diagnostics
        self.update_count = 0
        self.slow_updates = 0
        self.imu_errors = 0
        
        logger.info("Gimbal stabilization ENABLED")
    
    def disable(self):
        """Disable gimbal stabilization and center servo"""
        self.enabled = False
        self.roll_servo.value = 0
        
        # Print final statistics
        if self.update_count > 0:
            logger.info(f"📊 Final Stats: Total updates: {self.update_count} | "
                       f"Slow: {self.slow_updates} ({100*self.slow_updates/self.update_count:.1f}%) | "
                       f"IMU errors: {self.imu_errors}")
        
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
    print("🎥 GIMBAL STANDALONE TEST MODE (DEBUG)")
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
    print(f"✓ Update rate: 50 Hz")
    print(f"✓ PID gains: Kp={config.GIMBAL_PID_KP}, Ki={config.GIMBAL_PID_KI}, Kd={config.GIMBAL_PID_KD}")
    print("=" * 60)
    print("Gimbal stabilization starting... Tilt the IMU!")
    print("Performance diagnostics will show every 100 updates")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    gimbal.enable()
    
    try:
        while True:
            gimbal.update()
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