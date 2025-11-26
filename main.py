import asyncio
import csv
import os
from datetime import datetime
import logging

from pixhawk_interface import PixhawkInterface
from image_capture import ImageCapture
from ai_classifier import TFLiteClassifier
from flight_metrics import FlightMetricsLogger

logging.basicConfig(level=logging.INFO)       # Configure logging
logger = logging.getLogger("Main")            # Create logger for main script

# Paths
OUTPUT_CSV = "/home/ece4/PINYASURI/image_classification_log.csv"        # Path to Output CSV
MODEL_PATH = "/home/ece4/PINYASURI/pineapple_classifier.tflite"         # Path to TFLite model
IMAGE_DIR = "/home/ece4/PINYASURI/drone_images"                         # Directory to save captured images
PIXHAWK_ADDR = "serial:///dev/ttyAMA0:57600"                            # Pixhawk connection address

async def main():               # Main async function
    pix = PixhawkInterface(system_address=PIXHAWK_ADDR)                 # Initialize Pixhawk interface
    await pix.connect(timeout=30)                                       # Connect to Pixhawk with timeout

    # Queues for mission
    pos_queue = asyncio.Queue()                                         # Queue for position updates
    prog_queue = asyncio.Queue()                                        # Queue for mission progress updates
    pos_task = asyncio.create_task(pix.subscribe_positions(pos_queue))              # Subscribe to position updates
    prog_task = asyncio.create_task(pix.subscribe_mission_progress(prog_queue))     # Subscribe to mission progress updates

    # Initialize camera & classifier
    img = ImageCapture(output_dir=IMAGE_DIR)                               # Initialize camera
    clf = TFLiteClassifier(MODEL_PATH, input_size=(224,224))            # Initialize TFLite classifier

    # Ensure classification CSV exists
    header = ["timestamp_utc","image_path","lat","lon","abs_alt_m","rel_alt_m",
              "mission_item_current","mission_item_total","pred_idx","confidence"]

    if not os.path.exists(OUTPUT_CSV):                  # If CSV does not exist
        with open(OUTPUT_CSV, "w", newline="") as f:    # Create it
            writer = csv.writer(f)                      # Create writer
            writer.writerow(header)                     # Write header

    last_progress = -1                  # Last mission progress
    latest_pos = None                   # Latest position

    # Initialize flight metrics logger
    metrics_logger = FlightMetricsLogger(pix)
    metrics_task = asyncio.create_task(metrics_logger.run())

    try:
        while True:

            # Mission progress updates
            try:                        # Try to get mission progress
                while True:             # get latest mission progress
                    prog = prog_queue.get_nowait()      # Non-blocking get
                    last_progress = prog["current"]     # Update last progress
                    mission_total = prog["total"]       # Update total mission items
                    logger.info(f"Mission progress: {last_progress}/{mission_total}")   # Log progress
            except asyncio.QueueEmpty:
                pass

            # Latest position
            try:                        # Try to get position
                while True:             # get latest position
                    p = pos_queue.get_nowait()          # Non-blocking get
                    latest_pos = p                      # Update latest position
            except asyncio.QueueEmpty:
                pass

            if last_progress >= 0:      # Valid mission progress
                if not hasattr(main, "captured_at_progress"):       # Initialize capture state
                    main.captured_at_progress = -1                  # No captures yet

                if last_progress != main.captured_at_progress:      # New mission item
                    logger.info(f"Waypoint reached (index {last_progress}). Capturing image...")    # Log waypoint reached
                    image_path = img.capture(prefix=f"wp{last_progress}")                           # Capture image
                    
                    # Run classification
                    result = clf.predict(image_path)                      # Predict classification
                    ts = datetime.utcnow().isoformat()                    # Timestamp
                    lat = latest_pos["lat"] if latest_pos else ""         # Latitude
                    lon = latest_pos["lon"] if latest_pos else ""         # Longitude
                    abs_alt = latest_pos["abs_alt"] if latest_pos else "" # Absolute altitude
                    rel_alt = latest_pos["rel_alt"] if latest_pos else "" # Relative altitude
                    
                    # Log to CSV
                    with open(OUTPUT_CSV, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            ts, image_path, lat, lon, abs_alt, rel_alt,
                            last_progress, mission_total, result["index"], result["confidence"]
                        ])
                    logger.info(f"Saved result for {image_path} -> {result}")
                    main.captured_at_progress = last_progress

            await asyncio.sleep(0.2)

    except asyncio.CancelledError:          # Handle cancellation
        logger.info("Main cancelled")       # Log cancellation
    finally:                                # Cleanup
        await pix.close()                   # Close Pixhawk interface
        img.close()                         # Close image interface
        metrics_task.cancel()               # Cancel metrics logging
        await asyncio.sleep(0.2)            # Allow tasks to finish

if __name__ == "__main__":                  # Run main if executed as script
    asyncio.run(main())                     # Run main async