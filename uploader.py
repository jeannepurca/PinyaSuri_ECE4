#!/usr/bin/env python3
# uploader.py

import json
import requests
from datetime import datetime, timezone
from pathlib import Path
import logging
import time
import config
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


# ============================================================================
# SERVER ENDPOINTS
# ============================================================================
FLIGHT_LOG_ENDPOINT = config.FLIGHT_LOG_ENDPOINT
IMAGE_UPLOAD_ENDPOINT = config.IMAGE_UPLOAD_ENDPOINT

logger.info(f"📡 Flight Log Endpoint: {FLIGHT_LOG_ENDPOINT}")
logger.info(f"📡 Image Upload Endpoint: {IMAGE_UPLOAD_ENDPOINT}")


# ============================================================================
# CONNECTION SETTINGS
# ============================================================================
REQUEST_TIMEOUT = 30  # seconds

def test_server_connection():
    """Test if server is reachable before starting uploads"""
    try:
        base_url = config.SERVER_BASE
        response = requests.get(base_url, timeout=5)
        logger.info(f"✓ Server connection successful: {base_url}")
        return True
    except requests.exceptions.ConnectionError:
        logger.warning(f"⚠ Cannot connect to server: {config.SERVER_BASE}")
        logger.warning("  Make sure:")
        logger.warning("  1. Server is running")
        logger.warning("  2. IP address is correct")
        logger.warning("  3. Both devices are on same network")
        return False
    except Exception as e:
        logger.warning(f"⚠ Server connection test failed: {e}")
        return False


# ============================================================================
# UPLOAD HISTORY TRACKING
# ============================================================================
class UploadHistory:
    """Track successfully uploaded files to avoid duplicates"""
    
    def __init__(self):
        self.uploaded_files = set()
        self.history_file = config.JSON_DIR / "upload_history.json"
        self._load_history()
    
    def _load_history(self):
        """Load history of successfully uploaded files"""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r") as f:
                    data = json.load(f)
                    self.uploaded_files = set(data.get("uploaded", []))
                logger.info(f"✓ Loaded upload history: {len(self.uploaded_files)} files")
            except Exception as e:
                logger.warning(f"⚠ Could not load upload history: {e}")
    
    def _save_history(self):
        """Save history of successfully uploaded files"""
        try:
            config.ensure_directories()
            with open(self.history_file, "w") as f:
                json.dump({
                    "uploaded": list(self.uploaded_files),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"⚠ Could not save upload history: {e}")
    
    def is_uploaded(self, file_path):
        """Check if file was already uploaded"""
        return str(file_path) in self.uploaded_files
    
    def mark_uploaded(self, file_path):
        """Mark file as uploaded"""
        self.uploaded_files.add(str(file_path))
        self._save_history()


# Global upload history instance
upload_history = UploadHistory()


# ============================================================================
# DIRECT UPLOAD FUNCTIONS (from test_uploader.py)
# ============================================================================
def upload_json_directly(json_file):
    """Upload JSON directly to server"""
    logger.info(f"📤 Uploading JSON: {json_file.name}")
    
    try:
        with open(json_file, 'r') as f:
            json_data = json.load(f)
        
        logger.info(f"   Flight ID: {json_data.get('id')}")
        logger.info(f"   Waypoints: {len(json_data.get('waypoints', []))}")
        
        response = requests.post(
            FLIGHT_LOG_ENDPOINT,
            json=json_data,
            timeout=REQUEST_TIMEOUT,
            headers={"Content-Type": "application/json"}
        )
        
        logger.info(f"   Response Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            logger.info("   ✅ JSON uploaded successfully!")
            upload_history.mark_uploaded(json_file)
            return True
        elif response.status_code == 409:
            logger.info("   ℹ️  Flight already exists (409 - this is OK)")
            upload_history.mark_uploaded(json_file)
            return True
        else:
            logger.error(f"   ❌ Upload failed: {response.status_code}")
            logger.error(f"   Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        logger.error(f"   ❌ Connection error: {e}")
        return False
    except requests.exceptions.Timeout:
        logger.error(f"   ❌ Timeout error")
        return False
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def upload_image_directly(image_file, flight_id, waypoint):
    """Upload image directly to server"""
    logger.info(f"📤 Uploading image: {image_file.name}")
    logger.info(f"   Flight ID: {flight_id}")
    logger.info(f"   Waypoint: {waypoint}")
    
    try:
        with open(image_file, 'rb') as f:
            files = {"image": (image_file.name, f, "image/jpeg")}
            data = {
                "flight_id": flight_id,
                "waypoint": waypoint
            }
            
            response = requests.post(
                IMAGE_UPLOAD_ENDPOINT,
                files=files,
                data=data,
                timeout=REQUEST_TIMEOUT
            )
        
        logger.info(f"   Response Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            logger.info("   ✅ Image uploaded successfully!")
            
            # Try to get image URL from response
            try:
                response_data = response.json()
                image_url = (
                    response_data.get('url') or 
                    response_data.get('image_url') or 
                    response_data.get('path') or 
                    response_data.get('file_url') or
                    response_data.get('link')
                )
                if image_url:
                    logger.info(f"   📎 Image URL: {image_url}")
                    upload_history.mark_uploaded(image_file)
                    return image_url
            except:
                pass
            
            upload_history.mark_uploaded(image_file)
            return True
        else:
            logger.error(f"   ❌ Upload failed: {response.status_code}")
            logger.error(f"   Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        logger.error(f"   ❌ Connection error: {e}")
        return False
    except requests.exceptions.Timeout:
        logger.error(f"   ❌ Timeout error")
        return False
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


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
            'initialized': False
        })
        self.current_flight_id = None
    
    def start_flight(self, flight_id):
        """Initialize a new flight with proper start time"""
        self.current_flight_id = flight_id
        flight = self.flights[flight_id]
        
        if flight['start_time'] is None:
            flight['start_time'] = datetime.now()
            flight['initialized'] = True
            logger.info(f"✓ Flight aggregator initialized: {flight_id}")
            logger.info(f"  └─ Start time: {flight['start_time'].strftime('%H:%M:%S')}")
    
    def add_detection_data(self, flight_id, waypoint, image_path, detections):
        """Add detection data for a specific waypoint image"""
        flight = self.flights[flight_id]
        
        if not flight['initialized']:
            logger.warning(f"⚠️  Late initialization of flight {flight_id}")
            flight['start_time'] = datetime.now()
            flight['initialized'] = True
        
        current_time = datetime.now()
        flight['end_time'] = current_time
        
        if str(image_path) not in flight['images']:
            flight['images'].append(str(image_path))
        
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
        
        for det in detections:
            class_name = det['class_name']
            confidence = det['confidence']
            
            wp_data['total_pineapples'] += 1
            flight['total_detections'] += 1
            
            if class_name.lower() == 'healthy' or class_name.lower() == 'pineapple':
                wp_data['healthy'] += 1
                flight['healthy_count'] += 1
            else:
                wp_data['afflicted'] += 1
                flight['afflicted_count'] += 1
                
                wp_data['afflictions'][class_name] += 1
                flight['afflictions'][class_name].append({
                    'waypoint': waypoint,
                    'confidence': round(confidence, 3)
                })
        
        if str(image_path) not in wp_data['images']:
            wp_data['images'].append(str(image_path))
    
    def set_image_url(self, flight_id, local_path, server_url):
        """Map local image path to server URL and track waypoint relationship"""
        flight = self.flights[flight_id]
        local_path_str = str(local_path)
        
        flight['image_url_map'][local_path_str] = server_url
        
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
    
    def generate_flight_summary(self, flight_id, total_waypoints):
        """Generate comprehensive flight summary JSON with SERVER image URLs"""
        flight = self.flights[flight_id]
        flight['total_waypoints'] = total_waypoints
        
        captured_count = len(flight['captured_waypoints'])
        mission_status = "Completed" if captured_count >= total_waypoints else "Incomplete"
        
        most_common_affliction = None
        max_count = 0
        
        for affliction, instances in flight['afflictions'].items():
            count = len(instances)
            if count > max_count:
                max_count = count
                most_common_affliction = affliction
        
        all_confidences = []
        for instances in flight['afflictions'].values():
            for inst in instances:
                all_confidences.append(inst['confidence'])
        
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0
        
        date_str = flight['start_time'].strftime("%B %d, %Y") if flight['start_time'] else datetime.now().strftime("%B %d, %Y")
        start_time_str = flight['start_time'].strftime("%H:%M:%S") if flight['start_time'] else "00:00"
        end_time_str = flight['end_time'].strftime("%H:%M:%S") if flight['end_time'] else "00:00"
        
        waypoint_list = []
        for wp_num in sorted(flight['waypoints'].keys()):
            wp_data = flight['waypoints'][wp_num]
            
            waypoint_name = config.get_waypoint_name(wp_num) if hasattr(config, 'get_waypoint_name') else f"WP{wp_num}"
            
            waypoint_image_urls = self.get_waypoint_image_urls(flight_id, wp_num)
            
            primary_image_url = waypoint_image_urls[0] if waypoint_image_urls else ""
            
            waypoint_entry = {
                'waypoint_id': waypoint_name,
                'name': waypoint_name,
                'image': primary_image_url,
                'images': waypoint_image_urls,
                'num_pineapples': wp_data['total_pineapples'],
                'total': wp_data['total_pineapples'],
                'healthy': wp_data['healthy'],
                'afflicted': wp_data['afflicted'],
                'afflictions': dict(wp_data['afflictions'])
            }
            
            waypoint_list.append(waypoint_entry)
        
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
            if not self.has_flight_data(flight_id):
                logger.warning(f"⚠️  No flight data found for {flight_id}")
                return None
            
            summary = self.generate_flight_summary(flight_id, total_waypoints)
            
            summary_dir = config.JSON_DIR
            summary_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{flight_id}_summary.json"
            filepath = summary_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(summary, f, indent=4)
            
            logger.info(f"✓ Flight summary saved: {filepath}")
            logger.info(f"  └─ {summary['summary']['captured_waypoints']} waypoints captured")
            logger.info(f"  └─ {summary['image_metadata']['total_images']} images linked")
            
            return filepath
            
        except Exception as e:
            logger.error(f"⚠ Failed to save flight summary: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


# Global aggregator instance
flight_aggregator = FlightDataAggregator()


# ============================================================================
# UPLOAD STATE MANAGEMENT
# ============================================================================
class UploadManager:
    """Manages upload state - pause during flight, resume after"""
    
    def __init__(self):
        self.uploading_enabled = True
        self.current_flight_id = None
    
    def pause_uploads(self, flight_id):
        """Pause uploads when flight starts"""
        self.uploading_enabled = False
        self.current_flight_id = flight_id
        logger.info("=" * 60)
        logger.info("⏸️  UPLOADS PAUSED - Flight in progress")
        logger.info(f"   Flight ID: {flight_id}")
        logger.info("=" * 60)
    
    def resume_uploads(self):
        """Resume uploads when flight completes"""
        self.uploading_enabled = True
        logger.info("=" * 60)
        logger.info("▶️  UPLOADS RESUMED - Flight complete")
        logger.info("=" * 60)
    
    def can_upload(self):
        """Check if uploading is currently allowed"""
        return self.uploading_enabled


# Global upload manager
upload_manager = UploadManager()


# ============================================================================
# PUBLIC API FUNCTIONS
# ============================================================================
def start_new_flight(flight_id):
    """Start tracking a new flight in the aggregator"""
    flight_aggregator.start_flight(flight_id)
    upload_manager.pause_uploads(flight_id)


def add_detection_to_flight(flight_id, waypoint, image_path, detections):
    """Add detection data to flight aggregator"""
    flight_aggregator.add_detection_data(flight_id, waypoint, image_path, detections)


def finalize_flight_summary(flight_id, total_waypoints):
    """Generate and save comprehensive flight summary, then upload everything"""
    logger.info("=" * 60)
    logger.info(">>> FINALIZING FLIGHT SUMMARY")
    logger.info(f"   Flight ID: {flight_id}")
    logger.info("=" * 60)
    
    # Check if we have flight data
    if not flight_aggregator.has_flight_data(flight_id):
        logger.error(f"❌ No flight data found for {flight_id}")
        return None
    
    # Resume uploads after flight completes
    upload_manager.resume_uploads()
    
    # Test server connection
    if not test_server_connection():
        logger.error("❌ Server not reachable! Uploads will be retried later.")
        # Still save the summary locally
        summary_path = flight_aggregator.save_flight_summary(flight_id, total_waypoints)
        return summary_path
    
    # STEP 1: Generate flight summary (with placeholder image URLs)
    logger.info("=" * 60)
    logger.info("STEP 1: Generate Flight Summary")
    logger.info("=" * 60)
    
    summary_path = flight_aggregator.save_flight_summary(flight_id, total_waypoints)
    
    if not summary_path:
        logger.error("❌ Failed to generate flight summary")
        return None
    
    # STEP 2: Upload flight summary JSON FIRST (creates flight record on server)
    logger.info("=" * 60)
    logger.info("STEP 2: Upload Flight Summary JSON")
    logger.info("=" * 60)
    
    if upload_history.is_uploaded(summary_path):
        logger.info(f"⏭️  Already uploaded: {summary_path.name}")
    else:
        if upload_json_directly(summary_path):
            logger.info("✅ Flight summary uploaded successfully!")
        else:
            logger.error("❌ Failed to upload flight summary")
            logger.info("   Cannot upload images without flight record")
            return summary_path
    
    # Wait for server to process
    logger.info("\n⏳ Waiting 2 seconds for server to process...")
    time.sleep(2)
    
    # Get all flight images
    flight_images = flight_aggregator.get_flight_images(flight_id)
    logger.info(f"📸 Found {len(flight_images)} images from flight")
    
    # STEP 3: Upload all images (NOW flight exists on server)
    logger.info("=" * 60)
    logger.info("STEP 3: Upload Images")
    logger.info("=" * 60)
    
    uploaded_count = 0
    skipped_count = 0
    failed_count = 0
    
    # Get flight data to access waypoint mappings
    flight = flight_aggregator.flights[flight_id]

    for image_path in flight_images:
        image_file = Path(image_path)
        
        if not image_file.exists():
            logger.warning(f"⚠️  Image not found: {image_file}")
            failed_count += 1
            continue
        
        # Skip if already uploaded
        if upload_history.is_uploaded(image_file):
            logger.info(f"⏭️  Already uploaded: {image_file.name}")
            skipped_count += 1
            continue
        
        # Find which waypoint this image belongs to (from tracked data)
        waypoint = None
        waypoint_num = None
        image_path_str = str(image_path)
        
        for wp_num, wp_data in flight['waypoints'].items():
            if image_path_str in wp_data['images']:
                waypoint_num = wp_num
                waypoint = config.get_waypoint_name(wp_num)
                logger.debug(f"   Found in tracked data: WP{wp_num}")
                break
        
        # Fallback to filename parsing if not found in tracked data
        if not waypoint:
            logger.warning(f"⚠️  Not in tracked data, parsing filename: {image_file.name}")
            waypoint_match = re.search(r'_wp(\d+)_', image_file.name)
            if waypoint_match:
                waypoint_num = int(waypoint_match.group(1))
                waypoint = config.get_waypoint_name(waypoint_num)
            else:
                waypoint = "UNKNOWN"
        
        logger.info(f"📤 Uploading to waypoint: {waypoint}")
        
        # Upload image
        result = upload_image_directly(image_file, flight_id, waypoint)
        
        if result:
            uploaded_count += 1
            
            # If we got a URL back, link it
            if isinstance(result, str) and result.startswith('http'):
                flight_aggregator.set_image_url(flight_id, str(image_path), result)
            
            time.sleep(0.5)  # Small delay between uploads
        else:
            logger.warning(f"⚠️  Failed to upload: {image_file.name}")
            failed_count += 1
    
    logger.info(f"✅ Image Upload Summary:")
    logger.info(f"   • Uploaded: {uploaded_count}")
    logger.info(f"   • Skipped (already uploaded): {skipped_count}")
    logger.info(f"   • Failed: {failed_count}")
    logger.info(f"   • Total: {len(flight_images)}")

    # STEP 4: Re-generate and re-upload JSON with actual image URLs
    if uploaded_count > 0:
        logger.info("=" * 60)
        logger.info("STEP 4: Update Flight Summary with Image URLs")
        logger.info("=" * 60)
        
        # Re-generate summary with image URLs that were collected during upload
        updated_summary_path = flight_aggregator.save_flight_summary(flight_id, total_waypoints)
        
        if updated_summary_path:
            logger.info("📤 Re-uploading updated flight summary with image URLs...")
            
            # Force re-upload even if marked as uploaded
            # Remove from history first to allow re-upload
            if str(updated_summary_path) in upload_history.uploaded_files:
                upload_history.uploaded_files.remove(str(updated_summary_path))
            
            if upload_json_directly(updated_summary_path):
                logger.info("✅ Flight summary updated with image URLs!")
            else:
                logger.warning("⚠️  Failed to update flight summary with image URLs")
        else:
            logger.error("❌ Failed to re-generate flight summary")
    else:
        logger.warning("⚠️  No images uploaded, skipping summary update")
    
    logger.info("=" * 60)
    logger.info("✓ FLIGHT FINALIZATION COMPLETE")
    logger.info("   Ready for next flight")
    logger.info("=" * 60)

    return summary_path


# ============================================================================
# COMPATIBILITY FUNCTIONS (for existing code)
# ============================================================================
def start_upload_queue():
    """Compatibility function - test server connection"""
    logger.info("🔍 Testing server connection...")
    test_server_connection()
    logger.info("✓ Upload system ready")


def stop_upload_queue():
    """Compatibility function - no queue to stop"""
    logger.info("✓ Upload operations complete")


def disable_uploads_during_flight():
    """Disable uploads during active flight"""
    if upload_manager.current_flight_id:
        upload_manager.pause_uploads(upload_manager.current_flight_id)
    else:
        logger.info("⏸️  Uploads paused")


def enable_uploading(flight_id):
    """Enable uploading after flight completes"""
    upload_manager.current_flight_id = flight_id
    upload_manager.resume_uploads()


def queue_image_upload(image_path):
    """Compatibility function - direct upload instead of queue"""
    # This will be called during flight, but we'll upload at the end
    pass


# Backward compatibility
def upload_json_to_server(json_path):
    """Legacy function - direct upload"""
    if not upload_manager.can_upload():
        logger.warning("⚠️  Upload paused during flight")
        return False
    return upload_json_directly(json_path)


def upload_image_to_server(image_path):
    """Legacy function - needs flight_id and waypoint"""
    logger.warning("⚠️  upload_image_to_server called without flight context")
    return False