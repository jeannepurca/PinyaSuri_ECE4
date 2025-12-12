import asyncio
import logging
from mavsdk import System
from pymavlink import mavutil

# Configure Logging
logging.basicConfig(level=logging.INFO)        
logger = logging.getLogger("PixhawkInterface")

class PixhawkInterface:
    def __init__(self, system_address: str = "serial:///dev/ttyAMA0:57600"):
        self.system_address = system_address
        self.drone = System()
        self._connected = asyncio.Event()
        self.takeoff_time = None
        self.mavlink_connection = None

    # Connect to Pixhawk
    async def connect(self, timeout=30):        
        logger.info(f"》》》 Connecting to Pixhawk: {self.system_address}")
        await self.drone.connect(system_address=self.system_address)

        async def wait_for_connection():
            async for state in self.drone.core.connection_state():
                if state.is_connected:
                    logger.info("✓ Pixhawk connected.")
                    self._connected.set()
                    return

        try:
            await asyncio.wait_for(wait_for_connection(), timeout=timeout)
            await self._setup_mavlink_connection()
        except asyncio.TimeoutError:
            raise RuntimeError("⚠ Timeout waiting for Pixhawk connection.")

    async def _setup_mavlink_connection(self):
        """Setup direct MAVLink connection for mission tracking"""
        try:
            # Extract serial port and baud rate
            conn_str = self.system_address.replace("serial://", "")
            
            if ':' in conn_str:
                device, baud = conn_str.rsplit(':', 1)
                baud = int(baud)
            else:
                device = conn_str
                baud = 57600
            
            logger.info(f"》》》 Setting up secondary MAVLink connection for mission tracking...")
            logger.info(f"    Device: {device} at {baud} baud")
            
            # Create a separate MAVLink connection
            loop = asyncio.get_event_loop()
            self.mavlink_connection = await loop.run_in_executor(
                None, 
                lambda: mavutil.mavlink_connection(device, baud=baud, source_system=255)
            )
            
            logger.info("✓ Secondary MAVLink connection established for mission monitoring")
                
        except Exception as e:
            logger.error(f"⚠ Could not establish MAVLink connection: {e}", exc_info=True)
            logger.warning("Mission progress tracking may not work!")
            self.mavlink_connection = None

    # Subscribe to Position Updates
    async def subscribe_positions(self, pos_queue: asyncio.Queue):
        logger.info("》》》 Starting position telemetry subscription...")
        try:
            async for pos in self.drone.telemetry.position():
                await pos_queue.put({
                    "lat": pos.latitude_deg,
                    "lon": pos.longitude_deg,
                    "abs_alt": pos.absolute_altitude_m,
                    "rel_alt": pos.relative_altitude_m,
                    "ts": pos.timestamp_us
                })
        except Exception as e:
            logger.error(f"Position subscription error: {e}", exc_info=True)

    # Subscribe to Mission Progress Updates (Hybrid Approach)
    async def subscribe_mission_progress(self, prog_queue: asyncio.Queue):  
        """
        Subscribe to mission progress using RAW MAVLink MISSION_CURRENT messages.
        This is the most reliable method for Mission Planner missions.
        """
        if not self.mavlink_connection:
            logger.error("⚠ No MAVLink connection - trying MAVSDK fallback...")
            # Fallback to MAVSDK
            try:
                async for progress in self.drone.mission.mission_progress():
                    await prog_queue.put({
                        "current": progress.current,
                        "total": progress.total,
                        "source": "mavsdk"
                    })
            except Exception as e:
                logger.error(f"MAVSDK mission progress failed: {e}")
            return
        
        last_seq = -1
        mission_total = 0
        loop = asyncio.get_event_loop()
        
        logger.info("》》》 Starting MAVLink mission progress listener...")
        
        try:
            while True:
                # Non-blocking message receive
                msg = await loop.run_in_executor(
                    None,
                    lambda: self.mavlink_connection.recv_match(
                        type=['MISSION_CURRENT', 'MISSION_COUNT', 'MISSION_ITEM_REACHED'], 
                        blocking=True,
                        timeout=0.1
                    )
                )
                
                if msg is None:
                    await asyncio.sleep(0.01)
                    continue
                
                msg_type = msg.get_type()
                
                # Handle MISSION_COUNT
                if msg_type == 'MISSION_COUNT':
                    mission_total = msg.count
                    logger.info(f"》 Received mission count: {mission_total} waypoints")
                
                # Handle MISSION_CURRENT
                elif msg_type == 'MISSION_CURRENT':
                    current_seq = msg.seq
                    if current_seq != last_seq:
                        logger.info(f"》 MISSION_CURRENT: Waypoint {current_seq}/{mission_total}")
                        await prog_queue.put({
                            "current": current_seq,
                            "total": mission_total,
                            "source": "mavlink_current"
                        })
                        last_seq = current_seq
                
                # Handle MISSION_ITEM_REACHED (more reliable for waypoint detection)
                elif msg_type == 'MISSION_ITEM_REACHED':
                    reached_seq = msg.seq
                    logger.info(f"》 MISSION_ITEM_REACHED: Waypoint {reached_seq}/{mission_total}")
                    await prog_queue.put({
                        "current": reached_seq,
                        "total": mission_total,
                        "source": "mavlink_reached"
                    })
                    last_seq = reached_seq
                
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            logger.info("⚠ Mission progress listener cancelled.")
            raise
        except Exception as e:
            logger.error(f"✗ Error in mission progress listener: {e}", exc_info=True)

    # Subscribe to Flight Mode Updates
    async def subscribe_flight_mode(self, mode_queue: asyncio.Queue):
        """Subscribe to flight mode changes"""
        logger.info("》》》 Starting flight mode subscription...")
        try:
            async for flight_mode in self.drone.telemetry.flight_mode():
                await mode_queue.put(str(flight_mode))
        except Exception as e:
            logger.error(f"Flight mode subscription error: {e}", exc_info=True)

    # Subscribe to IMU Accelerometer Data
    async def subscribe_imu_accel(self, imu_queue: asyncio.Queue):
        try:
            async for imu in self.drone.telemetry.imu():                            
                await imu_queue.put({
                    "x": imu.accelerometer_m_s2.x,
                    "y": imu.accelerometer_m_s2.y,
                    "z": imu.accelerometer_m_s2.z,
                    "ts": imu.timestamp_us
                })
        except Exception as e:
            logger.error(f"IMU subscription error: {e}", exc_info=True)

    # Subscribe to Battery Status Updates
    async def subscribe_battery(self, battery_queue: asyncio.Queue):
        try:
            async for b in self.drone.telemetry.battery():
                await battery_queue.put({               
                    "percentage": b.remaining_percent,
                    "voltage": b.voltage_v,
                    "ts": b.timestamp_us
                })
        except Exception as e:
            logger.error(f"Battery subscription error: {e}", exc_info=True)

    # Subscribe to Armed Status Updates
    async def subscribe_armed(self, armed_queue: asyncio.Queue):
        logger.info("》》》 Starting armed status subscription...")
        try:
            async for a in self.drone.telemetry.armed():                            
                await armed_queue.put({"armed": a})     
                if a and self.takeoff_time is None:
                    self.takeoff_time = asyncio.get_event_loop().time()
        except Exception as e:
            logger.error(f"Armed subscription error: {e}", exc_info=True)

    # Subscribe to In-Air Status
    async def subscribe_in_air(self, in_air_queue: asyncio.Queue):
        """Subscribe to in-air status - detects when drone is flying or landed"""
        try:
            async for in_air in self.drone.telemetry.in_air():
                await in_air_queue.put(in_air)
        except Exception as e:
            logger.error(f"In-air subscription error: {e}", exc_info=True)

    # Request Mission Count
    async def request_mission_count(self):
        """Request mission count from the autopilot"""
        if self.mavlink_connection:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.mavlink_connection.mav.mission_request_list_send(
                        self.mavlink_connection.target_system,
                        self.mavlink_connection.target_component
                    )
                )
                logger.info("》 Requested mission list from Pixhawk")
            except Exception as e:
                logger.error(f"✗ Error requesting mission count: {e}")