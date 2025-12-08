"""
PinyaSuri Configuration
Central configuration file for all system parameters
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path("/home/ece4/PINYASURI")

# Pixhawk Connection
PIXHAWK_ADDRESS = "serial:///dev/ttyAMA0:57600"  # Serial connection to Pixhawk 2.4.8
CONNECTION_TIMEOUT = 30  # seconds

# Camera Settings
CAMERA_RESOLUTION = (4056, 3040)  # Raspberry Pi Camera Module V3 full resolution
IMAGE_DIR = BASE_DIR / "drone_images"

# AI Model
MODEL_PATH = BASE_DIR / "pineapple_classifier.tflite"
MODEL_INPUT_SIZE = (224, 224)  # Model input dimensions

# Output Files
CLASSIFICATION_CSV = BASE_DIR / "image_classification_log.csv"
FLIGHT_METRICS_CSV = BASE_DIR / "drone_flight_metrics.csv"

# Flight Metrics Settings
METRICS_WINDOW_SIZE = 10  # Rolling window size for metrics calculation
METRICS_LOG_INTERVAL = 0.5  # seconds between metric logs

# Main Loop Settings
MAIN_LOOP_INTERVAL = 0.2  # seconds - how often to check for new data

# Create necessary directories
def ensure_directories():
    """Ensure all required directories exist"""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    BASE_DIR.mkdir(parents=True, exist_ok=True)

# Classification labels (customize based on your model)
CLASS_LABELS = {
    0: "Healthy",
    1: "Disease_Type_1",
    2: "Disease_Type_2",
    # Add more classes as needed
}

def get_class_name(index: int) -> str:
    """Get human-readable class name from index"""
    return CLASS_LABELS.get(index, f"Unknown_Class_{index}")
