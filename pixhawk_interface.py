from pymavlink import mavutil

import time

class PixhawkInterface:
    def __init__(self, port='/dev/serial0', baud=57600):
        print("[Pixhawk] Connecting...")
        self.master = mavutil.mavlink_connection(port, baud=baud)
        self.master.wait_heartbeat()
        print("[Pixhawk] Connected!")

    def get_groundspeed(self):
        msg = self.master.recv_match(type='VFR_HUD', blocking=True)
        if msg:
            return msg.groundspeed
        return None

    def wait_for_waypoint(self):
        msg = self.master.recv_match(type='MISSION_ITEM_REACHED', blocking=True)
        if msg:
            print(f"[Pixhawk] Waypoint {msg.seq} reached.")
            return msg.seq
        return None
    
    def get_attitude(self):
        msg = self.master.recv_match(type='ATTITUDE', blocking=True)
        if msg:
            return {'roll': msg.roll, 'pitch': msg.pitch, 'yaw': msg.yaw}
        return None

    def get_imu(self):
        msg = self.master.recv_match(type='RAW_IMU', blocking=True)
        if msg:
            return {'ax': msg.xacc, 'ay': msg.yacc, 'az': msg.zacc}
        return None

    def get_gps(self):
        msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
        if msg:
            return {'lat': msg.lat / 1e7, 'lon': msg.lon / 1e7, 'alt': msg.alt / 1000}
        return None