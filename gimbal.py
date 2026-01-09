#!/usr/bin/env python3
# gimbal.py

import time
import logging
from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory

logger = logging.getLogger("Gimbal")

class PIDController:
    """Simple PID controller for smooth servo movements"""
    def __init__(self, kp, ki, kd, output_limits=(-1, 1)):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limits = output_limits
        
        self.integral = 0
        self.previous_error = 0
        self.previous_time = time.time()
    
    def update(self, error):
        current_time = time.time()
        dt = current_time - self.previous_time
        
        if dt <= 0:
            dt = 0.01
        
        # Proportional
        p_term = self.kp * error
        
        # Integral with anti-windup
        self.integral += error * dt
        self.integral = max(min(self.integral, 10), -10)
        i_term = self.ki * self.integral
        
        # Derivative
        derivative = (error - self.previous_error) / dt
        d_term = self.kd * derivative
        
        # Calculate output
        output = p_term + i_term + d_term
        
        # Limit output
        output = max(min(output, self.output_limits[1]), self.output_limits[0])
        
        # Update state
        self.previous_error = error
        self.previous_time = current_time
        
        return output
    
    def reset(self):
        """Reset PID state"""
        self.integral = 0
        self.previous_error = 0
        self.previous_time = time.time()


class CameraGimbal:
    """
    2-Axis Camera Gimbal Stabilizer
    - Roll axis: Compensates for drone roll
    - Pitch axis: Maintains fixed 45° downward angle
    
    Works WITHOUT local gyroscope by using Pixhawk attitude data
    """
    
    def __init__(self, 
                 roll_pin=17, 
                 pitch_pin=27,
                 target_pitch=-45,
                 max_roll_compensation=30):
        """
        Initialize gimbal controller
        
        Args:
            roll_pin: GPIO pin for roll servo (BCM numbering)
            pitch_pin: GPIO pin for pitch servo (BCM numbering)
            target_pitch: Fixed camera pitch angle in degrees (negative = down)
            max_roll_compensation: Maximum roll compensation angle
        """
        
        self.target_pitch = target_pitch
        self.max_roll_compensation = max_roll_compensation
        
        # Servo configuration
        self.servo_min_pulse = 0.5 / 1000  # 0.5ms
        self.servo_max_pulse = 2.5 / 1000  # 2.5ms
        
        # Initialize pigpio factory for better PWM
        try:
            self.factory = PiGPIOFactory()
            logger.info("✓ Using pigpio for servo control")
        except Exception as e:
            logger.warning(f"⚠ pigpio not available, using default: {e}")
            self.factory = None
        
        # Initialize servos
        self._init_servos(roll_pin, pitch_pin)
        
        # PID controller for roll stabilization
        # Conservative gains for SG90 servos
        self.roll_pid = PIDController(
            kp=0.8,   # Proportional gain
            ki=0.05,  # Integral gain (small to prevent windup)
            kd=0.1    # Derivative gain (damping)
        )
        
        # State tracking
        self.enabled = False
        self.last_update_time = time.time()
        self.current_roll_compensation = 0.0
        
        # Performance monitoring
        self.update_count = 0
        self.last_log_time = time.time()
        
        logger.info("=" * 60)
        logger.info("🎥 CAMERA GIMBAL INITIALIZED")
        logger.info(f"   Roll servo: GPIO {roll_pin}")
        logger.info(f"   Pitch servo: GPIO {pitch_pin}")
        logger.info(f"   Target pitch: {target_pitch}°")
        logger.info(f"   Max roll compensation: ±{max_roll_compensation}°")
        logger.info("=" * 60)
    
    def _init_servos(self, roll_pin, pitch_pin):
        """Initialize servo motors"""
        try:
            # Roll servo (compensates for drone roll)
            self.roll_servo = Servo(
                roll_pin,
                min_pulse_width=self.servo_min_pulse,
                max_pulse_width=self.servo_max_pulse,
                pin_factory=self.factory
            )
            
            # Pitch servo (maintains fixed angle)
            self.pitch_servo = Servo(
                pitch_pin,
                min_pulse_width=self.servo_min_pulse,
                max_pulse_width=self.servo_max_pulse,
                pin_factory=self.factory
            )
            
            # Set initial positions (centered and 45° pitch)
            self.set_roll_compensation(0)
            self.set_pitch_angle(self.target_pitch)
            
            logger.info("✓ Servos initialized successfully")
            
        except Exception as e:
            logger.error(f"⚠ Failed to initialize servos: {e}")
            raise
    
    def enable(self):
        """Enable gimbal stabilization"""
        if not self.enabled:
            self.enabled = True
            self.roll_pid.reset()
            logger.info("✓ Gimbal ENABLED - Stabilization active")
    
    def disable(self):
        """Disable gimbal and center servos"""
        if self.enabled:
            self.enabled = False
            self.set_roll_compensation(0)
            logger.info("⚠ Gimbal DISABLED - Servos centered")
    
    def angle_to_servo_value(self, angle, max_angle):
        """
        Convert angle to servo value (-1 to 1)
        
        Args:
            angle: Angle in degrees
            max_angle: Maximum angle range
            
        Returns:
            Servo value between -1 and 1
        """
        return max(min(angle / max_angle, 1.0), -1.0)
    
    def set_roll_compensation(self, angle):
        """
        Set roll servo to compensate for drone roll
        
        Args:
            angle: Compensation angle in degrees
        """
        # Limit compensation
        angle = max(min(angle, self.max_roll_compensation), 
                   -self.max_roll_compensation)
        
        # Convert to servo value
        servo_value = self.angle_to_servo_value(angle, self.max_roll_compensation)
        
        try:
            self.roll_servo.value = servo_value
            self.current_roll_compensation = angle
        except Exception as e:
            logger.error(f"⚠ Roll servo error: {e}")
    
    def set_pitch_angle(self, angle):
        """
        Set pitch servo to fixed angle
        
        Args:
            angle: Pitch angle in degrees (-90 to +90)
        """
        # Map -90 to +90 degrees to servo range
        servo_value = angle / 90.0
        servo_value = max(min(servo_value, 1.0), -1.0)
        
        try:
            self.pitch_servo.value = servo_value
        except Exception as e:
            logger.error(f"⚠ Pitch servo error: {e}")
    
    def update(self, drone_roll, drone_pitch=None):
        """
        Update gimbal stabilization based on drone attitude
        
        Args:
            drone_roll: Current drone roll angle in degrees
            drone_pitch: Current drone pitch angle (optional, for future use)
            
        Returns:
            Current roll compensation angle
        """
        
        if not self.enabled:
            return 0.0
        
        current_time = time.time()
        dt = current_time - self.last_update_time
        
        # Prevent too-fast updates (respect servo response time)
        if dt < 0.02:  # Max 50Hz for SG90 servos
            return self.current_roll_compensation
        
        self.last_update_time = current_time
        
        # Calculate roll error (negative to counter the roll)
        roll_error = -drone_roll
        
        # Use PID to calculate smooth compensation
        pid_output = self.roll_pid.update(roll_error)
        roll_compensation_angle = pid_output * self.max_roll_compensation
        
        # Apply roll compensation
        self.set_roll_compensation(roll_compensation_angle)
        
        # Update counter
        self.update_count += 1
        
        # Log performance every 5 seconds
        if current_time - self.last_log_time >= 5.0:
            update_rate = self.update_count / (current_time - self.last_log_time)
            logger.debug(f"Gimbal stats: {update_rate:.1f} Hz, "
                        f"Roll comp: {roll_compensation_angle:.1f}°")
            self.update_count = 0
            self.last_log_time = current_time
        
        return roll_compensation_angle
    
    def get_status(self):
        """
        Get current gimbal status
        
        Returns:
            Dictionary with gimbal state information
        """
        return {
            "enabled": self.enabled,
            "roll_compensation": self.current_roll_compensation,
            "target_pitch": self.target_pitch,
            "update_count": self.update_count
        }
    
    def cleanup(self):
        """Safely shutdown gimbal (center servos and cleanup)"""
        logger.info("⚠ Shutting down gimbal...")
        
        # Center roll servo
        self.set_roll_compensation(0)
        time.sleep(0.5)
        
        # Close servos
        try:
            self.roll_servo.close()
            self.pitch_servo.close()
            logger.info("✓ Gimbal shutdown complete")
        except Exception as e:
            logger.warning(f"⚠ Error during gimbal cleanup: {e}")


# ============================================================================
# TESTING FUNCTIONS (for standalone testing)
# ============================================================================

def test_gimbal_standalone():
    """Test gimbal without drone (manual testing)"""
    import random
    
    logging.basicConfig(level=logging.INFO)
    logger.info("=" * 60)
    logger.info("GIMBAL STANDALONE TEST")
    logger.info("Testing servos with simulated roll angles")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)
    
    gimbal = CameraGimbal()
    gimbal.enable()
    
    try:
        while True:
            # Simulate random drone roll
            simulated_roll = random.uniform(-20, 20)
            
            # Update gimbal
            compensation = gimbal.update(simulated_roll)
            
            logger.info(f"Drone roll: {simulated_roll:6.2f}° → "
                       f"Gimbal compensation: {compensation:6.2f}°")
            
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        logger.info("\n⚠ Test stopped by user")
    finally:
        gimbal.cleanup()


if __name__ == "__main__":
    test_gimbal_standalone()