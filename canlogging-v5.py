import can
import csv
import os
import time
from datetime import datetime, timedelta

import subprocess

vcu_instruction = False

def check_vcu_running():
    return vcu_instruction

def start_can_interface():
    try:
        subprocess.run(
            ["sudo", "ip", "link", "set", "can0", "up", "type", "can", "bitrate", "1000000"],
            check=True
        )
        print("CAN0 interface started.")
    except subprocess.CalledProcessError:
        print("Failed to start CAN0 interface.")
    
    try:
        subprocess.run(
            ["sudo", "ip", "link", "set", "can1", "up", "type", "can", "bitrate", "1000000"],
            check=True
        )
        print("CAN1 interface started.")
    except subprocess.CalledProcessError:
        print("Failed to start CAN1 interface.")

def connect_can(bus_channel='can0'):
    while True:
        try:
            return can.interface.Bus(channel=bus_channel, bustype='socketcan')
        except OSError:
            print("CAN not available, retrying in 5 sec...")
            time.sleep(5)

def new_csv_writer(base_dir, base_name):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(base_dir, f"{base_name}_{timestamp}.csv")
    f = open(filename, 'w', newline='')
    writer = csv.writer(f)
    writer.writerow(["Time Stamp", "ID", "Extended", "Dir", "Bus", "LEN", "D1",
                     "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10",
                     "D11", "D12"])
    return f, writer

def main():
    base_dir = "/home/pi/Desktop/RPI_Desktop/LOGS"
    os.makedirs(base_dir, exist_ok=True)

    bus0 = connect_can('can0')
    bus1 = connect_can('can1')
    
    
    recording = False
    recording_start_time = datetime.now()
    file, writer = new_csv_writer(base_dir, "can_log")
    rotate_at = recording_start_time + timedelta(minutes=20)
    last_status_send = 0
    
    print("CAN Logger started for CAN0 and CAN1 and wait for recording!")
    # print(f"Recording started at {recording_start_time}")
    print("Wait for VCU running!")
    print("You can still use control commands (0x420: 01=start, 02=stop)...")

    global vcu_instruction
    vcu_last = check_vcu_running()
    while True:
        # 從兩個 CAN bus 接收訊息
        msg0 = bus0.recv(timeout=0.001)  # 使用較短的 timeout
        msg1 = bus1.recv(timeout=0.001)
        
        # 檢查 VCU 指令 (從 can0)
        if msg0 is not None and hasattr(msg0, 'arbitration_id') and msg0.arbitration_id == 0x281 and len(msg0.data) > 0:
            vcu_instruction = msg0.data[0] & 0x20
        # 也檢查 can1 的 VCU 指令
        if msg1 is not None and hasattr(msg1, 'arbitration_id') and msg1.arbitration_id == 0x281 and len(msg1.data) > 0:
            vcu_instruction = msg1.data[0] & 0x20

        vcu_running = check_vcu_running()
        # VCU 狀態 edge: False -> True，強制新開檔記錄
        if vcu_running and not vcu_last:
            print("VCU狀態由False變True，強制新開檔記錄！")
            if file:
                file.close()
            recording_start_time = datetime.now()
            file, writer = new_csv_writer(base_dir, "can_log_vcu")
            rotate_at = recording_start_time + timedelta(minutes=20)
            recording = True
            print(f"Recording started at {recording_start_time}")
        # VCU 狀態 edge: True -> False，自動關閉記錄
        elif not vcu_running and vcu_last:
            print("VCU狀態由True變False，自動關閉記錄！")
            if recording and file:
                file.close()
                file = None
                writer = None
            recording = False
            recording_start_time = None
            print(f"Recording stopped at {datetime.now()}")
            print("Waiting for VCU or manual start...")
        vcu_last = vcu_running

        # VCU True: 只能自動記錄，不能被0x420打斷
        if vcu_running:
            if not recording:
                print("VCU running, auto start recording!")
                recording_start_time = datetime.now()
                file, writer = new_csv_writer(base_dir, "can_log")
                rotate_at = recording_start_time + timedelta(minutes=20)
                recording = True
                print(f"Recording started at {recording_start_time}")
        else:
            # VCU False: 0x420可控制記錄 (檢查兩個 CAN bus)
            for msg in [msg0, msg1]:
                if msg is not None and hasattr(msg, 'arbitration_id') and msg.arbitration_id == 0x420:
                    data_bytes = list(msg.data)
                    if len(data_bytes) > 0:
                        first_byte = data_bytes[0]
                        if first_byte == 0x01:
                            if not recording:
                                print("Start recording command received!")
                                recording_start_time = datetime.now()
                                file, writer = new_csv_writer(base_dir, "can_log")
                                rotate_at = recording_start_time + timedelta(minutes=20)
                                recording = True
                                print(f"Recording started at {recording_start_time}")
                            else:
                                print("Already recording, ignoring start command")
                        elif first_byte == 0x02:
                            if recording:
                                print("Stop recording command received!")
                                if file:
                                    file.close()
                                    file = None
                                    writer = None
                                recording = False
                                recording_start_time = None
                                print(f"Recording stopped at {datetime.now()}")
                                print("Waiting for next start command...")
                            else:
                                print("Not recording, ignoring stop command")
                    break  # 只處理一次控制指令

        try:
            # 2. 保留原本的 CAN 指令控制（已在主邏輯處理，這裡只處理寫檔與狀態訊息）
            current_time = time.time()
            if current_time - last_status_send >= 1.0:
                try:
                    if recording and recording_start_time:
                        timestamp = int(recording_start_time.timestamp())
                        data = [0x01]
                        data.extend([
                            (timestamp >> 0) & 0xFF,
                            (timestamp >> 8) & 0xFF,
                            (timestamp >> 16) & 0xFF,
                            (timestamp >> 24) & 0xFF,
                            0x00, 0x00, 0x00
                        ])
                        status_msg = can.Message(arbitration_id=0x421, data=data, is_extended_id=False)
                        bus0.send(status_msg)  # 從 can0 發送狀態
                    else:
                        data = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
                        status_msg = can.Message(arbitration_id=0x421, data=data, is_extended_id=False)
                        bus0.send(status_msg)  # 從 can0 發送狀態
                    last_status_send = current_time
                except Exception as e:
                    print(f"Failed to send status message: {e}")

            # 記錄 can0 的訊息
            if recording and writer and msg0 is not None and hasattr(msg0, 'arbitration_id'):
                timestamp = int(time.time() * 1000000)
                can_id = f"{msg0.arbitration_id:08X}"
                extended = 'true' if msg0.is_extended_id else 'false'
                direction = 'Rx' if not msg0.is_remote_frame else 'Tx'
                bus_num = 0  # can0
                dlc = msg0.dlc
                data_bytes = [f"{byte:02X}" for byte in msg0.data]
                data_bytes += ['00'] * (8 - len(data_bytes))
                writer.writerow([timestamp, can_id, extended, direction, bus_num, dlc] + data_bytes)

            # 記錄 can1 的訊息
            if recording and writer and msg1 is not None and hasattr(msg1, 'arbitration_id'):
                timestamp = int(time.time() * 1000000)
                can_id = f"{msg1.arbitration_id:08X}"
                extended = 'true' if msg1.is_extended_id else 'false'
                direction = 'Rx' if not msg1.is_remote_frame else 'Tx'
                bus_num = 1  # can1
                dlc = msg1.dlc
                data_bytes = [f"{byte:02X}" for byte in msg1.data]
                data_bytes += ['00'] * (8 - len(data_bytes))
                writer.writerow([timestamp, can_id, extended, direction, bus_num, dlc] + data_bytes)

            # 檢查是否需要輪換日誌檔案
            if recording and writer and datetime.now() >= rotate_at:
                print("Rotating log file...")
                file.close()
                recording_start_time = datetime.now()
                file, writer = new_csv_writer(base_dir, "can_log")
                rotate_at = recording_start_time + timedelta(minutes=20)
                print(f"New log file created at {recording_start_time}")

        except can.CanError as e:
            print(f"CAN Error: {e}")
            if recording and file:
                file.close()
                file = None
                writer = None
                recording = False
                recording_start_time = None
            # 重新連接兩個 CAN bus
            try:
                bus0 = connect_can('can0')
                print("CAN0 connection restored")
            except:
                print("Failed to restore CAN0")
            try:
                bus1 = connect_can('can1')
                print("CAN1 connection restored")
            except:
                print("Failed to restore CAN1")
        except Exception as e:
            print(f"Unexpected error: {e}")
            if recording and file:
                file.close()
                file = None
                writer = None
                recording = False
                recording_start_time = None

if __name__ == "__main__":
    try: 
        main()
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"Program error: {e}")
        with open("/tmp/can_logger_error.log", "w") as f:
            f.write(f"Error at {datetime.now()}: {str(e)}")
    finally:
        print("CAN Logger stopped")


