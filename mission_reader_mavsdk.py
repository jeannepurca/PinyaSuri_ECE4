"""
mission_reader_mavsdk.py
Read mission waypoints using MAVSDK's MAVLink passthrough (no serial port conflict)
"""

import asyncio
import logging

logger = logging.getLogger("MissionReader")

async def read_mission_waypoints_mavsdk(pixhawk_interface):
    """
    Read waypoints using MAVSDK's MAVLink passthrough.
    Args:
        pixhawk_interface: Connected PixhawkInterface instance
    Returns:
        List of waypoint tuples [(lat, lon, alt), ...]
    """
    try:
        drone = pixhawk_interface.drone
        
        logger.info("》 Requesting mission via MAVSDK MAVLink passthrough...")
        
        # Subscribe to MAVLink messages
        waypoint_count = 0
        waypoints = []
        mission_items = []
        
        # Request mission list
        await drone.mission_raw.subscribe_mission_count(lambda count: None)
        
        # Use mission_raw to download mission
        try:
            mission_import_data = await drone.mission_raw.download_mission()
            mission_items = mission_import_data.mission_items
            
            logger.info(f"》 Mission has {len(mission_items)} items")
            
            if len(mission_items) == 0:
                logger.warning("⚠ No mission items found")
                return []
            
            # Parse mission items
            for seq, item in enumerate(mission_items):
                # Command 16 = NAV_WAYPOINT
                # Skip HOME (seq 0), TAKEOFF (cmd 22), LAND (cmd 21), RTL (cmd 20)
                if item.command == 16 and seq > 0:
                    # mission_raw uses different field names
                    lat = item.x / 1e7  # Convert from int32 to degrees
                    lon = item.y / 1e7  # Convert from int32 to degrees
                    alt = item.z        # Altitude in meters
                    
                    waypoints.append((lat, lon, alt))
                    logger.info(f"  WP{len(waypoints)}: ({lat:.7f}, {lon:.7f}, {alt:.1f}m) [seq={seq}, cmd={item.command}]")
                else:
                    cmd_name = _get_command_name(item.command)
                    logger.info(f"  Item {seq}: {cmd_name} (cmd={item.command}) - skipped")
            
            logger.info(f"✓ Downloaded {len(waypoints)} waypoints from mission")
            return waypoints
            
        except Exception as download_error:
            logger.error(f"✗ Error with mission_raw download: {download_error}")
            
            # Fallback: Try standard mission download but handle frame errors
            try:
                logger.info("》 Attempting standard mission download as fallback...")
                mission_plan = await drone.mission.download_mission()
                
                for idx, item in enumerate(mission_plan.mission_items):
                    if item.command == 16 and idx > 0:
                        waypoints.append((item.latitude_deg, item.longitude_deg, item.altitude_m))
                        logger.info(f"  WP{len(waypoints)}: ({item.latitude_deg:.7f}, {item.longitude_deg:.7f})")
                
                logger.info(f"✓ Downloaded {len(waypoints)} waypoints via fallback method")
                return waypoints
                
            except Exception as fallback_error:
                logger.warning(f"⚠ Fallback also failed: {fallback_error}")
                return []
        
    except Exception as e:
        logger.error(f"✗ Error reading mission: {e}", exc_info=True)
        return []


def _get_command_name(cmd):
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