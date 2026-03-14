import io
import logging
import socketserver
import threading
from http import server
from threading import Condition, Thread

import cv2
import numpy as np
from picamera2 import Picamera2

import board
import busio
from adafruit_pca9685 import PCA9685


GRID_SIZE = 4
JPEG_QUALITY = 40
STREAM_PORT = 7123

# Servo settings
SERVO_CH_X = 15
SERVO_CH_Y = 14

SERVO_X_MIN = 2000
SERVO_X_MAX = 8000
SERVO_Y_MIN = 2500
SERVO_Y_MAX = 7500
SERVO_STEP = 350

SERVO_X_HOME = 4500
SERVO_Y_HOME = 5000


# ---------- PCA9685 / servo setup ----------
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 50

servo_lock = threading.Lock()
servo_x = SERVO_X_HOME
servo_y = SERVO_Y_HOME
last_move = "home"


def clamp(value, low, high):
    return max(low, min(high, value))


def set_servo(channel, pulse):
    pca.channels[channel].duty_cycle = int(pulse)


def set_servo_positions(x_pulse, y_pulse):
    global servo_x, servo_y
    with servo_lock:
        servo_x = clamp(x_pulse, SERVO_X_MIN, SERVO_X_MAX)
        servo_y = clamp(y_pulse, SERVO_Y_MIN, SERVO_Y_MAX)
        set_servo(SERVO_CH_X, servo_x)
        set_servo(SERVO_CH_Y, servo_y)


def move_servos_for_touch(row, col):
    global servo_x, servo_y, last_move

    with servo_lock:
        # Corners -> diagonal movement
        if row == 0 and col == 0:
            # top-left touch -> move right-down
            
            servo_x = clamp(servo_x - SERVO_STEP, SERVO_X_MIN, SERVO_X_MAX)
            servo_y = clamp(servo_y - SERVO_STEP, SERVO_Y_MIN, SERVO_Y_MAX)
            
            last_move = "right_down"

        elif row == 0 and col == (GRID_SIZE - 1):
            # top-right touch -> move left-down
        
            servo_x = clamp(servo_x + SERVO_STEP, SERVO_X_MIN, SERVO_X_MAX)
            servo_y = clamp(servo_y - SERVO_STEP, SERVO_Y_MIN, SERVO_Y_MAX)
        
            last_move = "left_down"

        elif row == (GRID_SIZE - 1) and col == 0:
            # bottom-left touch -> move right-up
            
            servo_x = clamp(servo_x - SERVO_STEP, SERVO_X_MIN, SERVO_X_MAX)
            servo_y = clamp(servo_y + SERVO_STEP, SERVO_Y_MIN, SERVO_Y_MAX)
        
            last_move = "right_up"

        elif row == (GRID_SIZE - 1) and col == (GRID_SIZE - 1):
            # bottom-right touch -> move left-up
        
            servo_x = clamp(servo_x + SERVO_STEP, SERVO_X_MIN, SERVO_X_MAX)
            servo_y = clamp(servo_y + SERVO_STEP, SERVO_Y_MIN, SERVO_Y_MAX)
        
            last_move = "left_up"

        # Left edge (not corners) -> move right
        elif col == 0 and 0 < row < (GRID_SIZE - 1):
            # servo_y = SERVO_Y_HOME
        
            servo_x = clamp(servo_x - SERVO_STEP, SERVO_X_MIN, SERVO_X_MAX)
        
            last_move = "right"

        # Right edge (not corners) -> move left
        elif col == (GRID_SIZE - 1) and 0 < row < (GRID_SIZE - 1):
            # servo_y = SERVO_Y_HOME
        
            servo_x = clamp(servo_x + SERVO_STEP, SERVO_X_MIN, SERVO_X_MAX)
        
            last_move = "left"

        # Top edge (not corners) -> move down
        elif row == 0 and 0 < col < (GRID_SIZE - 1):
            # servo_x = SERVO_X_HOME
       
            servo_y = clamp(servo_y - SERVO_STEP, SERVO_Y_MIN, SERVO_Y_MAX)
        
            last_move = "down"

        # Bottom edge (not corners) -> move up
        elif row == (GRID_SIZE - 1) and 0 < col < (GRID_SIZE - 1):
            # servo_x = SERVO_X_HOME
       
            servo_y = clamp(servo_y + SERVO_STEP, SERVO_Y_MIN, SERVO_Y_MAX)
        
            last_move = "up"

        # Centre area -> go to centre/home
        else:
            servo_x = SERVO_X_HOME
            servo_y = SERVO_Y_HOME
            last_move = "home"

        set_servo(SERVO_CH_X, servo_x)
        set_servo(SERVO_CH_Y, servo_y)

    logging.info(
        "Touch row=%s col=%s -> servo_x=%s servo_y=%s",
        row,
        col,
        servo_x,
        servo_y,
    )


# Initialise servos at centre
set_servo_positions(SERVO_X_HOME, SERVO_Y_HOME)


# ---------- Video streaming ----------
class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()
        self.quadrants = {}

    def process_frame(self, frame):
        image = np.array(frame, dtype=np.uint8)

        h, w = image.shape[:2]
        dh, dw = h // GRID_SIZE, w // GRID_SIZE

        quadrants = {}
        for i in range(GRID_SIZE):
            for j in range(GRID_SIZE):
                key = f"stream{i}{j}"
                sub_image = image[i * dh:(i + 1) * dh, j * dw:(j + 1) * dw]
                sub_image = cv2.resize(sub_image, (320, 240), interpolation=cv2.INTER_LINEAR)
                quadrants[key] = cv2.imencode(
                    ".jpg",
                    sub_image,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )[1].tobytes()

        with self.condition:
            self.quadrants = quadrants
            self.frame = quadrants
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(301)
            self.send_header("Location", "/index.html")
            self.end_headers()
            return

        if self.path == "/index.html":
            content = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if self.path.startswith("/touch"):
            # Expected format: /touchRC, e.g. /touch00, /touch12, /touch33
            suffix = self.path[len("/touch"):]
            if len(suffix) == 2 and suffix.isdigit():
                row = int(suffix[0])
                col = int(suffix[1])

                if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE:
                    move_servos_for_touch(row, col)
                    body = f"OK row={row} col={col}\n".encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

            self.send_error(400, "Invalid touch endpoint")
            return

        if self.path.startswith("/stream") and self.path.endswith(".mjpg"):
            key = self.path[1:-5]  # /stream00.mjpg -> stream00
            self.send_response(200)
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
            self.end_headers()

            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame.get(key, None) if output.frame else None

                    if frame:
                        self.wfile.write(b"--FRAME\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(
                            f"Content-Length: {len(frame)}\r\n\r\n".encode("utf-8")
                        )
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
            except Exception as e:
                logging.warning("Removed streaming client %s: %s", self.client_address, e)
            return

        self.send_error(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


PAGE = """\
<html>
<head>
<title>Picamera2 MJPEG Streaming - 4x4 Grid</title>
</head>
<body>
<h1>Picamera2 MJPEG Streaming - 4x4 Grid</h1>
<table cellspacing="10">
"""

for i in range(GRID_SIZE):
    PAGE += "<tr>"
    for j in range(GRID_SIZE):
        PAGE += f'<td><img src="stream{i}{j}.mjpg" width="160" height="120" /></td>'
    PAGE += "</tr>"

PAGE += """
</table>
</body>
</html>
"""


picam2 = Picamera2()
picam2.configure(
    picam2.create_still_configuration(
        main={"size": (640, 480), "format": "RGB888"}
    )
)
output = StreamingOutput()


def capture_frames():
    picam2.start()
    try:
        while True:
            frame = picam2.capture_array()
            output.process_frame(frame)
    except KeyboardInterrupt:
        picam2.stop()


thread = Thread(target=capture_frames, daemon=True)
thread.start()

try:
    address = ("", STREAM_PORT)
    httpd = StreamingServer(address, StreamingHandler)
    print(f"Server started on port {STREAM_PORT}...")
    httpd.serve_forever()
except KeyboardInterrupt:
    print("Server shutting down...")
finally:
    picam2.stop()
    pca.deinit()