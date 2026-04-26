# 🍍 PinyaSuri — An AI-Driven Autonomous Drone System for Pineapple Affliction Detection, Classification, and Monitoring

**Polytechnic University of the Philippines – Sto. Tomas Campus**  
*Bachelor of Science in Electronics Engineering* | *Academic Year 2025–2026*

***Capstone Project (ECE 4)***
| Researcher | Email |
|---|---|
| Andrea Marione D. De Guzman | andreamarioned1@gmail.com |
| Daniella Kim C. Hernandez | dnllkmhrnndz@gmail.com |
| Ashley Louise O. Libarnes | ashleylibarnes12@gmail.com |
| James Bernard A. Licayan | jblicayan28@gmail.com |
| Jeanne Mae M. Purca | jeannemaemanicpurca@gmail.com |
| April T. Roxas | aprilroxas.univ@gmail.com |

**Academic Advisers:** Dr. Robert G. de Luna, PECE · Engr. Isagani G. Garcia

---

## 📖 Overview

**PinyaSuri** is an AI-based autonomous drone system developed to address the limitations of traditional manual inspection in pineapple plantation monitoring. The system integrates drone technology, image processing, deep learning, and a **grid-based localization framework** to enable efficient, scalable, and non-invasive detection and classification of pineapple afflictions.

Aerial images are captured by a drone-mounted Raspberry Pi Camera Module V3 during autonomous grid-based flight and processed in real-time using a **YOLOv8n Model** deployed on a Raspberry Pi 5. Detection results — along with GPS coordinates and timestamps — are logged for post-flight analysis and monitoring.

> **📌 Repository Scope**  
> This repository contains exclusively the **onboard control system** code running on the **Raspberry Pi 5** — covering autonomous flight control, image capture, real-time AI inference, and telemetry logging. The **AI model training pipeline** and the **web-based monitoring interface** are maintained in separate repositories and are not included here.

---

## 🔍 Detectable Pineapple Conditions (7 Classes)

| Class | Description |
|---|---|
| ✅ Healthy | No detected abnormalities |
| 👑 Crown Rot Disease | Fungal decay of the crown tissue |
| 🌱 Root Rot Disease | Soil-borne infection affecting roots |
| 🍍 Fruit Rot Disease | Post-harvest or field fruit decay |
| 🦠 Mealybug Wilt Disease | Pest-caused wilting and leaf discoloration |
| 👑👑 Multiple Crown Disorder | Abnormal multiple crown growth |
| 🔀 Fruit Fasciation Disorder | Abnormal flattening or fasciation of the fruit |

---

## 🤖 AI Model Performance

Four YOLO architectures were trained and evaluated. YOLOv8n achieved the highest testing accuracy with strong generalization and minimal overfitting, making it the best-suited model for edge deployment on the Raspberry Pi 5. Therefore, it was selected as the optimal model for deployment.

---

## 🔧 Hardware Components

| Component | Model | Role |
|---|---|---|
| Flight Controller | Pixhawk 2.4.8 | Autonomous navigation, GPS-based waypoint tracking, attitude control |
| Onboard Computer | Raspberry Pi 5 | AI inference, image processing, data logging |
| Camera | Raspberry Pi Camera Module V3 (12MP) | Aerial image capture |
| Frame | S500 Quadcopter Frame | Drone structure |
| Motors | Brushless Motors (2212 920KV) | Propulsion via ESCs |
| ESC | 30A Electronic Speed Controllers | Motor speed and direction control |
| Propellers | 1045 Propellers | Lift generation |
| RC Control | FlySky FS-i6X Transmitter & Receiver | Manual override |
| Connection | Serial UART (`/dev/ttyAMA0`) | MAVLink communication between Pixhawk and RPi |
| Power | LiPo Battery (3S–4S) | Monitored via Pixhawk telemetry |

> The camera is mounted **downward-facing beneath the frame**, capturing images at **1.5m altitude and 45° angle** for optimal field coverage.

---

## 💻 Software Requirements

- **OS**: Raspberry Pi OS Bookworm (64-bit)
- **Python**: 3.9+
- **Ground Station**: Mission Planner (for mission planning and waypoint upload)

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

Install all dependencies:
```bash
pip install -r requirements.txt
```

---

## 🗂️ Repository Structure

This repository contains only the files that run directly on the **Raspberry Pi 5** during drone operation. Supporting components such as the AI model training notebooks and the web monitoring interface are not part of this codebase.

```
PinyaSuri_ECE4/
├── main_ai.py              # Main Entry Point
├── classifier.py           # YOLOv8n TFLite Inference Engine
├── camera.py               # Raspberry Pi Camera Control
├── pixhawk.py              # Pixhawk / MAVLink Interface
├── metrics.py              # Flight Telemetry Logger
├── config.py               # System-wide Configuration
├── logging_config.py       # Logging Setup
├── requirements.txt        # Python Dependencies
│
├── models/
│   └── YOLOv8n_PinyaSuri_AI.tflite    # Deployed AI model (not included — place here)
│
├── logs/                              # Auto-generated at runtime
│   ├── raw_flight_data.csv            # Telemetry logs (20 Hz)
│   ├── image_captures.csv             # Per-image metadata
│   ├── ai_classifications.csv         # AI detection results
│   └── flight_YYYY-MM-DD.log          # Daily text logs
│
├── images/                            # Auto-generated at runtime
│   └── YYYYMMDD/
│       └── pinyasuri_*.jpg            # Timestamped captured images
│
├── metrics_compu/          # Performance Metrics Computation Notebooks
├── other_codes/            # Supplementary/Experimental Scripts
└── pinyasuri_env/          # Python Virtual Environment
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

Add:
```
enable_uart=1
dtoverlay=disable-bt
```

Disable serial console via `raspi-config`:
```
Interface Options → Serial Port
  Login shell over serial: NO
  Serial port hardware enabled: YES
```

Add your user to the `dialout` group:
```bash
sudo usermod -a -G dialout $USER
sudo reboot
```

Verify:
```bash
ls -l /dev/ttyAMA0
# Expected: crw-rw---- 1 root dialout
```

### 5. Deploy the AI Model

The trained YOLOv8n TFLite model is not included in this repository. Place your model file in the `models/` directory:

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
2. Plan a grid mission: `TAKEOFF → grid waypoints → RTL`
3. Set flight altitude to **1.5 meters**, camera angle at **45°**
4. Upload mission to Pixhawk and verify waypoint count

### Step 2: Run the System on Raspberry Pi

```bash
source pinyasuri_env/bin/activate
python3 main_ai.py
```

### Step 3: Fly
1. Wait for `✓ Pixhawk connected successfully!`
2. Arm the drone in Mission Planner
3. Switch to AUTO mode to begin the grid mission
4. The system will autonomously navigate, capture, run inference, and log results per waypoint

### Stopping
- **Graceful**: `Ctrl+C` — logs are finalized automatically
- **Emergency**: Disarm via Mission Planner or RC transmitter override

---

## 🧠 10-Point Waypoint Capture Validation

Before capturing at any waypoint, the system verifies all of the following:

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

## ⚙️ Configuration (`config.py`)

| Parameter | Default | Description |
|---|---|---|
| `MIN_ALTITUDE_FOR_CAPTURE` | `0.5 m` | Minimum altitude to allow capture |
| `MAX_ALTITUDE_FOR_CAPTURE` | `5 m` | Maximum altitude to allow capture |
| `WAYPOINT_CAPTURE_DISTANCE` | `1.5 m` | Acceptable distance from waypoint |
| `HOVER_SPEED_THRESHOLD` | `0.5 m/s` | Speed below which hover is assumed |
| `STABILIZATION_DELAY` | `2 s` | Wait time before burst begins |
| `BURST_CAPTURE_COUNT` | `5` | Frames per waypoint |
| `BURST_INTERVAL` | `0.5 s` | Interval between burst frames |
| `DETECTION_THRESHOLD` | `0.5` | Minimum AI confidence to log |

---

## 📊 Output Files

All output files are auto-generated at runtime on the Raspberry Pi 5.

### `logs/raw_flight_data.csv` — Telemetry (20 Hz)
Columns: `flight_id`, `timestamp_utc`, `roll_deg`, `pitch_deg`, `yaw_deg`, `accel_x/y/z_m_s2`, `lat_deg`, `lon_deg`, `alt_m`, `groundspeed_m_s`, `waypoint_index`, `flight_mode`, `nav_state`, `is_hovering`

### `logs/image_captures.csv` — Image Metadata
Columns: `timestamp`, `flight_id`, `waypoint`, `lat_deg`, `lon_deg`, `rel_alt_m`, `burst_id`, `burst_index`, `image_path`

### `logs/ai_classifications.csv` — AI Results
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

## 🐛 Troubleshooting

**Pixhawk not connecting (`⚠ Waiting for heartbeat...`):**
```bash
ls -l /dev/ttyAMA0                          # Check device exists
grep enable_uart /boot/firmware/config.txt  # Verify UART is enabled
groups | grep dialout                       # Confirm dialout group membership
```

**Camera not initializing:**
```bash
libcamera-hello --list-cameras   # Verify camera is detected
libcamera-still -o test.jpg      # Test a manual capture
```

**No images captured during flight:**
- Confirm altitude is between 0.5m and 5m
- Ensure the drone reaches within 1.5m of each waypoint
- Check that the flight mode is AUTO (not GUIDED or STABILIZE)

**AI model not loading:**
```bash
ls -l models/YOLOv8n_PinyaSuri_AI.tflite
python3 -c "import tflite_runtime.interpreter as tflite; print('TFLite OK')"
```

**CSV column mismatch from old logs:**
```bash
rm logs/*.csv   # Delete outdated CSVs — headers regenerate on next run
```

---

## ⚠️ Safety & Legal Notice

This system is intended for **research and educational use**.

Before operating, ensure you:
- ✅ Comply with Philippine CAAP drone regulations
- ✅ Register your drone if required
- ✅ Obtain proper permits for agricultural airspace use
- ✅ Maintain visual line-of-sight at all times
- ✅ Have an RC transmitter ready for manual override
- ✅ Monitor battery levels throughout the mission

The developers are not liable for accidents, property damage, or regulatory violations arising from use of this system.

---

## 🔮 Future Work

- Expanding the dataset to improve robustness under varying lighting and field conditions
- Integrating real-time decision support for automated field interventions
- Real-time image streaming to a ground station or web dashboard
- Multi-spectral imaging support (NDVI) for deeper crop health analysis
- Cloud-based storage and upload of images and detection logs
- Battery-based auto-RTL triggers for safe autonomous return
- Obstacle avoidance module integration

---

## 🛠 Tools and Frameworks: 
[Pixhawk](https://pixhawk.org/) · [MAVLink](https://mavlink.io/) · [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) · [Raspberry Pi Foundation](https://www.raspberrypi.org/) · [OpenCV](https://opencv.org/) · [Roboflow](https://roboflow.com/) · [Flask](https://flask.palletsprojects.com/)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 📚 Citation

If you use this work in your research, please cite:

> De Guzman, Hernandez, Libarnes, Licayan, Purca, Roxas, de Luna, & Garcia (2026). PinyaSuri: An AI-driven autonomous drone system with grid localization for pineapple afflictions detection, classification, and monitoring. *Polytechnic University of the Philippines – Sto. Tomas Campus.*