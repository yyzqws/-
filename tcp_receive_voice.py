# -*- coding: gbk -*-
import socket
import struct
import threading
import os
import numpy as np
import sounddevice as sd
import time
from contextlib import contextmanager

# ���� ���� ����
HOST, PORT = '0.0.0.0', 5001
SAVE_AUDIO_DIR = 'received_data/audio'
AUDIO_CHUNK = 1024
SOCKET_TIMEOUT = 1  # ����socket��ʱ����

os.makedirs(SAVE_AUDIO_DIR, exist_ok=True)

# ���� ȫ��״̬ ����
playback_buf = []
playback_lock = threading.Lock()  # �������Ż�������
running = True
conn = None  # �������Ӷ�������


@contextmanager
def socket_context(*args, **kwargs):
    """socket�����Ĺ�����"""
    sock = socket.socket(*args, **kwargs)
    try:
        yield sock
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        sock.close()


def audio_callback(outdata, frames, t, status):
    global playback_buf
    with playback_lock:  # �������ʻ�����
        available = len(playback_buf)
        if available < frames:
            outdata[:, 0] = np.zeros(frames, dtype=np.float32)
            if available > 0:
                outdata[:available, 0] = np.array(playback_buf, dtype=np.float32)
                playback_buf = []
        else:
            chunk = playback_buf[:frames]
            playback_buf = playback_buf[frames:]
            outdata[:, 0] = np.array(chunk, dtype=np.float32)


def recvall(sock, n):
    data = b''
    while len(data) < n and running:
        try:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        except (socket.timeout, ConnectionResetError, BrokenPipeError) as e:
            if not running:
                return None
            continue
        except Exception as e:
            print(f'[�����] ���������쳣: {str(e)}')
            return None
    return data if len(data) == n else None


def network_thread(conn):
    global playback_buf, running
    wav_count = 1
    print('[�����] �����߳����������ȴ�����...')

    try:
        conn.settimeout(SOCKET_TIMEOUT)  # ����socket��ʱ
        while running:
            h = recvall(conn, 4)
            if h is None:
                break

            length = struct.unpack('>I', h)[0]
            if length > 0:
                data = recvall(conn, length)
                if data is None:
                    continue
                pcm = np.frombuffer(data, dtype=np.float32)
                with playback_lock:  # �����޸Ļ�����
                    playback_buf += pcm.tolist()
                time.sleep(0.005)
            else:
                fl = recvall(conn, 4)
                if fl is None:
                    continue
                file_len = struct.unpack('>I', fl)[0]
                if file_len > 10 * 1024 * 1024:
                    print('[�����] �ļ���С�쳣')
                    continue
                wav = recvall(conn, file_len)
                if wav is None:
                    continue
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(SAVE_AUDIO_DIR, f"{timestamp}.wav")
                with open(path, 'wb') as f:
                    f.write(wav)
                print(f'[�����] �ѱ���¼���ļ���{path}')
                wav_count += 1
    except Exception as e:
        print(f'[�����] �����߳��쳣: {str(e)}')
    finally:
        try:
            conn.close()
        except:
            pass


def run_server():
    global running, conn

    with socket_context(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(1)
        print(f'[�����] �����˿� {PORT}')

        try:
            with sd.OutputStream(
                    samplerate=44100, channels=1,
                    dtype='float32', blocksize=AUDIO_CHUNK,
                    callback=audio_callback
            ) as stream:
                stream.start()

                while running:
                    try:
                        conn, addr = s.accept()
                        print(f'[�����] �ͻ��������ӣ�{addr}')
                        # �������������̴߳���ͻ���
                        net_thread = threading.Thread(target=network_thread, args=(conn,))
                        net_thread.daemon = True
                        net_thread.start()
                        # �ȴ������߳̽�����������
                        while net_thread.is_alive():
                            time.sleep(0.1)
                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        print(f'[�����] ���������쳣: {str(e)}')
                        continue
        except KeyboardInterrupt:
            print("\n[�����] �յ��ж��źţ����ڹر�...")
        except Exception as e:
            print(f'[�����] ��Ƶ���쳣: {str(e)}')
        finally:
            running = False
            # ȷ��������Դ�ر�
            conn.close()
            s.close()
            print('[�����] ���˳�')


if __name__ == '__main__':
    try:
        run_server()
    except KeyboardInterrupt:
        print("\n[�����] ������ֹ")
    except Exception as e:
        print(f'[�����] �������쳣: {str(e)}')