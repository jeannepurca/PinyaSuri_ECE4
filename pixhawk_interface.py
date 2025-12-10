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
    """Setup direct MAVLink connection for raw message access"""
    try:
        # Extract serial port and baud rate
        # MAVSDK format: "serial:///dev/ttyAMA0:57600"
        # pymavlink needs: device='/dev/ttyAMA0', baud=57600
        
        conn_str = self.system_address.replace("serial://", "")
        
        # Split device and baud rate
        if ':' in conn_str:
            device, baud = conn_str.rsplit(':', 1)
            baud = int(baud)
        else:
            device = conn_str
            baud = 57600  # default
        
        logger.info(f"》》》 Setting up MAVLink connection: {device} at {baud} baud")
        
        # Create MAVLink connection in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        self.mavlink_connection = await loop.run_in_executor(
            None, 
            lambda: mavutil.mavlink_connection(device, baud=baud)
        )
        
        # Wait for heartbeat to confirm connection
        logger.info("》》》 Waiting for MAVLink heartbeat...")
        msg = await loop.run_in_executor(
            None,
            lambda: self.mavlink_connection.wait_heartbeat(timeout=5)
        )
        
        if msg:
            logger.info(f"✓ Direct MAVLink connection established. System ID: {self.mavlink_connection.target_system}")
        else:
            logger.error("✗ No heartbeat received from Pixhawk")
            self.mavlink_connection = None
            
    except Exception as e:
        logger.error(f"⚠ Could not establish direct MAVLink connection: {e}", exc_info=True)
        logger.warning("Will rely on MAVSDK telemetry only.")
        self.mavlink_connection = None
        
    # Subscribe to Position Updates
    async def subscribe_positions(self, pos_queue: asyncio.Queue):
        async for pos in self.drone.telemetry.position():
            await pos_queue.put({
                "lat": pos.latitude_deg,
                "lon": pos.longitude_deg,
                "abs_alt": pos.absolute_altitude_m,
                "rel_alt": pos.relative_altitude_m,
                "ts": pos.timestamp_us
            })

    # Subscribe to Mission Progress Updates
    async def subscribe_mission_progress(self, prog_queue: asyncio.Queue):  
        """
        Subscribe to mission progress using MAVLink MISSION_CURRENT messages.
        This works with Mission Planner missions.
        """
        if not self.mavlink_connection:
            logger.error("⚠ No MAVLink connection available for mission tracking!")
            logger.error("Mission progress will NOT be tracked!")
            return
        
        last_seq = -1
        mission_total = 0
        
        loop = asyncio.get_event_loop()
        
        try:
            logger.info("》》》 Starting MAVLink mission progress listener...")
            while True:
                # Receive MAVLink message (non-blocking with timeout)
                msg = await loop.run_in_executor(
                    None,
                    lambda: self.mavlink_connection.recv_match(
                        type=['MISSION_CURRENT', 'MISSION_COUNT'], 
                        blocking=True,
                        timeout=0.5
                    )
                )
                
                if msg is None:
                    await asyncio.sleep(0.05)
                    continue
                
                # Handle MISSION_COUNT (total waypoints)
                if msg.get_type() == 'MISSION_COUNT':
                    mission_total = msg.count
                    logger.info(f"》 Mission has {mission_total} total waypoints.")
                
                # Handle MISSION_CURRENT (current waypoint)
                elif msg.get_type() == 'MISSION_CURRENT':
                    current_seq = msg.seq
                    
                    if current_seq != last_seq:
                        logger.info(f"》 MAVLink MISSION_CURRENT: Waypoint {current_seq}/{mission_total}")
                        await prog_queue.put({
                            "current": current_seq,
                            "total": mission_total,
                            "source": "mavlink"
                        })
                        last_seq = current_seq
                
                await asyncio.sleep(0.05)
                
        except asyncio.CancelledError:
            logger.info("⚠ Mission progress listener cancelled.")
            raise
        except Exception as e:
            logger.error(f"✗ Error in MAVLink mission listener: {e}", exc_info=True)

    # Subscribe to Flight Mode Updates
    async def subscribe_flight_mode(self, mode_queue: asyncio.Queue):
        """Subscribe to flight mode changes"""
        async for flight_mode in self.drone.telemetry.flight_mode():
            await mode_queue.put(str(flight_mode))

    # Subscribe to IMU Accelerometer Data
    async def subscribe_imu_accel(self, imu_queue: asyncio.Queue):              
        async for imu in self.drone.telemetry.imu():                            
            await imu_queue.put({
                "x": imu.accelerometer_m_s2.x,
                "y": imu.accelerometer_m_s2.y,
                "z": imu.accelerometer_m_s2.z,
                "ts": imu.timestamp_us
            })

    # Subscribe to Battery Status Updates
    async def subscribe_battery(self, battery_queue: asyncio.Queue):            
        async for b in self.drone.telemetry.battery():
            await battery_queue.put({               
                "percentage": b.remaining_percent,
                "voltage": b.voltage_v,
                "ts": b.timestamp_us
            })

    # Subscribe to Armed Status Updates
    async def subscribe_armed(self, armed_queue: asyncio.Queue):
        async for a in self.drone.telemetry.armed():                            
            await armed_queue.put({"armed": a})     
            if a and self.takeoff_time is None:
                self.takeoff_time = asyncio.get_event_loop().time()

    # Subscribe to In-Air Status
    async def subscribe_in_air(self, in_air_queue: asyncio.Queue):
        """Subscribe to in-air status - detects when drone is flying or landed"""
        async for in_air in self.drone.telemetry.in_air():
            await in_air_queue.put(in_air)  

    # Request Mission List (get total count)
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
                logger.info("》 Requested mission count from Pixhawk")
            except Exception as e:
                logger.error(f"✗ Error requesting mission count: {e}")