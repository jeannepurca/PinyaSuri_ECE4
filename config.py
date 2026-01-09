#!/usr/bin/env python3
# config.py

from pathlib import Path

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
IMAGE_DIR = BASE_DIR / "images"
TEST_IMAGE_DIR = IMAGE_DIR / "test"

# Pixhawk Connection
PIXHAWK_ADDRESS = "/dev/ttyAMA0"

# Flight Capture Settings
MIN_ALTITUDE_FOR_CAPTURE = 2.0

# Timing Configuration
MAIN_LOOP_INTERVAL = 0.1  # seconds
METRICS_LOG_INTERVAL = 0.5  # seconds
METRICS_WINDOW_SIZE = 10

# ============================================================================
# GIMBAL CONFIGURATION
# ============================================================================

# Enable/Disable Gimbal
GIMBAL_ENABLED = True  # Set to False to disable gimbal

# GPIO Pins (BCM numbering)
GIMBAL_ROLL_PIN = 17   # GPIO 17 for roll stabilization servo
GIMBAL_PITCH_PIN = 27  # GPIO 27 for pitch angle servo

# Gimbal Angles
GIMBAL_TARGET_PITCH = -45  # Camera pitch angle (negative = downward)
GIMBAL_MAX_ROLL_COMPENSATION = 30  # Maximum roll compensation (degrees)

# Servo Pulse Width (microseconds)
GIMBAL_SERVO_MIN_PULSE = 500   # 0.5ms (minimum pulse width)
GIMBAL_SERVO_MAX_PULSE = 2500  # 2.5ms (maximum pulse width)

# PID Tuning (adjust these based on your servo response)
GIMBAL_PID_KP = 0.8   # Proportional gain
GIMBAL_PID_KI = 0.05  # Integral gain
GIMBAL_PID_KD = 0.1   # Derivative gain

# ============================================================================

# AI Model Configuration
MODEL_PATH = BASE_DIR / "models" / "pinyasuri_model.tflite"
MODEL_INPUT_SIZE = (224, 224)

# Class Labels
CLASS_NAMES = {
    0: "Healthy",
    1: "Mealybug Wilt Disease",
    2: "Root Rot Disease",
    3: "Crown Rot Disease",
    4: "Fruit Fasciation Disorder",
    5: "Multiple Crown Disorder"
}

# CSV Output Files
FLIGHT_METRICS_CSV = LOG_DIR / "drone_flight_metrics.csv"
IMAGE_LOG_CSV = LOG_DIR / "image_log.csv"
CLASSIFICATION_CSV = LOG_DIR / "ai_classifications.csv"

def get_class_name(index: int) -> str:
    """Get class name from index"""
    return CLASS_NAMES.get(index, f"unknown_{index}")

def ensure_directories():
    """Create all necessary directories"""
    LOG_DIR.mkdir(exist_ok=True)
    IMAGE_DIR.mkdir(exist_ok=True)
    TEST_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "models").mkdir(exist_ok=True)