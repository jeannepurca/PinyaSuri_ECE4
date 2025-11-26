import asyncio
import csv
import os
from datetime import datetime
import logging
from pixhawk_interface import PixhawkInterface
from image_capture import ImageCapture
from flight_metrics import FlightMetricsLogger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestFlight")

# Configuration
PIXHAWK_ADDR = "serial:///dev/ttyAMA0:57600"
METRICS_CSV = "/home/ece4/PINYASURI/test_flight_metrics.csv"
IMAGE_DIR = "/home/ece4/PINYASURI/test_flight_images"

async def test_flight():
    """Test flight focusing on Pixhawk connection, metrics, and image capture"""
    
    # Initialize components
    pixhawk = PixhawkInterface(system_address=PIXHAWK_ADDR)
    camera = ImageCapture(output_dir=IMAGE_DIR)
    metrics_logger = FlightMetricsLogger(pixhawk, output_csv=METRICS_CSV)
    
    try:
        # Connect to Pixhawk
        logger.info("Connecting to Pixhawk...")
        await pixhawk.connect(timeout=30)
        logger.info("Pixhawk connected successfully!")
        
        # Start metrics logging
        metrics_task = asyncio.create_task(metrics_logger.run())
        logger.info("Started metrics logging")
        
        # Create queues for monitoring
        pos_queue = asyncio.Queue()
        armed_queue = asyncio.Queue()
        
        # Start subscriptions
        pos_task = asyncio.create_task(pixhawk.subscribe_positions(pos_queue))
        armed_task = asyncio.create_task(pixhawk.subscribe_armed(armed_queue))
        
        logger.info("Test flight started. Monitoring drone status...")
        logger.info("Press Ctrl+C to stop the test")
        
        waypoint_counter = 0
        latest_position = None
        
        while True:
            # Update position data
            try:
                while True:
                    latest_position = pos_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            
            # Check armed status
            try:
                while True:
                    armed_status = armed_queue.get_nowait()
                    if armed_status["armed"]:
                        logger.info("Drone is ARMED")
                    else:
                        logger.info("Drone is DISARMED")
            except asyncio.QueueEmpty:
                pass
            
            # Simulate waypoint reached every 30 seconds for testing
            # In real usage, this would be triggered by actual mission progress
            current_time = asyncio.get_event_loop().time()
            if not hasattr(test_flight, 'last_capture_time'):
                test_flight.last_capture_time = current_time
            
            if current_time - test_flight.last_capture_time >= 30:  # Every 30 seconds
                waypoint_counter += 1
                logger.info(f"Simulating waypoint {waypoint_counter} reached")
                
                # Capture image
                image_path = camera.capture(prefix=f"test_wp{waypoint_counter}")
                logger.info(f"Captured image: {image_path}")
                
                # Log waypoint information
                if latest_position:
                    logger.info(f"Position: Lat={latest_position['lat']:.6f}, "
                               f"Lon={latest_position['lon']:.6f}, "
                               f"Alt={latest_position['rel_alt']:.2f}m")
                
                test_flight.last_capture_time = current_time
            
            await asyncio.sleep(1)  # Main loop delay
            
    except KeyboardInterrupt:
        logger.info("Test flight interrupted by user")
    except Exception as e:
        logger.error(f"Test flight error: {e}")
    finally:
        # Cleanup
        logger.info("Cleaning up...")
        metrics_task.cancel()
        pos_task.cancel()
        armed_task.cancel()
        
        try:
            await asyncio.gather(metrics_task, pos_task, armed_task, return_exceptions=True)
        except:
            pass
        
        camera.close()
        await pixhawk.close()
        logger.info("Test flight completed")

if __name__ == "__main__":
    asyncio.run(test_flight())