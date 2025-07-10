import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget,
                             QPushButton, QFileDialog, QLabel, QHBoxLayout,
                             QProgressBar, QSlider, QDoubleSpinBox, QGroupBox,
                             QGridLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
import pyqtgraph as pg
import soundfile as sf
import sounddevice as sd
from scipy.signal import resample


class AudioLoaderThread(QThread):
    loaded = pyqtSignal(np.ndarray, int, str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit(10)
            audio_data, sample_rate = sf.read(self.file_path, always_2d=True)
            self.progress.emit(30)

            # 取左声道
            audio_data = audio_data[:, 0]
            self.progress.emit(50)

            self.loaded.emit(audio_data, sample_rate, self.file_path)
            self.progress.emit(100)
        except Exception as e:
            self.error.emit(str(e))


class AudioClipper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("高级音频截取工具")
        self.setGeometry(100, 100, 1200, 800)

        # 音频数据
        self.audio_data = None
        self.sample_rate = None
        self.current_selection = [0, 0]
        self.playback_obj = None
        self.display_data = None
        self.is_playing = False

        # 主部件和布局
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)

        # 顶部控制面板
        self.create_control_panel()

        # 波形显示区域
        self.create_waveform_display()

        # 底部精细控制面板
        self.create_precision_panel()

        # 初始化状态
        self.status_label.setText("请加载音频文件")

        # 性能优化设置
        pg.setConfigOptions(useOpenGL=True)
        pg.setConfigOptions(antialias=True)

        # 播放位置更新定时器
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.update_playback_position)

    def create_control_panel(self):
        """创建顶部控制面板"""
        control_group = QGroupBox("控制面板")
        control_layout = QHBoxLayout()

        self.load_btn = QPushButton("加载音频")
        self.load_btn.clicked.connect(self.load_audio)
        control_layout.addWidget(self.load_btn)

        self.play_btn = QPushButton("播放")
        self.play_btn.clicked.connect(self.toggle_playback)
        self.play_btn.setEnabled(False)
        control_layout.addWidget(self.play_btn)

        self.play_selection_btn = QPushButton("播放选区")
        self.play_selection_btn.clicked.connect(self.play_selection)
        self.play_selection_btn.setEnabled(False)
        control_layout.addWidget(self.play_selection_btn)

        self.save_btn = QPushButton("保存选区")
        self.save_btn.clicked.connect(self.save_selection)
        self.save_btn.setEnabled(False)
        control_layout.addWidget(self.save_btn)

        self.zoom_in_btn = QPushButton("放大")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        control_layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QPushButton("缩小")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        control_layout.addWidget(self.zoom_out_btn)

        control_group.setLayout(control_layout)
        self.layout.addWidget(control_group)

        # 进度条和状态标签
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel()
        self.layout.addWidget(self.status_label)

    def create_waveform_display(self):
        """创建波形显示区域"""
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', '振幅')
        self.plot_widget.setLabel('bottom', '时间 (秒)')
        self.plot_widget.showGrid(x=True, y=True)

        # 启用鼠标交互
        self.plot_widget.setMouseEnabled(x=True, y=False)
        self.plot_widget.scene().sigMouseClicked.connect(self.on_plot_clicked)

        # 创建波形曲线
        self.plot_item = self.plot_widget.plot(pen='b')

        # 创建选区
        self.region = pg.LinearRegionItem()
        self.region.setZValue(10)
        self.region.sigRegionChanged.connect(self.region_changed)
        self.plot_widget.addItem(self.region)

        # 创建播放位置指示器
        self.playback_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('r', width=2))
        self.plot_widget.addItem(self.playback_line)

        self.layout.addWidget(self.plot_widget, stretch=1)

    def create_precision_panel(self):
        """创建底部精细控制面板"""
        precision_group = QGroupBox("精确控制")
        precision_layout = QGridLayout()

        # 开始时间控制
        self.start_time_label = QLabel("开始时间 (s):")
        precision_layout.addWidget(self.start_time_label, 0, 0)

        self.start_time_spin = QDoubleSpinBox()
        self.start_time_spin.setRange(0, 0)
        self.start_time_spin.setSingleStep(0.01)
        self.start_time_spin.valueChanged.connect(self.update_selection_from_spinboxes)
        precision_layout.addWidget(self.start_time_spin, 0, 1)

        # 结束时间控制
        self.end_time_label = QLabel("结束时间 (s):")
        precision_layout.addWidget(self.end_time_label, 1, 0)

        self.end_time_spin = QDoubleSpinBox()
        self.end_time_spin.setRange(0, 0)
        self.end_time_spin.setSingleStep(0.01)
        self.end_time_spin.valueChanged.connect(self.update_selection_from_spinboxes)
        precision_layout.addWidget(self.end_time_spin, 1, 1)

        # 选区时长显示
        self.duration_label = QLabel("选区时长: 0.00s")
        precision_layout.addWidget(self.duration_label, 2, 0, 1, 2)

        # 导航滑块
        self.nav_slider = QSlider(Qt.Horizontal)
        self.nav_slider.setRange(0, 100)
        self.nav_slider.valueChanged.connect(self.on_nav_slider_changed)
        precision_layout.addWidget(self.nav_slider, 3, 0, 1, 2)

        precision_group.setLayout(precision_layout)
        self.layout.addWidget(precision_group)

    def load_audio(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开音频文件", "", "音频文件 (*.wav *.mp3 *.flac *.ogg)"
        )

        if file_path:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("正在加载音频...")
            QApplication.processEvents()

            self.loader_thread = AudioLoaderThread(file_path)
            self.loader_thread.loaded.connect(self.on_audio_loaded)
            self.loader_thread.error.connect(self.on_load_error)
            self.loader_thread.progress.connect(self.progress_bar.setValue)
            self.loader_thread.start()

    def on_audio_loaded(self, audio_data, sample_rate, file_path):
        self.audio_data = audio_data
        self.sample_rate = sample_rate

        # 为显示创建降采样数据
        self.display_factor = max(1, len(audio_data) // (sample_rate * 30))  # 30秒显示长度
        self.display_data = audio_data[::self.display_factor]

        self.plot_audio()
        self.status_label.setText(
            f"已加载: {file_path} | 采样率: {sample_rate}Hz | 时长: {len(audio_data) / sample_rate:.2f}s")

        # 启用控制按钮
        self.play_btn.setEnabled(True)
        self.play_selection_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

        # 设置初始选择区域为整个音频
        duration = len(audio_data) / sample_rate
        self.region.setRegion([0, duration])
        self.current_selection = [0, duration]

        # 更新精细控制
        self.start_time_spin.setRange(0, duration)
        self.end_time_spin.setRange(0, duration)
        self.start_time_spin.setValue(0)
        self.end_time_spin.setValue(duration)

        self.progress_bar.setVisible(False)

    def on_load_error(self, error_msg):
        self.status_label.setText(f"错误: {error_msg}")
        self.progress_bar.setVisible(False)

    def plot_audio(self):
        if self.audio_data is None or self.display_data is None:
            return

        time_axis = np.linspace(0, len(self.audio_data) / self.sample_rate, len(self.display_data))
        self.plot_item.setData(time_axis, self.display_data)

        # 自动调整视图范围
        self.plot_widget.setXRange(0, len(self.audio_data) / self.sample_rate)
        self.plot_widget.enableAutoRange('y')

    def region_changed(self):
        self.current_selection = self.region.getRegion()
        self.start_time_spin.setValue(self.current_selection[0])
        self.end_time_spin.setValue(self.current_selection[1])
        self.update_duration_label()

    def update_selection_from_spinboxes(self):
        start = self.start_time_spin.value()
        end = self.end_time_spin.value()

        if start >= end:
            if self.sender() == self.start_time_spin:
                self.end_time_spin.setValue(start + 0.01)
            else:
                self.start_time_spin.setValue(end - 0.01)
            return

        self.current_selection = [start, end]
        self.region.setRegion(self.current_selection)
        self.update_duration_label()

    def update_duration_label(self):
        duration = self.current_selection[1] - self.current_selection[0]
        self.duration_label.setText(f"选区时长: {duration:.2f}s")

    def on_plot_clicked(self, event):
        if self.audio_data is None:
            return

        pos = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
        x = pos.x()

        # 如果点击在选区左侧，移动选区开始
        if x < self.current_selection[0] + (self.current_selection[1] - self.current_selection[0]) / 2:
            self.current_selection[0] = max(0, x)
        else:
            self.current_selection[1] = min(len(self.audio_data) / self.sample_rate, x)

        self.region.setRegion(self.current_selection)
        self.start_time_spin.setValue(self.current_selection[0])
        self.end_time_spin.setValue(self.current_selection[1])

    def toggle_playback(self):
        if self.is_playing:
            self.stop_playback()
        else:
            self.play_audio()

    def play_audio(self):
        if self.audio_data is None:
            return

        self.stop_playback()
        self.is_playing = True
        self.play_btn.setText("停止")

        self.playback_obj = sd.play(self.audio_data, self.sample_rate)
        self.playback_timer.start(50)  # 每50ms更新一次播放位置

        duration = len(self.audio_data) / self.sample_rate
        self.status_label.setText(f"正在播放整个音频 (0.00/{duration:.2f}s)...")

    def play_selection(self):
        if self.audio_data is None or self.current_selection is None:
            return

        start, end = self.current_selection
        start_sample = int(start * self.sample_rate)
        end_sample = int(end * self.sample_rate)

        if end_sample - start_sample < 100:
            self.status_label.setText("选区太短!")
            return

        self.stop_playback()
        self.is_playing = True
        self.play_selection_btn.setText("停止")

        selection = self.audio_data[start_sample:end_sample]
        self.playback_obj = sd.play(selection, self.sample_rate)
        self.playback_timer.start(50)

        duration = end - start
        self.status_label.setText(f"正在播放选区 ({start:.2f}-{end:.2f}s, {duration:.2f}s)...")

    def stop_playback(self):
        if self.playback_obj is not None:
            sd.stop()
            self.playback_obj = None
        self.is_playing = False
        self.play_btn.setText("播放")
        self.play_selection_btn.setText("播放选区")
        self.playback_timer.stop()
        self.playback_line.setValue(0)

    def update_playback_position(self):
        if self.playback_obj is None:
            return

        # 获取当前播放位置
        current_pos = sd.get_stream().time

        # 更新播放位置线
        self.playback_line.setValue(current_pos)

        # 更新状态标签
        if self.is_playing:
            if self.play_selection_btn.text() == "停止":
                start, end = self.current_selection
                self.status_label.setText(f"正在播放选区 ({start:.2f}-{end:.2f}s, 当前位置: {current_pos:.2f}s)")
            else:
                duration = len(self.audio_data) / self.sample_rate
                self.status_label.setText(f"正在播放整个音频 ({current_pos:.2f}/{duration:.2f}s)")

    def save_selection(self):
        if self.audio_data is None or self.current_selection is None:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存选区", "", "WAV 文件 (*.wav);;FLAC 文件 (*.flac);;OGG 文件 (*.ogg)"
        )

        if file_path:
            start, end = self.current_selection
            start_sample = int(start * self.sample_rate)
            end_sample = int(end * self.sample_rate)

            selection = self.audio_data[start_sample:end_sample]

            try:
                sf.write(file_path, selection, self.sample_rate)
                self.status_label.setText(f"已保存选区到: {file_path}")
            except Exception as e:
                self.status_label.setText(f"保存错误: {str(e)}")

    def zoom_in(self):
        if self.audio_data is None:
            return

        view_range = self.plot_widget.viewRange()[0]
        center = (view_range[0] + view_range[1]) / 2
        new_width = (view_range[1] - view_range[0]) * 0.8
        self.plot_widget.setXRange(center - new_width / 2, center + new_width / 2)

    def zoom_out(self):
        if self.audio_data is None:
            return

        view_range = self.plot_widget.viewRange()[0]
        center = (view_range[0] + view_range[1]) / 2
        new_width = (view_range[1] - view_range[0]) * 1.2
        duration = len(self.audio_data) / self.sample_rate
        new_width = min(new_width, duration)
        self.plot_widget.setXRange(max(0, center - new_width / 2), min(duration, center + new_width / 2))

    def on_nav_slider_changed(self, value):
        if self.audio_data is None:
            return

        duration = len(self.audio_data) / self.sample_rate
        current_pos = duration * value / 100
        self.playback_line.setValue(current_pos)

        # 如果正在播放，跳转到指定位置
        if self.is_playing and self.playback_obj is not None:
            sd.get_stream().time = current_pos

    def closeEvent(self, event):
        self.stop_playback()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置高DPI支持
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    window = AudioClipper()
    window.show()
    sys.exit(app.exec_())