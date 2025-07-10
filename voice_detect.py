import argparse
import functools
from mvector.predict import MVectorPredictor
from mvector.utils.utils import add_arguments, print_arguments
import numpy as np
import random
from pathlib import Path
from typing import List

# ===== 你可以在这里修改每组抽样多少个音频文件进行对比 =====
num_samples = 10

def find_max_with_index(arr):
    max_val = max(arr)
    max_index = arr.index(max_val) + 1
    return max_val, max_index

def get_subfolder_paths(root_dir: str) -> List[str]:
    root_path = Path(root_dir).resolve()
    subfolder_paths = []

    for entry in root_path.iterdir():
        if entry.is_dir():
            subfolder_paths.append(str(entry.resolve()))

    return sorted(subfolder_paths)

def get_audio_files(directory: str) -> List[str]:
    directory = Path(directory)
    if not directory.exists():
        raise ValueError(f"目录不存在: {directory}")
    return [
        str(file)
        for file in directory.glob("*")
        if file.suffix.lower() in ('.wav', '.mp3', '.flac')
    ]

def calculate_trimmed_mean(scores: List[float]) -> float:
    if len(scores) <= 2:
        return np.mean(scores) if scores else 0.0
    sorted_scores = sorted(scores)
    trimmed_scores = sorted_scores[1:-1]  # 去掉最大值和最小值
    return np.mean(trimmed_scores) if trimmed_scores else 0.0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="音频相似度组匹配")
    add_arg = functools.partial(add_arguments, argparser=parser)
    add_arg('configs',          str,    'voice_dataset/cam++.yml',   '配置文件')
    add_arg('use_gpu',          bool,   True,                        '是否使用GPU预测')
    add_arg('audio_path1',      str,    'received_data/audio/Bseal.wav', '预测第一个音频')
    add_arg('threshold',        float,  0.6,                         '判断是否为同一个人的阈值')
    add_arg('model_path',       str,    'voice_dataset/best_model',  '导出的预测模型文件路径')
    args = parser.parse_args()
    print_arguments(args=args)

    predictor = MVectorPredictor(
        configs=args.configs,
        model_path=args.model_path,
        use_gpu=args.use_gpu
    )

    subfolders = get_subfolder_paths('voice_dataset/data')

    print(f"共找到 {len(subfolders)} 个有效子目录（组）：")
    for idx, path in enumerate(subfolders):
        print(f"组 {idx+1}: {path}")

    animal_voices = [get_audio_files(p) for p in subfolders]
    voice_dist = []

    for i, files in enumerate(animal_voices):
        if not files:
            print(f"❗ 组 {i+1} 中没有音频文件，跳过")
            voice_dist.append(0.0)
            continue

        sample_files = files if len(files) <= num_samples else random.sample(files, num_samples)
        scores = []

        print(f"\n▶ 组 {i+1} 预测文件：")
        for file_path in sample_files:
            try:
                score = predictor.contrast(args.audio_path1, file_path)
                scores.append(score)
                print(f"   文件: {file_path} ，相似度: {score:.4f}")
            except Exception as e:
                print(f"❌ 对比失败: {file_path}，错误: {e}")

        avg_score = calculate_trimmed_mean(scores)
        voice_dist.append(avg_score)
        print(f"✅ 组 {i+1} 随机抽样 {len(scores)} 个文件，去除最高/最低后平均相似度：{avg_score:.4f}")

    if voice_dist:
        value, idx = find_max_with_index(voice_dist)
        matched_path = Path(subfolders[idx - 1])
        matched_folder_name = matched_path.name  # 只取文件夹名

        print(f"\n🔍 最大平均相似度: {value:.4f}，对应动物: {matched_folder_name}")
        if value > args.threshold:
            print(f"✅ 匹配成功，最相似的是动物: {matched_folder_name}，相似度为：{value:.4f}")
        else:
            print(f"⚠️ 无法确认是否匹配，仅最相似的动物是: {matched_folder_name}，相似度为：{value:.4f}")
    else:
        print("❗ 没有成功计算任何组的相似度")
