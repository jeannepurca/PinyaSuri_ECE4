import asyncio
import logging
import csv
import os
import signal
import sys

from datetime import datetime
from typing import Optional
from pathlib import Path
from mavsdk import System

from pixhawk_interface import PixhawkInterface
from image_capture import ImageCapture
from ai_classifier import TFLiteClassifier
from flight_metrics import FlightMetricsLogger

import config

# Configuration Paths  
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
IMG_DIR = BASE_DIR / "images"
RAW_IMG_DIR = IMG_DIR / "raw"
ANNOTATED_IMG_DIR = IMG_DIR / "annotated"

LOG_DIR.mkdir(exist_ok=True)
RAW_IMG_DIR.mkdir(parents=True, exist_ok=True)
ANNOTATED_IMG_DIR.mkdir(parents=True, exist_ok=True)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "flight.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PinyaSuri")

# Configuration Constants
class PinyaSuriSystem:
    """Main system coordinator for PinyaSuri"""


    def __init__(self):
        self.pixhawk: Optional[PixhawkInterface] = None
        self.camera: Optional[ImageCapture] = None
        self.classifier: Optional[TFLiteClassifier] = None
        self.metrics_logger: Optional[FlightMetricsLogger] = None
        self.shutdown_event = asyncio.Event()


    async def initialize(self, max_retries: int = 3) -> bool:
        """
        - Initialize all system components with retry logic.
        - Returns 'True' if successful, 'False' otherwise.
        """
        
        config.ensure_directories()
        
        # Initialize Pixhawk
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Initializing Pixhawk (attempt {attempt}/{max_retries})...")
                self.pixhawk = PixhawkInterface(system_address=config.PIXHAWK_ADDRESS)
                await self.pixhawk.connect(timeout=config.CONNECTION_TIMEOUT)
                logger.info("✓ Pixhawk connected successfully")
                break
            except Exception as e:
                logger.error(f"✗ Pixhawk connection failed: {e}")
                if attempt == max_retries:
                    logger.error("Maximum retry attempts reached for Pixhawk.")
                    return False
                await asyncio.sleep(2)

        # Initialize Camera
        try:
            logger.info("Initializing Camera...")
            self.camera = ImageCapture(
                output_dir=str(config.IMAGE_DIR)
            )
            logger.info("✓ Camera initialized successfully")
        except Exception as e:
            logger.error(f"✗ Camera initialization failed: {e}")
            return False
        
        # Initialize AI Classifier
        try:
            logger.info("Loading AI Model...")
            self.classifier = TFLiteClassifier(
                model_path=str(config.MODEL_PATH),
                input_size=config.MODEL_INPUT_SIZE
            )
            logger.info("✓ AI Model loaded successfully")
        except Exception as e:
            logger.error(f"✗ AI Model loading failed: {e}")
            return False
        
        # Initialize CSV for Classification Results
        self._initialize_classification_csv()

        # Initialize Flight Metrics Logger
        self.metrics_logger = FlightMetricsLogger(
            self.pixhawk,
            output_csv=str(config.FLIGHT_METRICS_CSV)
        )

        return True


    def _initialize_classification_csv(self):
        """
        - Create classification CSV with headers (if it doesn't exist)
        """

        if not config.CLASSIFICATION_CSV.exists():
            header = [
                "timestamp_utc", "image_path", "lat", "lon", "abs_alt_m", "rel_alt_m",
                "mission_item_current", "mission_item_total", "pred_idx", "pred_label",
                "confidence"
            ]
            
            with open(config.CLASSIFICATION_CSV, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
            logger.info(f"Created classification log: {config.CLASSIFICATION_CSV}")
    

    async def run_mission(self):
        """
        - Main mission loop: monitor progress and capture/classify images
        """
        
        # Create Queues for Telemetry
        pos_queue = asyncio.Queue()
        prog_queue = asyncio.Queue()
        imu_queue = asyncio.Queue()
        battery_queue = asyncio.Queue()
        armed_queue = asyncio.Queue()
        
        # Start Subscriptions
        pos_task = asyncio.create_task(self.pixhawk.subscribe_positions(pos_queue))
        prog_task = asyncio.create_task(self.pixhawk.subscribe_mission_progress(prog_queue))
        imu_task = asyncio.create_task(self.pixhawk.subscribe_imu_accel(imu_queue))
        batt_task = asyncio.create_task(self.pixhawk.subscribe_battery(battery_queue))
        armed_task = asyncio.create_task(self.pixhawk.subscribe_armed(armed_queue))
        
        # Pass queues to metrics logger instead of creating new ones
        self.metrics_logger.pos_queue = pos_queue
        self.metrics_logger.imu_queue = imu_queue
        self.metrics_logger.battery_queue = battery_queue
        self.metrics_logger.armed_queue = armed_queue

        metrics_task = asyncio.create_task(self.metrics_logger.run())

        # Mission State
        last_progress = -1
        captured_at_progress = -1
        latest_pos = None
        mission_total = 0
        
        logger.info("Monitoring started. Waiting for waypoints...")
        
        try:
            while not self.shutdown_event.is_set():
                # Drain Mission Progress Queue
                try:
                    while True:
                        prog = prog_queue.get_nowait()
                        last_progress = prog["current"]
                        mission_total = prog["total"]
                        logger.info(f"Mission Progress: {last_progress}/{mission_total}")
                except asyncio.QueueEmpty:
                    pass
                
                # Drain Position Queue
                try:
                    while True:
                        latest_pos = pos_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                
                # Process New Waypoint  
                if last_progress >= 0 and last_progress != captured_at_progress:
                    await self._process_waypoint(
                        last_progress, 
                        mission_total, 
                        latest_pos
                    )
                    captured_at_progress = last_progress
                
                await asyncio.sleep(config.MAIN_LOOP_INTERVAL)
        
        finally:
            # Cleanup
            logger.info("Stopping mission tasks...")
            pos_task.cancel()
            prog_task.cancel()
            imu_task.cancel()
            batt_task.cancel()
            armed_task.cancel()
            metrics_task.cancel()
            await asyncio.gather(pos_task, prog_task, imu_task, batt_task, 
                                 armed_task, metrics_task, return_exceptions=True)


    async def _process_waypoint(self, waypoint_idx: int, mission_total: int, position: Optional[dict]):
        """
        - Capture image and run classification at a waypoint
        """

        logger.info(f"Waypoint {waypoint_idx} reached. Processing...")
        
        try:
            # Capture Image
            image_path = self.camera.capture(prefix=f"wp{waypoint_idx}")
            logger.info(f"Image captured: {image_path}")
            
            # Run AI Classification
            result = self.classifier.predict(image_path)
            pred_label = config.get_class_name(result["index"])
            logger.info(f"Classification: {pred_label} (confidence: {result['confidence']:.2%})")
            
            # Log to CSV
            timestamp = datetime.utcnow().isoformat()
            lat = position["lat"] if position else ""
            lon = position["lon"] if position else ""
            abs_alt = position["abs_alt"] if position else ""
            rel_alt = position["rel_alt"] if position else ""
            
            with open(config.CLASSIFICATION_CSV, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp, image_path, lat, lon, abs_alt, rel_alt,
                    waypoint_idx, mission_total, result["index"], pred_label,
                    result["confidence"]
                ])
            
            logger.info(f"✓ Waypoint {waypoint_idx} processed successfully")
            
        except Exception as e:
            logger.error(f"✗ Error processing waypoint {waypoint_idx}: {e}", exc_info=True)


    async def shutdown(self):
        """
        - Graceful shutdown of all components
        """

        logger.info("Initiating shutdown...")
        self.shutdown_event.set()
        
        if self.camera:
            self.camera.close()
        
        logger.info("Shutdown complete")


async def main():
    """
    Main entry point
    """
    
    system = PinyaSuriSystem()
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(system.shutdown())
    
    # Register signal handlers (Unix-like systems)
    try:
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass
    
    # Initialize system
    logger.info("=== PinyaSuri System Starting ===")
    if not await system.initialize():
        logger.error("System initialization failed. Exiting.")
        return 1
    
    logger.info("=== All systems initialized ===")
    
    # Run mission
    try:
        await system.run_mission()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1
    finally:
        await system.shutdown()
    
    logger.info("=== PinyaSuri System Stopped ===")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))