# -*- coding: gbk -*-
import socket
import struct
import os
import threading
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import yaml

SERVER_IP = '0.0.0.0'
PORT_LARGE = 5002
SAVE_DIR = 'received_data/stero'
IMAGE_DIR = 'received_data/image'
BUFFER_SIZE = 4096
MAX_IMAGE_SIZE = 10 * 1024 * 1024

os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

file_io_lock = threading.Lock()

def load_camera_params(yaml_path: str):
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    cam_matrix = np.array(data["camera_matrix"]["data"]).reshape((3, 3))
    dist_coeffs = np.array(data["distortion_coefficients"]["data"]).reshape((1, 5))
    rect_matrix = np.array(data["rectification_matrix"]["data"]).reshape((3, 3))
    proj_matrix = np.array(data["projection_matrix"]["data"]).reshape((3, 4))
    return cam_matrix, dist_coeffs, rect_matrix, proj_matrix

yaml_dir = "yaml"
left_yaml = os.path.join(yaml_dir, "left.yaml")
right_yaml = os.path.join(yaml_dir, "right.yaml")
camL, distL, rectL, projL = load_camera_params(left_yaml)
camR, distR, rectR, projR = load_camera_params(right_yaml)

latest_large_frame = None
latest_frame_lock = threading.Lock()

def parse_large_messages(buf):
    global latest_large_frame
    offset = 0
    n = len(buf)

    while True:
        if n - offset < 5:
            # 不足以解析头部，等待更多数据
            break

        # 读取帧总长度（包括帧类型）
        L = struct.unpack('>L', buf[offset:offset + 4])[0]

        if n - offset < 4 + L:
            # 数据未完整接收，等待更多数据
            break

        # 解析帧
        frame_start = offset + 4
        frame_type = buf[frame_start]
        data_start = frame_start + 1
        data_end = data_start + (L - 1)
        data = buf[data_start:data_end]

        if frame_type == 0x01:
            arr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                with latest_frame_lock:
                    latest_large_frame = img

        # 移动到下一个包的位置
        offset = data_end

    # 返回未处理完的部分（作为新 buf）
    return buf[offset:]


def handle_large_client(conn, addr):
    print(f"[Server] 大图连接: {addr}")
    buf = b''
    try:
        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                break
            buf += data
            buf = parse_large_messages(buf)
    except Exception as e:
        print(f"[Server] 大图连接异常: {e}")
    finally:
        conn.close()
        print(f"[Server] 大图连接关闭: {addr}")

def save_current_frame():
    global latest_large_frame
    with latest_frame_lock:
        if latest_large_frame is None:
            print("[Server] 无图像缓存，无法保存")
            return
        img_to_save = latest_large_frame.copy()

    img_to_save = cv2.rotate(img_to_save, cv2.ROTATE_180)
    left_img = img_to_save[:, 1280:]
    right_img = img_to_save[:, :1280]

    left_img = cv2.remap(left_img, *cv2.initUndistortRectifyMap(
        camL, distL, rectL, projL, (left_img.shape[1], left_img.shape[0]), cv2.CV_32FC1), cv2.INTER_LINEAR)
    right_img = cv2.remap(right_img, *cv2.initUndistortRectifyMap(
        camR, distR, rectR, projR, (right_img.shape[1], right_img.shape[0]), cv2.CV_32FC1), cv2.INTER_LINEAR)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    left_path = os.path.join(SAVE_DIR, f"left_{timestamp}.jpg")
    right_path = os.path.join(SAVE_DIR, f"right_{timestamp}.jpg")
    with file_io_lock:
        success_left = cv2.imwrite(left_path, left_img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        success_right = cv2.imwrite(right_path, right_img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
    if success_left and success_right:
        print(f"[Server] 本地保存成功: {left_path} 和 {right_path}")
    else:
        print("[Server] 保存图片失败")

def save_display_right_image():
    global latest_large_frame
    with latest_frame_lock:
        if latest_large_frame is None:
            print("[Server] 无图像缓存，无法保存")
            return
        full_img = latest_large_frame.copy()

    full_img = cv2.rotate(full_img, cv2.ROTATE_180)
    right_img = full_img[:, 1280:]

    save_time = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    save_path = os.path.join(IMAGE_DIR, f"display_{save_time}.jpg")

    with file_io_lock:
        success = cv2.imwrite(save_path, right_img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])

    if success:
        print(f"[Server] 当前右图像保存成功: {save_path}")
    else:
        print("[Server] 保存当前右图像失败")

def display_worker():
    window_name = 'Server Stream - Right Image'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)

    fish_dir = "received_data/fish"
    os.makedirs(fish_dir, exist_ok=True)

    while True:
        with latest_frame_lock:
            frame = None if latest_large_frame is None else latest_large_frame.copy()

        if frame is not None:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
            right_img = frame[:, 1280:]
            cv2.imshow(window_name, right_img)

        key = cv2.waitKey(30) & 0xFF
        if key == 27:  # ESC
            print("[Server] 退出显示")
            break
        elif key == ord('s'):
            save_current_frame()
        elif key == ord('d'):
            save_display_right_image()
        elif key == ord('f'):
            # 保存到 fish 文件夹
            with latest_frame_lock:
                if latest_large_frame is None:
                    print("[Server] 无图像缓存，无法保存")
                    continue
                full_img = latest_large_frame.copy()

            full_img = cv2.rotate(full_img, cv2.ROTATE_180)
            right_img = full_img[:, 1280:]

            save_time = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            save_path = os.path.join(fish_dir, f"fish_{save_time}.jpg")

            with file_io_lock:
                success = cv2.imwrite(save_path, right_img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])

            if success:
                print(f"[Server] 鱼眼图像保存成功: {save_path}")
            else:
                print("[Server] 鱼眼图像保存失败")

    cv2.destroyAllWindows()


def run_server():
    display_thread = threading.Thread(target=display_worker, daemon=True)
    display_thread.start()

    s_large = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s_large.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s_large.bind((SERVER_IP, PORT_LARGE))
    s_large.listen(1)

    print(f"[Server] 监听大图端口 {PORT_LARGE}")

    try:
        while True:
            s_large.settimeout(0.5)
            try:
                conn_large, addr_large = s_large.accept()
                threading.Thread(target=handle_large_client, args=(conn_large, addr_large), daemon=True).start()
            except socket.timeout:
                pass

    except KeyboardInterrupt:
        print("\n[Server] 收到中断信号，退出")
    finally:
        s_large.close()
        print("[Server] 已退出")

if __name__ == '__main__':
    run_server()
