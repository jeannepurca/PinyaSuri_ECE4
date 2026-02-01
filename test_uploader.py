#!/usr/bin/env python3
# test_uploader.py

import time
import logging

import config
import uploader


# --------------------------------------------------
# LOGGING
# --------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    logger.info("🚀 Starting uploader test using EXISTING files")

    # Ensure directories exist
    config.ensure_directories()

    # --------------------------------------------------
    # Start upload worker
    # --------------------------------------------------
    uploader.start_upload_queue()

    # --------------------------------------------------
    # Enable uploading (required for scan to queue files)
    # Use a safe placeholder flight_id
    # --------------------------------------------------
    test_flight_id = "EXISTING_DATA_UPLOAD"
    uploader.upload_queue.enable_uploading(test_flight_id)

    # --------------------------------------------------
    # Scan directories and queue unuploaded files
    # --------------------------------------------------
    uploader.scan_and_queue_unuploaded_files()

    # --------------------------------------------------
    # Wait for uploads to process
    # --------------------------------------------------
    logger.info("⏳ Waiting for uploads to complete...")
    max_wait = 120  # seconds
    waited = 0

    while waited < max_wait:
        stats = uploader.upload_queue.get_stats()

        if stats["queue_size"] == 0:
            logger.info("✅ Upload queue empty")
            break

        logger.info(
            f"📤 Queue={stats['queue_size']} | "
            f"Images={stats['image_uploaded']} | "
            f"JSON={stats['json_uploaded']} | "
            f"Failed={stats['failed_count']}"
        )

        time.sleep(5)
        waited += 5

    if waited >= max_wait:
        logger.warning("⚠ Timeout waiting for uploads")

    # --------------------------------------------------
    # Stop uploader & print stats
    # --------------------------------------------------
    uploader.stop_upload_queue()

    logger.info("🏁 Existing-files upload test finished")


if __name__ == "__main__":
    main()
