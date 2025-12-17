#!/usr/bin/env python3
# pixhawk.py

import time
import logging
import config
from pymavlink import mavutil

logger = logging.getLogger("Pixhawk")

class Pixhawk:
    def __init__(self):
        self.master = mavutil.mavlink_connection(config.PIXHAWK_ADDRESS)
        self.last_wp = None
        self.position = None
        self.armed = False
        self.mode = "UNKNOWN"
        self.imu_accel = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.battery_remaining = None
        self.battery_type = None

    def wait_for_connection(self):
        print(">>> Waiting for heartbeat...")
        self.master.wait_heartbeat()
        print("✓ Pixhawk connected")

    def update(self):
        msg = self.master.recv_match(blocking=False)
        if not msg:
            return

        msg_type = msg.get_type()

        if msg_type == "GLOBAL_POSITION_INT":
            self.position = {
                "lat": msg.lat / 1e7,
                "lon": msg.lon / 1e7,
                "rel_alt": msg.relative_alt / 1000.0,
            }

        elif msg_type == "MISSION_CURRENT":
            self.last_wp = msg.seq + 1

        elif msg_type == "HEARTBEAT":
            self.armed = bool(
                msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            )   
            self.mode = self.master.flightmode
        
        elif msg_type == "RAW_IMU" or msg_type == "SCALED_IMU2":
            self.imu_accel = {
                "x": msg.xacc / 1000.0 * 9.81,
                "y": msg.yacc / 1000.0 * 9.81,
                "z": msg.zacc / 1000.0 * 9.81
            }
        
        elif msg_type == "BATTERY_STATUS":
            if hasattr(msg, 'battery_remaining'):
                self.battery_remaining = msg.battery_remaining
                self.battery_type = 'mah'
            elif hasattr(msg, 'current_consumed'):
                BATTERY_CAPACITY_MAH = 5000
                self.battery_remaining = BATTERY_CAPACITY_MAH - msg.current_consumed
                self.battery_type = 'mah'
        
        elif msg_type == "SYS_STATUS":
            # Only use SYS_STATUS if we don't have BATTERY_STATUS
            if self.battery_remaining is None and hasattr(msg, 'battery_remaining'):
                self.battery_remaining = msg.battery_remaining  # Percentage 0-100
                self.battery_type = 'percent'