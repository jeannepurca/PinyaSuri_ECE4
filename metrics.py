#!/usr/bin/env python3
# metrics.py

import time
import csv
import logging
import math
from collections import deque
from datetime import datetime
import config

logger = logging.getLogger("FlightMetrics")

class FlightMetrics:
    def __init__(self, window_size=100):
        # Rolling windows for real-time metrics
        self.altitude_window = deque(maxlen=window_size)
        self.accel_window = deque(maxlen=window_size)
        self.position_window = deque(maxlen=window_size)
        # Flight-wide metrics
        self.flight_start_time = None
        self.flight_end_time = None
        self.armed_timestamp = None
        self.disarmed_timestamp = None
        self.last_position = None
        self.distance_traveled = 0.0
        self.max_altitude = 0.0
        self.min_altitude = float('inf')
        self.waypoints_completed = 0
        self.battery_start = None
        self.battery_end = None
        self.current_flight_number = 1
        # CSV file
        self.csv_file = config.LOG_DIR / "flight_metrics.csv"
        self._initialize_csv()

    # CSV Initialization
    def _initialize_csv(self):
        try:
            with open(self.csv_file, "x", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "flight_number",
                    "start_time",
                    "end_time",
                    "duration_seconds",
                    "altitude_mean_m",
                    "altitude_std_dev_m",
                    "altitude_stability_score",
                    "imu_accel_rms_m_s2",
                    "position_jitter_m",
                    "distance_traveled_m",
                    "max_altitude_m",
                    "min_altitude_m",
                    "battery_consumed",
                    "waypoints_completed"
                ])
            logger.info("✓ Created flight_metrics.csv")
        except FileExistsError:
            logger.info("✓ flight_metrics.csv already exists")

    # Flight Lifecycle - Start
    def start_flight(self, armed_state, battery_level=None):
        """Call when drone arms"""
        if armed_state and self.armed_timestamp is None:
            self.armed_timestamp = time.time()
            self.flight_start_time = datetime.utcnow().isoformat()
            self.battery_start = battery_level

            # Reset metrics
            self.altitude_window.clear()
            self.accel_window.clear()
            self.position_window.clear()
            self.distance_traveled = 0.0
            self.max_altitude = 0.0
            self.min_altitude = float('inf')
            self.waypoints_completed = 0
            self.last_position = None

            logger.info(f"🛫 Flight {self.current_flight_number} started")

    # Flight Lifecycle - End
    def end_flight(self, disarmed_state):
        """Call when drone disarms"""
        if not disarmed_state or self.armed_timestamp is None:
            return

        self.disarmed_timestamp = time.time()
        self.flight_end_time = datetime.utcnow().isoformat()

        duration = self.disarmed_timestamp - self.armed_timestamp

        # Compute metrics
        altitude_mean, altitude_std, stability_score = self._calculate_altitude_metrics()
        imu_rms = self._calculate_imu_rms()
        position_jitter = self._calculate_position_jitter()
        battery_consumed = self._calculate_battery_consumed()

        # Write CSV
        self._write_metrics_to_csv(
            duration,
            altitude_mean,
            altitude_std,
            stability_score,
            imu_rms,
            position_jitter,
            battery_consumed
        )

        logger.info(f"🛬 Flight {self.current_flight_number} ended - Duration: {duration:.1f}s")
        logger.info(f"   Altitude Stability: {stability_score:.2f}, IMU RMS: {imu_rms:.2f}, Jitter: {position_jitter:.2f}m")

        # Reset for next flight
        self.current_flight_number += 1
        self.armed_timestamp = None
        self.disarmed_timestamp = None

    # Metrics Update
    def update(self, pixhawk_data):
        """Call every loop with telemetry data dictionary"""
        if not self.armed_timestamp:
            return

        # Altitude
        if "rel_alt" in pixhawk_data:
            alt = pixhawk_data["rel_alt"]
            self.altitude_window.append(alt)
            self.max_altitude = max(self.max_altitude, alt)
            self.min_altitude = min(self.min_altitude, alt)

        # IMU acceleration
        if "imu_accel" in pixhawk_data:
            ax, ay, az = pixhawk_data["imu_accel"]["x"], pixhawk_data["imu_accel"]["y"], pixhawk_data["imu_accel"]["z"]
            mag = math.sqrt(ax**2 + ay**2 + az**2)
            self.accel_window.append(mag)

        # Position
        if "lat" in pixhawk_data and "lon" in pixhawk_data:
            pos = (pixhawk_data["lat"], pixhawk_data["lon"])
            self.position_window.append(pos)
            if self.last_position:
                self.distance_traveled += self._haversine_distance(
                    self.last_position[0], self.last_position[1],
                    pos[0], pos[1]
                )
            self.last_position = pos

        # Battery
        if "battery_remaining" in pixhawk_data:
            self.battery_end = pixhawk_data["battery_remaining"]

    def increment_waypoint(self):
        self.waypoints_completed += 1

    # Metric Calculations
    def _calculate_altitude_metrics(self):
        if len(self.altitude_window) < 2:
            return 0.0, 0.0, 0.0
        samples = list(self.altitude_window)
        mean = sum(samples) / len(samples)
        std = math.sqrt(sum((x - mean) ** 2 for x in samples) / len(samples))
        stability = max(0, 100 - (std * 25))  # 0-100 scale
        return mean, std, stability

    def _calculate_imu_rms(self):
        if not self.accel_window:
            return 0.0
        samples = list(self.accel_window)
        mean_sq = sum(x**2 for x in samples) / len(samples)
        return math.sqrt(mean_sq)

    def _calculate_position_jitter(self):
        if len(self.position_window) < 2:
            return 0.0
        positions = list(self.position_window)
        distances = [
            self._haversine_distance(positions[i-1][0], positions[i-1][1],
                                     positions[i][0], positions[i][1])
            for i in range(1, len(positions))
        ]
        if len(distances) < 2:
            return 0.0
        mean_dist = sum(distances) / len(distances)
        variance = sum((d - mean_dist)**2 for d in distances) / len(distances)
        return math.sqrt(variance)

    def _calculate_battery_consumed(self):
        if self.battery_start is not None and self.battery_end is not None:
            return self.battery_start - self.battery_end
        return 0.0

    # Utilities
    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371000  # meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _write_metrics_to_csv(self, duration, altitude_mean, altitude_std, stability_score,
                              imu_rms, position_jitter, battery_consumed):
        with open(self.csv_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                self.current_flight_number,
                self.flight_start_time,
                self.flight_end_time,
                round(duration, 2),
                round(altitude_mean, 2),
                round(altitude_std, 3),
                round(stability_score, 2),
                round(imu_rms, 2),
                round(position_jitter, 3),
                round(self.distance_traveled, 2),
                round(self.max_altitude, 2),
                round(self.min_altitude, 2),
                round(battery_consumed, 1),
                self.waypoints_completed
            ])