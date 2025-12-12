from pymavlink import mavutil

master = mavutil.mavlink_connection('/dev/serial0', baud=57600)
master.wait_heartbeat()
master.mav.statustext_send(
    mavutil.mavlink.MAV_SEVERITY_NOTICE,
    b"TEST_MESSAGE"
)