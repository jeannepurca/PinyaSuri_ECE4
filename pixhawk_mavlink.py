#!/usr/bin/env python3

import asyncio
import logging
import time
from pymavlink import mavutil
from typing import Optional, Tuple

logger = logging.getLogger("PixhawkMAVLink")


class PixhawkMAVLink:
    """Direct MAVLink interface for Pixhawk telemetry via UDP"""
    
    def __init__(self, connection_string: str = "udpin:127.0.0.1:14551"):
        """
        Args:
            connection_string: MAVLink connection (default: UDP from MAVProxy)
        """
        self.connection_string = connection_string
        self.master = None
        self._connected = False
        
        # Latest telemetry data
        self.latest_position = None
        self.latest_attitude = None
        self.latest_battery = None
        self.latest_flight_mode = None
        self.is_armed = False
        self.is_in_air = False
        
        # Flight timing
        self.takeoff_time = None
    
    async def connect(self, timeout: int = 30):
        """Connect to MAVLink stream"""
        logger.info(f"》》》 Connecting to MAVLink: {self.connection_string}")
        
        try:
            # Create MAVLink connection (non-blocking)
            self.master = mavutil.mavlink_connection(self.connection_string)
            
            if not self.master:
                raise Exception("Failed to create MAVLink connection")
            
            logger.info("》 Connection object created, waiting for heartbeat...")
            
            # Wait for heartbeat with proper async handling
            start = time.time()
            heartbeat_received = False
            
            while time.time() - start < timeout:
                # Use non-blocking recv_match
                msg = self.master.recv_match(type='HEARTBEAT', blocking=False)
                
                if msg:
                    logger.info(f"✓ Heartbeat received from system {msg.get_srcSystem()}")
                    self._connected = True
                    heartbeat_received = True
                    
                    # Request data streams at 5 Hz
                    await self._request_data_streams()
                    
                    logger.info("✓ MAVLink connection established")
                    return
                
                # Don't block the event loop
                await asyncio.sleep(0.1)
            
            if not heartbeat_received:
                raise TimeoutError("No heartbeat received within timeout")
                
        except Exception as e:
            logger.error(f"✗ Failed to connect: {e}")
            raise
    
    async def _request_data_streams(self):
        """Request telemetry streams at specified rates"""
        
        # Request 5 Hz for position, attitude, and system status
        for stream_id in [
            mavutil.mavlink.MAV_DATA_STREAM_POSITION,
            mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
            mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS
        ]:
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                stream_id,
                5,  # 5 Hz
                1   # Start streaming
            )
            # Small delay between requests
            await asyncio.sleep(0.01)
        
        logger.info("》 Requested telemetry streams at 5 Hz")
    
    async def subscribe_positions(self, pos_queue: asyncio.Queue):
        """Subscribe to GPS position updates (GLOBAL_POSITION_INT)"""
        logger.info("》》》 Starting position telemetry subscription...")
        
        try:
            while True:
                # Non-blocking receive
                msg = self.master.recv_match(
                    type='GLOBAL_POSITION_INT',
                    blocking=False
                )
                
                if msg:
                    # Convert from int32 (degrees * 1e7) to float
                    position = {
                        "lat": msg.lat / 1e7,
                        "lon": msg.lon / 1e7,
                        "abs_alt": msg.alt / 1000.0,  # mm to meters
                        "rel_alt": msg.relative_alt / 1000.0,  # mm to meters
                        "ts": time.time()
                    }
                    
                    self.latest_position = position
                    await pos_queue.put(position)
                
                # Don't block the event loop
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            logger.info("⚠ Position subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"Position subscription error: {e}", exc_info=True)
    
    async def subscribe_imu_accel(self, imu_queue: asyncio.Queue):
        """Subscribe to IMU accelerometer data (SCALED_IMU2 or RAW_IMU)"""
        logger.info("》》》 Starting IMU subscription...")
        
        try:
            while True:
                # Non-blocking receive
                msg = self.master.recv_match(
                    type=['SCALED_IMU2', 'RAW_IMU'],
                    blocking=False
                )
                
                if msg:
                    # Convert millig to m/s² (1 millig = 0.00981 m/s²)
                    imu_data = {
                        "x": msg.xacc * 0.00981 if hasattr(msg, 'xacc') else 0,
                        "y": msg.yacc * 0.00981 if hasattr(msg, 'yacc') else 0,
                        "z": msg.zacc * 0.00981 if hasattr(msg, 'zacc') else 0,
                        "ts": time.time()
                    }
                    
                    await imu_queue.put(imu_data)
                
                # Don't block the event loop
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            logger.info("⚠ IMU subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"IMU subscription error: {e}", exc_info=True)
    
    async def subscribe_battery(self, battery_queue: asyncio.Queue):
        """Subscribe to battery status (SYS_STATUS)"""
        logger.info("》》》 Starting battery subscription...")
        
        try:
            while True:
                # Non-blocking receive
                msg = self.master.recv_match(
                    type='SYS_STATUS',
                    blocking=False
                )
                
                if msg:
                    battery = {
                        "percentage": msg.battery_remaining if msg.battery_remaining != -1 else 100,
                        "voltage": msg.voltage_battery / 1000.0,  # mV to V
                        "ts": time.time()
                    }
                    
                    self.latest_battery = battery
                    await battery_queue.put(battery)
                
                # Don't block the event loop
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            logger.info("⚠ Battery subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"Battery subscription error: {e}", exc_info=True)
    
    async def subscribe_armed(self, armed_queue: asyncio.Queue):
        """Subscribe to armed status (HEARTBEAT)"""
        logger.info("》》》 Starting armed status subscription...")
        
        try:
            while True:
                # Non-blocking receive
                msg = self.master.recv_match(
                    type='HEARTBEAT',
                    blocking=False
                )
                
                if msg:
                    # Check MAV_STATE_ACTIVE flag
                    is_armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                    
                    if is_armed != self.is_armed:
                        self.is_armed = is_armed
                        
                        if is_armed and self.takeoff_time is None:
                            self.takeoff_time = asyncio.get_event_loop().time()
                        
                        await armed_queue.put({"armed": is_armed})
                
                # Don't block the event loop
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            logger.info("⚠ Armed subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"Armed subscription error: {e}", exc_info=True)
    
    async def subscribe_flight_mode(self, mode_queue: asyncio.Queue):
        """Subscribe to flight mode changes (HEARTBEAT)"""
        logger.info("》》》 Starting flight mode subscription...")
        
        last_mode = None
        
        try:
            while True:
                # Non-blocking receive
                msg = self.master.recv_match(
                    type='HEARTBEAT',
                    blocking=False
                )
                
                if msg:
                    # Get flight mode name
                    mode = self.master.flightmode
                    
                    if mode != last_mode:
                        last_mode = mode
                        self.latest_flight_mode = mode
                        await mode_queue.put(mode)
                
                # Don't block the event loop
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            logger.info("⚠ Flight mode subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"Flight mode subscription error: {e}", exc_info=True)
    
    async def subscribe_in_air(self, in_air_queue: asyncio.Queue):
        """Subscribe to in-air status (EXTENDED_SYS_STATE)"""
        logger.info("》》》 Starting in-air subscription...")
        
        try:
            while True:
                # Non-blocking receive
                msg = self.master.recv_match(
                    type='EXTENDED_SYS_STATE',
                    blocking=False
                )
                
                if msg:
                    # MAV_LANDED_STATE: 1=ON_GROUND, 2=IN_AIR, 3=TAKEOFF, 4=LANDING
                    is_in_air = msg.landed_state in [2, 3, 4]
                    
                    if is_in_air != self.is_in_air:
                        self.is_in_air = is_in_air
                        await in_air_queue.put(is_in_air)
                
                # Don't block the event loop
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            logger.info("⚠ In-air subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"In-air subscription error: {e}", exc_info=True)
    
    async def download_mission(self) -> list:
        """
        Download mission waypoints from Pixhawk
        Returns: List of (lat, lon, alt) tuples
        """
        logger.info("》 Requesting mission waypoints...")
        
        try:
            # Request mission count
            self.master.mav.mission_request_list_send(
                self.master.target_system,
                self.master.target_component
            )
            
            # Wait for mission count
            start = time.time()
            msg = None
            while time.time() - start < 5.0:
                msg = self.master.recv_match(type='MISSION_COUNT', blocking=False)
                if msg:
                    break
                await asyncio.sleep(0.1)
            
            if not msg:
                logger.warning("⚠ No mission count received")
                return []
            
            count = msg.count
            logger.info(f"》 Mission has {count} items")
            
            if count == 0:
                return []
            
            waypoints = []
            
            # Request each mission item
            for seq in range(count):
                self.master.mav.mission_request_int_send(
                    self.master.target_system,
                    self.master.target_component,
                    seq
                )
                
                # Wait for mission item
                start = time.time()
                msg = None
                while time.time() - start < 5.0:
                    msg = self.master.recv_match(type='MISSION_ITEM_INT', blocking=False)
                    if msg and msg.seq == seq:
                        break
                    await asyncio.sleep(0.1)
                
                if msg:
                    # Command 16 = NAV_WAYPOINT, skip HOME/TAKEOFF/LAND
                    if msg.command == 16 and seq > 0:
                        lat = msg.x / 1e7  # Convert from int32
                        lon = msg.y / 1e7
                        alt = msg.z
                        
                        waypoints.append((lat, lon, alt))
                        logger.info(f"  WP{len(waypoints)}: ({lat:.7f}, {lon:.7f}, {alt:.1f}m)")
            
            # Send ACK
            self.master.mav.mission_ack_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_MISSION_ACCEPTED
            )
            
            logger.info(f"✓ Downloaded {len(waypoints)} waypoints")
            return waypoints
            
        except Exception as e:
            logger.error(f"✗ Mission download failed: {e}", exc_info=True)
            return []
    
    def is_connected(self) -> bool:
        """Check if connection is active"""
        return self._connected and self.master is not None