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
            logger.info("✓ Using MAVSDK for mission tracking")
        except asyncio.TimeoutError:
            raise RuntimeError("⚠ Timeout waiting for Pixhawk connection.")

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

    # Subscribe to Mission Progress Updates (MAVSDK Version)
    async def subscribe_mission_progress(self, prog_queue: asyncio.Queue):  
        """
        Subscribe to mission progress using MAVSDK mission monitoring.
        This works with both QGroundControl and Mission Planner missions.
        """
        try:
            logger.info("》》》 Starting MAVSDK mission progress listener...")
            last_current = -1
            last_total = 0
            
            async for progress in self.drone.mission.mission_progress():
                current = progress.current
                total = progress.total
                
                # Update total if changed
                if total != last_total:
                    last_total = total
                    logger.info(f"》 Mission has {total} total waypoints.")
                
                # Report waypoint changes
                if current != last_current:
                    logger.info(f"》 Mission Progress: Waypoint {current}/{total}")
                    await prog_queue.put({
                        "current": current,
                        "total": total,
                        "source": "mavsdk"
                    })
                    last_current = current
                    
        except asyncio.CancelledError:
            logger.info("⚠ Mission progress listener cancelled.")
            raise
        except Exception as e:
            logger.error(f"✗ Error in mission progress listener: {e}", exc_info=True)

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

    # Request Mission Count (not needed with MAVSDK)
    async def request_mission_count(self):
        """Request mission count - handled automatically by MAVSDK"""
        logger.info("》 MAVSDK will automatically track mission progress")