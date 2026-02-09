import cv2
import socket
import threading
import serial
from flask import Flask, Response

# ===== Serial settings =====
SERIAL_PORT = "/dev/ttyUSB0"   #  порт
SERIAL_BAUD = 9600

# ===== Open serial =====
try:
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
    print(f"Serial connected: {SERIAL_PORT} @ {SERIAL_BAUD}")
except Exception as e:
    print("Serial error:", e)
    ser = None

# ===== Flask video =====
app = Flask(__name__)
camera = cv2.VideoCapture(0)

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            continue
        _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
        )

@app.route('/video')
def video():
    return Response(
        gen_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

# ===== TCP command server =====
def command_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 5000))
    s.listen(1)
    print("TCP server started on port 5000")

    while True:
        conn, addr = s.accept()
        print(f"Client connected: {addr}")

        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    print("Client disconnected")
                    break

                command = data.decode().strip()
                print(f"Key pressed: {command}")

                # ---- SEND TO SERIAL ----
                if ser:
                    ser.write((command + "\n").encode())
                    ser.flush()

            except ConnectionResetError:
                print("Client connection reset")
                break

        conn.close()
        print("Waiting for new client...")

# ===== Start =====
if __name__ == "__main__":
    print("Starting Raspberry Pi server")

    threading.Thread(target=command_server, daemon=True).start()
    app.run(host="0.0.0.0", port=8000)
