import asyncio
import logging
import time
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

    async def connect(self, timeout=30):
        """Connect to Pixhawk via MAVSDK"""
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
            logger.info("✓ MAVSDK telemetry ready")
        except asyncio.TimeoutError:
            raise RuntimeError("⚠ Timeout waiting for Pixhawk connection.")

    async def subscribe_positions(self, pos_queue: asyncio.Queue):
        """Subscribe to GPS position updates"""
        logger.info("》》》 Starting position telemetry subscription...")
        try:
            async for pos in self.drone.telemetry.position():
                await pos_queue.put({
                    "lat": pos.latitude_deg,
                    "lon": pos.longitude_deg,
                    "abs_alt": pos.absolute_altitude_m,
                    "rel_alt": pos.relative_altitude_m,
                    "ts": time.time()  # Generate timestamp ourselves
                })
        except asyncio.CancelledError:
            logger.info("⚠ Position subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"Position subscription error: {e}", exc_info=True)

    async def subscribe_flight_mode(self, mode_queue: asyncio.Queue):
        """Subscribe to flight mode changes"""
        logger.info("》》》 Starting flight mode subscription...")
        try:
            async for flight_mode in self.drone.telemetry.flight_mode():
                await mode_queue.put(str(flight_mode))
        except asyncio.CancelledError:
            logger.info("⚠ Flight mode subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"Flight mode subscription error: {e}", exc_info=True)

    async def subscribe_imu_accel(self, imu_queue: asyncio.Queue):
        """Subscribe to IMU accelerometer data"""
        try:
            async for imu in self.drone.telemetry.imu():
                await imu_queue.put({
                    "x": imu.acceleration_frd.forward_m_s2,
                    "y": imu.acceleration_frd.right_m_s2,
                    "z": imu.acceleration_frd.down_m_s2,
                    "ts": time.time()  # Generate timestamp ourselves
                })
        except asyncio.CancelledError:
            logger.info("⚠ IMU subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"IMU subscription error: {e}", exc_info=True)

    async def subscribe_battery(self, battery_queue: asyncio.Queue):
        """Subscribe to battery status updates"""
        try:
            async for b in self.drone.telemetry.battery():
                await battery_queue.put({
                    "percentage": b.remaining_percent,
                    "voltage": b.voltage_v,
                    "ts": time.time()  # Generate timestamp ourselves
                })
        except asyncio.CancelledError:
            logger.info("⚠ Battery subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"Battery subscription error: {e}", exc_info=True)

    async def subscribe_armed(self, armed_queue: asyncio.Queue):
        """Subscribe to armed status updates"""
        logger.info("》》》 Starting armed status subscription...")
        try:
            async for a in self.drone.telemetry.armed():
                await armed_queue.put({"armed": a})
                if a and self.takeoff_time is None:
                    self.takeoff_time = asyncio.get_event_loop().time()
        except asyncio.CancelledError:
            logger.info("⚠ Armed subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"Armed subscription error: {e}", exc_info=True)

    async def subscribe_in_air(self, in_air_queue: asyncio.Queue):
        """Subscribe to in-air status - detects when drone is flying or landed"""
        try:
            async for in_air in self.drone.telemetry.in_air():
                await in_air_queue.put(in_air)
        except asyncio.CancelledError:
            logger.info("⚠ In-air subscription stopped.")
            raise
        except Exception as e:
            logger.error(f"In-air subscription error: {e}", exc_info=True)