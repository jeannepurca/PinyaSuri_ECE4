import asyncio
import logging
from mavsdk import System

logging.basicConfig(level=logging.INFO)         # Configure logging
logger = logging.getLogger("PixhawkInterface")  # Create logger for PixhawkInterface

class PixhawkInterface: # Interface for Pixhawk using MAVSDK
    def __init__(self, system_address: str = "serial:///dev/ttyAMA0:57600"):
        self.system_address = system_address    # MAVSDK connection string
        self.drone = System()                   # MAVSDK System object
        self._connected = asyncio.Event()       # Event to signal connection
        self._stop = False                      # Stop flag
        self.takeoff_time = None                # Takeoff time

    async def connect(self, timeout=30):        # Connect to Pixhawk
        logger.info(f"Connecting to Pixhawk: {self.system_address}")    # Log connection attempt
        await self.drone.connect(system_address=self.system_address)    # Connect to the drone

        async def wait_for_conn():              # Wait for connection establishment
            async for state in self.drone.core.connection_state():      # Monitor connection state
                if state.is_connected:          # If connected
                    logger.info("Pixhawk connected.")                   # Log successful connection
                    self._connected.set()                               # Set connected event
                    return

        try:                                    # Try to wait for connection with timeout
            await asyncio.wait_for(wait_for_conn(), timeout=timeout)    # Wait for connection
        except asyncio.TimeoutError:            # On timeout
            raise RuntimeError("Timeout waiting for Pixhawk connection.")    # Raise timeout error

    async def subscribe_positions(self, pos_queue: asyncio.Queue):      # Subscribe to position updates
        async for pos in self.drone.telemetry.position():
            await pos_queue.put({
                "lat": pos.latitude_deg,              # Extract latitude
                "lon": pos.longitude_deg,             # Extract longitude
                "abs_alt": pos.absolute_altitude_m,   # Extract absolute altitude
                "rel_alt": pos.relative_altitude_m,   # Extract relative altitude
                "ts": pos.timestamp_us                # Extract timestamp
            })
            if self._stop:                      # If stop flag is set
                break                           # Break the loop

    async def subscribe_mission_progress(self, prog_queue: asyncio.Queue):      # Subscribe to mission progress updates
        async for mp in self.drone.mission.mission_progress():                  # Monitor mission progress
            await prog_queue.put({"current": mp.current, "total": mp.total})    # Put progress dict into queue
            if self._stop:                      # If stop flag is set
                break                           # Break the loop

    async def subscribe_imu_accel(self, imu_queue: asyncio.Queue):              # Subscribe to IMU accelerometer data
        async for imu in self.drone.telemetry.imu():                            # Monitor IMU data  
            await imu_queue.put({
                "x": imu.accelerometer_m_s2.x,      # Extract X acceleration
                "y": imu.accelerometer_m_s2.y,      # Extract Y acceleration
                "z": imu.accelerometer_m_s2.z,      # Extract Z acceleration
                "ts": imu.timestamp_us              # Extract timestamp
            })
            if self._stop:                      # If stop flag is set
                break                           # Break the loop

    async def subscribe_battery(self, battery_queue: asyncio.Queue):            # Subscribe to battery status updates
        async for b in self.drone.telemetry.battery():                          # Monitor battery status
            await battery_queue.put({               
                "percentage": b.remaining_percent,  # Extract remaining percentage
                "voltage": b.voltage_v,             # Extract voltage
                "ts": b.timestamp_us                # Extract timestamp
            })
            if self._stop:
                break

    async def subscribe_armed(self, armed_queue: asyncio.Queue):                # Subscribe to armed status updates
        async for a in self.drone.telemetry.armed():                            # Monitor armed status
            await armed_queue.put({"armed": a})     # Put armed status into queue
            if self._stop:                      # If stop flag is set
                break                           # Break the loop

            if a and self.takeoff_time is None:                         # If armed and takeoff time not set
                self.takeoff_time = asyncio.get_event_loop().time()     # Set takeoff time

    async def close(self):                      # Close connection
        self._stop = True                       # Set stop flag