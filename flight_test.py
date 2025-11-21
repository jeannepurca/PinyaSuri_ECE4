import asyncio
import math
import csv
import time
from pathlib import Path
from mavsdk import System
from picamera2 import Picamera2
import numpy as np

# Utility Functions
def distance_m(lat1, lon1, lat2, lon2):
    """Haversine distance (meters)."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (math.sin(dphi / 2)**2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def vector_magnitude(x, y, z):
    return math.sqrt(x*x + y*y + z*z)

# Setup Camera
picam = Picamera2()
picam.configure(picam.create_still_configuration())
picam.start()

# CSV Logger Setup
LOG_DIR = Path("flight_logs")
LOG_DIR.mkdir(exist_ok=True)
CSV_FILE = LOG_DIR / f"flight_metrics_{int(time.time())}.csv"

with open(CSV_FILE, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp",
        "waypoint_index",
        "latitude",
        "longitude",
        "relative_alt",
        "velocity_mps",
        "imu_accel_x",
        "imu_accel_y",
        "imu_accel_z",
        "accel_rms",
        "distance_to_waypoint_m",
        "position_jitter_m"
    ])

print(f"[LOG] CSV logging to: {CSV_FILE}")

# Rolling window for hover jitter
jitter_window = []

# Main Flight Integration Test
async def main():
    drone = System()
    print("[INFO] Connecting to Pixhawk...")
    await drone.connect(system_address="serial:///dev/ttyAMA0:57600")

    print("[INFO] Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("[INFO] Drone connected!")
            break

    # Fetch mission waypoints
    mission_raw = await drone.mission_raw.download_mission()
    waypoints = mission_raw.mission_items
    print(f"[INFO] Mission has {len(waypoints)} waypoints.")

    current_wp = 0
    reached_wp = False

    async for mission_progress in drone.mission.mission_progress():
        if mission_progress.current >= 0:
            current_wp = mission_progress.current

        # When drone ARRIVES at waypoint
        if mission_progress.current == mission_progress.total - 1:
            # Last waypoint logic is the same
            pass

        # Detect if drone has stopped at waypoint
        async for pos in drone.telemetry.position():
            async for vel in drone.telemetry.velocity_ned():
                velocity = vector_magnitude(
                    vel.velocity_north_m_s,
                    vel.velocity_east_m_s,
                    vel.velocity_down_m_s
                )

                # Consider "stopped" if speed < 0.3 m/s
                if velocity < 0.3:
                    reached_wp = True

                if reached_wp:
                    print(f"[INFO] Drone stopped at waypoint {current_wp}. Capturing image...")

                    # ----------- CAPTURE IMAGE ------------
                    img_path = LOG_DIR / f"wp_{current_wp}_{int(time.time())}.jpg"
                    picam.capture_file(str(img_path))
                    print(f"[IMAGE] Saved: {img_path}")

                    # ----------- LOG METRICS -------------
                    imu = None
                    async for imu_data in drone.telemetry.scaled_imu():
                        imu = imu_data
                        break

                    accel_rms = vector_magnitude(
                        imu.accelerometer_x,
                        imu.accelerometer_y,
                        imu.accelerometer_z
                    )

                    # Position jitter window (hover stability)
                    jitter_window.append((pos.latitude_deg, pos.longitude_deg))
                    if len(jitter_window) > 30:
                        jitter_window.pop(0)

                    # Compute jitter as max distance between points
                    jitter = 0
                    if len(jitter_window) > 2:
                        ref_lat, ref_lon = jitter_window[0]
                        distances = [
                            distance_m(ref_lat, ref_lon, lat, lon)
                            for lat, lon in jitter_window
                        ]
                        jitter = max(distances)

                    # Distance to waypoint target
                    target = waypoints[current_wp]
                    distance_wp = distance_m(
                        pos.latitude_deg, pos.longitude_deg,
                        target.latitude_deg, target.longitude_deg
                    )

                    # Write CSV
                    with open(CSV_FILE, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            time.time(),
                            current_wp,
                            pos.latitude_deg,
                            pos.longitude_deg,
                            pos.relative_altitude_m,
                            velocity,
                            imu.accelerometer_x,
                            imu.accelerometer_y,
                            imu.accelerometer_z,
                            accel_rms,
                            distance_wp,
                            jitter
                        ])

                    print("[LOG] Metrics saved to CSV.")

                    reached_wp = False  # Reset until next waypoint
                    break

            break  # Break velocity loop

# Run
asyncio.run(main())