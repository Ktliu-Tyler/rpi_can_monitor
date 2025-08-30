import can
import struct
import time
import os
import csv
import threading
import sys
from datetime import datetime
from CanDecoder import CanDecoder

frequency = 1.0

class CanReceiver:
    def __init__(self, use_csv=False, csv_file='can_file.csv', csv_speed=1.0, display_mode='scroll'):
        self.use_csv = use_csv
        self.csv_file = csv_file
        self.csv_speed = csv_speed
        self.display_mode = display_mode
        self.running = True
        
        # Initialize CAN bus or CSV reader
        if self.use_csv:
            self.csv_data = []
            self.csv_index = 0
            self.csv_start_time = None
            self.bus = None
            self.load_csv_file()
        else:
            try:
                self.bus = can.interface.Bus(channel='can0', interface='socketcan')
            except Exception as e:
                print(f"Failed to initialize CAN interface: {e}")
                self.bus = None
        
        # Initialize CAN decoder
        self.decoder = CanDecoder()
        self.message_count = 0
        
        # Threading for CAN receiving
        self.can_thread = None
        self.display_thread = None
        
        mode_str = "CSV Playback" if self.use_csv else "Real CAN"
        if self.display_mode == 'dashboard':
            print(f"CAN Receiver Started - Dashboard Mode ({mode_str})")
        else:
            print(f"CAN Receiver Started - Scrolling Mode ({mode_str})")
        
        if self.use_csv:
            print(f"Using CSV file: {self.csv_file} (Speed: {self.csv_speed}x)")
        
        print("Configured for available data: NavSatFix (/fix) + TwistStamped (/vel)")

    def load_csv_file(self):
        """載入 CSV 檔案"""
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # 解析 CSV 行
                    timestamp = int(row['Time Stamp'])
                    can_id = int(row['ID'], 16)  # 16進制轉換
                    length = int(row['LEN'])
                    
                    # 提取數據字節
                    data = []
                    for i in range(1, min(length + 1, 13)):  # D1-D12, 但只取 LEN 指定的長度
                        data_key = f'D{i}'
                        if data_key in row and row[data_key] != '':  # 只要不是空字符串就處理
                            try:
                                data.append(int(row[data_key], 16))
                            except ValueError:
                                # 如果無法解析，添加 0
                                print(f"Invalid data for {data_key}: {row[data_key]}, adding 0")
                                data.append(0)
                        else:
                            # 如果字段不存在或為空，添加 0
                            data.append(0)
                    
                    self.csv_data.append({
                        'timestamp': timestamp,
                        'can_id': can_id,
                        'data': bytes(data)
                    })
            
            print(f"Loaded {len(self.csv_data)} CAN messages from CSV")
            
        except FileNotFoundError:
            print(f"CSV file not found: {self.csv_file}")
            self.csv_data = []

    def create_mock_can_message(self, can_id, data):
        """創建模擬的 CAN 訊息對象"""
        class MockCanMessage:
            def __init__(self, arbitration_id, data):
                self.arbitration_id = arbitration_id
                self.data = data
        
        return MockCanMessage(can_id, data)

    def can_receive_callback(self):
        if self.use_csv:
            self.csv_receive_callback()
        else:
            self.real_can_receive_callback()

    def real_can_receive_callback(self):
        """原始的 CAN 接收回調函數"""
        try:
            # 非阻塞方式接收CAN訊息
            message = self.bus.recv(timeout=0)
            if message:
                self.message_count += 1
                self.process_can_message(message)
        except Exception as e:
            pass  # 忽略timeout異常

    def csv_receive_callback(self):
        """CSV 模式的接收回調函數"""
        if self.csv_index >= len(self.csv_data):
            return  # 已經播放完畢
        
        current_time = time.time()
        
        # 初始化開始時間
        if self.csv_start_time is None:
            self.csv_start_time = current_time
            self.csv_base_timestamp = self.csv_data[0]['timestamp']
        
        # 計算應該播放的時間點
        elapsed_time = (current_time - self.csv_start_time) * self.csv_speed
        target_timestamp = self.csv_base_timestamp + elapsed_time * 1000000  # 轉換為微秒
        
        # 播放所有應該在當前時間播放的訊息
        while (self.csv_index < len(self.csv_data) and 
               self.csv_data[self.csv_index]['timestamp'] <= target_timestamp):
            
            csv_msg = self.csv_data[self.csv_index]
            mock_message = self.create_mock_can_message(csv_msg['can_id'], csv_msg['data'])
            
            self.message_count += 1
            self.process_can_message(mock_message)
            self.csv_index += 1

    def log_message(self, message):
        """根據模式選擇日誌輸出方式"""
        if self.display_mode == 'scroll':
            print(message)
        # Dashboard mode uses print in update_dashboard function

    def process_can_message(self, msg: can.Message):
        """處理 CAN 訊息，使用 CanDecoder"""
        self.decoder.process_can_message(msg)

    def format_value(self, value, format_func=None):
        """格式化數值顯示"""
        if value is None:
            return "N/A"
        elif format_func:
            if callable(format_func):
                return format_func(value)
            else:
                return format_func.format(value)
        else:
            return str(value)

    def update_dashboard(self):
        """更新儀表板顯示"""
        # Clear screen and move cursor to top
        print("\033[2J\033[H", end='')
        
        # Header
        print("=" * 90)
        print("                                     CAN Data Dashboard")
        print("=" * 90)
        
        # Timestamp Section (show decoded time from 0x100)
        timestamp = self.decoder.data_store['timestamp']
        if timestamp['time'] is not None:
            time_str = timestamp['time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            print(f"[Data Time]    {time_str}")
        else:
            print(f"[Data Time]    N/A")

        canlogging = self.decoder.data_store['canlogging']
        if canlogging['is_recording']:
            start_time = canlogging['start_time'].strftime('%Y-%m-%d %H:%M:%S')
            elapsed_time = time.time() - canlogging['start_timestamp']
            print(f"[CAN Logging]  Recording started at {start_time}, Elapsed: {elapsed_time:.2f} seconds")
        else:
            print(f"[CAN Logging]  Not recording")
        print("-" * 90)
        
        # VCU Section
        vcu = self.decoder.data_store['vcu']
        print(f"[VCU]          Steer: {self.format_value(vcu['steer'], '{:>6}'):>8} "
              f"Accel: {self.format_value(vcu['accel'], '{:>6}'):>8} "
              f"Brake: {self.format_value(vcu['brake'], '{:>6}'):>8}")
        print(f"               APPS1: {self.format_value(vcu['apps1'], '{:>6}'):>8} "
              f"APPS2: {self.format_value(vcu['apps2'], '{:>6}'):>8}")
        print(f"               BSE1: {self.format_value(vcu['bse1'], '{:.2f}'):>8} "
              f"BSE2: {self.format_value(vcu['bse2'], '{:.2f}'):>8}")
        print("-" * 90)
        # IMU Section
        # imu = self.decoder.data_store['imu']
        # print(f"[IMU]          LSM6 Accel X: {self.format_value(imu['lsm6_accel']['x'], '{:.3f} m/s²'):>12} "
        #       f"Y: {self.format_value(imu['lsm6_accel']['y'], '{:.3f} m/s²'):>12} "
        #       f"Z: {self.format_value(imu['lsm6_accel']['z'], '{:.3f} m/s²'):>12}")
        # print(f"               LSM303 Accel X: {self.format_value(imu['lsm303_accel']['x'], '{:.3f} m/s²'):>11} "
        #       f"Y: {self.format_value(imu['lsm303_accel']['y'], '{:.3f} m/s²'):>12} "
        #       f"Z: {self.format_value(imu['lsm303_accel']['z'], '{:.3f} m/s²'):>12}")
        # print(f"               Gyro X: {self.format_value(imu['gyro']['x'], '{:.3f} rad/s'):>15} "
        #       f"Y: {self.format_value(imu['gyro']['y'], '{:.3f} rad/s'):>12} "
        #       f"Z: {self.format_value(imu['gyro']['z'], '{:.3f} rad/s'):>12}")
        # print(f"               Euler Roll: {self.format_value(imu['euler_angles']['roll'], '{:.1f}°'):>12} "
        #       f"Pitch: {self.format_value(imu['euler_angles']['pitch'], '{:.1f}°'):>10} "
        #       f"Yaw: {self.format_value(imu['euler_angles']['yaw'], '{:.1f}°'):>10}")
        # print(f"               Magnetometer X: {self.format_value(imu['magnetometer']['x'], '{:.1f} μT'):>10} "
        #       f"Y: {self.format_value(imu['magnetometer']['y'], '{:.1f} μT'):>10} "
        #       f"Z: {self.format_value(imu['magnetometer']['z'], '{:.1f} μT'):>10}")

        # IMU2 Section
        imu2 = self.decoder.data_store['imu2']
        print(f"[IMU]          Acceleration X: {self.format_value(imu2['acceleration']['x'], '{:.4f} g'):>12} "
              f"Y: {self.format_value(imu2['acceleration']['y'], '{:.4f} g'):>12} "
              f"Z: {self.format_value(imu2['acceleration']['z'], '{:.4f} g'):>12}")
        print(f"               Gyration X: {self.format_value(imu2['gyration']['x'], '{:.2f} deg/s'):>15} "
              f"Y: {self.format_value(imu2['gyration']['y'], '{:.2f} deg/s'):>12} "
              f"Z: {self.format_value(imu2['gyration']['z'], '{:.2f} deg/s'):>12}")
        print(f"               Quaternion W: {self.format_value(imu2['quaternion']['w'], '{:.4f}'):>12} "
              f"X: {self.format_value(imu2['quaternion']['x'], '{:.4f}'):>10} "
              f"Y: {self.format_value(imu2['quaternion']['y'], '{:.4f}'):>10} "
              f"Z: {self.format_value(imu2['quaternion']['z'], '{:.4f}'):>10}")
        print("-" * 90)
        # GPS Section
        gps = self.decoder.data_store['gps']
        cov = self.decoder.data_store['covariance']
        print(f"[GPS]          Lat: {self.format_value(gps['lat'], '{:.7f}'):>12} "
              f"Lon: {self.format_value(gps['lon'], '{:.7f}'):>12} "
              f"Alt: {self.format_value(gps['alt'], '{:.1f}m'):>8}")
        print(f"               Status: {self.format_value(gps['status'], '0x{:02X}'):>8} "
              f"Covariance Type: {cov['type_name']:>15}")
        print("-" * 90)
        # Velocity Section  
        vel = self.decoder.data_store['velocity']
        print(f"[Velocity]     Linear X: {self.format_value(vel['linear_x'], '{:.3f} m/s'):>10} "
              f"Y: {self.format_value(vel['linear_y'], '{:.3f} m/s'):>10} "
              f"Z: {self.format_value(vel['linear_z'], '{:.3f} m/s'):>10}")
        print(f"               Angular X: {self.format_value(vel['angular_x'], '{:.3f} rad/s'):>11} "
              f"Y: {self.format_value(vel['angular_y'], '{:.3f} rad/s'):>11} "
              f"Z: {self.format_value(vel['angular_z'], '{:.3f} rad/s'):>11}")
        print(f"               Total Speed: {self.format_value(vel['magnitude'], '{:.3f} m/s'):>11} "
              f"({self.format_value(vel['speed_kmh'], '{:.2f} km/h'):>10})")
        print("-" * 90)
        # Accumulator Section
        acc = self.decoder.data_store['accumulator']
        print(f"[Accumulator]  SOC: {self.format_value(acc['soc'], '{}%'):>5} "
              f"Voltage: {self.format_value(acc['voltage'], '{:.2f}V'):>8} "
              f"Current: {self.format_value(acc['current'], '{:.2f}A'):>8} "
              f"Temp: {self.format_value(acc['temperature'], '{:.1f}°C'):>7}")
        print(f"               Status: {self.format_value(acc['status'], '0x{:02X}'):>6} "
              f"Capacity: {self.format_value(acc['capacity'], '{:.2f}Ah'):>9} "
              f"Heartbeat: {self.format_value(acc['heartbeat'], lambda x: 'OK' if x else 'FAIL'):>4}")
        print("-" * 90)
        # Inverters Section
        for inv_id, inv in self.decoder.data_store['inverters'].items():
            # Calculate speed in km/h for inverters
            speed_kmh = None
            if inv['speed'] is not None:
                speed_kmh = abs(inv['speed']) * 0.0942  # 轉換為 km/h (假設輪胎直徑)
            
            # Format status
            if inv['status'] is not None:
                status1, status2 = inv['status']
                status_str = f"0x{status1:02X},{status2:02X}"
            else:
                status_str = self.format_value(inv['status'])
            print(f"[Inverter {inv['name']}]  Status: {status_str:>8} ")
            print(f"               Torque: {self.format_value(inv['torque'], '{:.3f}'):>7} "
                  f"    Speed: {self.format_value(inv['speed'], '{}RPM'):>8} ({self.format_value(speed_kmh, '{:.1f}km/h'):>6})")
            print(f"               Control: {self.format_value(inv['control_word'], '0x{:04X}'):>8} "
                  f"Target: {self.format_value(inv['target_torque'], '{:.3f}'):>7} "
                  f"DC: {self.format_value(inv['dc_voltage'], '{:.1f}V'):>6}/"
                  f"{self.format_value(inv['dc_current'], '{:.1f}A'):>6}")
            print(f"               Temps - MOS: {self.format_value(inv['mos_temp'], '{:.1f}°C'):>7} "
                  f"MCU: {self.format_value(inv['mcu_temp'], '{:.1f}°C'):>7} "
                  f"Motor: {self.format_value(inv['motor_temp'], '{:.1f}°C'):>7} "
                  f"    HB: {self.format_value(inv['heartbeat'], lambda x: 'OK' if x else 'FAIL'):>3}")
        
        # Footer
        print("=" * 90)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        print(f"Last Update: {current_time}  Messages: {self.message_count}")
        
        # Flush output
        import sys
        sys.stdout.flush()

    def run(self):
        """啟動 CAN 接收器"""
        # 啟動 CAN 接收線程
        self.can_thread = threading.Thread(target=self._can_receive_loop, daemon=True)
        self.can_thread.start()
        
        # 如果是 dashboard 模式，啟動顯示線程
        if self.display_mode == 'dashboard':
            import os
            os.system('clear')  # Clear screen initially
            self.display_thread = threading.Thread(target=self._display_loop, daemon=True)
            self.display_thread.start()
        
        # 主線程等待
        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """停止 CAN 接收器"""
        self.running = False
        if self.can_thread and self.can_thread.is_alive():
            self.can_thread.join(timeout=1.0)
        if self.display_thread and self.display_thread.is_alive():
            self.display_thread.join(timeout=1.0)
        print("CAN Receiver stopped.")

    def _can_receive_loop(self):
        """CAN 接收循環線程"""
        while self.running:
            try:
                self.can_receive_callback()
                time.sleep(0.001)  # 1ms
            except Exception as e:
                print(f"Error in CAN receive loop: {e}")
                time.sleep(0.1)

    def _display_loop(self):
        """Dashboard 顯示循環線程"""
        while self.running:
            try:
                self.update_dashboard()
                time.sleep(1.0/frequency)  # 50ms
            except Exception as e:
                print(f"Error in display loop: {e}")
                time.sleep(0.1)

def main(args=None):
    # 檢查命令行參數
    import sys
    use_csv = '--csv' in sys.argv
    dashboard_mode = '--dashboard' in sys.argv
    csv_file = './LOGS/can_log_20250727_112357.csv'
    csv_speed = 10.0
    
    # 解析 CSV 文件參數
    if '--csv-file' in sys.argv:
        idx = sys.argv.index('--csv-file')
        if idx + 1 < len(sys.argv):
            csv_file = sys.argv[idx + 1]
    
    # 解析速度參數
    if '--speed' in sys.argv:
        idx = sys.argv.index('--speed')
        if idx + 1 < len(sys.argv):
            try:
                csv_speed = float(sys.argv[idx + 1])
            except ValueError:
                print("Invalid speed value, using default 10.0")
    
    # 創建 CAN 接收器
    display_mode = 'dashboard' if dashboard_mode else 'scroll'
    receiver = CanReceiver(use_csv=use_csv, csv_file=csv_file, 
                          csv_speed=csv_speed, display_mode=display_mode)
    
    if use_csv:
        print(f"Using CSV mode: {csv_file} at {csv_speed}x speed")
    
    if dashboard_mode:
        import os
        os.system('clear')  # Clear screen initially
        print("Dashboard mode enabled")
    
    try:
        receiver.run()
    except KeyboardInterrupt:
        print("\nNode stopped by user.")
    finally:
        receiver.stop()

if __name__ == '__main__':
    main()
