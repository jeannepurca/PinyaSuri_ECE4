#!/usr/bin/env python3

from flask import Flask, Response
from picamera2 import Picamera2
import cv2

app = Flask(__name__)
picam2 = Picamera2()
picam2.start()

def generate_frames():
    while True:
        frame = picam2.capture_array()  # Capture frame
        # Encode as JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        # Yield frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return "<h1>Pi Camera MJPEG Stream</h1><img src='/video_feed' />"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
