import sys
import serial
import pygame
import serial.tools.list_ports
from time import sleep, time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFormLayout, QPushButton, QLineEdit
from PyQt5.QtCore import QTimer

class GameSirController:
    HEADER = 0x06
    FOOTER = 0x17

    def __init__(self, ui_update_callback):
        self.ui_update_callback = ui_update_callback
        pygame.init()
        pygame.joystick.init()

        self.serial_port = None
        self.joystick = None
        self.running = True

        self.button_map = [
            "A", "B", "X", "Y",
            "L1", "R1",
            "SELECT", "START",
            "L3", "R3",
            "HOME"
        ]

        self.axis_map = [
            "左摇杆X", "左摇杆Y",
            "右摇杆X", "右摇杆Y",
            "L2", "R2"
        ]

        self.last_state = {
            "buttons": [0] * len(self.button_map),
            "axes": [0.0] * len(self.axis_map),
            "hat": (0, 0)
        }

        self.init_joystick()
        self.init_serial()

    def init_joystick(self):
        if pygame.joystick.get_count() == 0:
            print("错误：未检测到手柄设备！")
            self.running = False
            return

        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()

        print(f"已连接手柄: {self.joystick.get_name()}")

    def init_serial(self):
        ports = serial.tools.list_ports.comports()
        if not ports:
            print("错误：未找到可用串口！")
            self.running = False
            return

        print("可用串口列表:")
        for i, port in enumerate(ports):
            print(f"{i + 1}. {port.device}")

        port_index = 0
        if len(ports) > 1:
            try:
                port_index = int(input("选择串口(1-{}): ".format(len(ports)))) - 1
                port_index = max(0, min(port_index, len(ports) - 1))
            except:
                print("将使用默认串口")

        baudrate = 115200
        try:
            self.serial_port = serial.Serial(
                port=ports[port_index].device,
                baudrate=baudrate,
                timeout=0.1
            )
            print(f"已连接串口: {ports[port_index].device} @ {baudrate}bps")
        except Exception as e:
            print(f"串口连接失败: {e}")
            self.running = False

    def read_joystick(self):
        pygame.event.pump()
        buttons = [self.joystick.get_button(i) for i in range(self.joystick.get_numbuttons())]
        axes = []
        for i in range(self.joystick.get_numaxes()):
            axis_val = self.joystick.get_axis(i)
            if i in [1, 3]:
                axis_val = -axis_val
            axes.append(axis_val)
        hat = (0, 0)
        if self.joystick.get_numhats() > 0:
            hat = self.joystick.get_hat(0)
        return {"buttons": buttons, "axes": axes, "hat": hat}

    def has_state_changed(self, new_state):
        if new_state["buttons"] != self.last_state["buttons"]:
            return True
        for i, (new_val, last_val) in enumerate(zip(new_state["axes"], self.last_state["axes"])):
            if abs(new_val - last_val) > 0.05:
                return True
        if new_state["hat"] != self.last_state["hat"]:
            return True
        return False

    def create_data_packet(self, state):
        button_bytes = bytes(state["buttons"])
        axis_bytes = bytes([int((axis + 1.0) * 127.5) for axis in state["axes"]])
        hat_bytes = bytes(
            [1 if state["hat"][1] == 1 else 0, 1 if state["hat"][1] == -1 else 0,
             1 if state["hat"][0] == -1 else 0, 1 if state["hat"][0] == 1 else 0])
        return bytes([self.HEADER]) + button_bytes + axis_bytes + hat_bytes + bytes([self.FOOTER])

    def send_pid_packet(self, pid_values):
        if self.serial_port and self.serial_port.is_open:
            packet = [self.HEADER, 0x05] + pid_values + [0xFF] * (20 - len(pid_values)) + [self.FOOTER]
            try:
                self.serial_port.write(bytes(packet))
                print(f"已发送 PID 数据包: {packet}")
            except Exception as e:
                print(f"发送失败: {e}")

    def update_ui(self, state):
        self.ui_update_callback(state)

    def run(self):
        try:
            last_send_time = 0
            while self.running:
                current_time = time()
                current_state = self.read_joystick()
                if self.has_state_changed(current_state) and (current_time - last_send_time >= 0.1):
                    self.last_state = current_state
                    self.update_ui(current_state)
                    if self.serial_port and self.serial_port.is_open:
                        packet = self.create_data_packet(current_state)
                        try:
                            self.serial_port.write(packet)
                            last_send_time = current_time
                        except Exception as e:
                            print(f"发送失败: {e}")
                sleep(0.01)
        except KeyboardInterrupt:
            print("\n正在退出程序...")
        finally:
            self.cleanup()

    def cleanup(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        pygame.quit()


class ControllerUI(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("盖世小鸡手柄控制器")
        self.setGeometry(300, 300, 500, 500)

        self.layout = QVBoxLayout()

        self.button_layout = QFormLayout()
        self.button_labels = {}
        for button in self.controller.button_map:
            label = QLabel(f"{button}: 释放")
            self.button_labels[button] = label
            self.button_layout.addRow(button, label)
        self.layout.addLayout(self.button_layout)

        self.axis_layout = QFormLayout()
        self.axis_labels = {}
        for axis in self.controller.axis_map:
            label = QLabel(f"{axis}: 0.000")
            self.axis_labels[axis] = label
            self.axis_layout.addRow(axis, label)
        self.layout.addLayout(self.axis_layout)

        self.hat_label = QLabel("方向键: 上: False 下: False 左: False 右: False")
        self.layout.addWidget(self.hat_label)

        self.pid_inputs = []
        self.pid_layout = QHBoxLayout()
        for i in range(12):
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f"PID{i+1}")
            line_edit.setFixedWidth(40)
            self.pid_inputs.append(line_edit)
            self.pid_layout.addWidget(line_edit)
        self.layout.addLayout(self.pid_layout)

        self.send_pid_button = QPushButton("发送 PID 数据包")
        self.send_pid_button.clicked.connect(self.send_pid_data)
        self.layout.addWidget(self.send_pid_button)

        self.quit_button = QPushButton("退出")
        self.quit_button.clicked.connect(self.close)
        self.layout.addWidget(self.quit_button)

        self.setLayout(self.layout)

    def update_ui(self, state):
        for i, button in enumerate(self.controller.button_map):
            self.button_labels[button].setText(f"{button}: {'按下' if state['buttons'][i] else '释放'}")
        for i, axis in enumerate(self.controller.axis_map):
            self.axis_labels[axis].setText(f"{axis}: {state['axes'][i]:.3f}")
        hat = state['hat']
        self.hat_label.setText(f"方向键: 上: {hat[1] == 1} 下: {hat[1] == -1} 左: {hat[0] == -1} 右: {hat[0] == 1}")

    def send_pid_data(self):
        try:
            pid_values = [int(edit.text()) & 0xFF for edit in self.pid_inputs]
            if len(pid_values) != 12:
                raise ValueError("请输入12个整数")
            self.controller.send_pid_packet(pid_values)
        except Exception as e:
            print(f"PID 输入错误: {e}")


def main():
    app = QApplication(sys.argv)
    controller = GameSirController(ui_update_callback=None)
    ui = ControllerUI(controller)
    controller.ui_update_callback = ui.update_ui
    ui.show()
    controller.run()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()