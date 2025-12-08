"""
Flight Metrics Logger
"""

import asyncio
import csv
import os
from math import sqrt
from statistics import stdev
import logging
from datetime import datetime

logger = logging.getLogger("FlightMetrics")     # Create logger for FlightMetrics

class FlightMetricsLogger:
    def __init__(self, pixhawk, output_csv="/home/ece4/PINYASURI/drone_flight_metrics.csv",
                 window_size=10, log_interval=0.5):
        self.pixhawk = pixhawk                  # Pixhawk interface
        self.output_csv = output_csv            # Output CSV file path
        self.window_size = window_size          # Rolling window size
        self.log_interval = log_interval        # Logging interval in seconds
        self.alt_window = []                    # Rolling window for altitude
        self.pos_window = []                    # Rolling window for position
        self.vib_window = []                    # Rolling window for vibration

        # create CSV if doesn't exist
        if not os.path.exists(self.output_csv): 
            with open(self.output_csv, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp_utc","lat","lon","abs_alt_m","rel_alt_m",
                    "vib_rms_m_s2","hover_jitter_m","altitude_stability_m",
                    "battery_pct","flight_time_s"
                ])

        # queues
        self.pos_queue = asyncio.Queue()        # Queue for position data
        self.imu_queue = asyncio.Queue()        # Queue for IMU data
        self.battery_queue = asyncio.Queue()    # Queue for battery data
        self.armed_queue = asyncio.Queue()      # Queue for armed status
        self.latest_pos = None                  # Latest position
        self.latest_imu = None                  # Latest IMU data
        self.latest_batt = None                 # Latest battery data
        self.armed = False                      # Armed status
        self.flight_start = None                # Flight start time

    async def run(self):
        # subscribe to Pixhawk streams
        asyncio.create_task(self.pixhawk.subscribe_positions(self.pos_queue))   # Position data
        asyncio.create_task(self.pixhawk.subscribe_imu_accel(self.imu_queue))   # IMU data
        asyncio.create_task(self.pixhawk.subscribe_battery(self.battery_queue)) # Battery data
        asyncio.create_task(self.pixhawk.subscribe_armed(self.armed_queue))     # Armed status

        while True:
            # Update latest data from queues
            try:
                while True:
                    self.latest_pos = self.pos_queue.get_nowait()               # Get latest position
            except asyncio.QueueEmpty:
                pass
            try:
                while True:
                    self.latest_imu = self.imu_queue.get_nowait()               # Get latest IMU data
            except asyncio.QueueEmpty:
                pass
            try:
                while True:
                    self.latest_batt = self.battery_queue.get_nowait()          # Get latest battery data
            except asyncio.QueueEmpty:
                pass
            try:
                while True:
                    armed_status = self.armed_queue.get_nowait()                # Get latest armed status
                    self.armed = armed_status["armed"]
                    if self.armed and self.flight_start is None:
                        self.flight_start = datetime.utcnow()
            except asyncio.QueueEmpty:  # No new armed status
                pass

            if self.latest_pos and self.latest_imu:                     # Ensure we have data
                # Metrics: Altitude Stability
                self.alt_window.append(self.latest_pos["rel_alt"])      # Relative altitude
                if len(self.alt_window) > self.window_size:             # If window is full
                    self.alt_window.pop(0)                              # Remove oldest entry

                self.pos_window.append((self.latest_pos["lat"], self.latest_pos["lon"], self.latest_pos["rel_alt"]))  # 3D position 
                if len(self.pos_window) > self.window_size:             # If window is full
                    self.pos_window.pop(0)                              # Remove oldest entry

                alt_stab = stdev(self.alt_window) if len(self.alt_window) > 1 else 0.0

                # Metrics: Vibration / IMU Acceleration RMS
                vib_rms = sqrt(self.latest_imu["x"]**2 + self.latest_imu["y"]**2 + self.latest_imu["z"]**2) # Vibration RMS
                self.vib_window.append(vib_rms)                         # Vibration RMS
                if len(self.vib_window) > self.window_size:             # If window is full
                    self.vib_window.pop(0)                              # Remove oldest entry   

                # Metrics: Position Jitter During Hover
                if len(self.pos_window) > 1:
                    mean_x = sum(p[0] for p in self.pos_window)/len(self.pos_window)    # Mean latitude
                    mean_y = sum(p[1] for p in self.pos_window)/len(self.pos_window)    # Mean longitude
                    mean_z = sum(p[2] for p in self.pos_window)/len(self.pos_window)    # Mean relative altitude
                    jitter = sqrt(sum((p[0]-mean_x)**2 + (p[1]-mean_y)**2 + (p[2]-mean_z)**2 for p in self.pos_window)/len(self.pos_window))    # RMS jitter
                else:
                    jitter = 0.0

                # Metrics: Flight Endurance
                battery_pct = self.latest_batt["percentage"] if self.latest_batt else 0.0   # Battery percentage
                flight_time = (datetime.utcnow() - self.flight_start).total_seconds() if self.flight_start else 0.0   # Flight time in seconds

                # Record metrics to CSV
                with open(self.output_csv, "a", newline="") as f:   # Append to CSV
                    writer = csv.writer(f)                          # Create writer
                    writer.writerow([                               # Write metrics row
                        datetime.utcnow().isoformat(),              # Timestamp
                        self.latest_pos["lat"],                     # Latitude
                        self.latest_pos["lon"],                     # Longitude
                        self.latest_pos["abs_alt"],                 # Absolute altitude
                        self.latest_pos["rel_alt"],                 # Relative altitude
                        vib_rms,                                    # Vibration RMS
                        jitter,                                     # Hover jitter
                        alt_stab,                                   # Altitude stability
                        battery_pct,                                # Battery percentage
                        flight_time                                 # Flight time in seconds
                    ])
            await asyncio.sleep(self.log_interval)                  # Wait before next log
