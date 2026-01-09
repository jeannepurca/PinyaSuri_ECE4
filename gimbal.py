#!/usr/bin/env python3
# gimbal.py - Enhanced with MPU6050 IMU sensor

import time
import logging
import math
from gpiozero import Servo

import config

logger = logging.getLogger("Gimbal")

CONTROL_HZ = 50.0
DT = 1.0 / CONTROL_HZ

# ============================================================================
# MPU6050 IMU Handler
# ============================================================================

class MPU6050Handler:
    """
    MPU6050 IMU sensor interface with calibration
    Provides local attitude sensing for gimbal stabilization
    """
    
    def __init__(self, i2c_address=0x68, calibration_samples=100):
        """Initialize MPU6050 sensor"""
        try:
            from mpu6050 import mpu6050
            self.sensor = mpu6050(i2c_address)
            logger.info(f"✓ MPU6050 connected at address 0x{i2c_address:02X}")
        except Exception as e:
            logger.error(f"⚠ Failed to initialize MPU6050: {e}")
            raise
        
        # Calibration offsets
        self.gyro_offset = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.accel_offset = {"x": 0.0, "y": 0.0, "z": 0.0}
        
        # Attitude state (complementary filter)
        self.roll = 0.0
        self.pitch = 0.0
        self.last_update_time = time.time()
        
        # Complementary filter coefficient (0.98 = 98% gyro, 2% accel)
        self.alpha = config.MPU6050_ALPHA
        
        # Perform initial calibration
        self.calibrate(config.MPU6050_CALIBRATION_SAMPLES)
        
    def calibrate(self, samples=100):
        """Calibrate gyroscope by measuring bias while stationary"""
        logger.info(f"⏳ Calibrating MPU6050... Keep gimbal STATIONARY!")
        
        gyro_sum = {"x": 0.0, "y": 0.0, "z": 0.0}
        accel_sum = {"x": 0.0, "y": 0.0, "z": 0.0}
        
        for i in range(samples):
            gyro = self.sensor.get_gyro_data()
            accel = self.sensor.get_accel_data()
            
            gyro_sum["x"] += gyro["x"]
            gyro_sum["y"] += gyro["y"]
            gyro_sum["z"] += gyro["z"]
            
            accel_sum["x"] += accel["x"]
            accel_sum["y"] += accel["y"]
            accel_sum["z"] += accel["z"]
            
            time.sleep(0.01)
        
        self.gyro_offset = {k: v / samples for k, v in gyro_sum.items()}
        self.accel_offset = {
            "x": accel_sum["x"] / samples,
            "y": accel_sum["y"] / samples,
            "z": (accel_sum["z"] / samples) - 9.81
        }
        
        logger.info(f"✓ Calibration complete!")
        logger.info(f"  Gyro offset: X={self.gyro_offset['x']:.2f}, "
                    f"Y={self.gyro_offset['y']:.2f}, "
                    f"Z={self.gyro_offset['z']:.2f}")
    
    def get_calibrated_gyro(self):
        raw = self.sensor.get_gyro_data()
        return {k: raw[k] - self.gyro_offset[k] for k in raw}
    
    def get_calibrated_accel(self):
        raw = self.sensor.get_accel_data()
        return {k: raw[k] - self.accel_offset[k] for k in raw}
    
    def calculate_accel_angles(self):
        accel = self.get_calibrated_accel()
        roll = math.atan2(accel["y"], accel["z"]) * 180 / math.pi
        pitch = math.atan2(-accel["x"], math.sqrt(accel["y"]**2 + accel["z"]**2)) * 180 / math.pi
        return roll, pitch
    
    def update_attitude(self):
        current_time = time.time()
        dt = current_time - self.last_update_time
        if dt > 0.1:
            dt = 0.02
        self.last_update_time = current_time
        
        gyro = self.get_calibrated_gyro()
        accel_roll, accel_pitch = self.calculate_accel_angles()
        
        gyro_roll = self.roll + gyro["x"] * dt
        gyro_pitch = self.pitch + gyro["y"] * dt
        
        self.roll = self.alpha * gyro_roll + (1 - self.alpha) * accel_roll
        self.pitch = self.alpha * gyro_pitch + (1 - self.alpha) * accel_pitch
        
        return self.roll, self.pitch
    
    def get_attitude(self):
        return self.roll, self.pitch


# ============================================================================
# PID Controller
# ============================================================================

class PIDController:
    def __init__(self, kp, ki, kd, output_limits=(-1, 1)):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limits = output_limits
        self.integral = 0.0
        self.prev_error = 0.0
    
    def update(self, error):
        p = self.kp * error
        self.integral += error * DT
        self.integral = max(min(self.integral, 5.0), -5.0)
        i = self.ki * self.integral
        d = self.kd * (error - self.prev_error) / DT
        output = max(min(p + i + d, self.output_limits[1]), self.output_limits[0])
        self.prev_error = error
        return output
    
    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0


# ============================================================================
# Camera Gimbal with MPU6050
# ============================================================================

class CameraGimbal:
    def __init__(self, 
                 roll_pin=config.GIMBAL_ROLL_PIN, 
                 pitch_pin=config.GIMBAL_PITCH_PIN,
                 target_pitch=config.GIMBAL_TARGET_PITCH,
                 max_roll_compensation=config.GIMBAL_MAX_ROLL_COMPENSATION,
                 use_mpu6050=config.USE_MPU6050,
                 mpu6050_address=config.MPU6050_I2C_ADDRESS):
        
        self.target_pitch = target_pitch
        self.max_roll_compensation = max_roll_compensation
        self.use_mpu6050 = use_mpu6050
        self.servo_min_pulse = config.GIMBAL_SERVO_MIN_PULSE / 1_000_000
        self.servo_max_pulse = config.GIMBAL_SERVO_MAX_PULSE / 1_000_000

        # Optional pigpio support
        try:
            from gpiozero.pins.pigpio import PiGPIOFactory
            self.factory = PiGPIOFactory()
            logger.info("✓ Using pigpio for servo control")
        except Exception:
            self.factory = None
            logger.info("ℹ Using default gpiozero PWM (pigpio unavailable)")
        
        # Initialize servos
        self._init_servos(roll_pin, pitch_pin)
        
        # Initialize MPU6050 IMU
        self.imu = None
        if use_mpu6050:
            try:
                self.imu = MPU6050Handler(i2c_address=mpu6050_address)
                logger.info("✓ MPU6050 IMU initialized - Using LOCAL attitude sensing")
            except Exception as e:
                logger.warning(f"⚠ MPU6050 initialization failed: {e}")
                logger.warning("⚠ Falling back to Pixhawk attitude data")
                self.use_mpu6050 = False
        
        self.roll_pid = PIDController(
            kp=config.GIMBAL_PID_KP,
            ki=config.GIMBAL_PID_KI,
            kd=config.GIMBAL_PID_KD
        )
        
        self.enabled = False
        self.last_update_time = time.time()
        self.current_roll_compensation = 0.0
        self.update_count = 0
        self.last_log_time = time.time()
        
        logger.info("="*60)
        logger.info("🎥 CAMERA GIMBAL INITIALIZED")
        logger.info(f"   Roll servo: GPIO {roll_pin}")
        logger.info(f"   Pitch servo: GPIO {pitch_pin}")
        logger.info(f"   Target pitch: {target_pitch}°")
        logger.info(f"   Max roll compensation: ±{max_roll_compensation}°")
        logger.info(f"   IMU mode: {'MPU6050 (LOCAL)' if self.use_mpu6050 else 'Pixhawk (REMOTE)'}")
        logger.info("="*60)
    
    def _init_servos(self, roll_pin, pitch_pin):
        """Initialize servo motors"""
        try:
            servo_kwargs = {}
            if self.factory:
                servo_kwargs["pin_factory"] = self.factory
            
            self.roll_servo = Servo(
                roll_pin,
                min_pulse_width=self.servo_min_pulse,
                max_pulse_width=self.servo_max_pulse,
                **servo_kwargs
            )
            
            self.pitch_servo = Servo(
                pitch_pin,
                min_pulse_width=self.servo_min_pulse,
                max_pulse_width=self.servo_max_pulse,
                **servo_kwargs
            )
            
            self.set_roll_compensation(0)
            self.set_pitch_angle(self.target_pitch)
            logger.info("✓ Servos initialized successfully")
            
        except Exception as e:
            logger.error(f"⚠ Failed to initialize servos: {e}")
            raise
    
    # --- Remaining methods remain unchanged ---
    
    def enable(self):
        if not self.enabled:
            self.enabled = True
            self.roll_pid.reset()
            if self.imu:
                self.imu.last_update_time = time.time()
            logger.info("✓ Gimbal ENABLED - Stabilization active.")
    
    def disable(self):
        if self.enabled:
            self.enabled = False
            self.set_roll_compensation(0)
            logger.info("⚠ Gimbal DISABLED - Servos centered.")
    
    def angle_to_servo_value(self, angle, max_angle):
        return max(min(angle / max_angle, 1.0), -1.0)
    
    def set_roll_compensation(self, angle):
        angle = max(min(angle, self.max_roll_compensation), -self.max_roll_compensation)
        servo_value = self.angle_to_servo_value(angle, self.max_roll_compensation)
        try:
            self.roll_servo.value = servo_value
            self.current_roll_compensation = angle
        except Exception as e:
            logger.error(f"⚠ Roll servo error: {e}")
    
    def set_pitch_angle(self, angle):
        servo_value = max(min(angle / 90.0, 1.0), -1.0)
        try:
            self.pitch_servo.value = servo_value
        except Exception as e:
            logger.error(f"⚠ Pitch servo error: {e}")
    
    def update(self, drone_roll=None, drone_pitch=None):
        if not self.enabled:
            return 0.0
        
        current_time = time.time()
        dt = current_time - self.last_update_time
        if dt < 0.02:
            return self.current_roll_compensation
        self.last_update_time = current_time
        
        if self.use_mpu6050 and self.imu:
            self.imu.update_attitude()
            gimbal_roll, gimbal_pitch = self.imu.get_attitude()
            roll_error = -gimbal_roll
        else:
            if drone_roll is None:
                return self.current_roll_compensation
            roll_error = -drone_roll
        
        pid_output = self.roll_pid.update(roll_error)
        roll_compensation_angle = pid_output * self.max_roll_compensation
        self.set_roll_compensation(roll_compensation_angle)
        
        self.update_count += 1
        if current_time - self.last_log_time >= 5.0:
            update_rate = self.update_count / (current_time - self.last_log_time)
            source = "MPU6050" if self.use_mpu6050 else "Pixhawk"
            logger.debug(f"Gimbal stats: {update_rate:.1f} Hz, "
                         f"Roll comp: {roll_compensation_angle:.1f}° ({source})")
            self.update_count = 0
            self.last_log_time = current_time
        
        return roll_compensation_angle
    
    def get_status(self):
        status = {
            "enabled": self.enabled,
            "roll_compensation": self.current_roll_compensation,
            "target_pitch": self.target_pitch,
            "update_count": self.update_count,
            "imu_source": "MPU6050" if self.use_mpu6050 else "Pixhawk"
        }
        if self.imu:
            roll, pitch = self.imu.get_attitude()
            status["imu_roll"] = roll
            status["imu_pitch"] = pitch
        return status
    
    def cleanup(self):
        logger.info("⚠ Shutting down gimbal...")
        self.set_roll_compensation(0)
        time.sleep(0.4)
        self.roll_servo.close()
        self.pitch_servo.close()
        logger.info("✓ Gimbal shutdown complete")


# ============================================================================
# TESTING FUNCTIONS
# ============================================================================

def test_mpu6050_standalone():
    logging.basicConfig(level=logging.INFO)
    logger.info("="*60)
    logger.info("MPU6050 STANDALONE TEST")
    logger.info("Press Ctrl+C to stop")
    logger.info("="*60)
    try:
        imu = MPU6050Handler()
        while True:
            imu.update_attitude()
            roll, pitch = imu.get_attitude()
            logger.info(f"Roll: {roll:7.2f}°  Pitch: {pitch:7.2f}°")
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("\n⚠ Test stopped by user")


def test_gimbal_with_mpu6050():
    logging.basicConfig(level=logging.INFO)
    logger.info("="*60)
    logger.info("GIMBAL + MPU6050 TEST")
    logger.info("Tilt the gimbal and watch it stabilize!")
    logger.info("Press Ctrl+C to stop")
    logger.info("="*60)
    gimbal = CameraGimbal(use_mpu6050=True)
    gimbal.enable()
    try:
        while True:
            compensation = gimbal.update()
            status = gimbal.get_status()
            logger.info(f"IMU Roll: {status.get('imu_roll', 0):6.2f}° → "
                        f"Compensation: {compensation:6.2f}°")
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("\n⚠ Test stopped by user")
    finally:
        gimbal.cleanup()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "imu":
        test_mpu6050_standalone()
    else:
        test_gimbal_with_mpu6050()