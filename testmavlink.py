from pymavlink import mavutil

conn = mavutil.mavlink_connection('/dev/ttyAMA0:57600')
print("Waiting for heartbeat...")
conn.wait_heartbeat(timeout=10)
print(f"✓ Connected! System ID: {conn.target_system}")