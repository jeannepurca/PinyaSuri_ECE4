import csv
import time

def log_event(filename, waypoint, gps, image_path):
    with open(filename, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([time.time(), waypoint, gps, image_path])