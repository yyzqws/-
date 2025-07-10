import matplotlib
matplotlib.use('TkAgg')

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from tkinter import Tk
from tkinter.filedialog import askopenfilename
import scipy.io.wavfile as wav
import os

def plot_and_select(filename):
    rate, data = wav.read(filename)
    times = np.arange(len(data)) / float(rate)

    print("❗ 需要两次点击设置起点和终点")

    fig, ax = plt.subplots()
    ax.plot(times, data)
    ax.set_title("点击两次以选择起点和终点")
    ax.set_xlabel("时间 (秒)")
    ax.set_ylabel("幅度")

    coords = []

    def onclick(event):
        if event.xdata is not None:
            coords.append(event.xdata)
            print(f"已点击时间: {event.xdata:.2f} 秒，已点击次数: {len(coords)}")
            if len(coords) == 2:
                plt.close()

    cid = fig.canvas.mpl_connect('button_press_event', onclick)
    plt.show()

    if len(coords) < 2:
        print("❌ 点击次数不足2次，退出")
        return None, None

    start, end = sorted(coords)
    print(f"选定切割区间: {start:.2f} 秒 - {end:.2f} 秒")
    return start, end

def cut_wav(input_file, start_sec, end_sec, output_file):
    rate, data = wav.read(input_file)
    start_sample = int(start_sec * rate)
    end_sample = int(end_sec * rate)
    cut_data = data[start_sample:end_sample]

    wav.write(output_file, rate, cut_data)
    print(f"✅ 已保存切割音频到：{output_file}")

if __name__ == "__main__":
    Tk().withdraw()
    audio_file = askopenfilename(title="选择一个WAV音频文件", filetypes=[("WAV音频文件", "*.wav")])
    if not audio_file:
        print("❌ 未选择音频文件，程序退出")
        exit()

    print(f"选择的音频文件: {audio_file}")
    start, end = plot_and_select(audio_file)
    if start is None or end is None:
        exit()

    # 创建保存目录
    output_dir = Path("received_data/cuts")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / (Path(audio_file).stem + f".wav")
    cut_wav(audio_file, start, end, str(output_path))
