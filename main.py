#!/usr/bin/env python3
# main.py - Using async/await

import asyncio
import time
import csv
import logging
import signal

import config
from pixhawk import Pixhawk
from camera import Camera
from metrics import FlightMetrics

running = True

def signal_handler(sig, frame):
    global running
    print("\n⚠ Shutdown requested...")
    running = False

def setup_logging():
    config.ensure_directories()
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s',
        handlers=[
            logging.FileHandler(config.LOG_DIR / "test_flight.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("TestFlight")

def initialize_csv():
    with open(config.LOG_DIR / "image_log.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "flight", "waypoint", "lat", "lon", "rel_alt", "image"])

async def log_image_capture_async(flight_number, waypoint, position, image_path):
    """Non-blocking CSV write"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, log_image_capture_sync, 
                               flight_number, waypoint, position, image_path)

def log_image_capture_sync(flight_number, waypoint, position, image_path):
    """Synchronous CSV write for executor"""
    with open(config.LOG_DIR / "image_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            time.time(), flight_number, waypoint,
            position["lat"], position["lon"], position["rel_alt"],
            image_path
        ])

async def capture_image_async(camera, waypoint, flight_number):
    """Non-blocking image capture"""
    loop = asyncio.get_event_loop()
    image_path = await loop.run_in_executor(
        None, 
        camera.capture,
        waypoint,
        flight_number,
        "pinyasuri"
    )
    return image_path

async def telemetry_updater(pixhawk, metrics):
    """Continuously update telemetry at high rate"""
    while running:
        pixhawk.update()
        
        if pixhawk.armed and pixhawk.position:
            telemetry = {
                "rel_alt": pixhawk.position["rel_alt"],
                "lat": pixhawk.position["lat"],
                "lon": pixhawk.position["lon"],
                "imu_accel": pixhawk.imu_accel,
                "battery_remaining": pixhawk.battery_remaining
            }
            metrics.update(telemetry)
        
        await asyncio.sleep(0.05)  # High-frequency telemetry updates

async def waypoint_monitor(pixhawk, camera, metrics, state):
    """Monitor and capture images at waypoints"""
    while running:
        if (
            pixhawk.armed
            and pixhawk.mode == "AUTO"
            and pixhawk.last_wp
            and pixhawk.last_wp not in state['captured_wp']
            and pixhawk.position
        ):
            wp = pixhawk.last_wp
            
            # Wait before capture (non-blocking)
            await asyncio.sleep(1.5)
            
            # Capture image (runs in thread pool)
            image_path = await capture_image_async(camera, wp, state['flight_number'])
            
            # Log to CSV (runs in thread pool)
            await log_image_capture_async(
                state['flight_number'], wp, pixhawk.position, image_path
            )
            
            print(f"📸 Captured WP{wp}")
            state['captured_wp'].add(wp)
            metrics.increment_waypoint()
        
        await asyncio.sleep(0.1)

async def arm_monitor(pixhawk, metrics, state):
    """Monitor arm/disarm state changes"""
    was_armed = False
    
    while running:
        if pixhawk.armed and not was_armed:
            # Just armed
            metrics.start_flight(True, pixhawk.battery_remaining)
            was_armed = True
            print(f"🛫 Flight {state['flight_number']} armed")
            
        elif not pixhawk.armed and was_armed:
            # Just disarmed
            metrics.end_flight(True)
            was_armed = False
            state['captured_wp'].clear()
            state['flight_number'] += 1
            print(f"🛬 Flight ended")
        
        await asyncio.sleep(0.2)

async def status_reporter(pixhawk, metrics):
    """Periodically report system status"""
    while running:
        await asyncio.sleep(10)  # Report every 10 seconds
        
        if pixhawk.armed:
            status = (
                f"📊 Status: Mode={pixhawk.mode}, "
                f"Alt={pixhawk.position['rel_alt']:.1f}m, "
                f"WP={pixhawk.last_wp}, "
                f"Battery={pixhawk.battery_remaining}"
            )
            print(status)

async def main_async():
    """Main async entry point"""
    # Setup
    logger = setup_logging()
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize components
    pixhawk = Pixhawk()
    camera = Camera()
    metrics = FlightMetrics()
    
    pixhawk.wait_for_connection()
    initialize_csv()
    
    # Shared state
    state = {
        'flight_number': 1,
        'captured_wp': set()
    }
    
    print("🚁 Mission monitoring started (async mode)")
    
    try:
        # Run all tasks concurrently
        await asyncio.gather(
            telemetry_updater(pixhawk, metrics),     # High-freq telemetry
            waypoint_monitor(pixhawk, camera, metrics, state),  # Image capture
            arm_monitor(pixhawk, metrics, state),    # Arm/disarm tracking
            status_reporter(pixhawk, metrics)        # Status updates
        )
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        print("\n🔧 Cleaning up...")
        try:
            camera.close()
        except Exception as e:
            print(f"⚠ Error closing camera: {e}")
        print("✓ Cleanup complete")

def main():
    """Entry point - starts the async event loop"""
    asyncio.run(main_async())

if __name__ == "__main__":
    main()