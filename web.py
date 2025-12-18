#!/usr/bin/env python3
"""
Web-based camera stream with capture for Raspberry Pi Camera Module v3
Access via browser at http://<raspberry-pi-ip>:8000
"""

from picamera2 import Picamera2
from libcamera import controls
import io
import socketserver
from http import server
from threading import Condition, Thread
from datetime import datetime
import time

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                print(f'Removed streaming client {self.client_address}: {str(e)}')
        elif self.path == '/capture':
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}.jpg"
            picam2.capture_file(filename)
            
            content = f'{{"status": "success", "filename": "{filename}"}}'.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
            print(f"Image saved as: {filename}")
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


PAGE = """\
<html>
<head>
<title>Raspberry Pi Camera Stream</title>
<style>
body {
    font-family: Arial, sans-serif;
    text-align: center;
    background-color: #f0f0f0;
    margin: 0;
    padding: 20px;
}
h1 {
    color: #333;
}
#stream {
    max-width: 100%;
    height: auto;
    border: 3px solid #333;
    border-radius: 8px;
    margin: 20px auto;
    display: block;
    background-color: #000;
}
button {
    background-color: #4CAF50;
    border: none;
    color: white;
    padding: 15px 32px;
    text-align: center;
    font-size: 16px;
    margin: 10px;
    cursor: pointer;
    border-radius: 5px;
}
button:hover {
    background-color: #45a049;
}
button:active {
    background-color: #3e8e41;
}
#message {
    margin-top: 20px;
    font-size: 14px;
    color: #666;
}
.success {
    color: #4CAF50 !important;
}
</style>
</head>
<body>
<h1>Raspberry Pi Camera Module v3</h1>
<img id="stream" src="stream.mjpg" />
<div>
    <button onclick="captureImage()">Capture Image</button>
</div>
<div id="message"></div>

<script>
function captureImage() {
    fetch('/capture')
        .then(response => response.json())
        .then(data => {
            const msg = document.getElementById('message');
            msg.className = 'success';
            msg.textContent = 'Image saved as: ' + data.filename;
            setTimeout(() => { msg.textContent = ''; }, 3000);
        })
        .catch(error => {
            const msg = document.getElementById('message');
            msg.textContent = 'Error capturing image';
        });
}
</script>
</body>
</html>
"""

# Initialize camera
picam2 = Picamera2()
config = picam2.create_video_configuration(
    main={"size": (1920, 1080)},
    lores={"size": (640, 480)}
)
picam2.configure(config)

# Set autofocus
picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})

output = StreamingOutput()
from picamera2.encoders import MJPEGEncoder
encoder = MJPEGEncoder()
picam2.start_recording(encoder, output)

try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    print("=" * 50)
    print("Camera web server started!")
    print("Access the camera at:")
    print("  http://<your-pi-ip-address>:8000")
    print("  (Replace <your-pi-ip-address> with your Pi's IP)")
    print("=" * 50)
    print("\nPress Ctrl+C to stop the server")
    server.serve_forever()
except KeyboardInterrupt:
    print("\nStopping server...")
finally:
    picam2.stop_recording()
    print("Camera stopped.")