#!/usr/bin/env python3
# uploader.py

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
# SERVER ENDPOINTS
# ============================================================================
FLIGHT_LOG_ENDPOINT = config.FLIGHT_LOG_ENDPOINT
IMAGE_UPLOAD_ENDPOINT = config.IMAGE_UPLOAD_ENDPOINT

logger.info(f"📡 Flight Log Endpoint: {FLIGHT_LOG_ENDPOINT}")
logger.info(f"📡 Image Upload Endpoint: {IMAGE_UPLOAD_ENDPOINT}")

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
            'image_url_map': {},
            'waypoint_images': defaultdict(list),
            'initialized': False  # Track if flight was properly initialized
        })
        self.current_flight_id = None
    
    def start_flight(self, flight_id):
        """Initialize a new flight with proper start time"""
        self.current_flight_id = flight_id
        flight = self.flights[flight_id]
        
        # Set start time immediately
        if flight['start_time'] is None:
            flight['start_time'] = datetime.now()
            flight['initialized'] = True
            logger.info(f"✓ Flight aggregator initialized: {flight_id}")
            logger.info(f"  └─ Start time: {flight['start_time'].strftime('%H:%M:%S')}")
    
    def add_detection_data(self, flight_id, waypoint, image_path, detections):
        """Add detection data for a specific waypoint image"""
        flight = self.flights[flight_id]
        
        # Initialize flight if not already done (safety fallback)
        if not flight['initialized']:
            logger.warning(f"⚠️  Late initialization of flight {flight_id}")
            flight['start_time'] = datetime.now()
            flight['initialized'] = True
        
        # Track current time
        current_time = datetime.now()
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
            logger.debug(f"  ✓ New waypoint tracked: WP{waypoint} for {flight_id}")
        
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
        """Map local image path to server URL and track waypoint relationship"""
        flight = self.flights[flight_id]
        local_path_str = str(local_path)
        
        # Store the URL mapping
        flight['image_url_map'][local_path_str] = server_url
        
        # Find which waypoint this image belongs to and add URL to that waypoint
        for waypoint, wp_data in flight['waypoints'].items():
            if local_path_str in wp_data['images']:
                if server_url not in flight['waypoint_images'][waypoint]:
                    flight['waypoint_images'][waypoint].append(server_url)
                logger.debug(f"✓ Linked image to WP{waypoint}: {server_url}")
                break
    
    def get_flight_images(self, flight_id):
        """Get all images associated with a flight"""
        return self.flights[flight_id]['images']
    
    def get_waypoint_image_urls(self, flight_id, waypoint):
        """Get all uploaded image URLs for a specific waypoint"""
        flight = self.flights[flight_id]
        return flight['waypoint_images'].get(waypoint, [])
    
    def has_flight_data(self, flight_id):
        """Check if we have any data for this flight"""
        flight = self.flights[flight_id]
        return flight['initialized'] and len(flight['images']) > 0
    
    def get_flight_info(self, flight_id):
        """Get diagnostic info about a flight"""
        flight = self.flights[flight_id]
        return {
            'initialized': flight['initialized'],
            'images': len(flight['images']),
            'waypoints': len(flight['waypoints']),
            'captured_waypoints': len(flight['captured_waypoints']),
            'start_time': flight['start_time'].strftime('%H:%M:%S') if flight['start_time'] else 'None',
            'end_time': flight['end_time'].strftime('%H:%M:%S') if flight['end_time'] else 'None'
        }
    
    def print_url_mapping_debug(self, flight_id):
        """Print debug information about URL mappings for this flight"""
        flight = self.flights[flight_id]
        
        logger.info(f"URL Mapping Debug for {flight_id}:")
        logger.info(f"  Total images tracked: {len(flight['images'])}")
        logger.info(f"  Images with URLs: {len(flight['image_url_map'])}")
        logger.info(f"  Waypoints with image URLs: {len(flight['waypoint_images'])}")
        
        # Show URL mapping details
        if flight['image_url_map']:
            logger.info("  Image URL mappings:")
            for local_path, url in flight['image_url_map'].items():
                logger.info(f"    {Path(local_path).name} → {url}")
        else:
            logger.warning("  ⚠️ No image URLs have been mapped yet!")
        
        # Show waypoint image associations
        if flight['waypoint_images']:
            logger.info("  Waypoint image URLs:")
            for waypoint, urls in flight['waypoint_images'].items():
                wp_name = config.get_waypoint_name(waypoint) if hasattr(config, 'get_waypoint_name') else f"WP{waypoint}"
                logger.info(f"    {wp_name}: {len(urls)} images")
                for url in urls:
                    logger.info(f"      - {url}")
        else:
            logger.warning("  ⚠️ No waypoint image URLs have been linked yet!")
    
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
        start_time_str = flight['start_time'].strftime("%H:%M:%S") if flight['start_time'] else "00:00"
        end_time_str = flight['end_time'].strftime("%H:%M:%S") if flight['end_time'] else "00:00"
        
        # Build waypoint details with SERVER URLs
        waypoint_list = []
        for wp_num in sorted(flight['waypoints'].keys()):
            wp_data = flight['waypoints'][wp_num]
            
            # Get waypoint name
            waypoint_name = config.get_waypoint_name(wp_num) if hasattr(config, 'get_waypoint_name') else f"WP{wp_num}"
            
            # GET ALL SERVER URLs FOR THIS WAYPOINT
            waypoint_image_urls = self.get_waypoint_image_urls(flight_id, wp_num)
            
            # Use first image URL for primary display, include all URLs
            primary_image_url = waypoint_image_urls[0] if waypoint_image_urls else ""
            
            waypoint_entry = {
                'waypoint_id': waypoint_name,
                'image': primary_image_url,
                'images': waypoint_image_urls,
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
            'waypoints': waypoint_list,
            'image_metadata': {
                'total_images': len(flight['image_url_map']),
                'images_per_waypoint': {
                    config.get_waypoint_name(wp): len(urls) 
                    for wp, urls in flight['waypoint_images'].items()
                }
            }
        }
        
        return summary
    
    def save_flight_summary(self, flight_id, total_waypoints):
        """Save flight summary to JSON file"""
        try:
            # Check if we have any data for this flight
            if not self.has_flight_data(flight_id):
                logger.warning(f"⚠️  No flight data found for {flight_id}")
                logger.warning(f"   Available flights:")
                for fid in self.flights.keys():
                    info = self.get_flight_info(fid)
                    logger.warning(f"     - {fid}: {info}")
                return None
            
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
            logger.info(f"  └─ {summary['summary']['captured_waypoints']} waypoints captured")
            logger.info(f"  └─ {summary['image_metadata']['total_images']} images linked")
            logger.info(f"  └─ Time: {summary['start_time']} - {summary['end_time']}")
            
            return filepath
            
        except Exception as e:
            logger.error(f"⚠ Failed to save flight summary: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
            logger.info(f"   Flight ID: {flight_id}")
            logger.info("=" * 60)
            
            # CRITICAL: Upload images FIRST, then JSON
            image_uploads = [(t, p) for t, p in self.pending_uploads if t == "image"]
            json_uploads = [(t, p) for t, p in self.pending_uploads if t == "json"]
            
            # Queue images first
            for upload_type, file_path in image_uploads:
                self.upload_queue.put((upload_type, file_path))
            
            # Queue JSON last
            for upload_type, file_path in json_uploads:
                self.upload_queue.put((upload_type, file_path))
            
            logger.info(f"✓ Queued {len(image_uploads)} images + {len(json_uploads)} JSON files")
            self.pending_uploads.clear()
    
    def disable_uploading(self):
        """Disable uploading during flight"""
        self.uploading_enabled = False
        logger.info("⏸️  Upload paused - Flight in progress")
    
    def add_json(self, json_path):
        """Add JSON file"""
        if str(json_path) not in self.uploaded_files:
            if self.uploading_enabled:
                self.upload_queue.put(("json", json_path))
                self.stats["json_queued"] += 1
            else:
                self.pending_uploads.append(("json", json_path))
                self.stats["pending_count"] += 1
            logger.debug(f"📥 Staged JSON: {Path(json_path).name}")
    
    def add_image(self, image_path):
        """Add image file"""
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
        """Internal JSON upload - USES FLIGHT_LOG_ENDPOINT"""
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
        """Upload image - USES IMAGE_UPLOAD_ENDPOINT and captures server URL"""
        try:
            image_file = Path(image_path)
            
            if not image_file.exists():
                logger.error(f"⚠ Image file not found: {image_path}")
                return False
            
            with open(image_file, "rb") as f:
                files = {"file": (image_file.name, f, "image/jpeg")}
                response = requests.post(
                    IMAGE_UPLOAD_ENDPOINT, 
                    files=files, 
                    timeout=60
                )
            
            if response.status_code in [200, 201]:
                try:
                    response_data = response.json()
                    
                    # Try multiple common response fields for the image URL
                    image_url = (
                        response_data.get('url') or 
                        response_data.get('image_url') or 
                        response_data.get('path') or 
                        response_data.get('file_url') or
                        response_data.get('link') or
                        response_data.get('src')
                    )
                    
                    if image_url:
                        # CRITICAL: Link image URL to flight data
                        if self.current_flight_id:
                            flight_aggregator.set_image_url(
                                self.current_flight_id,
                                str(image_path),
                                image_url
                            )
                            logger.info(f"✓ Image uploaded & linked: {image_file.name}")
                            logger.info(f"  └─ Server URL: {image_url}")
                        else:
                            logger.warning(f"✓ Image uploaded but no flight_id to link: {image_file.name}")
                            logger.warning(f"  └─ URL: {image_url}")
                        
                        return True
                    else:
                        # No URL in response - log the entire response for debugging
                        logger.warning(f"⚠ Image uploaded but no URL in response: {image_file.name}")
                        logger.warning(f"  └─ Response data: {response_data}")
                        return True  # Still count as success
                        
                except json.JSONDecodeError:
                    # Response wasn't JSON - maybe it's just a text URL?
                    response_text = response.text.strip()
                    if response_text.startswith('http'):
                        if self.current_flight_id:
                            flight_aggregator.set_image_url(
                                self.current_flight_id,
                                str(image_path),
                                response_text
                            )
                            logger.info(f"✓ Image uploaded & linked: {image_file.name}")
                            logger.info(f"  └─ Server URL: {response_text}")
                        return True
                    else:
                        logger.warning(f"✓ Image uploaded (non-JSON response): {image_file.name}")
                        logger.warning(f"  └─ Response: {response_text[:200]}")
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
            import traceback
            logger.error(traceback.format_exc())
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
        logger.info(f"   Pending: {stats['pending_count']}")
        logger.info(f"   Queue size: {stats['queue_size']}")
        logger.info(f"   Failed: {stats['failed_count']}")
        logger.info(f"   Total uploaded: {stats['uploaded_total']}")
        logger.info("="*60)


# Global upload queue instance
upload_queue = UploadQueue()

# ============================================================================
# PUBLIC API FUNCTIONS
# ============================================================================

def start_new_flight(flight_id):
    """Start tracking a new flight in the aggregator"""
    flight_aggregator.start_flight(flight_id)

def queue_image_upload(image_path):
    """Queue image for upload"""
    upload_queue.add_image(image_path)
    logger.debug(f"📤 Queued for upload: {Path(image_path).name}")

def add_detection_to_flight(flight_id, waypoint, image_path, detections):
    """Add detection data to flight aggregator"""
    flight_aggregator.add_detection_data(flight_id, waypoint, image_path, detections)


def finalize_flight_summary(flight_id, total_waypoints):
    """Generate and save comprehensive flight summary, then upload everything
    
    Process:
    1. Queue all images for upload
    2. Enable uploading (images upload first)
    3. Wait for images to upload and URLs to be captured
    4. Generate JSON with collected image URLs
    5. Upload JSON last
    """
    logger.info("=" * 60)
    logger.info("📦 FINALIZING FLIGHT SUMMARY")
    logger.info(f"   Flight ID: {flight_id}")
    logger.info("=" * 60)
    
    # Check if we have any data for this flight
    if not flight_aggregator.has_flight_data(flight_id):
        logger.error(f"❌ No flight data found for {flight_id}")
        
        # Show diagnostic info
        logger.info("   Flight info:")
        info = flight_aggregator.get_flight_info(flight_id)
        for key, value in info.items():
            logger.info(f"     {key}: {value}")
        
        logger.info("   Available flights:")
        for fid in flight_aggregator.flights.keys():
            finfo = flight_aggregator.get_flight_info(fid)
            logger.info(f"     - {fid}: {finfo}")
        
        # Try to find the most recent flight with data
        for fid in sorted(flight_aggregator.flights.keys(), reverse=True):
            if flight_aggregator.has_flight_data(fid):
                logger.info(f"   ✓ Using {fid} instead")
                flight_id = fid
                break
        else:
            logger.error("   ❌ No valid flight data found!")
            return None
    
    # Get all images for this flight
    flight_images = flight_aggregator.get_flight_images(flight_id)
    
    logger.info(f"📸 Found {len(flight_images)} images from flight {flight_id}")
    
    # STEP 1: Queue all flight images for upload
    logger.info("=" * 60)
    logger.info("📤 STEP 1: Queuing images for upload...")
    logger.info("=" * 60)
    
    image_count = 0
    for image_path in flight_images:
        upload_queue.add_image(image_path)
        image_count += 1
        
        # Check for detection image
        detection_path = str(image_path).replace("pinyasuri_", "detection_")
        if Path(detection_path).exists():
            upload_queue.add_image(detection_path)
            image_count += 1
    
    logger.info(f"✓ Queued {image_count} images")
    
    # STEP 2: Enable uploading (this will start uploading images)
    logger.info("=" * 60)
    logger.info("📤 STEP 2: Starting image uploads...")
    logger.info("=" * 60)
    
    upload_queue.enable_uploading(flight_id)
    
    # STEP 3: Wait for images to upload and URLs to be captured
    logger.info("=" * 60)
    logger.info("⏳ STEP 3: Waiting for images to upload and URLs to be captured...")
    logger.info("=" * 60)
    
    # Wait with progress updates
    max_wait_time = 120  # 2 minutes max
    wait_interval = 5  # Check every 5 seconds
    waited = 0
    last_uploaded_count = 0
    
    while waited < max_wait_time:
        # Check upload queue status
        stats = upload_queue.get_stats()
        queue_size = stats['queue_size']
        images_uploaded = stats['image_uploaded']
        
        # Show progress if changed
        if images_uploaded != last_uploaded_count:
            logger.info(f"⏳ Progress: {images_uploaded}/{image_count} uploaded, {queue_size} in queue...")
            last_uploaded_count = images_uploaded
        
        # If queue is empty or nearly empty, we're done
        if queue_size <= 1:  # Allow 1 item in queue (might be processing)
            logger.info("✓ All images uploaded!")
            time.sleep(2)  # Give a bit more time for final URL captures
            break
        
        time.sleep(wait_interval)
        waited += wait_interval
    
    if waited >= max_wait_time:
        logger.warning(f"⚠ Timeout waiting for uploads (waited {max_wait_time}s)")
        logger.warning("  Proceeding with available data...")
    
    # STEP 4: Debug - Check URL mapping
    logger.info("=" * 60)
    logger.info("🔍 STEP 4: Checking URL mapping...")
    logger.info("=" * 60)
    
    flight_aggregator.print_url_mapping_debug(flight_id)
    
    # STEP 5: Generate JSON with collected image URLs
    logger.info("=" * 60)
    logger.info("📝 STEP 5: Generating flight summary JSON with image URLs...")
    logger.info("=" * 60)
    
    summary_path = flight_aggregator.save_flight_summary(flight_id, total_waypoints)
    
    if summary_path:
        logger.info(f"✓ Flight summary created: {summary_path}")
        
        # Verify URLs were included
        with open(summary_path, 'r') as f:
            summary_data = json.load(f)
        
        total_urls = 0
        waypoints_with_urls = 0
        for waypoint_data in summary_data.get('waypoints', []):
            urls = waypoint_data.get('images', [])
            if urls:
                waypoints_with_urls += 1
                total_urls += len(urls)
        
        logger.info(f"  └─ {waypoints_with_urls} waypoints with image URLs")
        logger.info(f"  └─ {total_urls} total image URLs included")
        
        if total_urls == 0:
            logger.warning("  ⚠ WARNING: No image URLs were captured!")
            logger.warning("  Check your server's image upload response format")
        
        # STEP 6: Queue JSON for upload
        logger.info("=" * 60)
        logger.info("📤 STEP 6: Queuing JSON for upload...")
        logger.info("=" * 60)
        
        upload_queue.add_json(summary_path)
        logger.info("✓ Flight summary queued for upload")
    
    logger.info("=" * 60)
    logger.info("✅ FLIGHT FINALIZATION COMPLETE")
    logger.info("=" * 60)
    
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
    """Scan local directories for unuploaded files"""
    logger.info("🔍 Scanning for unuploaded files...")
    
    json_files = list(config.JSON_DIR.glob("**/*.json"))
    image_files = list(config.IMAGE_DIR.glob("**/*.jpg"))
    
    if upload_queue.uploading_enabled:
        for json_file in json_files:
            if "upload_history" not in str(json_file):
                upload_queue.add_json(json_file)
        
        for image_file in image_files:
            upload_queue.add_image(image_file)
        
        stats = upload_queue.get_stats()
        logger.info(f"✓ Queued {stats['json_queued']} JSON + {stats['image_queued']} images")
    else:
        logger.info("⏸️  Files found but uploads paused")


# Backward compatibility
def upload_json_to_server(json_path):
    upload_queue.add_json(json_path)
    return True

def upload_image_to_server(image_path):
    upload_queue.add_image(image_path)
    return True

def upload_mission_data(mission_dir):
    scan_and_queue_unuploaded_files()
    return upload_queue.get_stats()