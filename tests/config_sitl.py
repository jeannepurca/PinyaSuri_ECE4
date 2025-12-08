# config_sitl.py - Configuration for SITL Simulation
from pathlib import Path

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs_sitl"
IMAGE_DIR = BASE_DIR / "images_sitl"
RAW_IMG_DIR = IMAGE_DIR / "raw"
ANNOTATED_IMG_DIR = IMAGE_DIR / "annotated"

# CSV Output Files
CLASSIFICATION_CSV = LOG_DIR / "classifications_sitl.csv"
FLIGHT_METRICS_CSV = LOG_DIR / "drone_flight_metrics_sitl.csv"

# Pixhawk Configuration for SITL
# SITL typically uses UDP connection on port 14540
PIXHAWK_ADDRESS = "serial:///dev/ttyAMA0:57600"
CONNECTION_TIMEOUT = 30

# Model Configuration
MODEL_PATH = BASE_DIR / "models" / "pineapple_classifier.tflite"
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

# Timing Configuration
MAIN_LOOP_INTERVAL = 0.1  # seconds
METRICS_LOG_INTERVAL = 0.5  # seconds
METRICS_WINDOW_SIZE = 10

# SITL-Specific Settings
SIMULATION_MODE = True
USE_MOCK_CAMERA = True  # Use simulated camera instead of PiCamera
USE_MOCK_CLASSIFIER = False  # Set to True if you don't have the model yet

def get_class_name(index: int) -> str:
    """Get class name from index"""
    return CLASS_NAMES.get(index, f"unknown_{index}")

def ensure_directories():
    """Create all necessary directories"""
    LOG_DIR.mkdir(exist_ok=True)
    RAW_IMG_DIR.mkdir(parents=True, exist_ok=True)
    ANNOTATED_IMG_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "models").mkdir(exist_ok=True)
    print(f"SITL Mode: Directories created at {BASE_DIR}")