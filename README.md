# PinyaSuri: AI-Driven Autonomous Drone System for Pineapple Health Monitoring

An autonomous drone system for detecting and classifying pineapple afflictions using computer vision and AI. This capstone project combines autonomous flight control, real-time image capture, and on-device AI inference for precision agriculture monitoring.

## 🚁 System Overview

The PinyaSuri system autonomously:
1. **Flies pre-programmed grid missions** using waypoints defined in Mission Planner
2. **Detects waypoint arrival** using distance and hover detection algorithms
3. **Captures burst images** (5 frames per waypoint) for redundancy
4. **Runs AI inference** on each image using YOLOv8n TFLite model
5. **Logs telemetry and results** to CSV files with GPS coordinates

### Key Capabilities
- **Autonomous waypoint navigation** with AUTO mode verification
- **Intelligent capture triggering** based on 10 validation checks
- **Burst photography** with configurable count and intervals
- **Real-time AI detection** using Non-Maximum Suppression (NMS)
- **Comprehensive logging** of flight metrics, images, and classifications

---

## 🔧 Hardware Requirements

| Component | Model | Purpose |
|-----------|-------|---------|
| **Flight Controller** | Pixhawk 2.4.8 | Autonomous navigation and stabilization |
| **Onboard Computer** | Raspberry Pi 5 | Image processing and AI inference |
| **Camera** | Raspberry Pi Camera Module V3 (12MP) | High-resolution image capture |
| **Connection** | Serial UART (`/dev/ttyAMA0`) | MAVLink communication |
| **Battery** | LiPo (3S-4S) | Monitored via Pixhawk telemetry |

---

## 📋 Software Requirements

- **OS**: Raspberry Pi OS Bookworm (64-bit)
- **Python**: 3.9+
- **Ground Station**: Mission Planner (for mission planning)

### Python Dependencies
```
pymavlink>=2.4.40
picamera2>=0.3.12
opencv-python>=4.8.0
numpy>=1.24.0
tflite-runtime>=2.14.0
```

---

## 🛠️ Installation

### 1. Clone Repository
```bash
cd ~
git clone https://github.com/your-username/PinyaSuri.git
cd PinyaSuri
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

### 4. Configure Serial Connection

**Enable UART:**
```bash
sudo nano /boot/firmware/config.txt
```

Add these lines:
```ini
enable_uart=1
dtoverlay=disable-bt
```

**Disable Serial Console:**
```bash
sudo raspi-config
# Interface Options > Serial Port
# Login shell over serial: NO
# Serial port hardware: YES
```

**Reboot:**
```bash
sudo reboot
```

**Verify Connection:**
```bash
ls -l /dev/ttyAMA0
# Should show: crw-rw---- 1 root dialout
```

### 5. Add User to Dialout Group
```bash
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

### 6. Deploy AI Model

Place your YOLOv8n TFLite model:
```bash
mkdir -p models
cp /path/to/YOLOv8n_PinyaSuri_AI.tflite models/
```

Update `config.py`:
```python
MODEL_PATH = MODEL_DIR / "YOLOv8n_PinyaSuri_AI.tflite"
```

---

## 🚀 Usage

### Mission Planning (Mission Planner)

1. **Connect to Pixhawk** via USB
2. **Plan Grid Mission:**
   - Set home location
   - Add `TAKEOFF` command (waypoint 1)
   - Add grid waypoints (2, 3, 4, ...)
   - Add `RTL` (Return to Launch) as final waypoint
3. **Configure waypoint parameters:**
   - Altitude: 3-4 meters (configurable in `config.py`)
   - Delay: 0 seconds (handled by PinyaSuri)
4. **Upload mission** to Pixhawk
5. **Verify waypoint count** matches expected grid

### Running the System

```bash
cd ~/PinyaSuri
source pinyasuri_env/bin/activate
python3 main_ai.py  # With AI detection
# OR
python3 main.py     # Without AI (capture only)
```

### Flight Procedure

1. **Start the script** on Raspberry Pi
2. **Wait for connection** (you'll see `✓ Pixhawk connected successfully!`)
3. **Arm the drone** in Mission Planner
4. **Start AUTO mode** to begin mission
5. **Monitor logs** for waypoint progress and captures
6. System will automatically:
   - Detect waypoint arrivals
   - Wait for stabilization (2s default)
   - Capture burst images (5 frames)
   - Run AI detection on each frame
   - Log results to CSV

### Stopping the System

- **Graceful shutdown**: Press `Ctrl+C`
- **Emergency**: Disarm drone in Mission Planner (system will finalize logs)

---

## 📊 Output Files

All files saved to project directory:

### 1. Flight Telemetry Log
**File**: `logs/raw_flight_data.csv`

| Column | Description |
|--------|-------------|
| `flight_id` | Unique ID (YYYYMMDD_F#) |
| `timestamp_utc` | UTC timestamp |
| `roll_deg`, `pitch_deg`, `yaw_deg` | Attitude angles |
| `accel_x/y/z_m_s2` | IMU acceleration |
| `lat_deg`, `lon_deg`, `alt_m` | GPS position |
| `groundspeed_m_s` | Horizontal speed |
| `waypoint_index` | Current waypoint |
| `flight_mode` | AUTO/GUIDED/STABILIZE |
| `nav_state` | Navigation state |
| `is_hovering` | Boolean hover detection |

### 2. Image Capture Log
**File**: `logs/image_captures.csv`

| Column | Description |
|--------|-------------|
| `timestamp` | Capture time (Unix) |
| `flight_id` | Associated flight |
| `waypoint` | Waypoint index |
| `lat_deg`, `lon_deg`, `rel_alt_m` | GPS coordinates |
| `burst_id` | Unique burst identifier |
| `burst_index` | Frame number (0-4) |
| `image_path` | Full path to image |

### 3. AI Classification Log
**File**: `logs/ai_classifications.csv`

| Column | Description |
|--------|-------------|
| `timestamp` | Detection time |
| `flight_id` | Associated flight |
| `waypoint` | Waypoint index |
| `burst_id`, `burst_index` | Burst metadata |
| `image_path` | Image analyzed |
| `detection_count` | Number of pineapples found |
| `detections` | JSON array of detections |

**Detection JSON Format:**
```json
[
  {
    "class": "Healthy",
    "confidence": 0.927,
    "bbox": [0.1234, 0.5678, 0.2345, 0.6789]
  }
]
```

### 4. Captured Images
**Directory**: `images/YYYYMMDD/`

**Naming Convention:**
```
pinyasuri_flight{N}_wp{W}_burst{B}_{TIMESTAMP}.jpg
```

Example: `pinyasuri_flight1_wp3_burst2_20260122T143052123.jpg`

---

## 📁 Project Structure

```
PinyaSuri/
├── config.py                    # System configuration
├── main.py                      # Main flight script (no AI)
├── main_ai.py                   # Main flight script (with AI)
├── pixhawk.py                   # Pixhawk/MAVLink interface
├── camera.py                    # Camera control module
├── classifier.py                # YOLOv8 TFLite inference
├── metrics.py                   # Flight metrics logger
├── logging_config.py            # Logging configuration
├── requirements.txt             # Python dependencies
├── README.md                    # This file
│
├── logs/                        # Generated CSV logs
│   ├── raw_flight_data.csv
│   ├── image_captures.csv
│   ├── ai_classifications.csv
│   ├── daily_flight_id.txt      # Flight counter
│   └── flight_YYYY-MM-DD.log    # Daily text logs
│
├── images/                      # Captured images by date
│   └── YYYYMMDD/
│       └── pinyasuri_*.jpg
│
├── models/                      # AI models
│   └── YOLOv8n_PinyaSuri_AI.tflite
│
└── pinyasuri_env/               # Virtual environment
```

---

## 🔍 Key Features

### 1. Intelligent Waypoint Capture System

**10-Point Validation Before Capture:**
1. ✅ Drone is armed
2. ✅ Flight mode is AUTO
3. ✅ Valid waypoint received
4. ✅ GPS position available
5. ✅ Altitude in range (0.5m - 5m)
6. ✅ Waypoint not already captured
7. ✅ Waypoint is a mapping point (excludes HOME, TAKEOFF, RTL)
8. ✅ Distance to waypoint available
9. ✅ Drone is hovering (speed < 0.5 m/s)
10. ✅ Within capture distance (< 1.5m from waypoint)

### 2. Burst Capture with Stabilization
- **Pre-capture delay**: 2 seconds for drone stabilization
- **Burst count**: 5 images per waypoint
- **Interval**: 0.5 seconds between frames
- **Mode verification**: Checks AUTO mode before each frame
- **Abort protection**: Stops burst if mode changes

### 3. Real-time AI Detection (main_ai.py only)
- **Model**: YOLOv8n TFLite (optimized for edge devices)
- **NMS**: Non-Maximum Suppression to filter overlapping detections
- **Classes Detected**:
  - Healthy pineapples
  - Mealybug Wilt Disease
  - Root Rot Disease
  - Crown Rot Disease
  - Fruit Fasciation Disorder
  - Multiple Crown Disorder

### 4. Comprehensive Logging
- **Flight telemetry** at 20 Hz (50ms intervals)
- **Per-image metadata** with GPS coordinates
- **AI detection results** with confidence scores
- **Daily flight numbering** with automatic reset

### 5. Safety Features
- Auto-abort capture if mode changes from AUTO
- Battery monitoring (with telemetry logging)
- Graceful shutdown on Ctrl+C
- Telemetry timeout detection
- Position data validation

---

## ⚙️ Configuration

Edit `config.py` to customize:

### Flight Parameters
```python
MIN_ALTITUDE_FOR_CAPTURE = 0.5      # meters
MAX_ALTITUDE_FOR_CAPTURE = 5        # meters
WAYPOINT_CAPTURE_DISTANCE = 1.5     # meters
HOVER_SPEED_THRESHOLD = 0.5         # m/s
STABILIZATION_DELAY = 2             # seconds
```

### Burst Capture
```python
BURST_CAPTURE_COUNT = 5             # images per waypoint
BURST_INTERVAL = 0.5                # seconds between captures
```

### AI Settings
```python
DETECTION_THRESHOLD = 0.5           # minimum confidence
MODEL_PATH = MODEL_DIR / "YOLOv8n_PinyaSuri_AI.tflite"
```

### Waypoint Exclusions
```python
WP_HOME = 0
WP_TAKEOFF = 1
# Last waypoint (RTL) automatically excluded
```

---

## 🐛 Troubleshooting

### Pixhawk Connection Issues

**Problem**: `⚠ Waiting for heartbeat...` never completes

**Solutions:**
```bash
# Check serial device exists
ls -l /dev/ttyAMA0

# Verify UART is enabled
grep enable_uart /boot/firmware/config.txt

# Test with MAVProxy
mavproxy.py --master=/dev/ttyAMA0 --baudrate=57600

# Check permissions
groups | grep dialout  # Should include dialout group
```

### Camera Not Working

**Problem**: `⚠ Failed to initialize camera`

**Solutions:**
```bash
# Check camera is detected
libcamera-hello --list-cameras

# Test manual capture
libcamera-still -o test.jpg

# Check camera cable connection
vcgencmd get_camera
# Should show: supported=1 detected=1
```

### No Images Captured During Flight

**Check Debug Logs:**
```bash
tail -f logs/flight_$(date +%Y-%m-%d).log
```

**Common Issues:**
- Altitude too low/high (check `MIN/MAX_ALTITUDE_FOR_CAPTURE`)
- Distance to waypoint > 1.5m (increase `WAYPOINT_CAPTURE_DISTANCE`)
- Drone not hovering (reduce `HOVER_SPEED_THRESHOLD`)
- Wrong flight mode (must be AUTO)

### AI Model Not Loading

**Problem**: `⚠️ Failed to initialize AI detector`

**Solutions:**
```bash
# Check model file exists
ls -l models/YOLOv8n_PinyaSuri_AI.tflite

# Verify TFLite runtime
python3 -c "import tflite_runtime.interpreter as tflite; print('OK')"

# Test model manually
python3 -c "from classifier import PinyaSuriAI; ai = PinyaSuriAI()"
```

### CSV Columns Mismatch

**If you see missing data in CSVs:**
- Delete old CSV files: `rm logs/*.csv`
- Restart the system to regenerate headers
- Check `metrics.py` line 144 includes `nav_state`

---

## 📈 Performance Metrics

### Tested Performance
- **Waypoint accuracy**: ±0.5m GPS precision
- **Capture success rate**: 98% (in AUTO mode)
- **AI inference time**: ~200-300ms per image (Pi 5)
- **Burst capture time**: ~3 seconds total (5 frames)
- **Flight telemetry rate**: 20 Hz

### Resource Usage (Raspberry Pi 5)
- **CPU**: 40-60% during capture + inference
- **RAM**: ~500MB
- **Storage**: ~2MB per image (12MP JPEG)

---

## 🔮 Future Enhancements

- [ ] Real-time image streaming to ground station
- [ ] PostgreSQL database integration
- [ ] Web dashboard for live monitoring
- [ ] Automatic grid mission generation from field boundaries
- [ ] Multi-spectral imaging support (NDVI)
- [ ] Cloud upload of images and results
- [ ] Battery estimation and auto-RTL
- [ ] Obstacle avoidance integration

---

## 📚 Technical Documentation

### MAVLink Messages Used
- `HEARTBEAT` - System status and mode
- `GLOBAL_POSITION_INT` - GPS coordinates
- `ATTITUDE` - Roll, pitch, yaw
- `RAW_IMU` - Acceleration data
- `MISSION_CURRENT` - Current waypoint
- `NAV_CONTROLLER_OUTPUT` - Distance to waypoint
- `BATTERY_STATUS` - Battery telemetry

### Image Processing Pipeline
1. Capture image via Picamera2 (4056x3040)
2. Load image with OpenCV
3. Preprocess for YOLOv8 (resize, normalize)
4. Run TFLite inference
5. Apply NMS to filter detections
6. Log results with metadata

### Flight State Machine
```
DISARMED → ARMED (start flight) → AUTO mode → 
Waypoint navigation → Hover detection → 
Stabilization delay → Burst capture → 
AI inference → Next waypoint → ... → 
DISARMED (end flight)
```

---

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

---

## 👥 Contributors

**Electronics Engineering Capstone Project**
- [Your Name] - System Architecture & Integration
- [Team Member 2] - AI Model Development
- [Team Member 3] - Hardware Integration
- [Team Member 4] - Field Testing & Validation

**Academic Advisor**: [Advisor Name]  
**Institution**: [Your University]  
**Year**: 2026

---

## 📧 Contact

**Project Maintainer**: [Your Name]  
**Email**: your.email@university.edu  
**GitHub**: https://github.com/your-username/PinyaSuri

---

## ⚠️ Safety & Legal Notice

This system is designed for **research and educational purposes**.

**Before flying:**
- ✅ Check local drone regulations (CAA/FAA)
- ✅ Register your drone if required
- ✅ Obtain necessary permits for agricultural monitoring
- ✅ Ensure flight area is clear of obstacles
- ✅ Have manual override ready via RC transmitter
- ✅ Monitor battery levels continuously
- ✅ Follow line-of-sight regulations

**The developers are not responsible for:**
- Accidents or property damage
- Violations of aviation laws
- Misuse of the system

**Always prioritize safety over data collection.**

---

## 🙏 Acknowledgments

- **Pixhawk** - Open-source flight controller
- **MAVLink** - Micro Air Vehicle communication protocol
- **Ultralytics YOLOv8** - Object detection framework
- **Raspberry Pi Foundation** - Affordable computing platform
- **OpenCV** - Computer vision library

---

**Last Updated**: January 2026  
**Version**: 1.0.0