# -*- coding: gbk -*-
import serial
SERIAL_PORT  = 'COM3'
BAUDRATE     = 115200
TIMEOUT      = 0.01

ser  = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=TIMEOUT)

def parse_gamepad_packet(packet):
    if len(packet) != 23:
        raise ValueError("数据包长度不正确，应为23字节")

    if packet[0] != 0x06 or packet[-1] != 0x17:
        raise ValueError("数据包起始或结束字节不正确")

    # 按钮名称列表
    button_names = ["A", "B", "X", "Y", "L1", "R1", "SELECT", "START", "L3", "R3", "HOME", "UNKNOWN"]

    # 解析按钮状态
    buttons = {}
    for i, name in enumerate(button_names):
        buttons[name] = bool(packet[1 + i])

    return {
        "buttons": buttons,
    }
while True:
  if ser.in_waiting:
    data_packet = ser.read(23)
    try:
        gamepad_state = parse_gamepad_packet(data_packet)
        # 视频流传输
        if gamepad_state["buttons"]["L1"] == True:
            print("L1")
            ser.write(b'\xFF\x07\xFE')
        # 拍摄大图
        if gamepad_state["buttons"]["A"] == True:
            print("A")
            ser.write(b'\xFF\x01\xFE')

        # 音频流传输
        if gamepad_state["buttons"]["R1"] == True:
            print("R1")
            ser.write(b'\xFF\x08\xFE')

        # 音频流播放
        if gamepad_state["buttons"]["B"] == True:
            print("B")
            ser.write(b'\xFF\x04\xFE')
        # 音频录制
        if gamepad_state["buttons"]["X"] == True:
            print("X")
            ser.write(b'\xFF\x05\xFE')
        # 音频停止录制
        if gamepad_state["buttons"]["Y"] == True:
            print("Y")
            ser.write(b'\xFF\x06\xFE')


    except ValueError as e:
        print("解析数据包时发生错误:", e)

