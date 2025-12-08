import asyncio
import logging
from mavsdk import System

# Configure Logging
logging.basicConfig(level=logging.INFO)        
logger = logging.getLogger("PixhawkInterface")

class PixhawkInterface:
    def __init__(self, system_address: str = "serial:///dev/ttyAMA0:57600"):
        self.system_address = system_address
        self.drone = System()
        self._connected = asyncio.Event()
        self.takeoff_time = None


    # Connect to Pixhawk
    async def connect(self, timeout=30):        
        logger.info(f"Connecting to Pixhawk: {self.system_address}")
        await self.drone.connect(system_address=self.system_address)

        async def wait_for_connection():
            async for state in self.drone.core.connection_state():
                if state.is_connected:
                    logger.info("✓ Pixhawk connected.")
                    self._connected.set()
                    return

        try:
            await asyncio.wait_for(wait_for_connection(), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout waiting for Pixhawk connection.")


    # Subscribe to Position Updates
    async def subscribe_positions(self, pos_queue: asyncio.Queue):
        async for pos in self.drone.telemetry.position():
            await pos_queue.put({
                "lat": pos.latitude_deg,              # Extract latitude
                "lon": pos.longitude_deg,             # Extract longitude
                "abs_alt": pos.absolute_altitude_m,   # Extract absolute altitude
                "rel_alt": pos.relative_altitude_m,   # Extract relative altitude
                "ts": pos.timestamp_us                # Extract timestamp
            })

    # Subscribe to Mission Progress Updates
    async def subscribe_mission_progress(self, prog_queue: asyncio.Queue):      
        async for mp in self.drone.mission.mission_progress():
            await prog_queue.put({"current": mp.current, "total": mp.total})

    # Subscribe to IMU Accelerometer Data
    async def subscribe_imu_accel(self, imu_queue: asyncio.Queue):              
        async for imu in self.drone.telemetry.imu():                            
            await imu_queue.put({
                "x": imu.accelerometer_m_s2.x,      # Extract X acceleration
                "y": imu.accelerometer_m_s2.y,      # Extract Y acceleration
                "z": imu.accelerometer_m_s2.z,      # Extract Z acceleration
                "ts": imu.timestamp_us              
            })

    # Subscribe to Battery Status Updates
    async def subscribe_battery(self, battery_queue: asyncio.Queue):            
        async for b in self.drone.telemetry.battery():
            await battery_queue.put({               
                "percentage": b.remaining_percent,  # Extract remaining percentage
                "voltage": b.voltage_v,             # Extract voltage
                "ts": b.timestamp_us                # Extract timestamp
            })

    # Subscribe to Armed Satus Updates
    async def subscribe_armed(self, armed_queue: asyncio.Queue):
        async for a in self.drone.telemetry.armed():                            
            await armed_queue.put({"armed": a})     

            if a and self.takeoff_time is None:
                self.takeoff_time = asyncio.get_event_loop().time()     