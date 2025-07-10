import sys
import os
import cv2
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt


def cvimg_to_qpixmap(cv_img):
    """Convert OpenCV image to QPixmap"""
    height, width, channel = cv_img.shape
    bytes_per_line = 3 * width
    q_img = QImage(cv_img.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
    return QPixmap.fromImage(q_img)


def crop_image(img, mode='left', percent=0.7):
    h, w, _ = img.shape
    crop_w = int(w * percent)
    if mode == 'left':
        x1 = 0
    elif mode == 'center':
        x1 = (w - crop_w) // 2
    elif mode == 'right':
        x1 = w - crop_w
    else:
        raise ValueError("mode must be 'left', 'center', or 'right'")
    cut_image = img[:, x1:x1 + crop_w]
    return cut_image


class ImageCropApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("单张图片裁剪器")
        self.original_img = None
        self.image_path = ""

        self.image_label = QLabel("请选择图片文件")
        self.image_label.setAlignment(Qt.AlignCenter)

        # Buttons
        self.btn_load = QPushButton("选择图片")
        self.btn_left = QPushButton("左 70%")
        self.btn_center = QPushButton("中间 70%")
        self.btn_right = QPushButton("右 70%")

        # Layouts
        crop_layout = QHBoxLayout()
        crop_layout.addWidget(self.btn_left)
        crop_layout.addWidget(self.btn_center)
        crop_layout.addWidget(self.btn_right)

        layout = QVBoxLayout()
        layout.addWidget(self.btn_load)
        layout.addWidget(self.image_label)
        layout.addLayout(crop_layout)
        self.setLayout(layout)

        # Connect signals
        self.btn_load.clicked.connect(self.load_image)
        self.btn_left.clicked.connect(lambda: self.crop_and_save("left"))
        self.btn_center.clicked.connect(lambda: self.crop_and_save("center"))
        self.btn_right.clicked.connect(lambda: self.crop_and_save("right"))

    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片文件", "received_data/image", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return
        self.image_path = file_path
        self.original_img = cv2.imread(file_path)
        pixmap = cvimg_to_qpixmap(self.original_img)
        self.image_label.setPixmap(pixmap.scaled(
            self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def crop_and_save(self, mode):
        if self.original_img is None:
            return

        cropped = crop_image(self.original_img, mode=mode)
        base_name = os.path.splitext(os.path.basename(self.image_path))[0]
        save_dir = os.path.join("received_data", "cut_image")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"{base_name}.jpg")
        cv2.imwrite(save_path, cropped)
        print(f"[保存成功] {save_path}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ImageCropApp()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
