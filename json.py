#!/usr/bin/env python3
# json.py - With upload queue and retry mechanism

import json
import requests
from datetime import datetime, timezone
from pathlib import Path
import logging
import threading
import time
import queue
import config

logger = logging.getLogger("JSONUploader")

# ============================================================================
# UPLOAD QUEUE SYSTEM
# ============================================================================

class UploadQueue:
    """Manages upload queue with automatic retry when connection is restored"""
    def __init__(self, max_retries=3, retry_delay=60):
        self.upload_queue = queue.Queue()
        self.failed_uploads = []
        self.max_retries = max_retries
        self.retry_delay = retry_delay  # seconds between retries
        self.worker_thread = None
        self.running = False
        self.stats = {
            "json_queued": 0,
            "json_uploaded": 0,
            "json_failed": 0,
            "image_queued": 0,
            "image_uploaded": 0,
            "image_failed": 0
        }
        
        # Track uploaded files to avoid duplicates
        self.uploaded_files = set()
        self._load_upload_history()
    
    def _load_upload_history(self):
        """Load history of successfully uploaded files"""
        history_file = config.JSON_DIR / "upload_history.json"
        if history_file.exists():
            try:
                with open(history_file, "r") as f:
                    data = json.load(f)
                    self.uploaded_files = set(data.get("uploaded", []))
                logger.info(f"✓ Loaded upload history: {len(self.uploaded_files)} files")
            except Exception as e:
                logger.warning(f"⚠ Could not load upload history: {e}")
    
    def _save_upload_history(self):
        """Save history of successfully uploaded files"""
        history_file = config.JSON_DIR / "upload_history.json"
        try:
            config.ensure_directories()
            with open(history_file, "w") as f:
                json.dump({
                    "uploaded": list(self.uploaded_files),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"⚠ Could not save upload history: {e}")
    
    def start(self):
        """Start the background upload worker"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            logger.info("✓ Upload queue worker started")
    
    def stop(self):
        """Stop the background upload worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("⚠ Upload queue worker stopped")
    
    def add_json(self, json_path):
        """Add JSON file to upload queue"""
        if str(json_path) not in self.uploaded_files:
            self.upload_queue.put(("json", json_path))
            self.stats["json_queued"] += 1
            logger.debug(f"📥 Queued JSON: {Path(json_path).name}")
    
    def add_image(self, image_path):
        """Add image file to upload queue"""
        if str(image_path) not in self.uploaded_files:
            self.upload_queue.put(("image", image_path))
            self.stats["image_queued"] += 1
            logger.debug(f"📥 Queued image: {Path(image_path).name}")
    
    def _worker(self):
        """Background worker that processes upload queue"""
        logger.info("🔄 Upload worker thread running...")
        
        retry_counter = 0
        
        while self.running:
            try:
                # Get item from queue (wait up to 1 second)
                try:
                    upload_type, file_path = self.upload_queue.get(timeout=1.0)
                except queue.Empty:
                    # No items in queue, retry failed uploads periodically
                    if self.failed_uploads and retry_counter >= self.retry_delay:
                        logger.info(f"🔄 Retrying {len(self.failed_uploads)} failed uploads...")
                        self._retry_failed_uploads()
                        retry_counter = 0
                    retry_counter += 1
                    continue
                
                # Attempt upload
                success = False
                
                if upload_type == "json":
                    success = self._upload_json_internal(file_path)
                    if success:
                        self.stats["json_uploaded"] += 1
                    else:
                        self.stats["json_failed"] += 1
                        
                elif upload_type == "image":
                    success = self._upload_image_internal(file_path)
                    if success:
                        self.stats["image_uploaded"] += 1
                    else:
                        self.stats["image_failed"] += 1
                
                # Track result
                if success:
                    self.uploaded_files.add(str(file_path))
                    self._save_upload_history()
                else:
                    # Add to failed list for retry
                    self.failed_uploads.append((upload_type, file_path, 0))
                
                self.upload_queue.task_done()
                
            except Exception as e:
                logger.error(f"⚠ Upload worker error: {e}")
                time.sleep(1)
    
    def _retry_failed_uploads(self):
        """Retry failed uploads with exponential backoff"""
        still_failed = []
        
        for upload_type, file_path, retry_count in self.failed_uploads:
            if retry_count >= self.max_retries:
                logger.warning(f"❌ Max retries reached for {Path(file_path).name}")
                continue
            
            # Attempt upload
            success = False
            if upload_type == "json":
                success = self._upload_json_internal(file_path)
            elif upload_type == "image":
                success = self._upload_image_internal(file_path)
            
            if success:
                self.uploaded_files.add(str(file_path))
                self._save_upload_history()
                logger.info(f"✓ Retry successful: {Path(file_path).name}")
            else:
                still_failed.append((upload_type, file_path, retry_count + 1))
        
        self.failed_uploads = still_failed
    
    def _upload_json_internal(self, json_path):
        """Internal JSON upload with error handling"""
        try:
            if not Path(json_path).exists():
                logger.error(f"⚠ JSON file not found: {json_path}")
                return False
            
            with open(json_path, "r") as f:
                json_data = json.load(f)
            
            url = f"{config.SERVER}/upload/json"
            response = requests.post(url, json=json_data, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"✓ JSON uploaded: {Path(json_path).name}")
                return True
            else:
                logger.warning(f"⚠ Server error {response.status_code}: {Path(json_path).name}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.debug(f"⚠ No connection - will retry: {Path(json_path).name}")
            return False
        except requests.exceptions.Timeout:
            logger.debug(f"⚠ Timeout - will retry: {Path(json_path).name}")
            return False
        except Exception as e:
            logger.error(f"⚠ Upload error: {e}")
            return False
    
    def _upload_image_internal(self, image_path):
        """Internal image upload with error handling"""
        try:
            image_file = Path(image_path)
            
            if not image_file.exists():
                logger.error(f"⚠ Image file not found: {image_path}")
                return False
            
            url = f"{config.SERVER}/upload/image"
            
            with open(image_file, "rb") as f:
                files = {"file": (image_file.name, f, "image/jpeg")}
                response = requests.post(url, files=files, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"✓ Image uploaded: {image_file.name}")
                return True
            else:
                logger.warning(f"⚠ Server error {response.status_code}: {image_file.name}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.debug(f"⚠ No connection - will retry: {Path(image_path).name}")
            return False
        except requests.exceptions.Timeout:
            logger.debug(f"⚠ Timeout - will retry: {Path(image_path).name}")
            return False
        except Exception as e:
            logger.error(f"⚠ Upload error: {e}")
            return False
    
    def get_stats(self):
        """Get upload statistics"""
        return {
            **self.stats,
            "queue_size": self.upload_queue.qsize(),
            "failed_count": len(self.failed_uploads),
            "uploaded_total": len(self.uploaded_files)
        }
    
    def print_stats(self):
        """Print upload statistics"""
        stats = self.get_stats()
        logger.info("="*60)
        logger.info("📊 UPLOAD QUEUE STATISTICS")
        logger.info(f"   JSON: {stats['json_uploaded']}/{stats['json_queued']} uploaded, "
                    f"{stats['json_failed']} failed")
        logger.info(f"   Images: {stats['image_uploaded']}/{stats['image_queued']} uploaded, "
                    f"{stats['image_failed']} failed")
        logger.info(f"   Queue size: {stats['queue_size']}")
        logger.info(f"   Failed (retrying): {stats['failed_count']}")
        logger.info(f"   Total uploaded: {stats['uploaded_total']}")
        logger.info("="*60)


# Global upload queue instance
upload_queue = UploadQueue()


# ============================================================================
# PUBLIC API FUNCTIONS
# ============================================================================

def get_json_dir_for_today():
    """Create and return JSON directory for today's date"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    json_dir = config.JSON_DIR / date_str
    json_dir.mkdir(parents=True, exist_ok=True)
    return json_dir


def save_json(flight_number, waypoint, image_path=None, class_name="", prediction=""):
    """Save flight and waypoint data as JSON locally and queue for upload"""
    try:
        json_dir = get_json_dir_for_today()
        
        timestamp = datetime.now().strftime("%H%M%S")
        json_filename = f"flight_{flight_number:03d}_wp{waypoint}_{timestamp}.json"
        json_path = json_dir / json_filename

        data = {
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "flight_number": flight_number,
            "waypoint": waypoint,
            "class": class_name,
            "prediction": prediction,
            "image_id": f"flight_{flight_number:03d}_wp{waypoint}_{timestamp}",
            "image_path": str(image_path) if image_path else None
        }

        # Save locally
        with open(json_path, "w") as f:
            json.dump(data, f, indent=4)

        logger.info(f"✓ Saved JSON locally: {json_path}")
        
        # Queue for upload
        upload_queue.add_json(json_path)
        
        return json_path

    except Exception as e:
        logger.error(f"⚠ Failed to save JSON for flight {flight_number} WP {waypoint}: {e}")
        return None


def queue_image_upload(image_path):
    """Queue an image for upload"""
    upload_queue.add_image(image_path)


def start_upload_queue():
    """Start the background upload worker"""
    upload_queue.start()


def stop_upload_queue():
    """Stop the background upload worker and print stats"""
    upload_queue.print_stats()
    upload_queue.stop()


def scan_and_queue_unuploaded_files():
    """
    Scan local directories for files that haven't been uploaded yet
    Useful for startup recovery
    """
    logger.info("🔍 Scanning for unuploaded files...")
    
    # Scan JSON files
    json_files = list(config.JSON_DIR.glob("*/flight_*.json"))
    for json_file in json_files:
        if str(json_file) not in upload_queue.uploaded_files:
            upload_queue.add_json(json_file)
    
    # Scan image files
    image_files = list(config.IMAGE_DIR.glob("*/*.jpg"))
    for image_file in image_files:
        if str(image_file) not in upload_queue.uploaded_files:
            upload_queue.add_image(image_file)
    
    stats = upload_queue.get_stats()
    logger.info(f"✓ Found {stats['json_queued']} JSON + {stats['image_queued']} images to upload")


# ============================================================================
# BACKWARD COMPATIBILITY (for existing code)
# ============================================================================

def upload_json_to_server(json_path):
    """Queue JSON for upload (maintains API compatibility)"""
    upload_queue.add_json(json_path)
    return True  # Queued successfully


def upload_image_to_server(image_path):
    """Queue image for upload (maintains API compatibility)"""
    upload_queue.add_image(image_path)
    return True  # Queued successfully


def upload_mission_data(mission_dir):
    """
    Scan mission directory and queue all unuploaded files
    """
    scan_and_queue_unuploaded_files()
    return upload_queue.get_stats()


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Start queue worker
    start_upload_queue()
    
    # Test saving JSON
    test_json = save_json(
        flight_number=1,
        waypoint=5,
        image_path="test_image.jpg",
        class_name="Healthy",
        prediction="0.95"
    )
    
    if test_json:
        print(f"✓ Test JSON created: {test_json}")
    
    # Wait for uploads to complete
    time.sleep(5)
    
    # Print stats
    upload_queue.print_stats()
    
    # Stop worker
    stop_upload_queue()