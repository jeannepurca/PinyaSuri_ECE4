#!/usr/bin/env python3
# uploader.py - Enhanced with comprehensive flight summary JSON

import json
import requests
from datetime import datetime, timezone
from pathlib import Path
import logging
import threading
import time
import queue
import config
import csv
from collections import defaultdict

logger = logging.getLogger(__name__)

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
            'end_time': None
        })
    
    def add_detection_data(self, flight_id, waypoint, image_path, detections):
        """Add detection data for a specific waypoint image"""
        flight = self.flights[flight_id]
        
        # Track start/end times
        current_time = datetime.now()
        if flight['start_time'] is None:
            flight['start_time'] = current_time
        flight['end_time'] = current_time
        
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
        if image_path not in wp_data['images']:
            wp_data['images'].append(str(image_path))
    
    def generate_flight_summary(self, flight_id, total_waypoints):
        """Generate comprehensive flight summary JSON in the new format"""
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
        
        # Build waypoint details
        waypoint_list = []
        for wp_num in sorted(flight['waypoints'].keys()):
            wp_data = flight['waypoints'][wp_num]
            
            # Get waypoint name
            waypoint_name = config.get_waypoint_name(wp_num) if hasattr(config, 'get_waypoint_name') else f"WP{wp_num}"
            
            # Use first image for this waypoint
            image_path = wp_data['images'][0] if wp_data['images'] else ""
            
            waypoint_entry = {
                'waypoint_id': waypoint_name,
                'image': image_path,
                'num_pineapples': wp_data['total_pineapples'],
                'healthy': wp_data['healthy'],
                'afflicted': wp_data['afflicted'],
                'afflictions': dict(wp_data['afflictions'])
            }
            
            waypoint_list.append(waypoint_entry)
        
        # Build complete summary in new format
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
                'avg_confidence': round(avg_confidence * 100, 1)  # Convert to percentage
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
# INDIVIDUAL UPLOAD DATA GENERATOR
# ============================================================================

def generate_upload_entry(image_path, detections, timestamp=None):
    """Generate an individual upload entry in the new format"""
    if timestamp is None:
        timestamp = datetime.now()
    
    # Sort detections by confidence
    sorted_detections = sorted(detections, key=lambda x: x['confidence'], reverse=True)
    
    # Get primary affliction (highest confidence)
    primary_affliction = sorted_detections[0]['class_name'] if sorted_detections else "Unknown"
    primary_confidence = sorted_detections[0]['confidence'] if sorted_detections else 0
    
    # Build afflictions list
    afflictions_list = []
    for det in sorted_detections:
        afflictions_list.append({
            'affliction': det['class_name'],
            'confidence': round(det['confidence'], 3)
        })
    
    # Format timestamp
    timestamp_str = timestamp.strftime("%B %d, %Y %H:%M:%S")
    date_str = timestamp.strftime("%B %d, %Y")
    time_str = timestamp.strftime("%H:%M:%S")
    
    upload_entry = {
        'type': 'upload',
        'date': date_str,
        'time': time_str,
        'image': str(image_path),
        'affliction': primary_affliction,
        'afflictions': afflictions_list,
        'confidence': round(primary_confidence, 3),
        'recommendation': 'Apply appropriate treatment' if primary_affliction.lower() != 'healthy' else 'No treatment needed',
        'timestamp': timestamp_str
    }
    
    return upload_entry


def save_upload_entry(image_path, detections):
    """Save individual upload entry to JSON file"""
    try:
        upload_entry = generate_upload_entry(image_path, detections)
        
        # Create upload directory
        upload_dir = config.JSON_DIR / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename based on timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"upload_{timestamp}.json"
        filepath = upload_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(upload_entry, f, indent=4)
        
        logger.info(f"✓ Upload entry saved: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"⚠ Failed to save upload entry: {e}")
        return None


# ============================================================================
# UPLOAD QUEUE SYSTEM
# ============================================================================

class UploadQueue:
    """Manages upload queue with automatic retry when connection is restored"""
    def __init__(self, max_retries=3, retry_delay=60):
        self.upload_queue = queue.Queue()
        self.failed_uploads = []
        self.max_retries = max_retries
        self.retry_delay = retry_delay
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
        """Retry failed uploads with exponential backoff"""
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

def add_detection_to_flight(flight_id, waypoint, image_path, detections):
    """Add detection data to flight aggregator"""
    flight_aggregator.add_detection_data(flight_id, waypoint, image_path, detections)


def finalize_flight_summary(flight_id, total_waypoints):
    """Generate and save comprehensive flight summary"""
    summary_path = flight_aggregator.save_flight_summary(flight_id, total_waypoints)
    if summary_path:
        upload_queue.add_json(summary_path)
    return summary_path


def save_individual_upload(image_path, detections):
    """Save individual upload entry and queue for upload"""
    upload_path = save_upload_entry(image_path, detections)
    if upload_path:
        upload_queue.add_json(upload_path)
    return upload_path


def get_json_dir_for_today():
    """Create and return JSON directory for today's date"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    json_dir = config.JSON_DIR / date_str
    json_dir.mkdir(parents=True, exist_ok=True)
    return json_dir


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
    """Scan local directories for files that haven't been uploaded yet"""
    logger.info("🔍 Scanning for unuploaded files...")
    
    json_files = list(config.JSON_DIR.glob("**/*.json"))
    for json_file in json_files:
        if str(json_file) not in upload_queue.uploaded_files:
            upload_queue.add_json(json_file)
    
    image_files = list(config.IMAGE_DIR.glob("**/*.jpg"))
    for image_file in image_files:
        if str(image_file) not in upload_queue.uploaded_files:
            upload_queue.add_image(image_file)
    
    stats = upload_queue.get_stats()
    logger.info(f"✓ Found {stats['json_queued']} JSON + {stats['image_queued']} images to upload")


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