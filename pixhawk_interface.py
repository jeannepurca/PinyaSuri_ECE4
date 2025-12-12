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
            logger.info("✓ Using MAVSDK with polling for mission tracking")
        except asyncio.TimeoutError:
            raise RuntimeError("⚠ Timeout waiting for Pixhawk connection.")

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

    # Subscribe to Mission Progress - POLLING VERSION
    async def subscribe_mission_progress(self, prog_queue: asyncio.Queue):  
        """
        Poll mission progress periodically.
        This is more reliable than subscriptions for Mission Planner missions.
        """
        logger.info("》》》 Starting mission progress polling (5Hz)...")
        
        last_current = -1
        last_total = 0
        poll_interval = 0.2  # Poll every 200ms (5Hz)
        
        try:
            while True:
                try:
                    # Poll mission progress
                    async for progress in self.drone.mission.mission_progress():
                        current = progress.current
                        total = progress.total
                        
                        # Update total if changed
                        if total != last_total and total > 0:
                            last_total = total
                            logger.info(f"》 Mission has {total} waypoints")
                        
                        # Report waypoint changes
                        if current != last_current:
                            logger.info(f"》 Mission Progress: Waypoint {current}/{total}")
                            await prog_queue.put({
                                "current": current,
                                "total": total,
                                "source": "mavsdk_poll"
                            })
                            last_current = current
                        
                        # Only get one reading per poll
                        break
                        
                except Exception as poll_error:
                    logger.debug(f"Poll error (normal during init): {poll_error}")
                
                await asyncio.sleep(poll_interval)
                    
        except asyncio.CancelledError:
            logger.info("⚠ Mission progress polling stopped.")
            raise
        except Exception as e:
            logger.error(f"✗ Error in mission progress polling: {e}", exc_info=True)

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
        """Not needed with polling approach"""
        pass