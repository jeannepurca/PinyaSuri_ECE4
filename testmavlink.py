import asyncio
from mavsdk import System

async def main():
    drone = System()
    await drone.connect("serial:///dev/ttyAMA0:57600")
    print("Waiting for heartbeat...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Pixhawk connected!")
            break

    # Set mission progress stream rate
    await drone.telemetry.set_rate_mission_progress(2)

    async for progress in drone.mission.mission_progress():
        print(f"Waypoint {progress.current}/{progress.total}")

asyncio.run(main())
