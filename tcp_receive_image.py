# -*- coding: gbk -*-
import socket
import struct
import os
import threading
import queue
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor

# ---------- ���� ----------
SERVER_IP = '0.0.0.0'
PORT = 5001
SAVE_DIR = 'received_data/image'
BUFFER_SIZE = 4096
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB���ͼƬ��С����

DELIM = b'|PROTOCOL_SWITCH|'  # Э��ָ���
os.makedirs(SAVE_DIR, exist_ok=True)

# ---------- �߳������ ----------
frame_queue = queue.Queue(maxsize=100)
executor = ThreadPoolExecutor(max_workers=2)

# ---------- ȫ��״̬ ----------
image_counter = 1


# ---------- ��̨���� ----------
def save_large_image(data, idx):
    """��ȫ�����ͼ�ĺ�̨����"""
    try:
        if len(data) > MAX_IMAGE_SIZE:
            print(f"[Server] ͼƬ����({len(data)} bytes)���Ѷ���")
            return

        arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            print("[Server] ͼƬ����ʧ��")
            return

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SAVE_DIR, f"{timestamp}.jpg")

        if not cv2.imwrite(path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 95]):
            print(f"[Server] ͼƬ����ʧ��: {path}")
            return

        print(f"[Server] ��ͼ����ɹ�: {path}")
    except Exception as e:
        print(f"[Server] ��ͼ�����쳣: {e}")



def display_worker():
    """�����̣߳�չʾ��Ƶ��"""
    while True:
        frame = frame_queue.get()
        if frame is None:  # �յ���ֹ�ź�
            break

        try:
            cv2.imshow('Server Stream', frame)
            if cv2.waitKey(1) & 0xFF == 27:  # ESC���˳�
                break
        except Exception as e:
            print(f"[Server] ��ʾ�쳣: {e}")
            break

    cv2.destroyAllWindows()


# ---------- ��Ϣ���� ----------
def parse_messages(buf):
    global image_counter

    offset = 0
    n = len(buf)
    while True:
        # ����Ƿ��ǿ�����Ϣ
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
                # ��ȡ��ͼ����
                if n - offset < 4:
                    offset -= (len(DELIM) + 1 + 4 + txt_len + len(DELIM))
                    break

                L = struct.unpack('>L', buf[offset:offset + 4])[0]
                if L > MAX_IMAGE_SIZE:
                    print(f"[Server] ͼƬ��С��������({L} bytes)")
                    offset += 4 + L if n - offset >= 4 + L else n - offset
                    continue

                if n - offset < 4 + L:
                    offset -= (len(DELIM) + 1 + 4 + txt_len + len(DELIM))
                    break

                offset += 4
                data = buf[offset:offset + L]
                offset += L

                # �ύ��̨���񱣴��ͼ
                executor.submit(save_large_image, data, image_counter)
                image_counter += 1
                continue

        # ��Ƶ�����ݣ�4�ֽڳ��� + JPEG
        if n - offset < 4:
            break

        L = struct.unpack('>L', buf[offset:offset + 4])[0]
        if n - offset < 4 + L:
            break

        offset += 4
        chunk = buf[offset:offset + L]
        offset += L

        # ������Ƶ֡
        try:
            arr = np.frombuffer(chunk, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                try:
                    frame_queue.put_nowait(frame)
                except queue.Full:
                    pass
        except Exception as e:
            print(f"[Server] ��Ƶ֡�����쳣: {e}")

    return buf[offset:]


# ---------- ��ѭ�� ----------
def run_server():
    # ������ʾ�߳�
    display_thread = threading.Thread(target=display_worker, daemon=True)
    display_thread.start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((SERVER_IP, PORT))
        s.listen(1)
        print(f"[Server] ���� {SERVER_IP}:{PORT}")

        try:
            conn, addr = s.accept()
            print(f"[Server] ������: {addr}")

            buf = b''
            while True:
                try:
                    data = conn.recv(BUFFER_SIZE)
                    if not data:
                        break
                    buf += data
                    buf = parse_messages(buf)
                except ConnectionResetError:
                    print("[Server] �ͻ��˶Ͽ�����")
                    break
                except Exception as e:
                    print(f"[Server] ���������쳣: {e}")
                    break

        except KeyboardInterrupt:
            print("\n[Server] �յ��ж��ź�")
        finally:
            # ������Դ
            frame_queue.put(None)  # ֪ͨ��ʾ�߳��˳�
            display_thread.join(timeout=1)
            executor.shutdown(wait=False)
            print("[Server] ���˳�")


if __name__ == '__main__':
    run_server()