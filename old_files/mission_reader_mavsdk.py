#!/usr/bin/env python3
"""
mission_reader_mavlink.py
Read mission waypoints using direct MAVLink (no MAVSDK dependency)
"""

import asyncio
import logging

logger = logging.getLogger("MissionReader")


async def read_mission_waypoints_mavlink(pixhawk_interface):
    """
    Read waypoints using direct MAVLink protocol.
    
    Args:
        pixhawk_interface: Connected PixhawkMAVLink instance
    
    Returns:
        List of waypoint tuples [(lat, lon, alt), ...]
    """
    try:
        logger.info("》 Requesting mission waypoints via MAVLink...")
        
        # Use the download_mission method from PixhawkMAVLink
        waypoints = await pixhawk_interface.download_mission()
        
        if len(waypoints) == 0:
            logger.warning("⚠ No mission waypoints found")
            return []
        
        logger.info(f"✓ Successfully downloaded {len(waypoints)} waypoints")
        
        # Log waypoints for verification
        for idx, (lat, lon, alt) in enumerate(waypoints):
            logger.info(f"  WP{idx+1}: ({lat:.7f}, {lon:.7f}, {alt:.1f}m)")
        
        return waypoints
        
    except Exception as e:
        logger.error(f"✗ Error reading mission: {e}", exc_info=True)
        return []


def _get_command_name(cmd):
    """Get human-readable MAVLink command name"""
    commands = {
        16: "NAV_WAYPOINT",
        20: "NAV_RETURN_TO_LAUNCH", 
        21: "NAV_LAND",
        22: "NAV_TAKEOFF",
        84: "NAV_VTOL_TAKEOFF",
        85: "NAV_VTOL_LAND",
        93: "NAV_DELAY",
        112: "CONDITION_DELAY",
        177: "DO_JUMP",
        183: "DO_SET_ROI",
        201: "DO_SET_SERVO",
        206: "DO_SET_HOME",
    }
    return commands.get(cmd, f"UNKNOWN_CMD_{cmd}")