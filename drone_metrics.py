import numpy as np
import math

class Metrics:
    @staticmethod
    def flight_stability(attitude_data):
        """Return std dev of roll, pitch, yaw"""
        return (np.std(attitude_data['roll']),
                np.std(attitude_data['pitch']),
                np.std(attitude_data['yaw']))

    @staticmethod
    def rms_vibration(ax, ay, az):
        return np.sqrt(np.mean(np.array(ax)**2 + np.array(ay)**2 + np.array(az)**2))

    @staticmethod
    def waypoint_error(planned, actual):
        return math.sqrt((planned[0] - actual[0])**2 + (planned[1] - actual[1])**2)