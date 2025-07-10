# -*- coding: gbk -*-
import socket
import struct
import threading
import os
import numpy as np
import sounddevice as sd
import time
from contextlib import contextmanager

# —— 配置 ——
HOST, PORT = '0.0.0.0', 5001
SAVE_AUDIO_DIR = 'received_data/audio'
AUDIO_CHUNK = 1024
SOCKET_TIMEOUT = 1  # 新增socket超时设置

os.makedirs(SAVE_AUDIO_DIR, exist_ok=True)

# —— 全局状态 ——
playback_buf = []
playback_lock = threading.Lock()  # 新增播放缓冲区锁
running = True
conn = None  # 新增连接对象引用


@contextmanager
def socket_context(*args, **kwargs):
    """socket上下文管理器"""
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
    with playback_lock:  # 加锁访问缓冲区
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
            print(f'[服务端] 接收数据异常: {str(e)}')
            return None
    return data if len(data) == n else None


def network_thread(conn):
    global playback_buf, running
    wav_count = 1
    print('[服务端] 网络线程已启动，等待数据...')

    try:
        conn.settimeout(SOCKET_TIMEOUT)  # 设置socket超时
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
                with playback_lock:  # 加锁修改缓冲区
                    playback_buf += pcm.tolist()
                time.sleep(0.005)
            else:
                fl = recvall(conn, 4)
                if fl is None:
                    continue
                file_len = struct.unpack('>I', fl)[0]
                if file_len > 10 * 1024 * 1024:
                    print('[服务端] 文件大小异常')
                    continue
                wav = recvall(conn, file_len)
                if wav is None:
                    continue
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(SAVE_AUDIO_DIR, f"{timestamp}.wav")
                with open(path, 'wb') as f:
                    f.write(wav)
                print(f'[服务端] 已保存录制文件：{path}')
                wav_count += 1
    except Exception as e:
        print(f'[服务端] 网络线程异常: {str(e)}')
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
        print(f'[服务端] 监听端口 {PORT}')

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
                        print(f'[服务端] 客户端已连接：{addr}')
                        # 启动独立网络线程处理客户端
                        net_thread = threading.Thread(target=network_thread, args=(conn,))
                        net_thread.daemon = True
                        net_thread.start()
                        # 等待网络线程结束或新连接
                        while net_thread.is_alive():
                            time.sleep(0.1)
                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        print(f'[服务端] 接受连接异常: {str(e)}')
                        continue
        except KeyboardInterrupt:
            print("\n[服务端] 收到中断信号，正在关闭...")
        except Exception as e:
            print(f'[服务端] 音频流异常: {str(e)}')
        finally:
            running = False
            # 确保所有资源关闭
            conn.close()
            s.close()
            print('[服务端] 已退出')


if __name__ == '__main__':
    try:
        run_server()
    except KeyboardInterrupt:
        print("\n[服务端] 程序终止")
    except Exception as e:
        print(f'[服务端] 主程序异常: {str(e)}')