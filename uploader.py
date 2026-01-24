#!/usr/bin/env python3
# uploader.py - FIXED: Now uploads images and updates JSON with URLs

import json
import requests
from datetime import datetime, timezone
from pathlib import Path
import logging
import threading
import time
import queue
import config
from collections import defaultdict

logger = logging.getLogger(__name__)

# ============================================================================
# SERVER ENDPOINTS - UPDATE THESE TO MATCH YOUR ACTUAL API
# ============================================================================
FLIGHT_LOG_ENDPOINT = "https://finalfinaledit-pinyasuri-webdev.onrender.com/api/upload-flight-log"
IMAGE_UPLOAD_ENDPOINT = "https://finalfinaledit-pinyasuri-webdev.onrender.com/api/save-upload-result"

# ============================================================================
# FLIGHT DATA AGGREGATOR
# ============================================================================

class FlightDataAggregator:
    """Aggregates detection data to create comprehensive flight summaries"""
    
    def __init__(self):
        self.flights = defaultdict(lambda: {
            'waypoints': {},
            'total_waypoints': 0,
            'captured_waypoints': set(),
            'total_detections': 0,
            'healthy_count': 0,
            'afflicted_count': 0,
            'afflictions': defaultdict(list),
            'start_time': None,
            'end_time': None,
            'images': [],
            'image_url_map': {}
        })
    
    def add_detection_data(self, flight_id, waypoint, image_path, detections):
        """Add detection data for a specific waypoint image"""
        flight = self.flights[flight_id]
        
        # Track start/end times
        current_time = datetime.now()
        if flight['start_time'] is None:
            flight['start_time'] = current_time
        flight['end_time'] = current_time
        
        # Track images for this flight
        if str(image_path) not in flight['images']:
            flight['images'].append(str(image_path))
        
        # Initialize waypoint if first time
        if waypoint not in flight['waypoints']:
            flight['waypoints'][waypoint] = {
                'images': [],
                'total_pineapples': 0,
                'healthy': 0,
                'afflicted': 0,
                'afflictions': defaultdict(int)
            }
            flight['captured_waypoints'].add(waypoint)
        
        wp_data = flight['waypoints'][waypoint]
        
        # Process detections for this image
        for det in detections:
            class_name = det['class_name']
            confidence = det['confidence']
            
            # Update waypoint counts
            wp_data['total_pineapples'] += 1
            flight['total_detections'] += 1
            
            # Classify as healthy or afflicted
            if class_name.lower() == 'healthy' or class_name.lower() == 'pineapple':
                wp_data['healthy'] += 1
                flight['healthy_count'] += 1
            else:
                wp_data['afflicted'] += 1
                flight['afflicted_count'] += 1
                
                # Track affliction counts
                wp_data['afflictions'][class_name] += 1
                flight['afflictions'][class_name].append({
                    'waypoint': waypoint,
                    'confidence': round(confidence, 3)
                })
        
        # Store image path for this waypoint
        if str(image_path) not in wp_data['images']:
            wp_data['images'].append(str(image_path))
    
    def set_image_url(self, flight_id, local_path, server_url):
        """Map local image path to server URL"""
        self.flights[flight_id]['image_url_map'][str(local_path)] = server_url
    
    def get_flight_images(self, flight_id):
        """Get all images associated with a flight"""
        return self.flights[flight_id]['images']
    
    def generate_flight_summary(self, flight_id, total_waypoints):
        """Generate comprehensive flight summary JSON with SERVER image URLs"""
        flight = self.flights[flight_id]
        flight['total_waypoints'] = total_waypoints
        
        # Calculate mission status
        captured_count = len(flight['captured_waypoints'])
        mission_status = "Completed" if captured_count >= total_waypoints else "Incomplete"
        
        # Find most common affliction
        most_common_affliction = None
        max_count = 0
        
        for affliction, instances in flight['afflictions'].items():
            count = len(instances)
            if count > max_count:
                max_count = count
                most_common_affliction = affliction
        
        # Calculate overall average confidence
        all_confidences = []
        for instances in flight['afflictions'].values():
            for inst in instances:
                all_confidences.append(inst['confidence'])
        
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0
        
        # Format times
        date_str = flight['start_time'].strftime("%B %d, %Y") if flight['start_time'] else datetime.now().strftime("%B %d, %Y")
        start_time_str = flight['start_time'].strftime("%H:%M") if flight['start_time'] else "00:00"
        end_time_str = flight['end_time'].strftime("%H:%M") if flight['end_time'] else "00:00"
        
        # Build waypoint details with SERVER URLs
        waypoint_list = []
        for wp_num in sorted(flight['waypoints'].keys()):
            wp_data = flight['waypoints'][wp_num]
            
            # Get waypoint name
            waypoint_name = config.get_waypoint_name(wp_num) if hasattr(config, 'get_waypoint_name') else f"WP{wp_num}"
            
            # Use first image for this waypoint
            local_image_path = wp_data['images'][0] if wp_data['images'] else ""
            
            # ✅ GET SERVER URL instead of local path
            image_url = flight['image_url_map'].get(local_image_path, local_image_path)
            
            waypoint_entry = {
                'waypoint_id': waypoint_name,
                'image': image_url,  # Now contains server URL!
                'num_pineapples': wp_data['total_pineapples'],
                'healthy': wp_data['healthy'],
                'afflicted': wp_data['afflicted'],
                'afflictions': dict(wp_data['afflictions'])
            }
            
            waypoint_list.append(waypoint_entry)
        
        # Build complete summary
        summary = {
            'id': flight_id,
            'type': 'flight',
            'date': date_str,
            'start_time': start_time_str,
            'end_time': end_time_str,
            'summary': {
                'total_waypoints': total_waypoints,
                'captured_waypoints': captured_count,
                'mission_status': mission_status,
                'pineapples_detected': flight['total_detections'],
                'healthy_pineapples': flight['healthy_count'],
                'afflicted_pineapples': flight['afflicted_count'],
                'most_common_affliction': most_common_affliction,
                'avg_confidence': round(avg_confidence * 100, 1)
            },
            'waypoints': waypoint_list
        }
        
        return summary
    
    def save_flight_summary(self, flight_id, total_waypoints):
        """Save flight summary to JSON file"""
        try:
            summary = self.generate_flight_summary(flight_id, total_waypoints)
            
            # Create summary directory
            summary_dir = config.JSON_DIR / "flight_summaries"
            summary_dir.mkdir(parents=True, exist_ok=True)
            
            # Save to file
            filename = f"{flight_id}_summary.json"
            filepath = summary_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(summary, f, indent=4)
            
            logger.info(f"✓ Flight summary saved: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"⚠ Failed to save flight summary: {e}")
            return None


# Global aggregator instance
flight_aggregator = FlightDataAggregator()


# ============================================================================
# UPLOAD QUEUE SYSTEM (POST-FLIGHT ONLY)
# ============================================================================

class UploadQueue:
    """Manages upload queue - uploads images FIRST, then JSON with URLs"""
    def __init__(self, max_retries=3, retry_delay=60):
        self.pending_uploads = []
        self.upload_queue = queue.Queue()
        self.failed_uploads = []
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.worker_thread = None
        self.running = False
        self.uploading_enabled = False
        self.current_flight_id = None
        self.stats = {
            "json_queued": 0,
            "json_uploaded": 0,
            "json_failed": 0,
            "image_queued": 0,
            "image_uploaded": 0,
            "image_failed": 0,
            "pending_count": 0
        }
        
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
            logger.info("✓ Upload queue worker started (uploads paused during flight)")
    
    def stop(self):
        """Stop the background upload worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("⚠ Upload queue worker stopped")
    
    def enable_uploading(self, flight_id):
        """Enable uploading after flight completes"""
        if not self.uploading_enabled:
            self.uploading_enabled = True
            self.current_flight_id = flight_id
            logger.info("=" * 60)
            logger.info("📤 UPLOAD ENABLED - Flight complete, starting uploads...")
            logger.info("=" * 60)
            
            # ✅ CRITICAL: Upload images FIRST, then JSON
            # Separate images and JSON files
            image_uploads = [(t, p) for t, p in self.pending_uploads if t == "image"]
            json_uploads = [(t, p) for t, p in self.pending_uploads if t == "json"]
            
            # Queue images first
            for upload_type, file_path in image_uploads:
                self.upload_queue.put((upload_type, file_path))
            
            # Queue JSON last (after images are uploaded)
            for upload_type, file_path in json_uploads:
                self.upload_queue.put((upload_type, file_path))
            
            logger.info(f"✓ Queued {len(image_uploads)} images + {len(json_uploads)} JSON files")
            self.pending_uploads.clear()
    
    def disable_uploading(self):
        """Disable uploading during flight"""
        self.uploading_enabled = False
        self.current_flight_id = None
        logger.info("⏸️  Upload paused - Flight in progress")
    
    def add_json(self, json_path):
        """Add JSON file (will be held until flight ends)"""
        if str(json_path) not in self.uploaded_files:
            if self.uploading_enabled:
                self.upload_queue.put(("json", json_path))
                self.stats["json_queued"] += 1
            else:
                self.pending_uploads.append(("json", json_path))
                self.stats["pending_count"] += 1
            logger.debug(f"📥 Staged JSON: {Path(json_path).name}")
    
    def add_image(self, image_path):
        """Add image file (will be held until flight ends)"""
        if str(image_path) not in self.uploaded_files:
            if self.uploading_enabled:
                self.upload_queue.put(("image", image_path))
                self.stats["image_queued"] += 1
            else:
                self.pending_uploads.append(("image", image_path))
                self.stats["pending_count"] += 1
            logger.debug(f"📥 Staged image: {Path(image_path).name}")
    
    def _worker(self):
        """Background worker that processes upload queue"""
        logger.info("🔄 Upload worker thread running...")
        
        retry_counter = 0
        
        while self.running:
            try:
                if not self.uploading_enabled:
                    time.sleep(1)
                    continue
                
                try:
                    upload_type, file_path = self.upload_queue.get(timeout=1.0)
                except queue.Empty:
                    if self.failed_uploads and retry_counter >= self.retry_delay:
                        logger.info(f"🔄 Retrying {len(self.failed_uploads)} failed uploads...")
                        self._retry_failed_uploads()
                        retry_counter = 0
                    retry_counter += 1
                    continue
                
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
                
                if success:
                    self.uploaded_files.add(str(file_path))
                    self._save_upload_history()
                else:
                    self.failed_uploads.append((upload_type, file_path, 0))
                
                self.upload_queue.task_done()
                
            except Exception as e:
                logger.error(f"⚠ Upload worker error: {e}")
                time.sleep(1)
    
    def _retry_failed_uploads(self):
        """Retry failed uploads"""
        still_failed = []
        
        for upload_type, file_path, retry_count in self.failed_uploads:
            if retry_count >= self.max_retries:
                logger.warning(f"❌ Max retries reached for {Path(file_path).name}")
                continue
            
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
            
            response = requests.post(
                FLIGHT_LOG_ENDPOINT, 
                json=json_data, 
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            # Accept both 200 and 201
            if response.status_code in [200, 201]:
                logger.info(f"✓ JSON uploaded: {Path(json_path).name}")
                return True
            else:
                logger.warning(f"⚠ Server error {response.status_code}: {Path(json_path).name}")
                logger.warning(f"   Response: {response.text[:200]}")
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
        """Upload image and update flight aggregator with server URL"""
        try:
            image_file = Path(image_path)
            
            if not image_file.exists():
                logger.error(f"⚠ Image file not found: {image_path}")
                return False
            
            # Upload image to server
            with open(image_file, "rb") as f:
                files = {"file": (image_file.name, f, "image/jpeg")}
                response = requests.post(
                    IMAGE_UPLOAD_ENDPOINT, 
                    files=files, 
                    timeout=60
                )
            
            # Accept both 200 and 201
            if response.status_code in [200, 201]:
                try:
                    response_data = response.json()
                    # ✅ CRITICAL: Get image URL from server response
                    image_url = response_data.get('url') or response_data.get('image_url') or response_data.get('path')
                    
                    if image_url and self.current_flight_id:
                        # Update aggregator with server URL
                        flight_aggregator.set_image_url(
                            self.current_flight_id,
                            str(image_path),
                            image_url
                        )
                        logger.info(f"✓ Image uploaded: {image_file.name} -> {image_url}")
                    else:
                        logger.info(f"✓ Image uploaded: {image_file.name}")
                    
                    return True
                except:
                    logger.info(f"✓ Image uploaded: {image_file.name}")
                    return True
            else:
                logger.warning(f"⚠ Server error {response.status_code}: {image_file.name}")
                logger.warning(f"   Response: {response.text[:200]}")
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
            "uploaded_total": len(self.uploaded_files),
            "pending_count": len(self.pending_uploads)
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
        logger.info(f"   Pending (not yet uploaded): {stats['pending_count']}")
        logger.info(f"   Queue size: {stats['queue_size']}")
        logger.info(f"   Failed (retrying): {stats['failed_count']}")
        logger.info(f"   Total uploaded: {stats['uploaded_total']}")
        logger.info("="*60)


# Global upload queue instance
upload_queue = UploadQueue()

# ============================================================================
# PUBLIC API FUNCTIONS
# ============================================================================

def queue_image_upload(image_path):
    """Queue image for immediate upload during flight"""
    upload_queue.add_image(image_path)
    logger.debug(f"📤 Queued for upload: {Path(image_path).name}")

def add_detection_to_flight(flight_id, waypoint, image_path, detections):
    """Add detection data to flight aggregator"""
    flight_aggregator.add_detection_data(flight_id, waypoint, image_path, detections)


def finalize_flight_summary(flight_id, total_waypoints):
    """Generate and save comprehensive flight summary, then upload everything"""
    logger.info("=" * 60)
    logger.info("📦 FINALIZING FLIGHT SUMMARY")
    logger.info("=" * 60)
    
    # Get all images for this flight
    flight_images = flight_aggregator.get_flight_images(flight_id)
    
    logger.info(f"📸 Found {len(flight_images)} images from flight {flight_id}")
    
    # Queue all flight images (BEFORE enabling uploads)
    for image_path in flight_images:
        # Queue both original and detection images
        upload_queue.add_image(image_path)
        
        # Check for corresponding detection image
        detection_path = str(image_path).replace("pinyasuri_", "detection_")
        if Path(detection_path).exists():
            upload_queue.add_image(detection_path)
    
    # Save summary (this will be updated after images are uploaded)
    summary_path = flight_aggregator.save_flight_summary(flight_id, total_waypoints)
    if summary_path:
        upload_queue.add_json(summary_path)
    
    # ✅ NOW ENABLE UPLOADING - images upload first, then JSON
    upload_queue.enable_uploading(flight_id)
    
    # Wait a moment for images to upload before regenerating JSON with URLs
    logger.info("⏳ Waiting for images to upload before finalizing JSON...")
    time.sleep(2)  # Give images time to start uploading
    
    # Regenerate JSON with updated image URLs
    if summary_path:
        flight_aggregator.save_flight_summary(flight_id, total_waypoints)
        logger.info("✓ JSON updated with image URLs")
    
    return summary_path


def start_upload_queue():
    """Start the background upload worker"""
    upload_queue.start()


def stop_upload_queue():
    """Stop the background upload worker and print stats"""
    upload_queue.print_stats()
    upload_queue.stop()


def disable_uploads_during_flight():
    """Disable uploads when flight starts"""
    upload_queue.disable_uploading()


def scan_and_queue_unuploaded_files():
    """Scan local directories for files that haven't been uploaded yet"""
    logger.info("🔍 Scanning for unuploaded files from previous flights...")
    
    json_files = list(config.JSON_DIR.glob("**/*.json"))
    image_files = list(config.IMAGE_DIR.glob("**/*.jpg"))
    
    if upload_queue.uploading_enabled:
        for json_file in json_files:
            if "upload_history" not in str(json_file):
                upload_queue.add_json(json_file)
        
        for image_file in image_files:
            upload_queue.add_image(image_file)
        
        stats = upload_queue.get_stats()
        logger.info(f"✓ Queued {stats['json_queued']} JSON + {stats['image_queued']} images from previous flights")
    else:
        logger.info("⏸️  Files found but uploads paused (will upload after flight)")


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

def upload_json_to_server(json_path):
    """Queue JSON for upload"""
    upload_queue.add_json(json_path)
    return True


def upload_image_to_server(image_path):
    """Queue image for upload"""
    upload_queue.add_image(image_path)
    return True


def upload_mission_data(mission_dir):
    """Scan mission directory and queue all unuploaded files"""
    scan_and_queue_unuploaded_files()
    return upload_queue.get_stats()