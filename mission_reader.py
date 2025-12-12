"""
mission_reader.py
Read mission waypoints directly from Pixhawk using pymavlink (bypasses MAVSDK frame issue)
"""

import time
import logging
from pymavlink import mavutil

logger = logging.getLogger("MissionReader")

class MissionReader:
    """Read mission waypoints from Pixhawk using pymavlink"""
    
    def __init__(self, connection_string="/dev/ttyAMA0", baudrate=57600):
        self.connection_string = connection_string
        self.baudrate = baudrate
        self.master = None
    
    def connect(self, timeout=10):
        """Connect to Pixhawk via pymavlink"""
        try:
            logger.info(f"》 Connecting to Pixhawk via pymavlink: {self.connection_string}:{self.baudrate}")
            self.master = mavutil.mavlink_connection(
                self.connection_string,
                baud=self.baudrate
            )
            
            # Wait for heartbeat
            logger.info("》 Waiting for heartbeat...")
            self.master.wait_heartbeat(timeout=timeout)
            logger.info(f"✓ Heartbeat received from system {self.master.target_system}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to connect: {e}")
            return False
    
    def download_waypoints(self):
        """
        Download waypoints from Pixhawk.
        Returns: List of tuples [(lat, lon, alt), ...] for actual waypoints only
        """
        try:
            # Request waypoint count
            logger.info("》 Requesting waypoint count...")
            self.master.waypoint_request_list_send()
            
            # Wait for waypoint count message
            msg = self.master.recv_match(type='MISSION_COUNT', blocking=True, timeout=5)
            if msg is None:
                logger.error("✗ Timeout waiting for MISSION_COUNT")
                return []
            
            waypoint_count = msg.count
            logger.info(f"》 Mission has {waypoint_count} items")
            
            if waypoint_count == 0:
                logger.warning("⚠ No waypoints in mission")
                return []
            
            # Request each waypoint
            waypoints = []
            all_items = []
            
            for seq in range(waypoint_count):
                self.master.waypoint_request_send(seq)
                
                msg = self.master.recv_match(type='MISSION_ITEM', blocking=True, timeout=5)
                if msg is None:
                    logger.warning(f"⚠ Timeout waiting for waypoint {seq}")
                    continue
                
                all_items.append(msg)
                
                # Only extract actual waypoints (command 16 = NAV_WAYPOINT)
                # Skip: HOME (seq 0), TAKEOFF (cmd 22), LAND (cmd 20), RTL (cmd 20)
                if msg.command == 16 and seq > 0:  # NAV_WAYPOINT and not HOME
                    lat = msg.x  # Latitude
                    lon = msg.y  # Longitude
                    alt = msg.z  # Altitude
                    waypoints.append((lat, lon, alt))
                    logger.info(f"  WP{len(waypoints)}: ({lat:.7f}, {lon:.7f}, {alt:.1f}m) [seq={seq}, cmd={msg.command}]")
                else:
                    cmd_name = self._get_command_name(msg.command)
                    logger.info(f"  Item {seq}: {cmd_name} (cmd={msg.command}) - skipped")
            
            logger.info(f"✓ Downloaded {len(waypoints)} waypoints from mission")
            
            # Send ACK (not critical if this fails)
            try:
                self.master.mav.mission_ack_send(
                    self.master.target_system,
                    self.master.target_component,
                    0  # MAV_MISSION_ACCEPTED
                )
            except Exception as ack_error:
                logger.warning(f"⚠ Could not send mission ACK: {ack_error}")
            
            return waypoints
            
        except Exception as e:
            logger.error(f"✗ Error downloading waypoints: {e}", exc_info=True)
            return []
    
    def _get_command_name(self, cmd):
        """Get human-readable command name"""
        commands = {
            16: "NAV_WAYPOINT",
            20: "NAV_RETURN_TO_LAUNCH",
            21: "NAV_LAND",
            22: "NAV_TAKEOFF",
            84: "NAV_VTOL_TAKEOFF",
            85: "NAV_VTOL_LAND",
        }
        return commands.get(cmd, f"UNKNOWN_{cmd}")
    
    def close(self):
        """Close connection"""
        if self.master:
            self.master.close()
            logger.info("✓ pymavlink connection closed")


def read_mission_waypoints(connection_string="/dev/ttyAMA0", baudrate=57600):
    """
    Convenience function to read waypoints.
    Returns: List of waypoint tuples [(lat, lon, alt), ...]
    """
    reader = MissionReader(connection_string, baudrate)
    
    if not reader.connect():
        return []
    
    waypoints = reader.download_waypoints()
    reader.close()
    
    return waypoints


# Test function
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("Testing Mission Reader")
    print("=" * 60)
    
    waypoints = read_mission_waypoints()
    
    print("\n" + "=" * 60)
    print(f"Found {len(waypoints)} waypoints:")
    for idx, (lat, lon, alt) in enumerate(waypoints, 1):
        print(f"  WP{idx}: ({lat:.7f}, {lon:.7f}, {alt:.1f}m)")
    print("=" * 60)