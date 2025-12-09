# PinyaSuri: An AI-Driven Autonomous Drone System with Grid Localization for Pineapple Afflictions Detection, Classification, and Monitoring

This is a capstone project made by a group of Electronics Engineering students for the purpose of automating pineapple health monitoring using a drone powered by Pixhawk 2.4.8, Raspberry Pi 5 Microcontroller, and an AI-based image classification model.

## 🚁 System Overview
The PinyaSuri drone system autonomously:
1. Flies in a grid pattern, guided by different waypoints defined using Mission Planner software.
2. Stops at each waypoint and captures high-resolution images of pineapples
3. Analyzes images using an AI classifier to detect pineapple health status
4. Logs GPS coordinates, classifications, and flight metrics to CSV files

## 🔧 Hardware Requirements
- **Drone Controller**: Pixhawk 2.4.8
- **Onboard Computer**: Raspberry Pi 5
- **Camera**: Raspberry Pi Camera Module V3 (Standard)
- **Connection**: Serial connection between Raspberry Pi and Pixhawk (via `/dev/ttyAMA0`)

## 📋 Software Requirements
- Python 3.9+
- Raspbian OS (Bookworm) or compatible
- Mission Planner (for waypoint planning)
- See `requirements.txt` for Python dependencies

## 🛠️ Installation

### 1. Clone the Repository
```bash
cd ~
git clone <your-repo-url> PinyaSuri_ECE4
cd PinyaSuri_ECE4
```

### 2. Create Virtual Environment
```bash
python3 -m venv pinyasuri_env
source pinyasuri_env/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Enable Serial Connection
Edit `/boot/config.txt`:
```bash
sudo nano /boot/config.txt
```

Add or ensure these lines are present:
```
enable_uart=1
dtoverlay=disable-bt
```

Disable serial console:
```bash
sudo raspi-config
# Navigate to: Interface Options > Serial Port
# Disable login shell over serial: No
# Enable serial port hardware: Yes
```

Reboot:
```bash
sudo reboot
```

### 5. Configure the System
Edit `config.py` to customize:
- Base directory paths
- Pixhawk connection address
- Camera resolution
- Model paths
- Classification labels

### 6. Prepare Your AI Model
Place your TFLite model file at:
```
/home/ece4/PINYASURI/pineapple_classifier.tflite
```

Update `CLASS_LABELS` in `config.py` to match your model's output classes.

## 🚀 Usage

### Basic Usage

```bash
cd ~/PinyaSuri_ECE4
source pinyasuri_env/bin/activate
python3 main_improved.py
```

### Mission Planning

1. Open Mission Planner
2. Connect to your Pixhawk
3. Plan waypoints in a grid pattern over your pineapple field
4. Upload mission to Pixhawk
5. Start the PinyaSuri system on the Raspberry Pi
6. Arm and start the mission from Mission Planner

### Testing Without Flight

For ground testing:
```bash
python3 test_flight.py
```

## 📊 Output Files

The system generates several output files in `/home/ece4/PINYASURI/`:

### 1. Image Classification Log
**File**: `image_classification_log.csv`

Columns:
- `timestamp_utc`: When the image was captured
- `image_path`: Path to captured image
- `lat`, `lon`: GPS coordinates
- `abs_alt_m`, `rel_alt_m`: Altitude in meters
- `mission_item_current`: Waypoint index
- `mission_item_total`: Total waypoints
- `pred_idx`: Predicted class index
- `pred_label`: Human-readable class name
- `confidence`: Prediction confidence (0-1)

### 2. Flight Metrics Log
**File**: `drone_flight_metrics.csv`

Columns:
- `timestamp_utc`: Timestamp
- `lat`, `lon`: GPS coordinates
- `abs_alt_m`, `rel_alt_m`: Altitudes
- `vib_rms_m_s2`: Vibration RMS
- `hover_jitter_m`: Position jitter during hover
- `altitude_stability_m`: Altitude standard deviation
- `battery_pct`: Battery percentage
- `flight_time_s`: Flight duration in seconds

### 3. Captured Images
**Directory**: `drone_images/`

Images are named: `wp{waypoint_index}_{timestamp}.jpg`

## 📁 Project Structure

```
PinyaSuri_ECE4/
├── config.py                  # Configuration settings
├── main.py                    # Original main script (fixed)
├── main_improved.py           # Improved main with retry logic
├── pixhawk_interface.py       # Pixhawk/MAVSDK interface
├── image_capture.py           # Camera control module
├── ai_classifier.py           # TFLite classifier
├── flight_metrics.py          # Flight metrics logger
├── test_flight.py             # Test script
├── requirements.txt           # Python dependencies
├── README.md                  # This file
└── pinyasuri_env/             # Virtual environment
```

## 🔍 Key Features

### 1. Robust Error Handling
- Automatic retry logic for Pixhawk connection
- Graceful handling of camera/model failures
- Comprehensive error logging

### 2. Real-time Monitoring
- Mission progress tracking
- GPS position logging
- Battery and flight time monitoring

### 3. Flight Metrics
- Vibration analysis (IMU data)
- Altitude stability measurement
- Hover jitter calculation

### 4. Data Persistence
- CSV logging for easy analysis
- Timestamped images with metadata
- Detailed classification results

## ⚠️ Troubleshooting

### Pixhawk Won't Connect

```bash
# Check serial devices
ls -l /dev/ttyAMA* /dev/serial*

# Test connection
python3 -c "from mavsdk import System; import asyncio; asyncio.run(System().connect('serial:///dev/ttyAMA0:57600'))"
```

### Camera Not Working

```bash
# Check camera is detected
libcamera-hello --list-cameras

# Test capture
libcamera-still -o test.jpg
```

### Model Loading Error

Ensure:
- Model file exists at the specified path
- Model is in `.tflite` format
- Model input size matches config

## 📝 Development Notes

### Main Components

1. **PixhawkInterface**: Handles MAVSDK communication, telemetry subscriptions
2. **ImageCapture**: Manages Picamera2 for high-resolution captures
3. **TFLiteClassifier**: Runs inference on captured images
4. **FlightMetricsLogger**: Calculates and logs flight performance metrics

### Adding New Classification Classes

Edit `config.py`:
```python
CLASS_LABELS = {
    0: "Healthy",
    1: "Black_Rot",
    2: "Heart_Rot",
    3: "Pink_Disease",
    # Add more...
}
```

## 🔮 Future Enhancements

- [ ] Web server integration for real-time monitoring
- [ ] Database storage instead of CSV
- [ ] Real-time classification result transmission to ground station
- [ ] Automatic mission generation based on field boundaries
- [ ] Multi-spectral imaging support
- [ ] Edge computing optimization for faster inference

## 📄 License

[Your License Here]

## 👥 Contributors

- [Your Name] - Thesis Project

## 📧 Contact

[Your Contact Information]

---

**Note**: This system is designed for research and educational purposes. Always follow local aviation regulations and safety guidelines when operating drones.
