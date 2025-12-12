import math
import logging

logger = logging.getLogger("WaypointDetector")

class WaypointDetector:
    """Detect waypoint arrivals based on GPS distance"""
    
    def __init__(self, waypoints, radius_meters=5.0):
        """
        waypoints: List of tuples [(lat, lon, alt), ...]
        radius_meters: Detection radius in meters
        """
        self.waypoints = waypoints
        self.radius = radius_meters
        self.captured = set()
        logger.info(f"》 WaypointDetector initialized with {len(waypoints)} waypoints, radius={radius_meters}m")
    
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two GPS coordinates in meters"""
        R = 6371000  # Earth radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def check_position(self, current_lat, current_lon):
        """
        Check if current position is near any uncaptured waypoint.
        Returns (waypoint_index, distance) if near one, (None, None) otherwise.
        """
        for idx, (wp_lat, wp_lon, wp_alt) in enumerate(self.waypoints):
            if idx in self.captured:
                continue
            
            distance = self.haversine_distance(current_lat, current_lon, wp_lat, wp_lon)
            
            if distance <= self.radius:
                self.captured.add(idx)
                logger.info(f"》 Waypoint {idx + 1} detected! Distance: {distance:.2f}m")
                return idx, distance
        
        return None, None
    
    def reset(self):
        """Reset captured waypoints (for testing)"""
        self.captured.clear()
        logger.info("》 Waypoint detector reset")