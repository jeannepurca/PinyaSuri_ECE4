# PinyaSuri Quick Start Guide

## 🚀 First Time Setup (on Raspberry Pi 5)

```bash
# 1. Install dependencies
cd ~/PinyaSuri_ECE4
python3 -m venv pinyasuri_env
source pinyasuri_env/bin/activate
pip install -r requirements.txt

# 2. Configure serial port
sudo raspi-config
# Interface Options > Serial Port
# Login shell: No | Hardware: Yes

# 3. Add user to dialout group
sudo usermod -a -G dialout $USER
# Then logout and login

# 4. Reboot
sudo reboot
```

## 🔧 Configuration

Edit `config.py`:
```python
# Update these for your setup:
BASE_DIR = Path("/home/ece4/PINYASURI")
PIXHAWK_ADDRESS = "serial:///dev/ttyAMA0:57600"
MODEL_PATH = BASE_DIR / "pineapple_classifier.tflite"

# Update classification labels:
CLASS_LABELS = {
    0: "Healthy",
    1: "Disease_Name_1",
    2: "Disease_Name_2",
}
```

## ✅ Pre-Flight Checks

```bash
# Run system check
python3 system_check.py

# Test camera
libcamera-still -o test.jpg

# Check Pixhawk connection
ls -l /dev/ttyAMA0
```

## 🎯 Running the System

### Ground Test (No Flight)
```bash
source pinyasuri_env/bin/activate
python3 test_flight.py
```

### Real Mission
```bash
# 1. Plan mission in Mission Planner
# 2. Upload mission to Pixhawk
# 3. Start PinyaSuri system
source pinyasuri_env/bin/activate
python3 main_improved.py

# 4. Arm drone and start mission from Mission Planner
```

## 📊 Checking Results

```bash
# View classification log
cat /home/ece4/PINYASURI/image_classification_log.csv

# View flight metrics
cat /home/ece4/PINYASURI/drone_flight_metrics.csv

# View images
ls -lh /home/ece4/PINYASURI/drone_images/
```

## 🛑 Emergency Stop

Press `Ctrl+C` in the terminal running the script

## 📝 Common Commands

```bash
# Activate environment
source pinyasuri_env/bin/activate

# Check system
python3 system_check.py

# View logs
tail -f /home/ece4/PINYASURI/pinyasuri.log

# Test components individually
python3 test_flight.py
```

## ⚠️ Troubleshooting

### Pixhawk not connecting
```bash
ls -l /dev/ttyAMA0  # Check device exists
sudo chmod 666 /dev/ttyAMA0  # Fix permissions if needed
```

### Camera not working
```bash
libcamera-hello --list-cameras  # Check camera
sudo raspi-config  # Enable camera interface
```

### Model not found
```bash
# Check path in config.py matches actual location
ls -l /home/ece4/PINYASURI/pineapple_classifier.tflite
```

## 📖 More Info

- Full documentation: `README.md`
- Fix details: `FIXES_SUMMARY.md`
- System architecture: See code comments

---

**Pro Tip**: Always run `system_check.py` before field deployment!
