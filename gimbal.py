#!/usr/bin/env python3
# gimbal.py - Enhanced with MPU6050 IMU sensor (integrated working PID + complementary filter)

import time
import logging
import math
from gpiozero import Servo

import config

logger = logging.getLogger("Gimbal")

CONTROL_HZ = 50.0
DT = 1.0 / CONTROL_HZ

# ==============================
# MPU6050 Handler (integrated)
# ==============================

class MPU6050Handler:
    def __init__(self, i2c_address=0x68, alpha=0.98, calibration_samples=100):
        """Initialize MPU6050 sensor"""
        try:
            from mpu6050 import mpu6050
            self.sensor = mpu6050(i2c_address)
            logger.info(f"✓ MPU6050 connected at 0x{i2c_address:02X}")
        except Exception as e:
            logger.error(f"⚠ MPU6050 init failed: {e}")
            raise
        
        self.alpha = alpha
        self.roll = 0.0
        self.pitch = 0.0
        self.last_time = time.time()

        self.gyro_offset = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.accel_offset = {"x": 0.0, "y": 0.0, "z": 0.0}
        
        self.calibrate(calibration_samples)

    def calibrate(self, samples=100):
        logger.info("⏳ Calibrating MPU6050, keep gimbal stationary...")
        gyro_sum = {"x":0,"y":0,"z":0}
        accel_sum = {"x":0,"y":0,"z":0}
        for _ in range(samples):
            g = self.sensor.get_gyro_data()
            a = self.sensor.get_accel_data()
            for k in "xyz":
                gyro_sum[k] += g[k]
            for k in "xyz":
                accel_sum[k] += a[k]
            time.sleep(0.01)
        self.gyro_offset = {k: v / samples for k,v in gyro_sum.items()}
        self.accel_offset = {k: accel_sum[k]/samples for k in "xyz"}
        logger.info("✓ Calibration complete")

    def get_calibrated_gyro(self):
        raw = self.sensor.get_gyro_data()
        return {k: raw[k]-self.gyro_offset[k] for k in raw}

    def get_calibrated_accel(self):
        raw = self.sensor.get_accel_data()
        return {k: raw[k]-self.accel_offset[k] for k in raw}

    def accel_to_angles(self, accel):
        roll = math.degrees(math.atan2(accel["y"], accel["z"]))
        pitch = math.degrees(math.atan2(-accel["x"], math.sqrt(accel["y"]**2 + accel["z"]**2)))
        return roll, pitch

    def update_attitude(self):
        now = time.time()
        dt = now - self.last_time
        if dt <= 0: dt = DT
        self.last_time = now

        accel = self.get_calibrated_accel()
        gyro = self.get_calibrated_gyro()
        accel_roll, accel_pitch = self.accel_to_angles(accel)

        # complementary filter
        self.roll = self.alpha*(self.roll + gyro["x"]*dt) + (1-self.alpha)*accel_roll
        self.pitch = self.alpha*(self.pitch + gyro["y"]*dt) + (1-self.alpha)*accel_pitch

        return self.roll, self.pitch

    def get_attitude(self):
        return self.roll, self.pitch

# ==============================
# PID Controller
# ==============================

class PIDController:
    def __init__(self, kp, ki, kd, output_limits=(-1,1), integral_limit=50.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limits = output_limits
        self.integral_limit = integral_limit
        self.integral = 0.0
        self.prev_error = 0.0

    def update(self, error, dt):
        self.integral += error*dt
        self.integral = max(min(self.integral, self.integral_limit), -self.integral_limit)
        derivative = (error - self.prev_error)/dt if dt>0 else 0
        output = self.kp*error + self.ki*self.integral + self.kd*derivative
        output = max(min(output, self.output_limits[1]), self.output_limits[0])
        self.prev_error = error
        return output

    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0

# ==============================
# Camera Gimbal
# ==============================

class CameraGimbal:
    def __init__(self,
                 roll_pin=config.GIMBAL_ROLL_PIN,
                 pitch_pin=config.GIMBAL_PITCH_PIN,
                 use_mpu6050=config.USE_MPU6050,
                 max_roll=config.GIMBAL_MAX_ROLL_COMPENSATION,
                 target_pitch=config.GIMBAL_TARGET_PITCH):

        self.target_pitch = target_pitch
        self.max_roll_compensation = max_roll
        self.use_mpu6050 = use_mpu6050
        self.enabled = False

        # init PID
        self.roll_pid = PIDController(kp=config.GIMBAL_PID_KP,
                                      ki=config.GIMBAL_PID_KI,
                                      kd=config.GIMBAL_PID_KD,
                                      output_limits=(-1,1))

        # init servos
        try:
            from gpiozero.pins.pigpio import PiGPIOFactory
            factory = PiGPIOFactory()
        except Exception:
            factory = None

        pulse_min = config.GIMBAL_SERVO_MIN_PULSE / 1_000_000
        pulse_max = config.GIMBAL_SERVO_MAX_PULSE / 1_000_000

        self.roll_servo = Servo(roll_pin, min_pulse_width=pulse_min, max_pulse_width=pulse_max, pin_factory=factory)
        self.pitch_servo = Servo(pitch_pin, min_pulse_width=pulse_min, max_pulse_width=pulse_max, pin_factory=factory)

        # init IMU
        self.imu = None
        if use_mpu6050:
            try:
                self.imu = MPU6050Handler(alpha=config.MPU6050_ALPHA)
            except Exception as e:
                logger.warning(f"MPU6050 init failed: {e}")
                self.use_mpu6050 = False

        # init state
        self.current_roll_comp = 0.0
        self.last_time = time.time()

    def angle_to_servo_value(self, angle, max_angle):
        return max(min(angle/max_angle, 1.0), -1.0)

    def set_roll_compensation(self, angle):
        angle = max(min(angle, self.max_roll_compensation), -self.max_roll_compensation)
        self.roll_servo.value = self.angle_to_servo_value(angle, self.max_roll_compensation)
        self.current_roll_comp = angle

    def set_pitch_angle(self, angle):
        self.pitch_servo.value = self.angle_to_servo_value(angle, 90.0)

    def enable(self):
        self.enabled = True
        self.roll_pid.reset()
        if self.imu:
            self.imu.last_time = time.time()
        logger.info("✓ Gimbal ENABLED")

    def disable(self):
        self.enabled = False
        self.set_roll_compensation(0)
        self.set_pitch_angle(self.target_pitch)
        logger.info("⚠ Gimbal DISABLED")

    def update(self, drone_roll=None, drone_pitch=None):
        if not self.enabled:
            return 0.0

        now = time.time()
        dt = now - self.last_time
        if dt <= 0: dt = DT
        self.last_time = now

        if self.use_mpu6050 and self.imu:
            self.imu.update_attitude()
            roll, pitch = self.imu.get_attitude()
            roll_error = -roll
        else:
            if drone_roll is None:
                return self.current_roll_comp
            roll_error = -drone_roll

        roll_pid_output = self.roll_pid.update(roll_error, dt)
        roll_angle = roll_pid_output * self.max_roll_compensation
        self.set_roll_compensation(roll_angle)

        # maintain target pitch
        self.set_pitch_angle(self.target_pitch)

        return roll_angle

    def get_status(self):
        status = {"enabled": self.enabled, "roll_comp": self.current_roll_comp, "target_pitch": self.target_pitch}
        if self.imu:
            status["imu_roll"], status["imu_pitch"] = self.imu.get_attitude()
        return status

    def cleanup(self):
        logger.info("Shutting down gimbal...")
        self.set_roll_compensation(0)
        self.set_pitch_angle(self.target_pitch)
        time.sleep(0.2)
        self.roll_servo.close()
        self.pitch_servo.close()
        logger.info("✓ Gimbal shutdown complete")