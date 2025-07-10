# -*- coding: gbk -*-
import socket
import struct
import os
import threading
import queue
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor

# ---------- 配置 ----------
SERVER_IP = '0.0.0.0'
PORT = 5001
SAVE_DIR = 'received_data/image'
BUFFER_SIZE = 4096
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB最大图片大小限制

DELIM = b'|PROTOCOL_SWITCH|'  # 协议分隔符
os.makedirs(SAVE_DIR, exist_ok=True)

# ---------- 线程与队列 ----------
frame_queue = queue.Queue(maxsize=100)
executor = ThreadPoolExecutor(max_workers=2)

# ---------- 全局状态 ----------
image_counter = 1


# ---------- 后台任务 ----------
def save_large_image(data, idx):
    """安全保存大图的后台任务"""
    try:
        if len(data) > MAX_IMAGE_SIZE:
            print(f"[Server] 图片过大({len(data)} bytes)，已丢弃")
            return

        arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            print("[Server] 图片解码失败")
            return

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SAVE_DIR, f"{timestamp}.jpg")

        if not cv2.imwrite(path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 95]):
            print(f"[Server] 图片保存失败: {path}")
            return

        print(f"[Server] 大图保存成功: {path}")
    except Exception as e:
        print(f"[Server] 大图保存异常: {e}")



def display_worker():
    """独立线程：展示视频流"""
    while True:
        frame = frame_queue.get()
        if frame is None:  # 收到终止信号
            break

        try:
            cv2.imshow('Server Stream', frame)
            if cv2.waitKey(1) & 0xFF == 27:  # ESC键退出
                break
        except Exception as e:
            print(f"[Server] 显示异常: {e}")
            break

    cv2.destroyAllWindows()


# ---------- 消息解析 ----------
def parse_messages(buf):
    global image_counter

    offset = 0
    n = len(buf)
    while True:
        # 检查是否是控制消息
        if buf.startswith(DELIM, offset):
            if n - offset < len(DELIM) + 1 + 4 + len(DELIM):
                break

            offset += len(DELIM) + 1
            txt_len = struct.unpack('>L', buf[offset:offset + 4])[0]
            offset += 4

            if n - offset < txt_len + len(DELIM):
                break

            cmd = buf[offset:offset + txt_len].decode()
            offset += txt_len + len(DELIM)

            if cmd == 'image':
                # 读取大图数据
                if n - offset < 4:
                    offset -= (len(DELIM) + 1 + 4 + txt_len + len(DELIM))
                    break

                L = struct.unpack('>L', buf[offset:offset + 4])[0]
                if L > MAX_IMAGE_SIZE:
                    print(f"[Server] 图片大小超过限制({L} bytes)")
                    offset += 4 + L if n - offset >= 4 + L else n - offset
                    continue

                if n - offset < 4 + L:
                    offset -= (len(DELIM) + 1 + 4 + txt_len + len(DELIM))
                    break

                offset += 4
                data = buf[offset:offset + L]
                offset += L

                # 提交后台任务保存大图
                executor.submit(save_large_image, data, image_counter)
                image_counter += 1
                continue

        # 视频流数据：4字节长度 + JPEG
        if n - offset < 4:
            break

        L = struct.unpack('>L', buf[offset:offset + 4])[0]
        if n - offset < 4 + L:
            break

        offset += 4
        chunk = buf[offset:offset + L]
        offset += L

        # 解码视频帧
        try:
            arr = np.frombuffer(chunk, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                try:
                    frame_queue.put_nowait(frame)
                except queue.Full:
                    pass
        except Exception as e:
            print(f"[Server] 视频帧解码异常: {e}")

    return buf[offset:]


# ---------- 主循环 ----------
def run_server():
    # 启动显示线程
    display_thread = threading.Thread(target=display_worker, daemon=True)
    display_thread.start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((SERVER_IP, PORT))
        s.listen(1)
        print(f"[Server] 监听 {SERVER_IP}:{PORT}")

        try:
            conn, addr = s.accept()
            print(f"[Server] 已连接: {addr}")

            buf = b''
            while True:
                try:
                    data = conn.recv(BUFFER_SIZE)
                    if not data:
                        break
                    buf += data
                    buf = parse_messages(buf)
                except ConnectionResetError:
                    print("[Server] 客户端断开连接")
                    break
                except Exception as e:
                    print(f"[Server] 接收数据异常: {e}")
                    break

        except KeyboardInterrupt:
            print("\n[Server] 收到中断信号")
        finally:
            # 清理资源
            frame_queue.put(None)  # 通知显示线程退出
            display_thread.join(timeout=1)
            executor.shutdown(wait=False)
            print("[Server] 已退出")


if __name__ == '__main__':
    run_server()