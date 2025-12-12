from pymavlink import mavutil

# Connect to Pixhawk
conn = mavutil.mavlink_connection(device='/dev/ttyAMA0', baud=57600)

# Wait for heartbeat
print("Waiting for heartbeat...")
conn.wait_heartbeat()
print("Heartbeat received from system %u component %u" % (conn.target_system, conn.target_component))

# Try reading one message
msg = conn.recv_match(blocking=True)
print(msg)