#!/usr/bin/env python3
# config.py

from pathlib import Path
from datetime import datetime
from pymavlink import mavutil

# ============================================================================
# DIRECTORY AND FILE PATH CONFIGURATION
# ============================================================================

# --- Base Directories
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
IMAGE_DIR = BASE_DIR / "images"
MODEL_DIR = BASE_DIR / "models"
JSON_DIR = BASE_DIR / "results"

def get_flight_log_dir():
    date_str = datetime.now().strftime("%Y-%m-%d")
    flight_log_dir = LOG_DIR / date_str
    flight_log_dir.mkdir(parents=True, exist_ok=True)
    return flight_log_dir

# --- Centralized paths (used everywhere)
FLIGHT_LOG_DIR = get_flight_log_dir()

# --- Output File
FLIGHT_LOG_FILE = FLIGHT_LOG_DIR / "flight.log"
FLIGHT_METRICS_CSV = FLIGHT_LOG_DIR / "drone_flight_metrics.csv"
IMAGE_LOG_CSV = FLIGHT_LOG_DIR / "image_captures.csv"
CLASSIFICATION_CSV = FLIGHT_LOG_DIR / "ai_classifications.csv"

def ensure_directories():
    LOG_DIR.mkdir(exist_ok=True)
    IMAGE_DIR.mkdir(exist_ok=True)
    MODEL_DIR.mkdir(exist_ok=True)
    JSON_DIR.mkdir( exist_ok=True)


# ============================================================================
# PIXHAWK CONNECTION SETTINGS
# ============================================================================

# --- Pixhawk Connection
PIXHAWK_ADDRESS = "/dev/ttyAMA0"


# ============================================================================
# MISSION WAYPOINT DEFINITIONS
# ============================================================================

# --- System waypoints (never capture images here)
WP_HOME = 0
WP_TAKEOFF = 1

def is_mapping_waypoint(wp_number):
    return wp_number not in (WP_HOME, WP_TAKEOFF)

def get_waypoint_name(wp_number):
    if wp_number == WP_HOME:
        return "HOME"
    elif wp_number == WP_TAKEOFF:
        return "TAKEOFF"
    else:
        return f"WAYPOINT_{wp_number}"

def get_waypoint_type(wp_number):
    if wp_number == WP_HOME:
        return "home"
    elif wp_number == WP_TAKEOFF:
        return "takeoff"
    elif is_mapping_waypoint(wp_number):
        return "waypoint"
    else:
        return "other"


# ============================================================================
# FLIGHT CAPTURE CONFIGURATION
# ============================================================================

# --- Flight Capture Settings
MIN_ALTITUDE_FOR_CAPTURE = 2.0

# --- Timing Configuration
MAIN_LOOP_INTERVAL = 0.1  # seconds
METRICS_LOG_INTERVAL = 0.5  # seconds
METRICS_WINDOW_SIZE = 10


# ============================================================================
# MPU6050 IMU SENSOR CONFIGURATION
# ============================================================================

# ---Enable/Disable MPU6050 (falls back to Pixhawk if False)
USE_MPU6050 = True

# --- I2C Address (0x68 if AD0 pin is LOW, 0x69 if HIGH)
MPU6050_I2C_ADDRESS = 0x68

# --- Complementary filter coefficient (0.90-0.98 recommended)
# Higher = more trust in gyroscope (fast, but drifts)
# Lower = more trust in accelerometer (stable, but noisy)
# Try 0.96-0.99 if you experience drift
MPU6050_ALPHA = 0.98

# --- Calibration samples (more = better accuracy, but slower startup)
# Increase to 200-500 if you see persistent angle errors
MPU6050_CALIBRATION_SAMPLES = 100


# ============================================================================
# GIMBAL CONFIGURATION
# ============================================================================

# --- Enable/Disable Gimbal
GIMBAL_ENABLED = True  # Set to False to disable gimbal

# --- GPIO Pin (BCM numbering) - Roll servo only
GIMBAL_ROLL_PIN = 17   # GPIO 17 for roll stabilization servo

# NOTE: Pitch angle is physically fixed at 45° downward (no servo needed)

# --- Servo Pulse Width (microseconds)
GIMBAL_SERVO_MIN_PULSE = 500   # 0.5ms (minimum pulse width)
GIMBAL_SERVO_MAX_PULSE = 2500  # 2.5ms (maximum pulse width)

# --- PID Tuning (adjust these based on your servo response)
GIMBAL_PID_KP = 0.85   # Proportional gain
GIMBAL_PID_KI = 0.05  # Integral gain
GIMBAL_PID_KD = 0.1   # Derivative gain


# ============================================================================
# AI CONFIGURATION
# ============================================================================

# --- Server Configuration for JSON Uploads
SERVER = "http://WEB_SERVER_IP:5000"

# --- AI Model Configuration
MODEL_PATH = MODEL_DIR / "models" / "pinyasuri_model.tflite"

# --- Class Labels
CLASS_NAMES = {
    0: "Healthy",
    1: "Mealybug Wilt Disease",
    2: "Root Rot Disease",
    3: "Crown Rot Disease",
    4: "Fruit Fasciation Disorder",
    5: "Multiple Crown Disorder"
}

def get_class_name(index: int) -> str:
    return CLASS_NAMES.get(index, f"unknown_{index}")