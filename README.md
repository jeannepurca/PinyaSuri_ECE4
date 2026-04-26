# 🍍 PinyaSuri — AI-Driven Autonomous Drone System for Pineapple Health Monitoring

> An Electronics Engineering Capstone Project (ECE4) — autonomous drone system that detects and classifies pineapple plant diseases using computer vision and edge AI.

---

## 📖 Overview

**PinyaSuri** is a precision agriculture system that integrates autonomous drone flight, real-time image capture, and on-device AI inference to monitor pineapple crop health. The drone autonomously navigates a pre-programmed grid over a field, captures burst images at each waypoint, and classifies pineapple conditions using a YOLOv8n TFLite model running on a Raspberry Pi 5.

### What the system does:
1. Flies a pre-planned grid mission defined in Mission Planner
2. Detects arrival at each waypoint via distance and hover-detection algorithms
3. Captures 5-frame burst images per waypoint for redundancy
4. Runs real-time AI inference on each image using a YOLOv8n TFLite model
5. Logs all telemetry, images, and classification results to CSV files with GPS coordinates

---

## 🔍 Detectable Pineapple Conditions

| Class | Description |
|---|---|
| ✅ Healthy | No detected abnormalities |
| 🦠 Mealybug Wilt Disease | Pest-caused wilting |
| 🌱 Root Rot Disease | Soil-borne fungal infection |
| 👑 Crown Rot Disease | Crown tissue decay |
| 🍍 Fruit Fasciation Disorder | Abnormal fruit flattening |
| 👑👑 Multiple Crown Disorder | Multiple crown growth anomaly |

---

## 🔧 Hardware Requirements

| Component | Model | Role |
|---|---|---|
| Flight Controller | Pixhawk 2.4.8 | Autonomous navigation & stabilization |
| Onboard Computer | Raspberry Pi 5 | AI inference & image processing |
| Camera | Raspberry Pi Camera Module V3 (12MP) | High-resolution image capture |
| Connection | Serial UART (`/dev/ttyAMA0`) | MAVLink communication |
| Power | LiPo Battery (3S–4S) | Monitored via Pixhawk telemetry |

---

## 💻 Software Requirements

- **OS**: Raspberry Pi OS Bookworm (64-bit)
- **Python**: 3.9+
- **Ground Station**: Mission Planner (for mission planning and upload)

### Python Dependencies

```
mavsdk>=1.4.0
pymavlink>=0.3.0
picamera2
tflite-runtime
Pillow>=9.0.0
numpy>=1.21.0
aiofiles
```

Install all dependencies with:
```bash
pip install -r requirements.txt
```

---

## 🗂️ Project Structure

```
PinyaSuri_ECE4/
├── main_ai.py              # Main entry point with AI detection
├── main.py                 # Entry point without AI (capture only)
├── classifier.py           # YOLOv8n TFLite inference engine
├── camera.py               # Raspberry Pi camera control
├── pixhawk.py              # Pixhawk / MAVLink interface
├── metrics.py              # Flight telemetry logger
├── config.py               # System-wide configuration
├── logging_config.py       # Logging setup
├── requirements.txt        # Python dependencies
│
├── models/
│   └── YOLOv8n_PinyaSuri_AI.tflite
│
├── logs/
│   ├── raw_flight_data.csv
│   ├── image_captures.csv
│   ├── ai_classifications.csv
│   └── flight_YYYY-MM-DD.log
│
├── images/
│   └── YYYYMMDD/
│       └── pinyasuri_*.jpg
│
├── metrics_compu/          # Metrics computation notebooks
├── other_codes/            # Supplementary scripts
└── pinyasuri_env/          # Virtual environment
```

---

## 🛠️ Installation & Setup

### 1. Clone the Repository

```bash
cd ~
git clone https://github.com/jeannepurca/PinyaSuri_ECE4.git
cd PinyaSuri_ECE4
```

### 2. Create a Virtual Environment

```bash
python3 -m venv pinyasuri_env
source pinyasuri_env/bin/activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Serial (UART) Connection

Enable UART in the Pi's boot config:

```bash
sudo nano /boot/firmware/config.txt
```

Add the following lines:
```
enable_uart=1
dtoverlay=disable-bt
```

Disable the serial console via `raspi-config`:
```
Interface Options → Serial Port
  Login shell over serial: NO
  Serial port hardware enabled: YES
```

Then reboot and add your user to the `dialout` group:
```bash
sudo usermod -a -G dialout $USER
sudo reboot
```

### 5. Deploy the AI Model

```bash
mkdir -p models
cp /path/to/YOLOv8n_PinyaSuri_AI.tflite models/
```

Confirm the path in `config.py`:
```python
MODEL_PATH = MODEL_DIR / "YOLOv8n_PinyaSuri_AI.tflite"
```

---

## 🚀 Usage

### Step 1: Plan Mission in Mission Planner
1. Connect to Pixhawk via USB
2. Define a grid mission with `TAKEOFF → waypoints → RTL`
3. Set altitude to 3–4 meters
4. Upload mission to Pixhawk

### Step 2: Run the System

```bash
source pinyasuri_env/bin/activate

# With AI detection (recommended)
python3 main_ai.py

# Without AI (image capture only)
python3 main.py
```

### Step 3: Fly
1. Wait for `✓ Pixhawk connected successfully!`
2. Arm the drone in Mission Planner
3. Switch to AUTO mode to begin the mission
4. Monitor output for waypoint arrivals and capture events

### Stopping
- **Graceful**: `Ctrl+C` — the system will finalize logs before shutting down
- **Emergency**: Disarm via Mission Planner

---

## ⚙️ Configuration (`config.py`)

| Parameter | Default | Description |
|---|---|---|
| `MIN_ALTITUDE_FOR_CAPTURE` | `0.5 m` | Minimum altitude to trigger capture |
| `MAX_ALTITUDE_FOR_CAPTURE` | `5 m` | Maximum altitude to trigger capture |
| `WAYPOINT_CAPTURE_DISTANCE` | `1.5 m` | Distance threshold from waypoint |
| `HOVER_SPEED_THRESHOLD` | `0.5 m/s` | Speed below which hover is assumed |
| `STABILIZATION_DELAY` | `2 s` | Wait time before burst capture |
| `BURST_CAPTURE_COUNT` | `5` | Frames captured per waypoint |
| `BURST_INTERVAL` | `0.5 s` | Interval between burst frames |
| `DETECTION_THRESHOLD` | `0.5` | Minimum AI confidence to log |

---

## 🧠 How the 10-Point Capture Validation Works

Before capturing at any waypoint, the system checks all 10 of the following conditions:

1. ✅ Drone is armed
2. ✅ Flight mode is AUTO
3. ✅ A valid waypoint has been received
4. ✅ GPS position is available
5. ✅ Altitude is within capture range (0.5m – 5m)
6. ✅ Waypoint has not already been captured
7. ✅ Waypoint is a mapping point (excludes HOME, TAKEOFF, RTL)
8. ✅ Distance to waypoint is available
9. ✅ Drone is hovering (ground speed < 0.5 m/s)
10. ✅ Drone is within 1.5m of the waypoint

---

## 📊 Output Files

### `logs/raw_flight_data.csv` — Flight Telemetry (20 Hz)
Columns: `flight_id`, `timestamp_utc`, `roll_deg`, `pitch_deg`, `yaw_deg`, `accel_x/y/z`, `lat_deg`, `lon_deg`, `alt_m`, `groundspeed_m_s`, `waypoint_index`, `flight_mode`, `nav_state`, `is_hovering`

### `logs/image_captures.csv` — Capture Metadata
Columns: `timestamp`, `flight_id`, `waypoint`, `lat_deg`, `lon_deg`, `rel_alt_m`, `burst_id`, `burst_index`, `image_path`

### `logs/ai_classifications.csv` — AI Detection Results
Columns: `timestamp`, `flight_id`, `waypoint`, `burst_id`, `burst_index`, `image_path`, `detection_count`, `detections`

Detection JSON format:
```json
[
  {
    "class": "Healthy",
    "confidence": 0.927,
    "bbox": [0.1234, 0.5678, 0.2345, 0.6789]
  }
]
```

### `images/YYYYMMDD/` — Captured Images
Naming: `pinyasuri_flight{N}_wp{W}_burst{B}_{TIMESTAMP}.jpg`

---

## 📈 Performance (Tested on Raspberry Pi 5)

| Metric | Value |
|---|---|
| Waypoint GPS accuracy | ±0.5 m |
| Capture success rate | ~98% (in AUTO mode) |
| AI inference time | 200–300 ms per image |
| Burst capture duration | ~3 seconds (5 frames) |
| Telemetry logging rate | 20 Hz |
| CPU usage during capture + inference | 40–60% |
| RAM usage | ~500 MB |
| Image size | ~2 MB (12MP JPEG) |

---

## 🐛 Troubleshooting

**Pixhawk not connecting (`⚠ Waiting for heartbeat...`)**
```bash
ls -l /dev/ttyAMA0               # Check device exists
grep enable_uart /boot/firmware/config.txt  # Verify UART enabled
groups | grep dialout             # Confirm dialout group membership
```

**Camera not initializing**
```bash
libcamera-hello --list-cameras   # Check camera is detected
libcamera-still -o test.jpg      # Test manual capture
```

**No images captured during flight**
- Check if altitude is within `MIN/MAX_ALTITUDE_FOR_CAPTURE`
- Verify drone is reaching within 1.5m of each waypoint
- Confirm the drone is in AUTO mode (not GUIDED or STABILIZE)

**AI model not loading**
```bash
ls -l models/YOLOv8n_PinyaSuri_AI.tflite
python3 -c "import tflite_runtime.interpreter as tflite; print('TFLite OK')"
```

**CSV column mismatch**
```bash
rm logs/*.csv   # Delete old CSVs and restart — headers will regenerate
```

---

## ⚠️ Safety & Legal Notice

This system is intended for **research and educational use**.

Before flying, ensure you:
- ✅ Comply with local drone regulations (Philippines' CAAP, FAA, CAA, etc.)
- ✅ Register your drone if required
- ✅ Obtain permits for agricultural airspace use
- ✅ Maintain line-of-sight with the drone at all times
- ✅ Have an RC transmitter ready for manual override
- ✅ Monitor battery levels throughout the mission

The developers are not liable for accidents, property damage, or regulatory violations.

---

## 🔮 Future Work

- Real-time image streaming to a ground station
- Web dashboard for live monitoring
- PostgreSQL / cloud database integration
- Automatic grid mission generation from field boundaries
- Multi-spectral imaging (NDVI support)
- Cloud upload of images and detection logs
- Battery-based auto-RTL triggers
- Obstacle avoidance integration

---

## 🙏 Acknowledgments

- [Pixhawk](https://pixhawk.org/) — Open-source flight controller platform
- [MAVLink](https://mavlink.io/) — Lightweight UAV communication protocol
- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) — Object detection framework
- [Raspberry Pi Foundation](https://www.raspberrypi.org/) — Edge computing hardware
- [OpenCV](https://opencv.org/) — Computer vision library

---

## 👥 Team

**Electronics Engineering Capstone Project (ECE4)**
Institution: *(your university)*
Academic Year: 2025–2026

| Role | Name |
|---|---|
| System Architecture & Integration | *(name)* |
| AI Model Development | *(name)* |
| Hardware Integration | *(name)* |
| Field Testing & Validation | *(name)* |

**Academic Advisor**: *(advisor name)*

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
