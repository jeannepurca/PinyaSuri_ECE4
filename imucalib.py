# mpu6050_calibration.py
from mpu6050 import mpu6050
import time

# Create sensor object
sensor = mpu6050(0x68)

# Number of samples for averaging
NUM_SAMPLES = 1000

print("Keep the MPU6050 flat and stationary...")
time.sleep(2)

# Initialize sums
gyro_sum = {'x': 0, 'y': 0, 'z': 0}
accel_sum = {'x': 0, 'y': 0, 'z': 0}

# Collect samples
for i in range(NUM_SAMPLES):
    accel_data = sensor.get_accel_data()
    gyro_data = sensor.get_gyro_data()
    
    # Sum for averaging
    for axis in ['x','y','z']:
        gyro_sum[axis] += gyro_data[axis]
        accel_sum[axis] += accel_data[axis]
    
    time.sleep(0.002)  # small delay ~500Hz sampling

# Compute average (offset)
gyro_offset = {axis: gyro_sum[axis]/NUM_SAMPLES for axis in ['x','y','z']}
accel_offset = {axis: accel_sum[axis]/NUM_SAMPLES for axis in ['x','y','z']}

# Adjust accel Z for gravity (assuming flat, 1g on Z)
accel_offset['z'] -= 1.0  # if using g units; skip if in raw values

print("\n--- Calibration Results ---")
print("Gyro Offsets (deg/s):", gyro_offset)
print("Accel Offsets (g):", accel_offset)
print("---------------------------\n")

print("Use these offsets in your gimbal code like this:")
print("corrected_gyro = raw_gyro - gyro_offset")
print("corrected_accel = raw_accel - accel_offset")