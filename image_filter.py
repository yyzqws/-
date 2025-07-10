from ultralytics import YOLO
import argparse
import os
import shutil
import cv2
import numpy as np

def get_all_path_pairs(input_paths, output_path):
    if not isinstance(input_paths, list):
        input_paths = [input_paths]
    inputs = []
    outputs = []

    for path in input_paths:
        if not os.path.exists(path):
            print(f"Warning: Input path '{path}' does not exist, skipping.")
            continue
        for inp in os.listdir(path):
            if inp.endswith(('.jpg', '.png', '.jpeg')):
                in_full = os.path.join(path, inp)
                out_full = os.path.join(output_path, inp)
                inputs.append(in_full)
                outputs.append(out_full)

    return dict(zip(inputs, outputs))
def read_classes(file):
    with open(file, 'r') as f:
        lines = f.read().split('\n')
    id2name = {i:name for i, name in enumerate(lines) if name}
    name2id = {name:i for i, name in enumerate(lines) if name}
    return id2name, name2id

def parse_arg():
    parser = argparse.ArgumentParser(description="Copy images containing specified classes to target folder")
    parser.add_argument('-i', type=str, default='received_data/stero', help='Input image path')
    parser.add_argument('-o', type=str, default='result/fish', help='Output image path')
    parser.add_argument('-t', type=str, default='Fish,Shark,Goldenfish', help='Target classes to filter')
    parser.add_argument('-f', type=str, default='classes.txt', help='txt file with classes one per line')
    args = parser.parse_args()
    return args

def calculate_crop_region(box, img_width, img_height, target_coverage=0.3):
    """Calculate crop region centered around the fish with target coverage percentage"""
    x1, y1, x2, y2 = box
    # Calculate box dimensions
    box_width = x2 - x1
    box_height = y2 - y1
    
    # Calculate desired crop area based on target coverage
    desired_area = (box_width * box_height) / target_coverage
    
    # Calculate crop dimensions (square crop)
    crop_size = int(np.sqrt(desired_area))
    
    # Get center of the fish box
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    
    # Calculate crop coordinates
    x1_crop = max(0, center_x - crop_size // 2)
    y1_crop = max(0, center_y - crop_size // 2)
    x2_crop = min(img_width, center_x + crop_size // 2)
    y2_crop = min(img_height, center_y + crop_size // 2)
    
    # Adjust if we're at image boundaries
    if x2_crop - x1_crop < crop_size:
        if x1_crop == 0:
            x2_crop = min(img_width, x1_crop + crop_size)
        else:
            x1_crop = max(0, x2_crop - crop_size)
    
    if y2_crop - y1_crop < crop_size:
        if y1_crop == 0:
            y2_crop = min(img_height, y1_crop + crop_size)
        else:
            y1_crop = max(0, y2_crop - crop_size)
    
    return int(x1_crop), int(y1_crop), int(x2_crop), int(y2_crop)

def resize_if_small(image, min_width=640, min_height=480):
    """Resize image if it's smaller than specified dimensions"""
    height, width = image.shape[:2]
    
    if width < min_width or height < min_height:
        # Calculate scaling factors
        scale_width = max(1.0, min_width / width)
        scale_height = max(1.0, min_height / height)
        scale = max(scale_width, scale_height)
        
        # Calculate new dimensions
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # Resize image
        resized_img = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        print(f"Resized image from {width}x{height} to {new_width}x{new_height}")
        return resized_img
    return image

def main(model, args):
    # 多个输入目录
    input_paths = ['received_data/stero', 'received_data/image', 'received_data/fish']
    pairs = get_all_path_pairs(input_paths, args.o)
    target_classes = set(args.t.split(','))
    id2name, name2id = read_classes(args.f)
    print("开始抓鱼")

    for inp, outp in pairs.items():
        img = cv2.imread(inp)
        if img is None:
            continue

        img_height, img_width = img.shape[:2]
        results = model.predict(inp, verbose=False)
        fish_detected = False

        for r in results:
            if r.boxes is not None:
                for box, cls_id in zip(r.boxes.xyxy, r.boxes.cls):
                    cls_name = id2name.get(int(cls_id), '')
                    if cls_name in target_classes:
                        fish_detected = True
                        box = box.tolist()

                        x1, y1, x2, y2 = calculate_crop_region(box, img_width, img_height)
                        cropped_img = img[y1:y2, x1:x2]
                        resized_img = resize_if_small(cropped_img)

                        cv2.imwrite(outp, resized_img)
                        print(f"Processed and saved {inp} -> {outp}")
                        break  # 只处理一条鱼
                if fish_detected:
                    break

if __name__ == '__main__':
    model = YOLO("yolov8x-oiv7.pt")
    args = parse_arg()
    main(model, args)