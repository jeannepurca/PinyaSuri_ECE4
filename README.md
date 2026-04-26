# 🍍 PinyaSuri — AI-Driven Autonomous Drone System for Pineapple Affliction Detection, Classification, and Monitoring

> **ECE Capstone Project** · Polytechnic University of the Philippines – Sto. Tomas Campus  
> Bachelor of Science in Electronics Engineering · Academic Year 2025–2026

---

## 📖 Overview

**PinyaSuri** is an AI-based autonomous drone system developed to address the limitations of traditional manual inspection in pineapple plantation monitoring. The system integrates drone technology, image processing, deep learning, and a **grid-based localization framework** to enable efficient, scalable, and non-invasive detection and classification of pineapple afflictions.

Aerial images are captured by a drone-mounted Raspberry Pi Camera Module V3 during autonomous grid-based flight and processed in real-time using a **YOLOv8n Model** deployed on a Raspberry Pi 5. Detection results — along with GPS coordinates and timestamps — are logged and displayed through a Flask-based web interface, enabling spatially-aware crop health monitoring.

---

## 🎯 Objectives

1. Develop a drone-based image acquisition system for pineapple field monitoring
2. Design and train a YOLO-based deep learning model for affliction detection and classification
3. Implement a grid-based localization framework to map affliction occurrences spatially
4. Provide farmers and decision-makers with actionable, data-driven crop management support

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

Four YOLO architectures were trained and evaluated on a dataset of **2,100 annotated images** (70% train / 20% validation / 10% test). **YOLOv8n** was selected as the optimal model for deployment.

### Model Comparison

| Model | Training Accuracy (%) | Testing Accuracy (%) | Precision (%) | Recall (%) | F1-Score (%) | mAP@0.5 (%) |
|---|---|---|---|---|---|---|
| **YOLOv8n** ✅ | **87.06** | **89.36** | **89.28** | **80.18** | **84.75** | **89.36** |
| YOLOv8s | 77.19 | 81.62 | 88.72 | 66.70 | 78.13 | 81.62 |
| YOLOv11 | 85.84 | 88.02 | 88.52 | 80.20 | 84.77 | 88.02 |
| YOLOv11s | 67.40 | 66.03 | 81.29 | 66.73 | 66.31 | 66.03 |

YOLOv8n achieved the highest testing accuracy with strong generalization and minimal overfitting, making it the best-suited model for edge deployment on the Raspberry Pi 5.

### Field Validation (PinyaSuri AI System)

The system was validated against expert farmer visual inspection on **35 pineapple samples** (30 same, 5 different):

| Metric | Macro Average | Micro Average |
|---|---|---|
| Accuracy | 0.962 | 0.962 |
| Precision | 0.840 | 0.897 |
| Recall | 0.900 | 0.963 |
| F1-Score | 0.861 | 0.929 |

**Cohen's Kappa: 83.5 → Almost Perfect Agreement** with farmer-validated ground truth labels.

### Per-Class Recall Highlights (YOLOv8n)

| Class | Recall |
|---|---|
| Fruit Rot Disease | 100% |
| Healthy | 98% |
| Root Rot Disease | 93% |
| Fruit Fasciation Disorder | 91% |
| Multiple Crown Disorder | 88% |
| Mealybug Wilt Disease | 87% |
| Crown Rot Disease | 83% |

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
- **Web Framework**: Flask (for the GUI/web interface)
- **Deployment**: Render.com (web application hosting)
- **Annotation Tool**: Roboflow (used for dataset labeling)

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

## 🗂️ Project Structure

```
PinyaSuri_ECE4/
├── main_ai.py              # Main entry point — with AI detection
├── main.py                 # Entry point — image capture only (no AI)
├── classifier.py           # YOLOv8n TFLite inference engine
├── camera.py               # Raspberry Pi camera control
├── pixhawk.py              # Pixhawk / MAVLink interface
├── metrics.py              # Flight telemetry logger
├── config.py               # System-wide configuration
├── logging_config.py       # Logging setup
├── requirements.txt        # Python dependencies
│
├── models/
│   └── YOLOv8n_PinyaSuri_AI.tflite   # Deployed AI model
│
├── logs/
│   ├── raw_flight_data.csv            # Telemetry logs (20 Hz)
│   ├── image_captures.csv             # Per-image metadata
│   ├── ai_classifications.csv         # AI detection results
│   └── flight_YYYY-MM-DD.log          # Daily text logs
│
├── images/
│   └── YYYYMMDD/
│       └── pinyasuri_*.jpg            # Timestamped captured images
│
├── metrics_compu/          # Performance metrics computation notebooks
├── other_codes/            # Supplementary/experimental scripts
└── pinyasuri_env/          # Python virtual environment
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

# With AI detection (recommended)
python3 main_ai.py

# Without AI — image capture only
python3 main.py
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

## 🌐 Web Interface (GUI)

The PinyaSuri web interface is built with **Flask** and hosted on **Render.com**. It includes:

| Section | Description |
|---|---|
| 🏠 Landing Page | Welcome page and system introduction |
| 📊 Main Dashboard | Overview of AI detection results and crop health summary |
| 📋 Data Logs | Per-flight detection records with timestamps and GPS |
| 📷 Upload Section | Upload images for on-demand AI analysis |
| 💊 Management Strategies | Recommended interventions per detected affliction |

---

## 📈 System Performance Summary

| Metric | Value |
|---|---|
| Dataset size | 2,100 images across 7 classes |
| Train / Val / Test split | 70% / 20% / 10% |
| Image resolution (training) | 640×640 px |
| Best model | YOLOv8n (89.36% mAP@0.5) |
| Field accuracy | 96.2% |
| Cohen's Kappa (vs. farmer) | 83.5 — Almost Perfect Agreement |
| Field agreement rate | 30 / 35 samples |
| Flight altitude | 1.5 m |
| Camera angle | 45° |
| Telemetry logging rate | 20 Hz |
| AI inference time (RPi 5) | ~200–300 ms per image |

---

## 🐛 Troubleshooting

**Pixhawk not connecting (`⚠ Waiting for heartbeat...`)**
```bash
ls -l /dev/ttyAMA0                          # Check device exists
grep enable_uart /boot/firmware/config.txt  # Verify UART is enabled
groups | grep dialout                       # Confirm dialout group membership
```

**Camera not initializing**
```bash
libcamera-hello --list-cameras   # Verify camera is detected
libcamera-still -o test.jpg      # Test a manual capture
```

**No images captured during flight**
- Confirm altitude is between 0.5m and 5m
- Ensure the drone reaches within 1.5m of each waypoint
- Check that the flight mode is AUTO (not GUIDED or STABILIZE)

**AI model not loading**
```bash
ls -l models/YOLOv8n_PinyaSuri_AI.tflite
python3 -c "import tflite_runtime.interpreter as tflite; print('TFLite OK')"
```

**CSV column mismatch from old logs**
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

## 🙏 Acknowledgments

The researchers gratefully acknowledge:
- **Polytechnic University of the Philippines – Sto. Tomas Campus** for providing the research environment
- **Dr. Robert G. de Luna, PECE** and **Engr. Isagani G. Garcia** — project advisers
- **Alumni contributors**: Aeris John P. Alonzo, Patrica Nicole A. Austria, Kiar Howard P. Fule, Raniel Joseph G. Ison, Kurt Lheo M. Luna, and Josiah Miguel M. Paniza — for additional dataset contributions
- **Mr. Rodrigo Arcillas** and the **Roxas family** — for field access, crops, and hospitality during data collection
- Pineapple farmers across Batangas, Cavite, and Laguna for their cooperation

Tools and frameworks: [Pixhawk](https://pixhawk.org/) · [MAVLink](https://mavlink.io/) · [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) · [Raspberry Pi Foundation](https://www.raspberrypi.org/) · [OpenCV](https://opencv.org/) · [Roboflow](https://roboflow.com/) · [Flask](https://flask.palletsprojects.com/)

---

## 👥 Research Team

**Polytechnic University of the Philippines – Sto. Tomas Campus**  
BS Electronics Engineering | Capstone Project (ECE4) | 2025–2026

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

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 📚 Citation

If you use this work in your research, please cite:

> De Guzman, A. M. D., Hernandez, D. K. C., Libarnes, A. L. O., Licayan, J. B. A., Purca, J. M. M., Roxas, A. T., de Luna, R. G., & Garcia, I. G. (2026). *PinyaSuri: An AI-Driven Autonomous Drone System with Grid Localization for Pineapple Afflictions Detection, Classification, and Monitoring*. Polytechnic University of the Philippines – Sto. Tomas Campus.