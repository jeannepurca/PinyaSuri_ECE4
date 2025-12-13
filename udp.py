from mavsdk import System
import asyncio

async def main():
    drone = System()
    await drone.connect(system_address="udpin://127.0.0.1:14550")  # note 'udpin://'

    async for state in drone.telemetry.connection_state():
        if state.is_connected:
            print("UDP connection OK!")
            break

asyncio.run(main())
