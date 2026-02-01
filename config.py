#!/usr/bin/env python3
# config.py

from pathlib import Path
from datetime import datetime

# ============================================================================  
# BASE DIRECTORIES  
# ============================================================================  
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
IMAGE_DIR = BASE_DIR / "images"
MODEL_DIR = BASE_DIR / "models"
JSON_DIR = BASE_DIR / "results"

def ensure_directories():
    """Ensure all base directories exist"""
    LOG_DIR.mkdir(exist_ok=True)
    IMAGE_DIR.mkdir(exist_ok=True)
    MODEL_DIR.mkdir(exist_ok=True)
    JSON_DIR.mkdir(exist_ok=True)


# ============================================================================  
# API ENDPOINTS
# ============================================================================  
# --- Base server URL
# For local server (Raspberry Pi network):
#SERVER_BASE = "http://192.168.1.16:5000"
SERVER_BASE = "http://10.12.127.21:5000"


# --- For cloud server
# SERVER_BASE = "https://finalfinaledit-pinyasuri-webdev.onrender.com"

# Separate endpoints for different data types
FLIGHT_LOG_ENDPOINT = f"{SERVER_BASE}/api/upload-flight-log"
IMAGE_UPLOAD_ENDPOINT = f"{SERVER_BASE}/api/waypoint-image"

# Legacy support
SERVER = FLIGHT_LOG_ENDPOINT


# ============================================================================  
# FLIGHT LOG FILES  
# ============================================================================  
def get_flight_log_file():
    """Daily flight log file (one per day)"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / f"flight_{date_str}.log"

# Single CSV files (accumulate all flights)
FLIGHT_RAW_CSV = LOG_DIR / "raw_flight_data.csv"
IMAGE_LOG_CSV = LOG_DIR / "image_captures.csv"
CLASSIFICATION_CSV = LOG_DIR / "ai_classifications.csv"

# Daily flight log (for logging only)
FLIGHT_LOG_FILE = get_flight_log_file()


# ============================================================================  
# IMAGE CAPTURE DIRECTORY
# ============================================================================  
def get_image_day_dir():
    """Return the base image directory (daily folders removed)"""
    return IMAGE_DIR


# ============================================================================  
# PIXHAWK CONNECTION SETTINGS  
# ============================================================================  
PIXHAWK_ADDRESS = "/dev/ttyAMA0"


# ============================================================================  
# MISSION WAYPOINT DEFINITIONS
# ============================================================================  
WP_HOME = 0
WP_TAKEOFF = 1

def is_mapping_waypoint(wp_number, last_wp=None):
    excluded = [WP_HOME, WP_TAKEOFF]
    
    # Exclude last waypoint if provided
    if last_wp is not None:
        excluded.append(last_wp)
    
    return wp_number not in excluded

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
MAIN_LOOP_INTERVAL = 0.05  # seconds
MIN_ALTITUDE_FOR_CAPTURE = 0.5  # meters - minimum altitude (safety floor)
MAX_ALTITUDE_FOR_CAPTURE = 5  # meters - maximum altitude (upper limit)
WAYPOINT_CAPTURE_DISTANCE = 1.5  # meters - trigger capture when within this distance
HOVER_SPEED_THRESHOLD = 0.5 # m/s
STABILIZATION_DELAY = 2  # seconds


# ============================================================================  
# BURST CAPTURE CONFIGURATION  
# ============================================================================  
BURST_CAPTURE_COUNT = 3  # Number of images per waypoint
BURST_INTERVAL = 0.5  # Seconds between captures


# ============================================================================  
# AI CONFIGURATION  
# ============================================================================  
MODEL_PATH = MODEL_DIR / "YOLOv8n_PinyaSuri_AI.tflite"
DETECTION_THRESHOLD = 0.3

CLASS_NAMES = {
    0: "Crown Rot Disease",
    1: "Fruit Fasciation Disorder",
    2: "Fruit Rot Disease",
    3: "Healthy",
    4: "Mealybug Wilt Disease",
    5: "Multiple Crown Disorder",
    6: "Root Rot Disease"
}

def get_class_name(index: int) -> str:
    return CLASS_NAMES.get(index, f"unknown_{index}")

DRAW_BBOXES = True  # Enable/disable bounding box drawing
BBOX_THICKNESS = 2  # Thickness of bounding box lines
FONT_SCALE = 1.0    # Size of label text
NMS_IOU_THRESHOLD = 0.5  # IoU threshold for Non-Maximum Suppression

# Color scheme for each class (BGR format for OpenCV)
CLASS_COLORS = {
    0: (0, 0, 255),      # Crown Rot Disease - Red
    1: (0, 165, 255),    # Fruit Fasciation Disorder - Orange
    2: (0, 0, 139),      # Fruit Rot Disease - Dark Red
    3: (0, 255, 0),      # Healthy - Green
    4: (255, 0, 255),    # Mealybug Wilt Disease - Magenta
    5: (255, 255, 0),    # Multiple Crown Disorder - Cyan
    6: (128, 0, 128)     # Root Rot Disease - Purple
}

def get_class_color(index: int):
    """Get color for a specific class index"""
    return CLASS_COLORS.get(index, (255, 255, 255))