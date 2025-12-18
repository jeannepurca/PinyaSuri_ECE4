#!/usr/bin/env python3
# pixhawk.py

import time
import logging
import math
import config
from pymavlink import mavutil

logger = logging.getLogger("Pixhawk")


class Pixhawk:
    def __init__(self):
        self.master = mavutil.mavlink_connection(
            config.PIXHAWK_ADDRESS,
            baud=57600
        )

        # Flight state
        self.last_wp = None
        self.position = None
        self.armed = False
        self.mode = "UNKNOWN"

        # Sensors
        self.imu_accel = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.battery_remaining = None
        self.battery_type = None
        self.groundspeed = 0.0

        # Telemetry watchdog
        self.last_msg_time = None
        
        # Waypoint tracking (for logging/debugging only)
        self.wp_reached_log = set()  # Just for logging purposes

    # ---------------------------------------------------------
    # CONNECTION & STREAM SETUP
    # ---------------------------------------------------------

    def wait_for_connection(self):
        logger.info(">>> Waiting for heartbeat...")
        self.master.wait_heartbeat()
        logger.info("✓ Pixhawk connected successfully!")

        self._request_required_streams()
        logger.info("✓ MAVLink streams configured")

    def _request_message(self, msg_id, rate_hz):
        """Request a MAVLink message at a specific rate"""
        interval_us = int(1e6 / rate_hz)

        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
            0,
            msg_id,
            interval_us,
            0, 0, 0, 0, 0
        )

        time.sleep(0.05)

    def _request_required_streams(self):
        logger.info(">>> Requesting MAVLink message streams...")

        # Core system state
        self._request_message(
            mavutil.mavlink.MAVLINK_MSG_ID_HEARTBEAT, 1
        )

        # Mission / waypoints
        self._request_message(
            mavutil.mavlink.MAVLINK_MSG_ID_MISSION_CURRENT, 2
        )
        
        # Request waypoint reached messages
        self._request_message(
            mavutil.mavlink.MAVLINK_MSG_ID_MISSION_ITEM_REACHED, 2
        )

        # Position & altitude
        self._request_message(
            mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 5
        )

        # Battery info
        self._request_message(
            mavutil.mavlink.MAVLINK_MSG_ID_BATTERY_STATUS, 1
        )
        self._request_message(
            mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS, 1
        )

        # IMU
        self._request_message(
            mavutil.mavlink.MAVLINK_MSG_ID_RAW_IMU, 5
        )

    # ---------------------------------------------------------
    # TELEMETRY UPDATE LOOP
    # ---------------------------------------------------------

    def update(self):
        """
        Drain MAVLink queue completely.
        This MUST be non-blocking and process ALL messages.
        """

        while True:
            msg = self.master.recv_match(blocking=False)
            if not msg:
                break

            self.last_msg_time = time.time()
            msg_type = msg.get_type()

            # -------------------------------
            # POSITION
            # -------------------------------
            if msg_type == "GLOBAL_POSITION_INT":
                self.position = {
                    "lat": msg.lat / 1e7,
                    "lon": msg.lon / 1e7,
                    "rel_alt": msg.relative_alt / 1000.0
                }
                # Extract groundspeed
                self.groundspeed = math.sqrt(msg.vx**2 + msg.vy**2) / 100.0

            # -------------------------------
            # WAYPOINT (Current)
            # -------------------------------
            elif msg_type == "MISSION_CURRENT":
                new_wp = msg.seq + 1
                # Only update if it's a valid waypoint number
                if 0 <= new_wp <= 255:
                    self.last_wp = new_wp

            # -------------------------------
            # WAYPOINT REACHED EVENT (for logging only)
            # -------------------------------
            elif msg_type == "MISSION_ITEM_REACHED":
                # Only log in AUTO mode and for valid waypoint numbers
                if self.mode == "AUTO" and 1 <= msg.seq < 255:
                    wp_num = msg.seq + 1
                    
                    # Just log it, don't use for capture logic
                    if wp_num not in self.wp_reached_log:
                        self.wp_reached_log.add(wp_num)
                        logger.debug(f"📍 Waypoint {wp_num} reached event received")

            # -------------------------------
            # HEARTBEAT (MODE + ARM)
            # -------------------------------
            elif msg_type == "HEARTBEAT":
                self.armed = bool(
                    msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                )
                self.mode = self.master.flightmode

            # -------------------------------
            # IMU
            # -------------------------------
            elif msg_type == "RAW_IMU":
                self.imu_accel = {
                    "x": msg.xacc / 1000.0 * 9.81,
                    "y": msg.yacc / 1000.0 * 9.81,
                    "z": msg.zacc / 1000.0 * 9.81
                }

            # -------------------------------
            # BATTERY (preferred)
            # -------------------------------
            elif msg_type == "BATTERY_STATUS":
                if msg.battery_remaining != -1:
                    self.battery_remaining = msg.battery_remaining
                    self.battery_type = "percent"

            # -------------------------------
            # BATTERY (fallback)
            # -------------------------------
            elif msg_type == "SYS_STATUS":
                if self.battery_remaining is None and hasattr(msg, "battery_remaining"):
                    self.battery_remaining = msg.battery_remaining
                    self.battery_type = "percent"

    # ---------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------
    
    def is_hovering(self, threshold=0.5):
        """Check if drone is hovering (velocity < threshold m/s)"""
        return self.groundspeed < threshold
    
    def clear_waypoint_log(self):
        """Clear the waypoint log (call when disarmed)"""
        self.wp_reached_log.clear()

    # ---------------------------------------------------------
    # SAFETY / HEALTH
    # ---------------------------------------------------------

    def telemetry_ok(self, timeout=2.0):
        """Returns False if telemetry is stale"""
        if self.last_msg_time is None:
            return False
        return (time.time() - self.last_msg_time) < timeout