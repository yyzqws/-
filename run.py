import sys
import subprocess
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton,
                             QVBoxLayout, QWidget, QLabel, QFileDialog,
                             QMessageBox, QLineEdit)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.processes = {}  # 存储所有子进程
        self.init_ui()
        self.init_processes()

    def init_ui(self):
        self.setWindowTitle("流媒体控制中心")
        self.setGeometry(100, 100, 400, 380)

        layout = QVBoxLayout()

        self.status_label = QLabel("系统已就绪", self)
        layout.addWidget(self.status_label)

        self.audio_btn = QPushButton("传输音频流", self)
        self.audio_btn.clicked.connect(self.start_audio_stream)
        layout.addWidget(self.audio_btn)

        self.stereo_btn = QPushButton("传输双目视频流", self)
        self.stereo_btn.clicked.connect(self.start_stereo_stream)
        layout.addWidget(self.stereo_btn)

        self.file_label = QLabel("输入需要检测的文件:", self)
        layout.addWidget(self.file_label)

        self.file_input = QLineEdit(self)
        layout.addWidget(self.file_input)

        self.browse_btn = QPushButton("浏览...", self)
        self.browse_btn.clicked.connect(self.browse_file)
        layout.addWidget(self.browse_btn)

        self.detect_btn = QPushButton("检测音频", self)
        self.detect_btn.clicked.connect(self.detect_audio)
        layout.addWidget(self.detect_btn)

        # 按钮：打开外部切割音频程序
        self.open_cut_tool_btn = QPushButton("打开音频切割工具", self)
        self.open_cut_tool_btn.clicked.connect(self.open_cut_tool)
        layout.addWidget(self.open_cut_tool_btn)

        self.enhance_btn = QPushButton("批量图像增强", self)
        self.enhance_btn.clicked.connect(self.run_batch_enhance)
        layout.addWidget(self.enhance_btn)

        self.image_filter_btn = QPushButton("抓鱼程序", self)
        self.image_filter_btn.clicked.connect(self.run_image_filter)
        layout.addWidget(self.image_filter_btn)

        self.cut_zhu_btn = QPushButton("cut_zhu", self)
        self.cut_zhu_btn.clicked.connect(self.run_cut_zhu)
        layout.addWidget(self.cut_zhu_btn)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def run_cut_zhu(self):
        try:
            subprocess.Popen(['python', 'cut_zhu.py'])
            self.status_label.setText("cut_zhu.py 已启动")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法启动 cut_zhu.py: {e}")
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择音频文件", "received_data/cuts", "音频 (*.wav *.mp3)")
        if file_path:
            self.file_input.setText(os.path.basename(file_path))

    def init_processes(self):
        try:
            self.processes['handle'] = subprocess.Popen(['python', 'handle.py'])
            self.processes['test32'] = subprocess.Popen(['python', 'test_32.py'])
            self.status_label.setText("已启动手柄与32测试程序")
        except Exception as e:
            self.status_label.setText(f"启动失败: {e}")
            QMessageBox.critical(self, "错误", f"无法启动初始程序: {e}")

    def run_batch_enhance(self):
        # 选择多个图像文件
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择要增强的图像", "received_data/stero", "图像文件 (*.jpg *.png *.bmp)"
        )

        if not file_paths:
            return

        output_dir = QFileDialog.getExistingDirectory(
            self, "选择输出文件夹", "result/super"
        )
        if not output_dir:
            return

        success_count = 0
        for input_path in file_paths:
            try:
                base_name = os.path.basename(input_path)
                output_path = os.path.join(output_dir, base_name)

                process = subprocess.Popen([
                    'realesrgan-ncnn-vulkan.exe',
                    '-i', input_path,
                    '-o', output_path
                ])
                process.wait()
                success_count += 1
            except Exception as e:
                QMessageBox.warning(self, "警告", f"处理失败: {input_path}\n错误: {e}")

        self.status_label.setText(f"批量增强完成，成功处理 {success_count} 张图像")
        QMessageBox.information(self, "完成", f"共处理成功 {success_count} 张图像")
    def stop_other_streams(self, exclude):
        for name in ['video', 'audio', 'stereo']:
            if name != exclude and name in self.processes:
                proc = self.processes[name]
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait()
                    self.status_label.setText(f"已停止{name}流")


    def start_audio_stream(self):
        self.stop_other_streams('audio')
        try:
            self.processes['audio'] = subprocess.Popen(['python', 'tcp_receive_voice.py'])
            self.status_label.setText("音频流传输已启动")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法启动音频流: {e}")

    def run_image_filter(self):
        try:
            subprocess.Popen(['python', 'image_filter.py'])
            self.status_label.setText("抓鱼程序已启动")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法启动抓鱼程序: {e}")

    def start_stereo_stream(self):
        self.stop_other_streams('stereo')
        try:
            self.processes['stereo'] = subprocess.Popen(['python', 'tcp_receive_stero.py'])
            self.status_label.setText("立体声流传输已启动")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法启动立体声流: {e}")

    def detect_audio(self):
        file_name = self.file_input.text().strip()
        if not file_name:
            QMessageBox.warning(self, "警告", "请输入要检测的文件名")
            return
        audio_path = os.path.join("received_data/cuts", file_name)
        if not os.path.exists(audio_path):
            QMessageBox.warning(self, "错误", f"文件{audio_path}不存在")
            return
        try:
            self.processes['detect'] = subprocess.Popen(
                ['python', 'voice_detect.py', '--audio_path1', audio_path])
            self.status_label.setText(f"正在检测音频文件: {file_name}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法启动音频检测: {e}")

    def open_cut_tool(self):
        """打开外部音频切割程序"""
        try:
            subprocess.Popen(['python', '切割音频.py'])
            self.status_label.setText("音频切割工具已打开")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法启动音频切割工具: {e}")

    def closeEvent(self, event):
        for name, proc in self.processes.items():
            if proc.poll() is None:
                proc.terminate()
                proc.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
