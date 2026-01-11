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
    JSON_DIR.mkdir(exist_ok=True)


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