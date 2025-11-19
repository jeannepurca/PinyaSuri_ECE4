import asyncio
from mavsdk import System, telemetry, mission
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PixhawkInterface")

class PixhawkInterface:
    def __init__(self, system_address: str = "serial:///dev/ttyAMA0:57600"):
        """
        system_address: MAVSDK connection string. e.g. "serial:///dev/ttyAMA0:57600"
        """
        self.system_address = system_address
        self.drone = System()
        self._connected = asyncio.Event()
        self._stop = False

    async def connect(self, timeout=30):
        logger.info(f"Connecting to Pixhawk: {self.system_address}")
        await self.drone.connect(system_address=self.system_address)

        # wait until connected
        async def wait_for_conn():
            async for state in self.drone.core.connection_state():
                if state.is_connected:
                    logger.info("Pixhawk connected")
                    self._connected.set()
                    return

        try:
            await asyncio.wait_for(wait_for_conn(), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout waiting for Pixhawk connection")

    async def subscribe_positions(self, pos_queue: asyncio.Queue):
        """
        Put (lat, lon, abs_alt, relative_alt, timestamp) tuples into pos_queue.
        """
        async for pos in self.drone.telemetry.position():
            lat = pos.latitude_deg
            lon = pos.longitude_deg
            abs_alt = pos.absolute_altitude_m
            rel_alt = pos.relative_altitude_m
            ts = pos.timestamp_us
            await pos_queue.put({"lat": lat, "lon": lon, "abs_alt": abs_alt, "rel_alt": rel_alt, "ts": ts})
            if self._stop:
                break

    async def subscribe_mission_progress(self, prog_queue: asyncio.Queue):
        """
        Put mission progress dicts into prog_queue: {'current': int, 'total': int}
        """
        async for mp in self.drone.mission.mission_progress():
            await prog_queue.put({"current": mp.current, "total": mp.total})
            if self._stop:
                break

    async def get_armed_state(self):
        async for s in self.drone.telemetry.armed():
            return s

    async def close(self):
        self._stop = True