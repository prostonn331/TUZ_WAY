import cv2
import socket
import requests
import numpy as np

# ===== Настройки =====
PI_HOST = "10.42.0.1"  # IP Raspberry Pi
#PI_HOST = "192.168.1.85"  # IP Raspberry Pi
PI_PORT = 5000
VIDEO_URL = f"http://{PI_HOST}:8000/video"

# ===== TCP connection =====
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((PI_HOST, PI_PORT))
print("Connected to Raspberry Pi TCP server")

# ===== Video stream =====
stream = requests.get(VIDEO_URL, stream=True)
bytes_data = b""

print("Controls: arrows + SPACE, ESC to quit")

while True:
    for chunk in stream.iter_content(chunk_size=1024):
        bytes_data += chunk

        a = bytes_data.find(b'\xff\xd8')
        b = bytes_data.find(b'\xff\xd9')

        if a != -1 and b != -1:
            jpg = bytes_data[a:b + 2]
            bytes_data = bytes_data[b + 2:]

            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            cv2.imshow("Video", frame)

            key = cv2.waitKey(1) & 0xFF
            command = None

            if key == 27:  # ESC
                print("Exit")
                sock.close()
                cv2.destroyAllWindows()
                exit(0)
           # elif key == 82:
            elif key == ord('w'):
                command = "f"
           # elif key == 84:
            elif key == ord('s'):
                command = "b"
           # elif key == 81:
            elif key == ord('q'):
                command = "l"
            #elif key == 83:
            elif key == ord('e'):
                command = "r"
            elif key == 32:
                command = "s"
            elif key == ord('g'):
                command = "g"
            elif key == ord('h'):
                command = "h"
            elif key == ord('u'):
                command = "u"
            elif key == ord('d'):
                command = "d"


            # отправка команды каждый раз при нажатии клавиши
            if command:
                try:
                    sock.send(command.encode())
                except BrokenPipeError:
                    print("Connection lost")
                    exit(1)
