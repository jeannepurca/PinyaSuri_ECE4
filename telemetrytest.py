#!/usr/bin/env python3
# telemetry_test.py
"""
Telemetry test script - monitors drone status without image capture
Use this to verify GPS, battery, IMU, and flight modes before running missions
Focus: Tests MISSION_CURRENT waypoint detection logic
"""

import time
import signal
import sys
import logging
from datetime import datetime

import config
from pixhawk import Pixhawk

# Global flag for graceful shutdown
running = True

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global running
    print("\n⚠ Shutdown requested...")
    running = False

def setup_logging():
    """Configure logging system"""
    config.ensure_directories()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.LOG_DIR / "telemetry_test.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("TelemetryTest")

def print_header():
    """Print test header"""
    print("\n" + "="*70)
    print("  DRONE TELEMETRY TEST - MISSION_CURRENT BASED")
    print("="*70)
    print("\nPress Ctrl+C to stop monitoring")
    print("="*70 + "\n")

def format_position(position):
    """Format position data for display"""
    if not position:
        return "NO GPS FIX"
    return f"Lat: {position['lat']:.6f}°, Lon: {position['lon']:.6f}°, Alt: {position['rel_alt']:.2f}m"

def format_imu(imu_accel):
    """Format IMU data for display"""
    return f"X: {imu_accel['x']:6.2f} Y: {imu_accel['y']:6.2f} Z: {imu_accel['z']:6.2f} m/s²"

def format_battery(battery_remaining, battery_type):
    """Format battery data for display"""
    if battery_remaining is None:
        return "NO DATA"
    if battery_type == 'percent':
        return f"{battery_remaining:.1f}%"
    elif battery_type == 'mah':
        return f"{battery_remaining:.0f} mAh"
    return f"{battery_remaining}"

def print_status_line(pixhawk, loop_count):
    """Print single line status update"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    # Armed status
    armed_str = "🟢 ARMED" if pixhawk.armed else "🔴 DISARMED"
    
    # Mode
    mode_str = f"Mode: {pixhawk.mode:8s}"
    
    # Waypoint - show last_wp from MISSION_CURRENT
    if pixhawk.last_wp is not None:
        wp_str = f"WP: {pixhawk.last_wp:3d}"
    else:
        wp_str = "WP: ---"
    
    # Altitude
    if pixhawk.position:
        alt_str = f"Alt: {pixhawk.position['rel_alt']:6.2f}m"
    else:
        alt_str = "Alt: NO GPS"
    
    # Battery
    bat_str = f"Bat: {format_battery(pixhawk.battery_remaining, pixhawk.battery_type)}"
    
    print(f"[{timestamp}] {armed_str} | {mode_str} | {wp_str} | {alt_str} | {bat_str}", end='\r')

def should_capture_image(pixhawk, waypoint, captured_wp, logger):
    # Basic checks
    if not pixhawk.armed:
        logger.debug("❌ Not armed")
        return False, "Not armed"
    
    if not waypoint:
        logger.debug("❌ No waypoint from MISSION_CURRENT")
        return False, "No waypoint from MISSION_CURRENT"
    
    if not pixhawk.position:
        logger.debug("❌ No GPS position")
        return False, "No GPS position"

    if pixhawk.mode != "AUTO":
        logger.debug(f"❌ Not in AUTO mode (currently {pixhawk.mode})")
        return False, f"Not in AUTO mode (currently {pixhawk.mode})"
    
    # Check altitude
    if pixhawk.position['rel_alt'] < config.MIN_ALTITUDE_FOR_CAPTURE:
        msg = f"Altitude too low: {pixhawk.position['rel_alt']:.2f}m < {config.MIN_ALTITUDE_FOR_CAPTURE}m"
        logger.debug(f"⚠ {msg} ⚠")
        return False, msg
    
    if waypoint in captured_wp:
        logger.debug(f"❌ WP{waypoint} already captured")
        return False, f"WP{waypoint} already captured"
    
    # All checks passed!
    return True, "ALL CONDITIONS MET"

def print_detailed_status(pixhawk, logger):
    """Print detailed telemetry information"""
    print("\n" + "-"*70)
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔋 Battery: {format_battery(pixhawk.battery_remaining, pixhawk.battery_type)}")
    print(f"✈️  Mode: {pixhawk.mode}")
    print(f"🎯 Armed: {'YES' if pixhawk.armed else 'NO'}")
    print(f"📍 Position: {format_position(pixhawk.position)}")
    print(f"📊 IMU Accel: {format_imu(pixhawk.imu_accel)}")
    
    # Waypoint info - emphasize MISSION_CURRENT
    if pixhawk.last_wp is not None:
        print(f"🗺️  Current Waypoint (from MISSION_CURRENT): WP{pixhawk.last_wp}")
    else:
        print(f"🗺️  Current Waypoint: None (waiting for MISSION_CURRENT message)")
    
    print("-"*70)
    logger.info(f"Status: Armed={pixhawk.armed}, Mode={pixhawk.mode}, "
                f"WP={pixhawk.last_wp}, Position={pixhawk.position is not None}")

def check_capture_conditions(pixhawk, captured_wp, logger):
    """
    Check all capture conditions and provide detailed feedback
    This mimics the exact logic from main_test.py
    """
    print("\n📸 IMAGE CAPTURE CONDITION CHECK (based on MISSION_CURRENT):")
    
    conditions = []
    
    # Check 1: Armed
    if pixhawk.armed:
        conditions.append("   ✅ Drone is armed")
    else:
        conditions.append("   ❌ Drone is NOT armed")
    
    # Check 2: Waypoint Exists
    if pixhawk.last_wp is not None:
        conditions.append(f"   ✅ Waypoint detected: WP{pixhawk.last_wp} (from MISSION_CURRENT message)")
    else:
        conditions.append("   ❌ No waypoint detected (no MISSION_CURRENT message received)")
    
    # Check 3: Position Available
    if pixhawk.position:
        conditions.append(f"   ✅ GPS position available: {format_position(pixhawk.position)}")
    else:
        conditions.append("   ❌ No GPS position data")
    
    # Check 4: Mode is AUTO
    if pixhawk.mode == "AUTO":
        conditions.append("   ✅ Flight mode is AUTO")
    else:
        conditions.append(f"   ❌ Flight mode is NOT AUTO (currently {pixhawk.mode})")
    
    # Check 5: Altitude Check
    if pixhawk.position:
        if pixhawk.position['rel_alt'] >= config.MIN_ALTITUDE_FOR_CAPTURE:
            conditions.append(f"   ✅ Altitude sufficient: {pixhawk.position['rel_alt']:.2f}m >= {config.MIN_ALTITUDE_FOR_CAPTURE}m")
        else:
            conditions.append(f"   ❌ Altitude too low: {pixhawk.position['rel_alt']:.2f}m < {config.MIN_ALTITUDE_FOR_CAPTURE}m")
    else:
        conditions.append(f"   ⚠️  Cannot check altitude (no position data)")
    
    # Check 6: Not already captured
    if pixhawk.last_wp is not None:
        if pixhawk.last_wp not in captured_wp:
            conditions.append(f"   ✅ WP{pixhawk.last_wp} not yet captured")
        else:
            conditions.append(f"   ❌ WP{pixhawk.last_wp} already captured (in captured_wp set)")
    
    # Print all conditions
    for condition in conditions:
        print(condition)
    
    # Overall verdict using the same function as main_test.py
    would_capture, reason = should_capture_image(pixhawk, pixhawk.last_wp, captured_wp, logger)
    
    if would_capture:
        print(f"\n   ✅✅✅ CAPTURE WOULD TRIGGER HERE! ✅✅✅")
        print(f"   📸 Image would be saved as: pinyasuri_flight1_wp{pixhawk.last_wp}_<timestamp>.jpg")
    else:
        print(f"\n   ❌ Capture blocked: {reason}")
    
    print()
    return would_capture

def monitor_mission_current(pixhawk, previous_state, captured_wp, logger):
    """
    Monitor for MISSION_CURRENT message changes (waypoint detection)
    This is the core logic that main_test.py uses for capture triggering
    """
    current_state = {
        'armed': pixhawk.armed,
        'mode': pixhawk.mode,
        'waypoint': pixhawk.last_wp,  # This comes from MISSION_CURRENT
        'has_gps': pixhawk.position is not None
    }
    
    # Check for state changes
    if previous_state['armed'] != current_state['armed']:
        if current_state['armed']:
            print("\n" + "="*70)
            print("🚁 DRONE ARMED - Flight starting!")
            print("="*70)
            logger.info("ARMED - Flight started")
            # In main_test.py, this clears captured_wp and starts metrics
        else:
            print("\n" + "="*70)
            print("🛬 DRONE DISARMED - Flight ended")
            print("="*70)
            logger.info("DISARMED - Flight ended")
            # In main_test.py, this would save metrics and clear captured_wp
            captured_wp.clear()
    
    if previous_state['mode'] != current_state['mode']:
        print(f"\n✈️  MODE CHANGE: {previous_state['mode']} → {current_state['mode']}")
        logger.info(f"Mode changed: {previous_state['mode']} → {current_state['mode']}")
    
    # CRITICAL: Waypoint change detection (from MISSION_CURRENT message)
    if previous_state['waypoint'] != current_state['waypoint']:
        if current_state['waypoint'] is not None:
            print("\n" + "="*70)
            print(f"🎯 MISSION_CURRENT MESSAGE RECEIVED: WP{current_state['waypoint']}")
            print("="*70)
            print(f"   Pixhawk reports: Reached waypoint {current_state['waypoint']}")
            logger.info(f"MISSION_CURRENT: seq={current_state['waypoint']-1}, last_wp={current_state['waypoint']}")
            
            # This is where main_test.py checks if it should capture
            print(f"\n   Checking if capture should trigger...")
            would_capture = check_capture_conditions(pixhawk, captured_wp, logger)
            
            if would_capture:
                # Simulate what main_test.py does
                print(f"   ⏱️  Waiting 1.5s for stabilization...")
                print(f"   📸 camera.capture(waypoint={current_state['waypoint']}, flight_number=1, prefix='pinyasuri')")
                print(f"   📝 Logging to image_log.csv")
                print(f"   ✅ Adding WP{current_state['waypoint']} to captured_wp set")
                captured_wp.add(current_state['waypoint'])
            
            print("="*70)
    
    if previous_state['has_gps'] != current_state['has_gps']:
        if current_state['has_gps']:
            print("\n📡 GPS FIX ACQUIRED")
            logger.info("GPS fix acquired")
        else:
            print("\n📡 GPS FIX LOST")
            logger.warning("GPS fix lost")
    
    return current_state

def main_loop(pixhawk, logger):
    """Main monitoring loop - mimics main_test.py structure"""
    loop_count = 0
    last_detailed_print = time.time()
    DETAILED_INTERVAL = 10  # Print detailed status every 10 seconds
    
    # Simulate main_test.py variables
    captured_wp = set()  # Tracks which waypoints have been "captured"
    flight_number = 1
    
    previous_state = {
        'armed': False,
        'mode': 'UNKNOWN',
        'waypoint': None,
        'has_gps': False
    }
    
    print("🚁 Telemetry monitoring started. Watching for MISSION_CURRENT messages...\n")
    print("TIP: Upload a mission and switch to AUTO mode to see waypoint detection\n")
    
    while running:
        # Update telemetry - this receives MISSION_CURRENT messages
        pixhawk.update()
        
        # Monitor for MISSION_CURRENT changes and simulate capture logic
        previous_state = monitor_mission_current(pixhawk, previous_state, captured_wp, logger)
        
        # Print single-line status (overwrites itself)
        print_status_line(pixhawk, loop_count)
        
        # Print detailed status every N seconds
        current_time = time.time()
        if current_time - last_detailed_print >= DETAILED_INTERVAL:
            print_detailed_status(pixhawk, logger)
            check_capture_conditions(pixhawk, captured_wp, logger)
            last_detailed_print = current_time
        
        loop_count += 1
        time.sleep(config.MAIN_LOOP_INTERVAL)

def print_summary(logger):
    """Print test summary"""
    print("\n" + "="*70)
    print("  TEST SUMMARY - MISSION_CURRENT MONITORING")
    print("="*70)
    print("✓ Telemetry test completed")
    print(f"✓ Log saved to: {config.LOG_DIR / 'telemetry_test.log'}")
    print("\nWhat was tested:")
    print("  • MISSION_CURRENT message reception from Pixhawk")
    print("  • Waypoint detection logic (pixhawk.last_wp)")
    print("  • All 6 capture conditions from main_test.py")
    print("  • Capture simulation at detected waypoints")
    print("\nNext steps:")
    print("  1. Review the log file for MISSION_CURRENT messages")
    print("  2. Verify waypoints were detected when expected")
    print("  3. Check that capture conditions were met correctly")
    print("  4. If waypoint detection works, run main_test.py for actual capture")
    print("\nTroubleshooting:")
    print("  • No waypoints detected? Make sure mission is uploaded and AUTO mode active")
    print("  • WP stays at 0 or 1? That's the home/takeoff point, normal behavior")
    print("  • Capture blocked? Check the condition list for what's failing")
    print("="*70 + "\n")

def main():
    # Setup
    logger = setup_logging()
    signal.signal(signal.SIGINT, signal_handler)
    
    print_header()
    
    # Initialize Pixhawk (no camera or metrics needed for testing)
    print(">>> Initializing Pixhawk connection...")
    pixhawk = Pixhawk()
    
    pixhawk.wait_for_connection()
    print("✓ Connected to Pixhawk")
    print("✓ Monitoring for MISSION_CURRENT messages...\n")
    
    # Run monitoring loop
    try:
        main_loop(pixhawk, logger)
    except Exception as e:
        logger.error(f"⚠ Fatal error: {e} ⚠", exc_info=True)
        print(f"\n❌ Error occurred: {e}")
    finally:
        print_summary(logger)

if __name__ == "__main__":
    main()