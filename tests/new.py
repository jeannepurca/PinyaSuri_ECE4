

import asyncio
from mavsdk import System
from mavsdk.mission import MissionItem, MissionPlan
import logging
from picamera2 import Picamera2
import your_ai_model  # Your classification code

class PineappleInspector:
    def __init__(self):
        self.drone = System()
        self.camera = Picamera2()
        self.setup_camera()
        self.is_inspecting = False
        
    def setup_camera(self):
        config = self.camera.create_still_configuration()
        self.camera.configure(config)
        self.camera.start()
        
    async def connect_to_drone(self):
        """Connect to the Pixhawk"""
        await self.drone.connect(system_address="serial:///dev/serial0:57600")
        
        logging.info("Waiting for drone to connect...")
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                logging.info("Drone discovered!")
                break

    async def wait_for_mission_start(self):
        """Wait for the mission to be started from Ground Station"""
        logging.info("Waiting for mission to start...")
        async for mission_progress in self.drone.mission.mission_progress():
            if mission_progress.current > 0:  # Mission has started
                logging.info(f"Mission started! At item {mission_progress.current}")
                await self.start_inspection_monitoring()

    async def start_inspection_monitoring(self):
        """Monitor mission progress and trigger inspections"""
        logging.info("Starting inspection monitoring...")
        
        async for mission_progress in self.drone.mission.mission_progress():
            current_waypoint = mission_progress.current
            
            # Check if we're at a waypoint where we should inspect
            if await self.should_inspect_at_waypoint(current_waypoint):
                await self.perform_inspection(current_waypoint)

    async def should_inspect_at_waypoint(self, waypoint_index):
        """Determine if we should take a picture at this waypoint"""
        # Strategy 1: Check if drone is in loiter at this waypoint
        async for flight_mode in self.drone.telemetry.flight_mode():
            if flight_mode == "HOLD":  # Loiter mode
                return True
            return False
        
        # Strategy 2: Use specific waypoint indices from your grid mission
        # inspection_waypoints = [2, 4, 6, 8, 10]  # Your grid points
        # return waypoint_index in inspection_waypoints

    async def perform_inspection(self, waypoint_index):
        """Capture and analyze image at current position"""
        if self.is_inspecting:
            return
            
        self.is_inspecting = True
        logging.info(f"Performing inspection at waypoint {waypoint_index}")
        
        try:
            # 1. Get current position for logging
            position = await self.drone.telemetry.position()
            gps_info = await self.drone.telemetry.gps_info()
            
            # 2. Capture image
            image_path = f"inspections/wp_{waypoint_index}_lat_{position.latitude_deg:.6f}_lon_{position.longitude_deg:.6f}.jpg"
            self.camera.capture_file(image_path)
            logging.info(f"Image captured: {image_path}")
            
            # 3. Run AI classification
            health_status = await self.analyze_image(image_path)
            
            # 4. Log results with GPS coordinates
            await self.log_inspection_result(
                waypoint_index, position, gps_info, health_status, image_path
            )
            
            # 5. Optional: Send status to ground station
            status_text = f"WP{waypoint_index}: Pineapple {health_status}"
            await self.drone.telemetry.set_status_text(status_text)
            
        except Exception as e:
            logging.error(f"Inspection failed: {e}")
        finally:
            self.is_inspecting = False

    async def analyze_image(self, image_path):
        """Run your AI classification on the captured image"""
        # Your existing AI classification code here
        try:
            # Example structure:
            # prediction = your_ai_model.classify(image_path)
            # return "HEALTHY" if prediction == 0 else "DISEASED"
            return "HEALTHY"  # Placeholder
        except Exception as e:
            logging.error(f"AI analysis failed: {e}")
            return "UNKNOWN"

    async def log_inspection_result(self, waypoint, position, gps, status, image_path):
        """Save inspection results with metadata"""
        log_entry = {
            'timestamp': asyncio.get_event_loop().time(),
            'waypoint': waypoint,
            'latitude': position.latitude_deg,
            'longitude': position.longitude_deg,
            'altitude': position.absolute_altitude_m,
            'satellites': gps.num_satellites,
            'health_status': status,
            'image_path': image_path
        }
        
        # Save to CSV, JSON, or database
        with open('inspection_log.json', 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        logging.info(f"Inspection logged: {status} at WP{waypoint}")

    async def run(self):
        """Main execution function"""
        await self.connect_to_drone()
        
        # Start monitoring mission progress
        await self.wait_for_mission_start()

async def main():
    inspector = PineappleInspector()
    await inspector.run()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())