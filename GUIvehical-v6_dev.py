import can
import struct
import asyncio
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
import time
import json
import threading
from typing import List
import csv
import os
# 0112 update distance

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USE_CSV = False
# CSV_FILE = '../LOGS/can_log_20250727_112357.csv'
CSV_FILE = "../LOGS/can_log_20250731_00445.csv"
CSV_SPEED = 1.0
PORT = 8888
DIRBASE = "../LOGS/"

templates = Jinja2Templates(directory="templates")

# WebSocket connections
connections: List[WebSocket] = []

class CanReceiverWebApp:
    def __init__(self, use_csv=USE_CSV, csv_file=CSV_FILE, csv_speed=CSV_SPEED):
        self.csv_data = []
        self.use_csv = use_csv
        self.csv_file = csv_file
        self.csv_speed = csv_speed
        self.index = 0
        self.is_paused = False
        self.playback_speed = 1.0
        self.current_csv_file = csv_file
        self.available_csv_files = self.scan_csv_files()
        self.total_csv_messages = 0
        
        # 運行標誌
        self.running = True
        
        # Initialize CAN bus or CSV reader
        if self.use_csv:
            self.csv_data = []
            self.csv_index = 0
            self.csv_start_time = None
            self.bus = None
            self.bus1 = None
            self.load_csv_file()
        else:
            try:
                from packaging import version
                # 初始化 can0 用於主要數據
                can_kwargs = dict(channel='can0')
                if version.parse(can.__version__) >= version.parse('4.2.0'):
                    can_kwargs['interface'] = 'socketcan'
                else:
                    can_kwargs['bustype'] = 'socketcan'
                self.bus = can.interface.Bus(**can_kwargs)
                print("CAN0 initialized successfully")
            except Exception as e:
                print(f"Warning: Could not initialize CAN0 bus: {e}")
                self.bus = None
                
            # 初始化 can1 用於 GPS 數據
            try:
                from packaging import version
                can1_kwargs = dict(channel='can1')
                if version.parse(can.__version__) >= version.parse('4.2.0'):
                    can1_kwargs['interface'] = 'socketcan'
                else:
                    can1_kwargs['bustype'] = 'socketcan'
                self.bus1 = can.interface.Bus(**can1_kwargs)
                print("CAN1 initialized successfully for GPS data")
            except Exception as e:
                print(f"Warning: Could not initialize CAN1 bus: {e}")
                self.bus1 = None
        
        # Data storage
        self.data_store = {
            'timestamp': {'time': None, 'last_update': None},
            'gps': {
                'lat': None, 'lon': None, 'alt': None, 'status': None,
                'last_update': None
            },
            'covariance': {
                'values': [0.0] * 9, 'type': 0, 'type_name': 'UNKNOWN',
                'last_update': None
            },
            'velocity': {
                'linear_x': None, 'linear_y': None, 'linear_z': None,
                'angular_x': None, 'angular_y': None, 'angular_z': None,
                'magnitude': None, 'speed_kmh': None,
                'last_update': None
            },
            'accumulator': {
                'soc': None, 'voltage': None, 'current': None, 'temperature': None,
                'status': None, 'heartbeat': None, 'capacity': None,
                'cell_voltages': [None] * 105, 'cell_temperatures': [None] * 224,
                'last_update': None
            },
            'inverters': {
                1: {'name': 'FL', 'status': None, 'torque': None, 'speed': None,
                    'control_word': None, 'target_torque': None,
                    'dc_voltage': None, 'dc_current': None,
                    'mos_temp': None, 'mcu_temp': None, 'motor_temp': None,
                    'heartbeat': None, 'last_update': None},
                2: {'name': 'FR', 'status': None, 'torque': None, 'speed': None,
                    'control_word': None, 'target_torque': None,
                    'dc_voltage': None, 'dc_current': None,
                    'mos_temp': None, 'mcu_temp': None, 'motor_temp': None,
                    'heartbeat': None, 'last_update': None},
                3: {'name': 'RL', 'status': None, 'torque': None, 'speed': None,
                    'control_word': None, 'target_torque': None,
                    'dc_voltage': None, 'dc_current': None,
                    'mos_temp': None, 'mcu_temp': None, 'motor_temp': None,
                    'heartbeat': None, 'last_update': None},
                4: {'name': 'RR', 'status': None, 'torque': None, 'speed': None,
                    'control_word': None, 'target_torque': None,
                    'dc_voltage': None, 'dc_current': None,
                    'mos_temp': None, 'mcu_temp': None, 'motor_temp': None,
                    'heartbeat': None, 'last_update': None}
            },
            'vcu': {
                'steer': None, 'accel': None, 'apps1': None,    
                'apps2': None, 'brake': None, 'bse1': None, 'bse2': None,
                'suspF': None, 'suspR': None,
                'last_update': None},
            'imu': {
                'accel_km6': {'x': None, 'y': None, 'z': None},
                'accel_km308': {'x': None, 'y': None, 'z': None},
                'gyro': {'x': None, 'y': None, 'z': None},
                'euler': {'roll': None, 'pitch': None, 'yaw': None},
                'mag': {'x': None, 'y': None, 'z': None},
                'last_update': None
            },
            'imu2': {
                'accel': {'x': None, 'y': None, 'z': None},
                'gyro': {'x': None, 'y': None, 'z': None},
                'quaternion': {'w': None, 'x': None, 'y': None, 'z': None},
                'last_update': None
            },
            'distance': {
                'trip_distance_km': None,
                'last_update': None
            },
            'xsens': {
                'quaternion': {'q0': None, 'q1': None, 'q2': None, 'q3': None},
                'delta_v': {'x': None, 'y': None, 'z': None, 'exponent': None},
                'rate_of_turn': {'gyr_x': None, 'gyr_y': None, 'gyr_z': None},
                'delta_q': {'dq0': None, 'dq1': None, 'dq2': None, 'dq3': None},
                'acceleration': {'acc_x': None, 'acc_y': None, 'acc_z': None},
                'magnetic_field': {'mag_x': None, 'mag_y': None, 'mag_z': None},
                'gps': {'lat': None, 'lon': None, 'alt': None},
                'velocity': {'vel_x': None, 'vel_y': None, 'vel_z': None},
                'last_update': None
            }

        }
        
        self.message_count = 0
        self.running = True
        
        # Legacy GPS數據暫存
        self.gps_lat = None
        self.gps_lon = None
        self.gps_alt = None
        
        # Position covariance 暫存
        self.position_covariance = [0.0] * 9
        self.position_covariance_type = 0
        
        print("CAN Receiver Web App Started")

    async def start_can_receiver(self):
        """啟動CAN接收循環和廣播循環"""
        # 建立兩個並行的任務
        receiver_task = asyncio.create_task(self.receiver_loop())
        broadcaster_task = asyncio.create_task(self.broadcaster_loop())
        
        # 等待兩個任務完成（實際上會一直運行）
        await asyncio.gather(receiver_task, broadcaster_task)

    async def receiver_loop(self):
        """CAN 訊息接收主循環"""
        while self.running:
            try:
                if self.use_csv:
                    await self.csv_receive_callback()
                else:
                    # 同時接收 can0 和 can1 的訊息
                    await self.real_can_receive_callback()
                    await self.real_can1_receive_callback()
                await asyncio.sleep(0.0001) 
            except Exception as e:
                print(f"Error in receiver loop: {e}")
                await asyncio.sleep(0.1)

    async def broadcaster_loop(self):
        """定期廣播數據的循環"""
        while self.running:
            # 只在有客戶端連接時才廣播
            if connections:
                await self.broadcast_data()
            # 固定廣播頻率，例如每 50ms 一次 (20 FPS)
            await asyncio.sleep(0.05)

    def load_csv_file(self):
        """載入 CSV 檔案"""
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    can_id = row['ID']
                    # print(f"Processing CSV row{self.index} with ID: {can_id}")
                    self.index += 1
                    try:
                        # 解析 CSV 行
                        timestamp = int(row['Time Stamp'])
                        can_id = int(row['ID'], 16)  # 16進制轉換
                        length = int(row['LEN'])
                        
                        data = []
                        for i in range(1, 13):  # D1-D12
                            data_key = f'D{i}'
                            if data_key in row and row[data_key] != '' and row[data_key] is not None:  # 只處理存在且不為空的欄位
                                try:
                                    # 確保是字符串並移除可能的空白字符
                                    data_value = str(row[data_key]).strip()
                                    if data_value:  # 確保不是空字符串
                                        data.append(int(data_value, 16))
                                    else:
                                        data.append(0)
                                        # print(f"Missing or empty data for {data_key}, stopping further data extraction.1")
                                except ValueError as ve:
                                    # 如果無法解析，跳過此欄位而不是添加 0
                                    print(f"Invalid data for {data_key}: '{row[data_key]}' (type: {type(row[data_key])}), skipping - {ve}")
                                    break
                            else:
                                data.append(0)
                                break
                        
                        # 確保數據長度不超過 LEN 指定的長度
                        if len(data) > length:
                            data = data[:length]
                        
                        self.csv_data.append({
                            'timestamp': timestamp,
                            'can_id': can_id,
                            'data': bytes(data)
                        })
                    except Exception as e:
                        print(f"Error parsing CSV row: {e}")
                        print(f"Row data: {dict(row)}")
                        continue  # 跳過錯誤的行，繼續處理下一行
            
            print(f"Loaded {len(self.csv_data)} CAN messages from CSV")
            
        except FileNotFoundError:
            print(f"CSV file not found: {self.csv_file}")
            self.csv_data = []
        except Exception as e:
            print(f"Error loading CSV file: {e}")
            self.csv_data = []

    def scan_csv_files(self):
        """掃描可用的 CSV 檔案"""
        import os
        import glob
        
        csv_dir = "../LOGS/"
        if os.path.exists(csv_dir):
            files = glob.glob(os.path.join(csv_dir, "*.csv"))
            return [os.path.basename(f) for f in files]
        return []

    def pause_playback(self):
        """暫停播放"""
        self.is_paused = True
        print("Playback paused")

    def resume_playback(self):
        """恢復播放"""
        self.is_paused = False
        # 重新設定時間基準點以避免時間跳躍
        if self.csv_start_time and self.csv_index < len(self.csv_data):
            current_time = time.time()
            elapsed_time = (self.csv_data[self.csv_index]['timestamp'] - self.csv_base_timestamp) / 1000000
            self.csv_start_time = current_time - (elapsed_time / self.playback_speed)
        print("Playback resumed")

    def set_playback_speed(self, speed):
        """設定播放速度"""
        if speed > 0:
            # 調整時間基準點以保持連續性
            if self.csv_start_time and not self.is_paused:
                current_time = time.time()
                elapsed_time = (current_time - self.csv_start_time) * self.playback_speed
                self.csv_start_time = current_time - (elapsed_time / speed)
            
            self.playback_speed = speed
            print(f"Playback speed set to {speed}x")

    def jump_to_percentage(self, percentage):
        """跳到指定百分比位置"""
        if not self.csv_data:
            return False
        
        percentage = max(0, min(100, percentage))
        target_index = int(len(self.csv_data) * percentage / 100)
        
        self.csv_index = target_index
        if self.csv_index < len(self.csv_data):
            current_time = time.time()
            elapsed_time = (self.csv_data[self.csv_index]['timestamp'] - self.csv_base_timestamp) / 1000000
            self.csv_start_time = current_time - (elapsed_time / self.playback_speed)
        
        print(f"Jumped to {percentage}% ({self.csv_index}/{len(self.csv_data)})")
        return True

    def jump_time(self, seconds):
        """前進或後退指定秒數"""
        if not self.csv_data or not self.csv_start_time:
            return False
        
        # 計算目標時間戳
        current_timestamp = self.csv_data[self.csv_index]['timestamp'] if self.csv_index < len(self.csv_data) else self.csv_data[-1]['timestamp']
        target_timestamp = current_timestamp + (seconds * 1000000)  # 轉換為微秒
        
        # 找到最接近的索引
        target_index = self.csv_index
        if seconds > 0:  # 前進
            for i in range(self.csv_index, len(self.csv_data)):
                if self.csv_data[i]['timestamp'] >= target_timestamp:
                    target_index = i
                    break
            else:
                target_index = len(self.csv_data) - 1
        else:  # 後退
            for i in range(self.csv_index, -1, -1):
                if self.csv_data[i]['timestamp'] <= target_timestamp:
                    target_index = i
                    break
            else:
                target_index = 0
        
        self.csv_index = target_index
        current_time = time.time()
        elapsed_time = (self.csv_data[self.csv_index]['timestamp'] - self.csv_base_timestamp) / 1000000
        self.csv_start_time = current_time - (elapsed_time / self.playback_speed)
        
        print(f"Jumped {seconds}s to index {self.csv_index}")
        return True

    def switch_csv_file(self, filename):
        """切換 CSV 檔案"""
        import os
        
        new_file_path = os.path.join(DIRBASE, filename)
        if not os.path.exists(new_file_path):
            print(f"CSV file not found: {new_file_path}")
            return False
        
        self.current_csv_file = new_file_path
        self.csv_file = new_file_path
        self.csv_data = []
        self.csv_index = 0
        self.csv_start_time = None
        self.csv_base_timestamp = None
        self.is_paused = False
        
        # 重新載入檔案
        self.load_csv_file()
        print(f"Switched to CSV file: {filename}")
        return True

    def get_playback_status(self):
        """獲取播放狀態"""
        progress = 0
        if self.csv_data:
            progress = (self.csv_index / len(self.csv_data)) * 100
        
        current_time_str = "00:00"
        total_time_str = "00:00"
        
        if self.csv_data and self.csv_base_timestamp:
            if self.csv_index < len(self.csv_data):
                current_seconds = (self.csv_data[self.csv_index]['timestamp'] - self.csv_base_timestamp) / 1000000
                current_time_str = f"{int(current_seconds//60):02d}:{int(current_seconds%60):02d}"
            
            total_seconds = (self.csv_data[-1]['timestamp'] - self.csv_base_timestamp) / 1000000
            total_time_str = f"{int(total_seconds//60):02d}:{int(total_seconds%60):02d}"
        
        return {
            'is_paused': self.is_paused,
            'speed': self.playback_speed,
            'current_file': os.path.basename(self.current_csv_file) if self.current_csv_file else None,
            'progress': progress,
            'current_time': current_time_str,
            'total_time': total_time_str,
            'available_files': self.available_csv_files
        }

    # 在 CanReceiverWebApp 類中添加以下方法

    def switch_mode(self, use_csv):
        """切換 CSV 模式和 CAN 模式"""
        if self.use_csv == use_csv:
            return True  # 已經是目標模式
        
        old_mode = "CSV" if self.use_csv else "CAN"
        new_mode = "CSV" if use_csv else "CAN"
        
        try:
            # 停止當前模式
            if self.bus:
                self.bus.shutdown()
                self.bus = None
            if hasattr(self, 'bus1') and self.bus1:
                self.bus1.shutdown()
                self.bus1 = None
            
            # 重置數據
            self.use_csv = use_csv
            self.csv_index = 0
            self.csv_start_time = None
            self.csv_base_timestamp = None
            self.is_paused = False
            
            if use_csv:
                # 切換到 CSV 模式
                self.csv_data = []
                self.load_csv_file()
                print(f"Switched from {old_mode} to CSV mode")
            else:
                # 切換到 CAN 模式
                try:
                    from packaging import version
                    # 初始化 can0
                    can_kwargs = dict(channel='can0')
                    if version.parse(can.__version__) >= version.parse('4.2.0'):
                        can_kwargs['interface'] = 'socketcan'
                    else:
                        can_kwargs['bustype'] = 'socketcan'
                    self.bus = can.interface.Bus(**can_kwargs)
                    print(f"Switched from {old_mode} to CAN0 mode")
                    
                    # 初始化 can1 用於 GPS
                    try:
                        can1_kwargs = dict(channel='can1')
                        if version.parse(can.__version__) >= version.parse('4.2.0'):
                            can1_kwargs['interface'] = 'socketcan'
                        else:
                            can1_kwargs['bustype'] = 'socketcan'
                        self.bus1 = can.interface.Bus(**can1_kwargs)
                        print("CAN1 initialized for GPS data")
                    except Exception as e:
                        print(f"Warning: Could not initialize CAN1 bus: {e}")
                        self.bus1 = None
                        
                except Exception as e:
                    print(f"Warning: Could not initialize CAN bus: {e}")
                    # 如果 CAN 初始化失敗，回到 CSV 模式
                    self.use_csv = True
                    self.csv_data = []
                    self.load_csv_file()
                    return False
            
            return True
        except Exception as e:
            print(f"Error switching mode: {e}")
            return False

    def get_current_mode(self):
        """獲取當前模式信息"""
        return {
            'mode': 'CSV' if self.use_csv else 'CAN',
            'use_csv': self.use_csv,
            'can_available': self.is_can_available()
        }

    def is_can_available(self):
        """檢查 CAN 介面是否可用"""
        try:
            test_bus = can.interface.Bus(channel='can0', bustype='socketcan')
            test_bus.shutdown()
            return True
        except:
            return False

    async def broadcast_data(self):
        """廣播數據到所有連接的客戶端"""
        if not connections:
            return
        broadcast_data = {
            'timestamp': self.data_store['timestamp']['time'].isoformat() if self.data_store['timestamp']['time'] else None,
            'gps': self.data_store['gps'],
            'velocity': self.data_store['velocity'],
            'distance': self.data_store['distance'],
            'accumulator': self.data_store['accumulator'],
            'inverters': self.data_store['inverters'],
            'vcu': self.data_store['vcu'],
            'imu': self.data_store['imu'],
            'imu2': self.data_store['imu2'],
            'xsens': self.data_store['xsens'],
            'message_count': self.message_count,
            'update_time': datetime.now().isoformat(),
            'playback_control': self.get_playback_status() 
        }
        
        # 發送到所有連接的客戶端
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_text(json.dumps(broadcast_data))
            except:
                disconnected.append(websocket)
        
        # 移除斷開的連接
        for ws in disconnected:
            if ws in connections:
                connections.remove(ws)

    async def can_receive_callback(self):
        if self.use_csv:
            await self.csv_receive_callback()
        else:
            await self.real_can_receive_callback()

    async def real_can_receive_callback(self):
        """原始的 CAN 接收回調函數 (async)"""
        try:
            if self.bus:
                message = self.bus.recv(timeout=0.001)
                if message:
                    self.message_count += 1
                    self.process_can_message(message)
                    # await self.broadcast_data() # REMOVED to prevent flooding
            # await asyncio.sleep(0.001) # REMOVED, handled by receiver_loop
        except Exception as e:
            await asyncio.sleep(0.1)

    async def real_can1_receive_callback(self):
        """CAN1 接收回調函數 (async)"""
        try:
            if self.bus1:
                message = self.bus1.recv(timeout=0.001)
                if message:
                    self.message_count += 1
                    self.process_can_message(message)
            # await asyncio.sleep(0.001) # REMOVED, handled by receiver_loop
        except Exception as e:
            await asyncio.sleep(0.1)

    async def csv_receive_callback(self):
        """CSV 模式的接收回調函數 (async)"""
        if self.is_paused:
            await asyncio.sleep(0.1)
            return
            
        if self.csv_index >= len(self.csv_data):
            await asyncio.sleep(0.01)
            return 
        
        current_time = time.time()
        if self.csv_start_time is None:
            self.csv_start_time = current_time
            self.csv_base_timestamp = self.csv_data[0]['timestamp']
        elapsed_time = (current_time - self.csv_start_time) * self.csv_speed * self.playback_speed
        target_timestamp = self.csv_base_timestamp + elapsed_time * 1000000  # 轉換為微秒
        updated = False
        while (self.csv_index < len(self.csv_data) and 
               self.csv_data[self.csv_index]['timestamp'] <= target_timestamp):
            csv_msg = self.csv_data[self.csv_index]
            mock_message = self.create_mock_can_message(csv_msg['can_id'], csv_msg['data'])
            self.message_count += 1
            self.process_can_message(mock_message)
            self.csv_index += 1
            updated = True
        if updated:
            pass # await self.broadcast_data() # REMOVED to prevent flooding
        # await asyncio.sleep(0.001) # REMOVED, handled by receiver_loop

    def create_mock_can_message(self, can_id, data):
        """創建模擬的 CAN 訊息對象"""
        class MockCanMessage:
            def __init__(self, arbitration_id, data):
                self.arbitration_id = arbitration_id
                self.data = data
        
        return MockCanMessage(can_id, data)

    def process_can_message(self, msg: can.Message):
        can_id = msg.arbitration_id
        data = msg.data
        
        try:
            # Timestamp 解碼
            if can_id == 0x100:
                self.decode_timestamp(data)
            
            elif can_id == 0x181:
                self.decode_vcu_cockpit(data)
            elif can_id == 0x381:
                self.decode_vcu_suspension(data)
            # GPS 解碼
            elif can_id == 0x400:
                self.decode_gps_basic(data)
            elif can_id == 0x401:
                self.decode_gps_extended(data)
            elif 0x410 <= can_id <= 0x418:
                self.decode_position_covariance(data, can_id - 0x410)
            elif can_id == 0x419:
                self.decode_position_covariance_type(data)
                
            # 速度資料解碼
            elif can_id == 0x402:
                self.decode_velocity_x(data)
            elif can_id == 0x403:
                self.decode_velocity_y(data)
            elif can_id == 0x404:
                self.decode_velocity_z(data)
            elif can_id == 0x405:
                self.decode_angular_x(data)
            elif can_id == 0x406:
                self.decode_angular_y(data)
            elif can_id == 0x407:
                self.decode_angular_z(data)
            elif can_id == 0x408:
                self.decode_velocity_magnitude(data)
            elif can_id == 0x440:
                print(f"[DEBUG] Received CAN ID 0x440, data: {data.hex()}")
                self.decode_distance(data)
            
            # Accumulator 解碼
            elif can_id == 0x601:
                self.decode_cell_voltage(data)
            elif can_id == 0x651:
                self.decode_accumulator_temperature(data)
            elif can_id == 0x710:
                self.decode_accumulator_heartbeat(data)
            elif can_id == 0x501:
                self.decode_accumulator_status(data)
            elif can_id == 0x511:
                self.decode_accumulator_state(data)
            
            # Inverter 解碼
            elif 0x191 <= can_id <= 0x194:
                inv_num = can_id - 0x190
                self.decode_inverter_status(data, inv_num)
            elif 0x291 <= can_id <= 0x294:
                inv_num = can_id - 0x290
                self.decode_inverter_state(data, inv_num)
            elif 0x391 <= can_id <= 0x394:
                inv_num = can_id - 0x390
                self.decode_inverter_temperature(data, inv_num)
            elif 0x711 <= can_id <= 0x714:
                inv_num = can_id - 0x710
                self.decode_inverter_heartbeat(data, inv_num)
            elif 0x210 <= can_id <= 0x214:
                inv_num = can_id - 0x210
                self.decode_inverter_control(data, inv_num)
            
            # IMU 解碼
            elif can_id == 0x185:
                self.decode_imu_accel_km6(data)
            elif can_id == 0x426:
                self.decode_imu_accel_km308(data)
            elif can_id == 0x285:
                self.decode_imu_gyro(data)
            elif can_id == 0x385:
                self.decode_imu_euler(data)
            elif can_id == 0x429:
                self.decode_imu_mag(data)
            
            # IMU2 解碼
            elif can_id == 0x188:
                self.decode_imu2_accel(data)
            elif can_id == 0x288:
                self.decode_imu2_gyro(data)
            elif can_id == 0x488:
                self.decode_imu2_quaternion(data)
            
            # Xsens IMU 解碼 (can1)
            elif can_id == 0x021:  # Quaternion
                self.decode_xsens_quaternion(data)
            elif can_id == 0x031:  # DeltaV
                self.decode_xsens_delta_v(data)
            elif can_id == 0x032:  # RateOfTurn
                self.decode_xsens_rate_of_turn(data)
            elif can_id == 0x033:  # DeltaQ
                self.decode_xsens_delta_q(data)
            elif can_id == 0x034:  # Acceleration
                self.decode_xsens_acceleration(data)
            elif can_id == 0x041:  # MagneticField
                self.decode_xsens_magnetic_field(data)
            elif can_id == 0x071:  # LatLon
                self.decode_xsens_latlon(data)
            elif can_id == 0x072:  # AltitudeEllipsoid
                self.decode_xsens_altitude(data)
            elif can_id == 0x076:  # Velocity
                self.decode_xsens_velocity(data)

        except Exception as e:
            print(f"Failed to decode CAN message ID 0x{can_id:03X}: {e}")



# define all decode functions
    def decode_timestamp(self, data):
        if len(data) >= 6:
            ms_since_midnight = struct.unpack('<I', data[0:4])[0]
            days_since_1984 = struct.unpack('<H', data[4:6])[0]
            
            base_timestamp = 441763200
            total_seconds = base_timestamp + (days_since_1984 * 86400) + (ms_since_midnight / 1000.0)
            decoded_time = datetime.fromtimestamp(total_seconds)
            
            current_time = time.time()
            self.data_store['timestamp']['time'] = decoded_time
            self.data_store['timestamp']['last_update'] = current_time

    def decode_vcu_cockpit(self, data):
        if len(data) >= 8:
            stear_raw = struct.unpack('<h', data[0:2])[0]
            accel_raw = data[2] 
            apps1_raw = data[3]
            apps2_raw = data[4]
            brake_raw = data[5]
            bse1_raw = data[6]
            bse2_raw = data[7]
            stear_data = stear_raw *100
            # 更新 VCU 數據
            current_time = time.time()
            self.data_store['vcu']['steer'] = stear_data
            self.data_store['vcu']['accel'] = accel_raw
            self.data_store['vcu']['apps1'] = apps1_raw
            self.data_store['vcu']['apps2'] = apps2_raw
            self.data_store['vcu']['brake'] = brake_raw
            self.data_store['vcu']['bse1'] = bse1_raw
            self.data_store['vcu']['bse2'] = bse2_raw
            self.data_store['vcu']['last_update'] = current_time

    def decode_vcu_suspension(self, data):
        """解碼前後懸吊數據 (0x381)
        SuspF: bytes 0-1, 公式: 值 * 0.0001 + 0.3 (m)
        SuspR: bytes 2-3, 公式: 值 * 0.0001 + 0.3 (m)
        """
        if len(data) >= 4:
            # 前懸吊 (bytes 0-1)
            suspF_raw = struct.unpack('<H', data[0:2])[0]
            suspF = suspF_raw * 0.0001 + 0.3
            
            # 後懸吊 (bytes 2-3)
            suspR_raw = struct.unpack('<H', data[2:4])[0]
            suspR = suspR_raw * 0.0001 + 0.3
            
            # 更新 VCU 數據
            current_time = time.time()
            self.data_store['vcu']['suspF'] = suspF
            self.data_store['vcu']['suspR'] = suspR
            self.data_store['vcu']['last_update'] = current_time

    def decode_gps_basic(self, data):
        if len(data) >= 8:
            lat_raw = struct.unpack('<i', data[0:4])[0]
            self.gps_lat = lat_raw / 10**7
            
            lon_raw = struct.unpack('<i', data[4:8])[0]
            self.gps_lon = lon_raw / 10**7
            
            current_time = time.time()
            self.data_store['gps']['lat'] = self.gps_lat
            self.data_store['gps']['lon'] = self.gps_lon
            self.data_store['gps']['last_update'] = current_time

    def decode_gps_extended(self, data):
        if len(data) >= 2:
            alt_raw = struct.unpack('<h', data[0:2])[0]
            status_byte = data[2] if len(data) > 2 else 0
            self.gps_alt = float(alt_raw)
            
            current_time = time.time()
            self.data_store['gps']['alt'] = self.gps_alt
            self.data_store['gps']['status'] = status_byte
            self.data_store['gps']['last_update'] = current_time

    def decode_position_covariance(self, data, index):
        if len(data) >= 8 and 0 <= index < 9:
            covariance_value = struct.unpack('<d', data[0:8])[0]
            self.position_covariance[index] = covariance_value

    def decode_position_covariance_type(self, data):
        if len(data) >= 1:
            self.position_covariance_type = struct.unpack('<B', data[0:1])[0]
            
            covariance_types = {
                0: "UNKNOWN",
                1: "APPROXIMATED", 
                2: "DIAGONAL_KNOWN",
                3: "KNOWN"
            }
            type_name = covariance_types.get(self.position_covariance_type, "UNKNOWN")
            
            current_time = time.time()
            self.data_store['covariance']['type'] = self.position_covariance_type
            self.data_store['covariance']['type_name'] = type_name
            self.data_store['covariance']['last_update'] = current_time

    def decode_velocity_x(self, data):
        if len(data) >= 4:
            vx_raw = struct.unpack('<i', data[0:4])[0]
            vx = vx_raw / 1000.0
            
            current_time = time.time()
            self.data_store['velocity']['linear_x'] = vx
            self.data_store['velocity']['last_update'] = current_time

    def decode_velocity_y(self, data):
        if len(data) >= 4:
            vy_raw = struct.unpack('<i', data[0:4])[0]
            vy = vy_raw / 1000.0
            
            current_time = time.time()
            self.data_store['velocity']['linear_y'] = vy
            self.data_store['velocity']['last_update'] = current_time

    def decode_velocity_z(self, data):
        if len(data) >= 4:
            vz_raw = struct.unpack('<i', data[0:4])[0]
            vz = vz_raw / 1000.0
            
            current_time = time.time()
            self.data_store['velocity']['linear_z'] = vz
            self.data_store['velocity']['last_update'] = current_time

    def decode_angular_x(self, data):
        if len(data) >= 4:
            wx_raw = struct.unpack('<i', data[0:4])[0]
            wx = wx_raw / 1000.0
            
            current_time = time.time()
            self.data_store['velocity']['angular_x'] = wx
            self.data_store['velocity']['last_update'] = current_time

    def decode_angular_y(self, data):
        if len(data) >= 4:
            wy_raw = struct.unpack('<i', data[0:4])[0]
            wy = wy_raw / 1000.0
            
            current_time = time.time()
            self.data_store['velocity']['angular_y'] = wy
            self.data_store['velocity']['last_update'] = current_time

    def decode_angular_z(self, data):
        if len(data) >= 4:
            wz_raw = struct.unpack('<i', data[0:4])[0]
            wz = wz_raw / 1000.0
            
            current_time = time.time()
            self.data_store['velocity']['angular_z'] = wz
            self.data_store['velocity']['last_update'] = current_time

    def decode_velocity_magnitude(self, data):
        if len(data) >= 4:
            vmag_raw = struct.unpack('<i', data[0:4])[0]
            vmag = vmag_raw / 1000.0
            speed_kmh = vmag * 3.6
            
            current_time = time.time()
            self.data_store['velocity']['magnitude'] = vmag
            self.data_store['velocity']['speed_kmh'] = speed_kmh
            self.data_store['velocity']['last_update'] = current_time

    def decode_distance(self, data):
        """解碼 CAN ID 0x440 的里程數據 (來自 can1)"""
        if len(data) >= 4:
            # 解包32位無符號整數 (little-endian)，單位為毫米 (mm)
            distance_mm = struct.unpack('<I', data[0:4])[0]
            # 轉換為公里 (km)
            distance_km = distance_mm / 1000000.0
            
            current_time = time.time()
            self.data_store['distance']['trip_distance_km'] = distance_km
            self.data_store['distance']['last_update'] = current_time
            print(f"[DISTANCE] Received: {distance_mm} mm = {distance_km:.3f} km")

    def decode_cell_voltage(self, data):
        if len(data) >= 8:
            # 第一個位元組是 index (0, 7, 14, 21, ..., 98)
            index = data[0]
            
            # 驗證 index 是否有效 (應該是 7 的倍數且 <= 98)
            if index % 7 != 0 or index > 98:
                print(f"[ACCUMULATOR] Invalid cell voltage index: {index}")
                return
            
            # 接下來 7 個位元組是電壓數值
            voltages = []
            for i in range(1, min(8, len(data))):
                voltage = data[i] * 0.02  # 20mV/LSB
                voltages.append(voltage)
            
            # 更新一維陣列中對應位置的數值
            current_time = time.time()
            for i, voltage in enumerate(voltages):
                array_index = index + i
                if array_index < 105:  # 確保不超出陣列範圍
                    self.data_store['accumulator']['cell_voltages'][array_index] = voltage
            
            self.data_store['accumulator']['last_update'] = current_time

    def decode_accumulator_temperature(self, data):
        if len(data) >= 8:
            # 第一個位元組是 index (0, 7, 14, 21, ..., 98)
            index = data[0]
            
            # 驗證 index 是否有效 (應該是 7 的倍數且 <= 98)
            if index % 7 != 0 or index > 217:
                print(f"[ACCUMULATOR] Invalid temperature index: {index}")
                return
            
            # 接下來 7 個位元組是溫度數值
            temperatures = []
            for i in range(1, min(8, len(data))):
                temp = data[i] - 32  
                temperatures.append(temp)
            
            current_time = time.time()
            for i, temp in enumerate(temperatures):
                array_index = index + i
                if array_index < 224: 
                    self.data_store['accumulator']['cell_temperatures'][array_index] = temp

            self.data_store['accumulator']['last_update'] = current_time

    def decode_accumulator_heartbeat(self, data):
        if len(data) >= 1:
            heartbeat = data[0] == 0x7F
            
            current_time = time.time()
            self.data_store['accumulator']['heartbeat'] = heartbeat
            self.data_store['accumulator']['last_update'] = current_time

    def decode_accumulator_status(self, data):
        if len(data) >= 7:
            status = data[0]
            temp_raw = struct.unpack('<h', data[1:3])[0]
            voltage_raw = struct.unpack('<I', data[3:7])[0] if len(data) >= 7 else 0
            
            temperature = temp_raw * 0.125
            voltage = voltage_raw / 1024.0
            
            current_time = time.time()
            self.data_store['accumulator']['status'] = status
            self.data_store['accumulator']['temperature'] = temperature
            self.data_store['accumulator']['voltage'] = voltage
            self.data_store['accumulator']['last_update'] = current_time

    def decode_accumulator_state(self, data):
        if len(data) >= 5:
            soc = data[0]
            current_raw = struct.unpack('<h', data[1:3])[0]
            capacity_raw = struct.unpack('<h', data[3:5])[0] if len(data) >= 5 else 0
            
            current = current_raw * 0.01
            capacity = capacity_raw * 0.01
            
            current_time = time.time()
            self.data_store['accumulator']['soc'] = soc
            self.data_store['accumulator']['current'] = current
            self.data_store['accumulator']['capacity'] = capacity
            self.data_store['accumulator']['last_update'] = current_time

    def decode_inverter_status(self, data, inv_num):
        if len(data) >= 6:
            status_word1 = data[0]
            status_word2 = data[1]
            feedback_torque_raw = struct.unpack('<h', data[2:4])[0]
            speed_raw = struct.unpack('<h', data[4:6])[0]
            feedback_torque = feedback_torque_raw / 1000.0 * 20
            speed = speed_raw
            if inv_num == (0x213-0x210):
                feedback_torque *= -1
            
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['status'] = (status_word1, status_word2) 
                self.data_store['inverters'][inv_num]['torque'] = feedback_torque
                self.data_store['inverters'][inv_num]['speed'] = speed
                self.data_store['inverters'][inv_num]['last_update'] = current_time

    def decode_inverter_state(self, data, inv_num):
        if len(data) >= 4:
            dc_voltage_raw = struct.unpack('<H', data[0:2])[0]
            dc_current_raw = struct.unpack('<H', data[2:4])[0]
            
            dc_voltage = dc_voltage_raw / 100.0
            dc_current = dc_current_raw / 100.0
            
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['dc_voltage'] = dc_voltage
                self.data_store['inverters'][inv_num]['dc_current'] = dc_current
                self.data_store['inverters'][inv_num]['last_update'] = current_time

    def decode_inverter_temperature(self, data, inv_num):
        if len(data) >= 6:
            inv_mos_temp_raw = struct.unpack('<h', data[0:2])[0]
            mcu_temp_raw = struct.unpack('<h', data[2:4])[0]
            motor_temp_raw = struct.unpack('<h', data[4:6])[0]
            
            inv_mos_temp = inv_mos_temp_raw * 0.1
            mcu_temp = mcu_temp_raw * 0.1
            motor_temp = motor_temp_raw * 0.1
            
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['mos_temp'] = inv_mos_temp
                self.data_store['inverters'][inv_num]['mcu_temp'] = mcu_temp
                self.data_store['inverters'][inv_num]['motor_temp'] = motor_temp
                self.data_store['inverters'][inv_num]['last_update'] = current_time

    def decode_inverter_heartbeat(self, data, inv_num):
        if len(data) >= 1:
            heartbeat = data[0] == 0x05
            
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['heartbeat'] = heartbeat
                self.data_store['inverters'][inv_num]['last_update'] = current_time

    def decode_inverter_control(self, data, inv_num):
        if len(data) >= 4:
            control_word = struct.unpack('<H', data[0:2])[0]
            target_torque_raw = struct.unpack('<h', data[2:4])[0]
            target_torque = target_torque_raw / 1000.0 * 20
            if inv_num == (0x213-0x210):
                target_torque *= -1
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['control_word'] = control_word
                self.data_store['inverters'][inv_num]['target_torque'] = target_torque
                self.data_store['inverters'][inv_num]['last_update'] = current_time

    # IMU 解碼函數
    def decode_imu_accel_km6(self, data):
        """解碼IMU加速度數據km6 (0x185)
        X: bytes 0-1, Y: bytes 2-3, Z: bytes 4-5
        格式: 0.001 m/s^2 /LSB (signed)
        """
        if len(data) >= 6:
            x_raw = struct.unpack('<h', data[0:2])[0]
            y_raw = struct.unpack('<h', data[2:4])[0]
            z_raw = struct.unpack('<h', data[4:6])[0]
            
            # 轉換為 m/s^2
            x = x_raw * 0.001
            y = y_raw * 0.001
            z = z_raw * 0.001
            
            current_time = time.time()
            self.data_store['imu']['accel_km6']['x'] = x
            self.data_store['imu']['accel_km6']['y'] = y
            self.data_store['imu']['accel_km6']['z'] = z
            self.data_store['imu']['last_update'] = current_time

    def decode_imu_accel_km308(self, data):
        """解碼IMU加速度數據km308 (0x426)
        X: bytes 0-1, Y: bytes 2-3, Z: bytes 4-5
        格式: 0.001 m/s^2 /LSB (signed)
        """
        if len(data) >= 6:
            x_raw = struct.unpack('<h', data[0:2])[0]
            y_raw = struct.unpack('<h', data[2:4])[0]
            z_raw = struct.unpack('<h', data[4:6])[0]
            
            # 轉換為 m/s^2
            x = x_raw * 0.001
            y = y_raw * 0.001
            z = z_raw * 0.001
            
            current_time = time.time()
            self.data_store['imu']['accel_km308']['x'] = x
            self.data_store['imu']['accel_km308']['y'] = y
            self.data_store['imu']['accel_km308']['z'] = z
            self.data_store['imu']['last_update'] = current_time

    def decode_imu_gyro(self, data):
        """解碼IMU陀螺儀數據 (0x285)
        X: bytes 0-1, Y: bytes 2-3, Z: bytes 4-5
        格式: 0.1 deg/s /LSB (signed)
        """
        if len(data) >= 6:
            x_raw = struct.unpack('<h', data[0:2])[0]
            y_raw = struct.unpack('<h', data[2:4])[0]
            z_raw = struct.unpack('<h', data[4:6])[0]
            
            # 轉換為 deg/s
            x = x_raw * 0.1
            y = y_raw * 0.1
            z = z_raw * 0.1
            
            current_time = time.time()
            self.data_store['imu']['gyro']['x'] = x
            self.data_store['imu']['gyro']['y'] = y
            self.data_store['imu']['gyro']['z'] = z
            self.data_store['imu']['last_update'] = current_time

    def decode_imu_euler(self, data):
        """解碼IMU歐拉角數據 (0x385)
        Roll: bytes 0-1, Pitch: bytes 2-3, Yaw: bytes 4-5
        格式: 0.01 degree /LSB (signed)
        """
        if len(data) >= 6:
            roll_raw = struct.unpack('<h', data[0:2])[0]
            pitch_raw = struct.unpack('<h', data[2:4])[0]
            yaw_raw = struct.unpack('<h', data[4:6])[0]
            
            # 轉換為 degree
            roll = roll_raw * 0.01
            pitch = pitch_raw * 0.01
            yaw = yaw_raw * 0.01
            
            current_time = time.time()
            self.data_store['imu']['euler']['roll'] = roll
            self.data_store['imu']['euler']['pitch'] = pitch
            self.data_store['imu']['euler']['yaw'] = yaw
            self.data_store['imu']['last_update'] = current_time

    def decode_imu_mag(self, data):
        """解碼IMU磁力計數據 (0x429)
        X: bytes 0-1, Y: bytes 2-3, Z: bytes 4-5
        格式: 0.1 uT /LSB (signed)
        """
        if len(data) >= 6:
            x_raw = struct.unpack('<h', data[0:2])[0]
            y_raw = struct.unpack('<h', data[2:4])[0]
            z_raw = struct.unpack('<h', data[4:6])[0]
            
            # 轉換為 uT (微特斯拉)
            x = x_raw * 0.1
            y = y_raw * 0.1
            z = z_raw * 0.1
            
            current_time = time.time()
            self.data_store['imu']['mag']['x'] = x
            self.data_store['imu']['mag']['y'] = y
            self.data_store['imu']['mag']['z'] = z
            self.data_store['imu']['last_update'] = current_time

    # IMU2 解碼函數
    def decode_imu2_accel(self, data):
        """解碼IMU2加速度數據 (0x188)
        X: bytes 0-1, Y: bytes 2-3, Z: bytes 4-5
        格式: 0.001 g/LSB (signed)
        """
        if len(data) >= 6:
            x_raw = struct.unpack('<h', data[0:2])[0]
            y_raw = struct.unpack('<h', data[2:4])[0]
            z_raw = struct.unpack('<h', data[4:6])[0]
            
            # 轉換為 g
            x = x_raw * 0.001
            y = y_raw * 0.001
            z = z_raw * 0.001
            
            current_time = time.time()
            self.data_store['imu2']['accel']['x'] = x
            self.data_store['imu2']['accel']['y'] = y
            self.data_store['imu2']['accel']['z'] = z
            self.data_store['imu2']['last_update'] = current_time

    def decode_imu2_gyro(self, data):
        """解碼IMU2陀螺儀數據 (0x288)
        X: bytes 0-1, Y: bytes 2-3, Z: bytes 4-5
        格式: 0.1 deg/s /LSB (signed)
        """
        if len(data) >= 6:
            x_raw = struct.unpack('<h', data[0:2])[0]
            y_raw = struct.unpack('<h', data[2:4])[0]
            z_raw = struct.unpack('<h', data[4:6])[0]
            
            # 轉換為 deg/s
            x = x_raw * 0.1
            y = y_raw * 0.1
            z = z_raw * 0.1
            
            current_time = time.time()
            self.data_store['imu2']['gyro']['x'] = x
            self.data_store['imu2']['gyro']['y'] = y
            self.data_store['imu2']['gyro']['z'] = z
            self.data_store['imu2']['last_update'] = current_time

    def decode_imu2_quaternion(self, data):
        """解碼IMU2四元數數據 (0x488)
        W: bytes 0-1, X: bytes 2-3, Y: bytes 4-5, Z: bytes 6-7
        格式: 0.0001 /LSB (signed)
        """
        if len(data) >= 8:
            w_raw = struct.unpack('<h', data[0:2])[0]
            x_raw = struct.unpack('<h', data[2:4])[0]
            y_raw = struct.unpack('<h', data[4:6])[0]
            z_raw = struct.unpack('<h', data[6:8])[0]
            
            # 轉換為單位四元數
            w = w_raw * 0.0001
            x = x_raw * 0.0001
            y = y_raw * 0.0001
            z = z_raw * 0.0001
            
            current_time = time.time()
            self.data_store['imu2']['quaternion']['w'] = w
            self.data_store['imu2']['quaternion']['x'] = x
            self.data_store['imu2']['quaternion']['y'] = y
            self.data_store['imu2']['quaternion']['z'] = z
            self.data_store['imu2']['last_update'] = current_time

    # Xsens IMU 解碼函數
    def decode_xsens_quaternion(self, data):
        """解碼Xsens四元數數據 (0x021)
        Q0-Q3: bytes 0-7, 每個16位有符號
        格式: 3.05176e-05 /LSB
        """
        if len(data) >= 8:
            q0_raw = struct.unpack('>h', data[0:2])[0]  # Big-endian based on DBC
            q1_raw = struct.unpack('>h', data[2:4])[0]
            q2_raw = struct.unpack('>h', data[4:6])[0]
            q3_raw = struct.unpack('>h', data[6:8])[0]
            
            scale = 3.05176e-05
            q0 = q0_raw * scale
            q1 = q1_raw * scale
            q2 = q2_raw * scale
            q3 = q3_raw * scale
            
            current_time = time.time()
            self.data_store['xsens']['quaternion']['q0'] = q0
            self.data_store['xsens']['quaternion']['q1'] = q1
            self.data_store['xsens']['quaternion']['q2'] = q2
            self.data_store['xsens']['quaternion']['q3'] = q3
            self.data_store['xsens']['last_update'] = current_time

    def decode_xsens_delta_v(self, data):
        """解碼Xsens DeltaV數據 (0x031)
        X, Y, Z: bytes 0-5, Exponent: byte 6
        格式: X,Y scale=-7.62939e-06, Z scale=7.62939e-06
        """
        if len(data) >= 7:
            x_raw = struct.unpack('>h', data[0:2])[0]
            y_raw = struct.unpack('>h', data[2:4])[0]
            z_raw = struct.unpack('>h', data[4:6])[0]
            exponent = data[6]
            
            x = x_raw * (-7.62939e-06)
            y = y_raw * (-7.62939e-06)
            z = z_raw * 7.62939e-06
            
            current_time = time.time()
            self.data_store['xsens']['delta_v']['x'] = x
            self.data_store['xsens']['delta_v']['y'] = y
            self.data_store['xsens']['delta_v']['z'] = z
            self.data_store['xsens']['delta_v']['exponent'] = exponent
            self.data_store['xsens']['last_update'] = current_time

    def decode_xsens_rate_of_turn(self, data):
        """解碼Xsens角速度數據 (0x032)
        gyrX, gyrY, gyrZ: bytes 0-5
        格式: X,Y scale=-0.00195313, Z scale=0.00195313 rad/s
        """
        if len(data) >= 6:
            gyr_x_raw = struct.unpack('>h', data[0:2])[0]
            gyr_y_raw = struct.unpack('>h', data[2:4])[0]
            gyr_z_raw = struct.unpack('>h', data[4:6])[0]
            
            gyr_x = gyr_x_raw * (-0.00195313)
            gyr_y = gyr_y_raw * (-0.00195313)
            gyr_z = gyr_z_raw * 0.00195313
            
            current_time = time.time()
            self.data_store['xsens']['rate_of_turn']['gyr_x'] = gyr_x
            self.data_store['xsens']['rate_of_turn']['gyr_y'] = gyr_y
            self.data_store['xsens']['rate_of_turn']['gyr_z'] = gyr_z
            self.data_store['xsens']['last_update'] = current_time

    def decode_xsens_delta_q(self, data):
        """解碼Xsens DeltaQ數據 (0x033)
        DeltaQ0-3: bytes 0-7
        格式: 3.05185e-05 /LSB
        """
        if len(data) >= 8:
            dq0_raw = struct.unpack('>h', data[0:2])[0]
            dq1_raw = struct.unpack('>h', data[2:4])[0]
            dq2_raw = struct.unpack('>h', data[4:6])[0]
            dq3_raw = struct.unpack('>h', data[6:8])[0]
            
            scale = 3.05185e-05
            dq0 = dq0_raw * scale
            dq1 = dq1_raw * scale
            dq2 = dq2_raw * scale
            dq3 = dq3_raw * scale
            
            current_time = time.time()
            self.data_store['xsens']['delta_q']['dq0'] = dq0
            self.data_store['xsens']['delta_q']['dq1'] = dq1
            self.data_store['xsens']['delta_q']['dq2'] = dq2
            self.data_store['xsens']['delta_q']['dq3'] = dq3
            self.data_store['xsens']['last_update'] = current_time

    def decode_xsens_acceleration(self, data):
        """解碼Xsens加速度數據 (0x034)
        accX, accY, accZ: bytes 0-5
        格式: X,Y scale=-0.00390625, Z scale=0.00390625 m/s²
        """
        if len(data) >= 6:
            acc_x_raw = struct.unpack('>h', data[0:2])[0]
            acc_y_raw = struct.unpack('>h', data[2:4])[0]
            acc_z_raw = struct.unpack('>h', data[4:6])[0]
            
            acc_x = acc_x_raw * (-0.00390625)
            acc_y = acc_y_raw * (-0.00390625)
            acc_z = acc_z_raw * 0.00390625
            
            current_time = time.time()
            self.data_store['xsens']['acceleration']['acc_x'] = acc_x
            self.data_store['xsens']['acceleration']['acc_y'] = acc_y
            self.data_store['xsens']['acceleration']['acc_z'] = acc_z
            self.data_store['xsens']['last_update'] = current_time

    def decode_xsens_magnetic_field(self, data):
        """解碼Xsens磁場數據 (0x041)
        magX, magY, magZ: bytes 0-5
        格式: X,Y scale=-0.000976563, Z scale=0.000976563 a.u.
        """
        if len(data) >= 6:
            mag_x_raw = struct.unpack('>h', data[0:2])[0]
            mag_y_raw = struct.unpack('>h', data[2:4])[0]
            mag_z_raw = struct.unpack('>h', data[4:6])[0]
            
            mag_x = mag_x_raw * (-0.000976563)
            mag_y = mag_y_raw * (-0.000976563)
            mag_z = mag_z_raw * 0.000976563
            
            current_time = time.time()
            self.data_store['xsens']['magnetic_field']['mag_x'] = mag_x
            self.data_store['xsens']['magnetic_field']['mag_y'] = mag_y
            self.data_store['xsens']['magnetic_field']['mag_z'] = mag_z
            self.data_store['xsens']['last_update'] = current_time

    def decode_xsens_latlon(self, data):
        """解碼Xsens GPS經緯度數據 (0x071)
        latitude: bytes 0-3 (32位有符號)
        longitude: bytes 4-7 (32位有符號)
        格式: lat scale=5.96046e-08, lon scale=1.19209e-07 deg
        """
        if len(data) >= 8:
            lat_raw = struct.unpack('>i', data[0:4])[0]
            lon_raw = struct.unpack('>i', data[4:8])[0]
            
            lat = lat_raw * 5.96046e-08
            lon = lon_raw * 1.19209e-07
            
            current_time = time.time()
            self.data_store['xsens']['gps']['lat'] = lat
            self.data_store['xsens']['gps']['lon'] = lon
            self.data_store['xsens']['last_update'] = current_time

    def decode_xsens_altitude(self, data):
        """解碼Xsens高度數據 (0x072)
        altEllipsoid: bytes 0-3 (32位有符號)
        格式: scale=3.05176e-05 m
        """
        if len(data) >= 4:
            alt_raw = struct.unpack('>i', data[0:4])[0]
            alt = alt_raw * 3.05176e-05
            
            current_time = time.time()
            self.data_store['xsens']['gps']['alt'] = alt
            self.data_store['xsens']['last_update'] = current_time

    def decode_xsens_velocity(self, data):
        """解碼Xsens速度數據 (0x076)
        velX, velY, velZ: bytes 0-5
        格式: X,Y scale=-0.015625, Z scale=0.015625 m/s
        """
        if len(data) >= 6:
            vel_x_raw = struct.unpack('>h', data[0:2])[0]
            vel_y_raw = struct.unpack('>h', data[2:4])[0]
            vel_z_raw = struct.unpack('>h', data[4:6])[0]
            
            vel_x = vel_x_raw * (-0.015625)
            vel_y = vel_y_raw * (-0.015625)
            vel_z = vel_z_raw * 0.015625
            
            current_time = time.time()
            self.data_store['xsens']['velocity']['vel_x'] = vel_x
            self.data_store['xsens']['velocity']['vel_y'] = vel_y
            self.data_store['xsens']['velocity']['vel_z'] = vel_z
            self.data_store['xsens']['last_update'] = current_time

# global CAN receiver instance
can_receiver = None




app.mount("/static", StaticFiles(directory="static"), name="static")

# @app.get("/gps", response_class=HTMLResponse)
# async def read_index(request: Request):
#     return templates.TemplateResponse("gps_dashboard.html", {"request": request})

@app.get("/AMS", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("battery_dashboard _666.html", {"request": request})

@app.get("/TQ", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashchart.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("chart_dashboard-v4.html", {"request": request})
    # return templates.TemplateResponse("IMU2_3D_dashboard.html", {"request": request})

@app.get("/IMU", response_class=HTMLResponse)
async def imu_dashboard(request: Request):
    return templates.TemplateResponse("imu_realtime_dashboard.html", {"request": request})

@app.get("/xsens", response_class=HTMLResponse)
async def xsens_dashboard(request: Request):
    return templates.TemplateResponse("xsens_dashboard.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("enhanced_racing_dashboard.html", {"request": request})


@app.get('/api/data')
async def get_data():
    if can_receiver:
        return {
            'timestamp': can_receiver.data_store['timestamp']['time'].isoformat() if can_receiver.data_store['timestamp']['time'] else None,
            'gps': can_receiver.data_store['gps'],
            'velocity': can_receiver.data_store['velocity'],
            'distance': can_receiver.data_store['distance'],
            'accumulator': can_receiver.data_store['accumulator'],
            'inverters': can_receiver.data_store['inverters'],
            'vcu': can_receiver.data_store['vcu'],
            'imu': can_receiver.data_store['imu'],
            'imu2': can_receiver.data_store['imu2'],
            'xsens': can_receiver.data_store['xsens'],
            'message_count': can_receiver.message_count,
            'update_time': datetime.now().isoformat()
        }
    else:
        return {'error': 'CAN receiver not initialized'}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    print('Client connected')
    # 新增：連線時主動推送一次資料
    if can_receiver:
        await can_receiver.broadcast_data()
    try:
        while True:
            await websocket.receive_text()  # 等待客戶端發送消息以保持連接
    except Exception as e:
        print('Client disconnected', e)
    finally:
        if websocket in connections:
            connections.remove(websocket)

async def start_can_receiver():
    """啟動 CAN 接收器"""
    global can_receiver
    can_receiver = CanReceiverWebApp()
    await can_receiver.start_can_receiver()

@app.on_event("startup")
async def startup_event():
    # 啟動 CAN 接收器任務
    asyncio.create_task(start_can_receiver())

@app.post('/api/control/switch-mode')
async def switch_mode(request: Request):
    data = await request.json()
    use_csv = data.get('use_csv', True)
    
    if can_receiver:
        if can_receiver.switch_mode(use_csv):
            mode_name = 'CSV' if use_csv else 'CAN'
            return {'status': f'switched to {mode_name} mode', 'mode': mode_name}
        else:
            return {'error': 'Failed to switch mode'}
    return {'error': 'CAN receiver not initialized'}

@app.get('/api/control/mode')
async def get_current_mode():
    if can_receiver:
        return can_receiver.get_current_mode()
    return {'error': 'CAN receiver not initialized'}

@app.post('/api/control/pause')
async def pause_playback():
    if can_receiver:
        can_receiver.pause_playback()
        return {'status': 'paused'}
    return {'error': 'CAN receiver not initialized'}

@app.post('/api/control/resume')
async def resume_playback():
    if can_receiver:
        can_receiver.resume_playback()
        return {'status': 'resumed'}
    return {'error': 'CAN receiver not initialized'}

@app.post('/api/control/speed')
async def set_speed(request: Request):
    data = await request.json()
    speed = data.get('speed', 1.0)
    if can_receiver:
        can_receiver.set_playback_speed(speed)
        return {'status': f'speed set to {speed}x'}
    return {'error': 'CAN receiver not initialized'}

@app.post('/api/control/jump')
async def jump_playback(request: Request):
    data = await request.json()
    if 'percentage' in data:
        percentage = data['percentage']
        if can_receiver and can_receiver.jump_to_percentage(percentage):
            return {'status': f'jumped to {percentage}%'}
    elif 'seconds' in data:
        seconds = data['seconds']
        if can_receiver and can_receiver.jump_time(seconds):
            return {'status': f'jumped {seconds} seconds'}
    return {'error': 'Invalid jump request'}

@app.post('/api/control/switch-file')
async def switch_file(request: Request):
    data = await request.json()
    filename = data.get('filename')
    if can_receiver and filename:
        if can_receiver.switch_csv_file(filename):
            return {'status': f'switched to {filename}'}
        else:
            return {'error': f'Failed to switch to {filename}'}
    return {'error': 'Invalid file switch request'}

@app.get('/api/control/status')
async def get_control_status():
    if can_receiver:
        return can_receiver.get_playback_status()
    return {'error': 'CAN receiver not initialized'}

@app.get('/api/control/files')
async def get_available_files():
    if can_receiver:
        return {'files': can_receiver.available_csv_files}
    return {'error': 'CAN receiver not initialized'}

if __name__ == '__main__':
    print("Starting NTURT CAN Monitor Web Application...")
    print("Access the web interface at: http://100.127.237.75:8888")
    print("Access the web interface at: http://localhost:8888/dashboard")
    print("For remote access via Tailscale, use your Tailscale IP address.")
    print("CSV BASE DIRECTORY:", DIRBASE)
    print("Press Ctrl+C to stop the application.")
    
    uvicorn.run(app, host='0.0.0.0', port=PORT)
