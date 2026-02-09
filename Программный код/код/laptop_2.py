import cv2
import socket
import requests
import numpy as np
import time
import threading

PI_HOST = "10.42.0.1"
PI_PORT = 5000
VIDEO_URL = f"http://{PI_HOST}:8000/video"

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((PI_HOST, PI_PORT))
print("Connected to Raspberry Pi TCP server")

mode = input("Выберите режим (m = manual, a = auto): ").lower()

current_frame = None
frame_lock = threading.Lock()
video_active = True

# Оверлей "OBJECT FOUND"
overlay_text = ""
overlay_until = 0.0

NAMES = {
    "green_cylinder": "GREEN CYLINDER",
    "white_cylinder": "WHITE STRIPED CYLINDER",
    "red_cylinder": "RED CYLINDER",
    "blue_cylinder": "BLUE CYLINDER",
    "green_line": "GREEN LINE",
    "red_line": "RED LINE",
    "blue_line": "BLUE LINE",
}

WINDOW_NAME = "КАМЕРА"
_window_ready = False


def setup_camera_window_fullscreen():
    """
    Создаёт окно и переводит его в полноэкранный режим.
    """
    global _window_ready
    if _window_ready:
        return

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    # Полноэкранный режим
    try:
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    except Exception:
        pass

    _window_ready = True


def video_stream_thread():
    """Стабильный MJPEG-приём: одно подключение, без переподключения на каждый кадр."""
    global current_frame, video_active
    session = requests.Session()

    while video_active:
        try:
            with session.get(VIDEO_URL, stream=True, timeout=5) as response:
                response.raise_for_status()
                buf = b""

                for chunk in response.iter_content(chunk_size=4096):
                    if not video_active:
                        break
                    if not chunk:
                        continue

                    buf += chunk
                    a = buf.find(b"\xff\xd8")
                    b = buf.find(b"\xff\xd9")

                    if a != -1 and b != -1 and b > a:
                        jpg = buf[a: b + 2]
                        buf = buf[b + 2:]

                        frame = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
                        if frame is not None:
                            with frame_lock:
                                current_frame = frame
        except Exception:
            time.sleep(0.2)


def _mask_for_type(hsv, color_type):
    if color_type == "green_cylinder":
        lower = np.array([35, 80, 20]);  upper = np.array([85, 255, 150])
        return cv2.inRange(hsv, lower, upper), dict(kind="cyl", min_area=800, min_ar=1.2)

    if color_type == "green_line":
        lower = np.array([35, 80, 20]);  upper = np.array([85, 255, 150])
        return cv2.inRange(hsv, lower, upper), dict(kind="line", min_area=300, max_ar=0.7, min_w=100)

    if color_type == "white_cylinder":
        lower = np.array([0, 0, 200]);   upper = np.array([180, 30, 255])
        return cv2.inRange(hsv, lower, upper), dict(kind="white_striped", min_area=500, min_ar=1.5)

    if color_type == "red_cylinder":
        l1 = np.array([0, 100, 50]);  u1 = np.array([10, 255, 255])
        l2 = np.array([170, 100, 50]); u2 = np.array([180, 255, 255])
        m1 = cv2.inRange(hsv, l1, u1); m2 = cv2.inRange(hsv, l2, u2)
        return cv2.bitwise_or(m1, m2), dict(kind="cyl", min_area=800, min_ar=1.2)

    if color_type == "red_line":
        l1 = np.array([0, 100, 50]);  u1 = np.array([10, 255, 255])
        l2 = np.array([170, 100, 50]); u2 = np.array([180, 255, 255])
        m1 = cv2.inRange(hsv, l1, u1); m2 = cv2.inRange(hsv, l2, u2)
        return cv2.bitwise_or(m1, m2), dict(kind="line", min_area=300, max_ar=0.7, min_w=100)

    if color_type == "blue_cylinder":
        lower = np.array([100, 100, 50]); upper = np.array([130, 255, 255])
        return cv2.inRange(hsv, lower, upper), dict(kind="cyl", min_area=800, min_ar=1.2)

    if color_type == "blue_line":
        lower = np.array([100, 100, 50]); upper = np.array([130, 255, 255])
        return cv2.inRange(hsv, lower, upper), dict(kind="line", min_area=300, max_ar=0.7, min_w=100)

    return None, None


def _has_black_stripes(bgr, x, y, w, h):
    """
    Белый цилиндр с чёрными полосками сверху и снизу:
    проверяем, что в верхней и нижней полосе есть заметная доля тёмных пикселей.
    """
    H, W = bgr.shape[:2]
    x0 = max(0, x); y0 = max(0, y)
    x1 = min(W, x + w); y1 = min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return False

    roi = bgr[y0:y1, x0:x1]
    if roi.size == 0:
        return False

    band_h = max(3, int(0.18 * roi.shape[0]))
    top = roi[:band_h, :]
    bot = roi[-band_h:, :]

    hsv_top = cv2.cvtColor(top, cv2.COLOR_BGR2HSV)
    hsv_bot = cv2.cvtColor(bot, cv2.COLOR_BGR2HSV)

    dark_top = (hsv_top[..., 2] < 60).mean()
    dark_bot = (hsv_bot[..., 2] < 60).mean()

    return (dark_top > 0.10) and (dark_bot > 0.10)


def annotate_frame_all(frame, highlight_type=None):
    """
    Рисует рамки/центры для:
    - цилиндров: green/blue/red/white_striped
    - линий: green/red/blue
    Возвращает: annotated_frame, detected_dict, centers_dict
    """
    if frame is None:
        return None, {}, {}

    annotated = frame.copy()
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    types = [
        "green_cylinder", "red_cylinder", "blue_cylinder", "white_cylinder",
        "green_line", "red_line", "blue_line"
    ]

    draw_colors = {
        "green_cylinder": (0, 255, 0),
        "green_line": (0, 200, 100),
        "red_cylinder": (0, 0, 255),
        "red_line": (0, 0, 200),
        "blue_cylinder": (255, 0, 0),
        "blue_line": (200, 0, 0),
        "white_cylinder": (255, 255, 255),
    }

    detected = {t: False for t in types}
    centers = {t: (0, 0) for t in types}

    for t in types:
        mask, params = _mask_for_type(hsv, t)
        if mask is None:
            continue

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None  # (area, x,y,w,h,cx,cy)
        for c in contours:
            area = cv2.contourArea(c)
            if area < params["min_area"]:
                continue

            x, y, w, h = cv2.boundingRect(c)
            if w <= 0:
                continue
            ar = h / w

            if params["kind"] == "cyl":
                if ar <= params["min_ar"]:
                    continue

            elif params["kind"] == "line":
                if ar >= params["max_ar"]:
                    continue
                if w <= params["min_w"]:
                    continue

            elif params["kind"] == "white_striped":
                if ar <= params["min_ar"]:
                    continue
                if not _has_black_stripes(frame, x, y, w, h):
                    continue

            cx = x + w // 2
            cy = y + h // 2
            if (best is None) or (area > best[0]):
                best = (area, x, y, w, h, cx, cy)

        if best is not None:
            _, x, y, w, h, cx, cy = best
            detected[t] = True
            centers[t] = (cx, cy)

            color = draw_colors.get(t, (0, 255, 255))
            thickness = 3 if (highlight_type == t) else 2

            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, thickness)
            cv2.circle(annotated, (cx, cy), 3, color, -1)

            label = t.replace("_", " ")
            cv2.putText(
                annotated, label, (x, max(0, y - 7)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA
            )

    return annotated, detected, centers


def draw_overlay(frame):
    """Рисует на кадре 'OBJECT FOUND' пока не истечёт overlay_until."""
    global overlay_text, overlay_until
    if frame is None:
        return frame

    if time.time() < overlay_until and overlay_text:
        h, w = frame.shape[:2]

        # чёрная подложка
        text = overlay_text
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1.0
        thickness = 2
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        pad = 12

        x = max(10, (w - tw) // 2)
        y = max(th + 20, int(h * 0.12))

        cv2.rectangle(
            frame,
            (x - pad, y - th - pad),
            (x + tw + pad, y + pad),
            (0, 0, 0),
            -1
        )
        # белый текст
        cv2.putText(frame, text, (x, y), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

    return frame


def sleep_with_gui(duration):
    """Пауза без фриза GUI: показываем аннотированный кадр и обрабатываем окно."""
    setup_camera_window_fullscreen()

    end = time.time() + duration
    while time.time() < end:
        with frame_lock:
            frame = None if current_frame is None else current_frame.copy()

        if frame is not None:
            annotated, _, _ = annotate_frame_all(frame)
            annotated = draw_overlay(annotated)
            cv2.imshow(WINDOW_NAME, annotated)

        if cv2.waitKey(1) & 0xFF == 27:
            raise KeyboardInterrupt


def set_object_found_overlay(obj_type, seconds=1.0):
    """Установить оверлей 'OBJECT FOUND ...' на несколько секунд."""
    global overlay_text, overlay_until
    overlay_text = f"OBJECT FOUND: {NAMES.get(obj_type, obj_type)}"
    overlay_until = time.time() + seconds


# ---------- РЕЖИМЫ ----------

if mode == "a":
    print("АВТОРЕЖИМ")

    video_thread = threading.Thread(target=video_stream_thread, daemon=True)
    video_thread.start()

    time.sleep(1.0)

    try:
        setup_camera_window_fullscreen()

        def move_robot(command, duration):
            sock.send(command.encode())
            sleep_with_gui(duration)
            sock.send(b"s")
            sleep_with_gui(0.3)

        def search_object(color_type, search_time):
            """Ищем нужный объект, если нашли — 1 раз печатаем и показываем 'OBJECT FOUND' на видео."""
            start_time = time.time()
            printed = False

            while time.time() - start_time < search_time:
                with frame_lock:
                    frame = None if current_frame is None else current_frame.copy()

                if frame is not None:
                    annotated, detected, _ = annotate_frame_all(frame, highlight_type=color_type)

                    if detected.get(color_type, False):
                        if not printed:
                            printed = True
                            print(f"НАЙДЕН: {NAMES.get(color_type, color_type)}")
                            set_object_found_overlay(color_type, seconds=1.2)

                        annotated = draw_overlay(annotated)
                        cv2.imshow(WINDOW_NAME, annotated)
                        sleep_with_gui(0.3)
                        return True

                    annotated = draw_overlay(annotated)
                    cv2.imshow(WINDOW_NAME, annotated)

                if cv2.waitKey(1) & 0xFF == 27:
                    raise KeyboardInterrupt

            return False

        print("\nФАЗА 1: ЗЕЛЕНЫЙ ЦИЛИНДР")
        move_robot("b", 0.75)
        move_robot("r", 1.3)
        green_cylinder_found = search_object("green_cylinder", 5.0)

        move_robot("f", 0.4)
        sock.send(b"u"); sleep_with_gui(1.0)
        sock.send(b"g"); sleep_with_gui(1.0)

        move_robot("b", 1.0)
        move_robot("r", 1.65)
        search_object("green_line", 3.0)

        move_robot("f", 0.5)
        sock.send(b"d"); sleep_with_gui(1.0)
        sock.send(b"h"); sleep_with_gui(1.0)

        print("\nФАЗА 2: БЕЛЫЙ ЦИЛИНДР")
        move_robot("b", 1.4)
        move_robot("r", 1.65)
        white_cylinder_found = search_object("white_cylinder", 5.0)

        move_robot("f", 0.3)
        sock.send(b"u"); sleep_with_gui(1.0)
        sock.send(b"g"); sleep_with_gui(1.0)

        move_robot("b", 1.4)
        move_robot("l", 1.5)
        move_robot("b", 0.85)
        move_robot("l", 1.0)

        search_object("green_line", 3.0)

        move_robot("f", 0.5)
        sock.send(b"d"); sleep_with_gui(1.0)
        sock.send(b"h"); sleep_with_gui(1.0)

        print("\nФАЗА 3: КРАСНЫЙ ЦИЛИНДР")
        move_robot("b", 1.0)
        move_robot("r", 2.3)
        move_robot("b", 1.0)
        move_robot("r", 2.15)
        red_cylinder_found = search_object("red_cylinder", 5.0)

        move_robot("f", 0.65)
        sock.send(b"u"); sleep_with_gui(1.0)
        sock.send(b"g"); sleep_with_gui(1.0)

        move_robot("b", 1.0)
        move_robot("r", 1.0)
        search_object("red_line", 3.0)

        move_robot("f", 0.8)
        sock.send(b"u"); sleep_with_gui(1.0)
        sock.send(b"d"); sleep_with_gui(1.0)

        print("\nФАЗА 4: СИНИЙ ЦИЛИНДР")
        move_robot("b", 1.8)
        move_robot("r", 1.2)
        blue_cylinder_found = search_object("blue_cylinder", 5.0)

        move_robot("f", 0.9)
        sock.send(b"h"); sleep_with_gui(1.0)
        sock.send(b"g"); sleep_with_gui(1.0)

        move_robot("b", 1.5)
        move_robot("r", 2.1)
        search_object("blue_line", 3.0)

        move_robot("f", 0.7)
        sock.send(b"u"); sleep_with_gui(1.0)
        sock.send(b"d"); sleep_with_gui(1.0)

        move_robot("b", 2.3)
        move_robot("r", 1.4)

        print("\nАВТОРЕЖИМ ЗАВЕРШЕН")
        print(f"Зеленый: {'ДА' if green_cylinder_found else 'НЕТ'}")
        print(f"Белый: {'ДА' if white_cylinder_found else 'НЕТ'}")
        print(f"Красный: {'ДА' if red_cylinder_found else 'НЕТ'}")
        print(f"Синий: {'ДА' if blue_cylinder_found else 'НЕТ'}")

        sleep_with_gui(2.0)

    except KeyboardInterrupt:
        print("\nПрервано")
    except Exception as e:
        print(f"\nОшибка: {e}")
    finally:
        video_active = False
        try:
            sock.send(b"s")
        except Exception:
            pass
        sock.close()
        cv2.destroyAllWindows()

elif mode == "m":
    print("РУЧНОЙ РЕЖИМ")
    print("W-вперед, S-назад, A-влево, D-вправо")
    print("Q-разжатие, G-подъем, H-сжатие, E-опускание")
    print("ПРОБЕЛ-стоп, ESC-выход")

    video_thread = threading.Thread(target=video_stream_thread, daemon=True)
    video_thread.start()

    time.sleep(1.0)

    try:
        setup_camera_window_fullscreen()

        last_key_time = 0
        key_delay = 0.05

        while True:
            with frame_lock:
                frame = None if current_frame is None else current_frame.copy()

            if frame is not None:
                annotated, _, _ = annotate_frame_all(frame)
                annotated = draw_overlay(annotated)
                cv2.imshow(WINDOW_NAME, annotated)

            key = cv2.waitKey(1) & 0xFF

            current_time = time.time()
            if current_time - last_key_time < key_delay:
                continue

            if key == 27:
                break
            elif key == ord("w"):
                sock.send(b"f"); last_key_time = current_time
            elif key == ord("s"):
                sock.send(b"b"); last_key_time = current_time
            elif key == ord("a"):
                sock.send(b"l"); last_key_time = current_time
            elif key == ord("d"):
                sock.send(b"r"); last_key_time = current_time
            elif key == ord("q"):
                sock.send(b"u"); last_key_time = current_time
            elif key == 32:
                sock.send(b"s"); last_key_time = current_time
            elif key == ord("g"):
                sock.send(b"g"); last_key_time = current_time
            elif key == ord("h"):
                sock.send(b"h"); last_key_time = current_time
            elif key == ord("e"):
                sock.send(b"d"); last_key_time = current_time

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        video_active = False
        try:
            sock.send(b"s")
        except Exception:
            pass
        sock.close()
        cv2.destroyAllWindows()

else:
    print("Неверный режим!")
    sock.close()
