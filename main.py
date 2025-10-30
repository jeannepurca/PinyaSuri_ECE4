import time
from pixhawk_interface import PixhawkInterface
from image_capture import ImageCapture
from metrics import Metrics
from utils import log_event

def main():
    pixhawk = PixhawkInterface('/dev/serial0', 57600)                   # Connect to Pixhawk
    camera = ImageCapture("/home/ece4/PINYASURI/drone_images")          # Initialize camera
    log_file = "/home/ece4/PINYASURI/drone_metrics.csv"

    attitude_history = {'roll': [], 'pitch': [], 'yaw': []}
    ax_history, ay_history, az_history = [], [], []

    while True:
        groundspeed = pixhawk.get_groundspeed()                         # Get current groundspeed
        if groundspeed is not None:                                     # Valid groundspeed
            print(f"[Main]  Speed: {groundspeed:.2f} m/s")              # Print speed

            # Collect telemetry for metrics
            att = pixhawk.get_attitude()
            imu = pixhawk.get_imu()
            gps = pixhawk.get_gps()

            if att:
                for k in att: attitude_history[k].append(att[k])
            if imu:
                ax_history.append(imu['ax'])
                ay_history.append(imu['ay'])
                az_history.append(imu['az'])

            # If drone stopped, capture image and compute metrics
            if groundspeed < 0.5:                                       # Check if drone is stopped
                print("[Main] Drone stopped — capturing image...")      # Log event
                image_path = camera.capture_image()                     # Capture image

                # Compute metrics
                roll_std, pitch_std, yaw_std = Metrics.flight_stability(attitude_history)
                rms_vib = Metrics.rms_vibration(ax_history, ay_history, az_history)

                # Log everything
                log_event(log_file, waypoint=None, gps=gps, image_path=image_path)
                print(f"[Metrics] Roll σ={roll_std:.3f}, Pitch σ={pitch_std:.3f}, Yaw σ={yaw_std:.3f}, RMS vib={rms_vib:.3f}")

                time.sleep(5)                                           # Avoid repeated captures

if __name__ == "__main__":
    main()