import asyncio
import csv
import os
from math import sqrt
from statistics import stdev
import logging
from datetime import datetime

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FlightMetrics")

class FlightMetrics:
    def __init__(self, pixhawk, output_csv=None, window_size=10, log_interval=0.5):
        if output_csv is None:
            import config
            output_csv = str(config.FLIGHT_METRICS_CSV)
        self.pixhawk = pixhawk                  
        self.output_csv = output_csv            
        self.window_size = window_size         
        self.log_interval = log_interval
        self.alt_window = []                    
        self.pos_window = []                    
        self.vib_window = []              

        # Create CSV (if doesn't exist)
        if not os.path.exists(self.output_csv): 
            with open(self.output_csv, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp_utc","lat","lon","abs_alt_m","rel_alt_m",
                    "vib_rms_m_s2","hover_jitter_m","altitude_stability_m",
                    "battery_pct","flight_time_s"
                ])
            logger.info(f"》 Created flight metrics CSV: {self.output_csv}")

        # Queues will be set by main code
        self.pos_queue = None
        self.imu_queue = None
        self.battery_queue = None
        self.armed_queue = None
        
        # State tracking
        self.latest_pos = None
        self.latest_imu = None
        self.latest_batt = None
        self.armed = False
        self.flight_start = None
        self.metrics_count = 0  # DEBUG: Track how many metrics logged
        self.debug_check_count = 0  # DEBUG: Track how many times we checked for data

    async def run(self):
        """Main metrics logging loop"""
        logger.info("》 FlightMetrics logger started")
        
        try:
            while True:
                # Update latest data from queues
                if self.pos_queue:
                    try:
                        while True:
                            self.latest_pos = self.pos_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                
                if self.imu_queue:
                    try:
                        while True:
                            self.latest_imu = self.imu_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                
                if self.battery_queue:
                    try:
                        while True:
                            self.latest_batt = self.battery_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                
                if self.armed_queue:
                    try:
                        while True:
                            armed_status = self.armed_queue.get_nowait()
                            new_armed = armed_status["armed"]
                            
                            # Detect arming (start new flight timer)
                            if new_armed and not self.armed:
                                self.flight_start = datetime.utcnow()
                                logger.info("》 Flight timer started")
                            
                            # Detect disarming (reset timer for next flight)
                            if not new_armed and self.armed:
                                self.flight_start = None
                                logger.info("》 Flight timer reset")
                            
                            self.armed = new_armed
                    except asyncio.QueueEmpty:
                        pass

                # DEBUG: Check data availability every 20 cycles (10 seconds at 0.5s interval)
                self.debug_check_count += 1
                if self.metrics_count == 0 and self.debug_check_count % 20 == 0:
                    logger.info(f"》 DEBUG: Waiting for data - Pos: {self.latest_pos is not None}, "
                              f"IMU: {self.latest_imu is not None}, "
                              f"Battery: {self.latest_batt is not None}, "
                              f"Armed: {self.armed}")
                    if self.latest_pos:
                        logger.info(f"》 DEBUG: Position data available - Lat: {self.latest_pos['lat']:.6f}, "
                                  f"Lon: {self.latest_pos['lon']:.6f}, "
                                  f"Alt: {self.latest_pos['rel_alt']:.1f}m")
                    if self.latest_imu:
                        logger.info(f"》 DEBUG: IMU data available - X: {self.latest_imu['x']:.2f}, "
                                  f"Y: {self.latest_imu['y']:.2f}, "
                                  f"Z: {self.latest_imu['z']:.2f}")

                # Only log metrics if we have position and IMU data
                if self.latest_pos and self.latest_imu:
                    # First successful metrics write
                    if self.metrics_count == 0:
                        logger.info("》 ✓ Started writing flight metrics to CSV")
                    
                    # Metrics: Altitude Stability
                    self.alt_window.append(self.latest_pos["rel_alt"])
                    if len(self.alt_window) > self.window_size:
                        self.alt_window.pop(0)

                    self.pos_window.append((
                        self.latest_pos["lat"], 
                        self.latest_pos["lon"], 
                        self.latest_pos["rel_alt"]
                    ))
                    if len(self.pos_window) > self.window_size:
                        self.pos_window.pop(0)

                    alt_stab = stdev(self.alt_window) if len(self.alt_window) > 1 else 0.0

                    # Metrics: Vibration / IMU Acceleration RMS
                    vib_rms = sqrt(
                        self.latest_imu["x"]**2 + 
                        self.latest_imu["y"]**2 + 
                        self.latest_imu["z"]**2
                    )
                    self.vib_window.append(vib_rms)
                    if len(self.vib_window) > self.window_size:
                        self.vib_window.pop(0)

                    # Metrics: Position Jitter During Hover
                    if len(self.pos_window) > 1:
                        mean_x = sum(p[0] for p in self.pos_window) / len(self.pos_window)
                        mean_y = sum(p[1] for p in self.pos_window) / len(self.pos_window)
                        mean_z = sum(p[2] for p in self.pos_window) / len(self.pos_window)
                        jitter = sqrt(sum(
                            (p[0]-mean_x)**2 + (p[1]-mean_y)**2 + (p[2]-mean_z)**2 
                            for p in self.pos_window
                        ) / len(self.pos_window))
                    else:
                        jitter = 0.0

                    # Metrics: Battery and Flight Time
                    battery_pct = self.latest_batt["percentage"] if self.latest_batt else 0.0
                    flight_time = (datetime.utcnow() - self.flight_start).total_seconds() if self.flight_start else 0.0

                    # Record metrics to CSV
                    try:
                        with open(self.output_csv, "a", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow([
                                datetime.utcnow().isoformat(),
                                self.latest_pos["lat"],
                                self.latest_pos["lon"],
                                self.latest_pos["abs_alt"],
                                self.latest_pos["rel_alt"],
                                vib_rms,
                                jitter,
                                alt_stab,
                                battery_pct,
                                flight_time
                            ])
                        
                        self.metrics_count += 1
                        
                        # Log every 100 metrics to confirm it's working
                        if self.metrics_count % 100 == 0:
                            logger.info(f"》 Logged {self.metrics_count} flight metrics")
                    
                    except Exception as e:
                        logger.error(f"✗ Error writing metrics to CSV: {e}", exc_info=True)
                
                await asyncio.sleep(self.log_interval)
        
        except asyncio.CancelledError:
            logger.info(f"》 FlightMetrics logger stopped (logged {self.metrics_count} total metrics)")
            raise
        except Exception as e:
            logger.error(f"✗ FlightMetrics error: {e}", exc_info=True)