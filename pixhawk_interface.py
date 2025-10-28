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