import asyncio
import csv
import os
from datetime import datetime
import logging
import pathlib

from pixhawk_interface import PixhawkInterface
from image_capture import ImageCapture
from ai_classifier import TFLiteClassifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Main")

OUTPUT_CSV = "/home/ece4/PINYASURI/image_classification_log.csv"
MODEL_PATH = "/home/ece4/PINYASURI/pineapple_classifier.tflite"  # put your model here
IMAGE_DIR = "/home/ece4/PINYASURI/drone_images"
PIXHAWK_ADDR = "serial:///dev/ttyAMA0:57600"  # change port/baud if needed

async def main():
    pix = PixhawkInterface(system_address=PIXHAWK_ADDR)
    await pix.connect(timeout=30)

    pos_queue = asyncio.Queue()
    prog_queue = asyncio.Queue()

    # start subscribers
    pos_task = asyncio.create_task(pix.subscribe_positions(pos_queue))
    prog_task = asyncio.create_task(pix.subscribe_mission_progress(prog_queue))

    img = ImageCapture(out_dir=IMAGE_DIR)
    clf = TFLiteClassifier(MODEL_PATH, input_size=(224,224))

    # ensure CSV exists with header
    header = ["timestamp_utc","image_path","lat","lon","abs_alt_m","rel_alt_m","mission_item_current","mission_item_total","pred_idx","confidence"]
    if not os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)

    last_progress = -1
    latest_pos = None

    try:
        while True:
            # non-blockingly check mission progress and position
            try:
                while True:
                    prog = prog_queue.get_nowait()
                    last_progress = prog["current"]
                    mission_total = prog["total"]
                    logger.info(f"Mission progress: {last_progress}/{mission_total}")
            except asyncio.QueueEmpty:
                pass

            try:
                # always keep latest position
                while True:
                    p = pos_queue.get_nowait()
                    latest_pos = p
            except asyncio.QueueEmpty:
                pass

            # If we detected a new mission item index, capture+classify
            # (this simple logic captures when current increments)
            if last_progress >= 0:
                # Some systems report the same current multiple times; implement capture-on-change
                # Here we capture whenever current differs from last captured value stored in variable
                if not hasattr(main, "captured_at_progress"):
                    main.captured_at_progress = -1

                if last_progress != main.captured_at_progress:
                    logger.info(f"Waypoint reached (index {last_progress}). Capturing image...")
                    image_path = img.capture(prefix=f"wp{last_progress}")
                    # run classification
                    result = clf.predict(image_path)
                    ts = datetime.utcnow().isoformat()
                    lat = latest_pos["lat"] if latest_pos else ""
                    lon = latest_pos["lon"] if latest_pos else ""
                    abs_alt = latest_pos["abs_alt"] if latest_pos else ""
                    rel_alt = latest_pos["rel_alt"] if latest_pos else ""
                    # log to CSV
                    with open(OUTPUT_CSV, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([ts, image_path, lat, lon, abs_alt, rel_alt, last_progress, mission_total, result["index"], result["confidence"]])
                    logger.info(f"Saved result for {image_path} -> {result}")
                    main.captured_at_progress = last_progress

            await asyncio.sleep(0.2)

    except asyncio.CancelledError:
        logger.info("Main cancelled")
    finally:
        await pix.close()
        img.close()

if __name__ == "__main__":
    asyncio.run(main())