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
from CanDecoder import CanDecoder


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USE_CSV = True
# CSV_FILE = '../LOGS/can_log_20250727_112357.csv'
CSV_FILE = "../LOGS/can_log_20250731_004450.csv"
CSV_SPEED = 1.0
PORT = 8888
DIRBASE = "../LOGS/"

templates = Jinja2Templates(directory="templates")

# WebSocket connections
connections: List[WebSocket] = []

class CanReceiverWebApp:
    def __init__(self, use_csv=USE_CSV, csv_file=CSV_FILE, csv_speed=CSV_SPEED):
        self.use_csv = use_csv
        self.csv_file = csv_file
        self.csv_speed = csv_speed
        self.index = 0
        self.is_paused = False
        self.playback_speed = 1.0
        self.current_csv_file = csv_file
        self.available_csv_files = self.scan_csv_files()
        self.total_csv_messages = 0
        self.decoder = CanDecoder()
        self.running = True
        self.message_count = 0
        
        # Initialize CAN bus or CSV reader
        if self.use_csv:
            self.csv_data = []
            self.csv_index = 0
            self.csv_start_time = None
            self.bus = None
            self.load_csv_file()
        else:
            try:
                self.bus = can.interface.Bus(channel='can0', bustype='socketcan')
            except Exception as e:
                print(f"Warning: Could not initialize CAN bus: {e}")
                self.bus = None
        
        print("CAN Receiver Web App Started")

    async def start_can_receiver(self):
        """啟動CAN接收循環 (async)"""
        while self.running:
            try:
                if self.use_csv:
                    await self.csv_receive_callback()
                else:
                    await self.real_can_receive_callback()
                await asyncio.sleep(0.001)
            except Exception as e:
                print(f"Error in CAN receiver loop: {e}")
                await asyncio.sleep(0.1)

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
            return True  
        
        old_mode = "CSV" if self.use_csv else "CAN"
        new_mode = "CSV" if use_csv else "CAN"
        
        try:
            # 停止當前模式
            if self.bus:
                self.bus.shutdown()
                self.bus = None
            
            # 重置數據
            self.use_csv = use_csv
            self.csv_index = 0
            self.csv_start_time = None
            self.csv_base_timestamp = None
            self.is_paused = False
            
            if use_csv:
                # 切換到 CSV 模式
                self.csv_data = []
                # 刷新可用的 CSV 檔案列表
                self.available_csv_files = self.scan_csv_files()
                self.load_csv_file()
                print(f"Switched from {old_mode} to CSV mode")
                print(f"Refreshed CSV files list: {len(self.available_csv_files)} files found")
            else:
                # 切換到 CAN 模式
                try:
                    self.bus = can.interface.Bus(channel='can0', bustype='socketcan')
                    print(f"Switched from {old_mode} to CAN mode")
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

    def send_can_control_command(self, command_byte):
        """發送 CAN 控制命令到 0x420"""
        if not self.is_can_available():
            return False, "CAN interface not available"
        
        try:
            temp_bus = can.interface.Bus(channel='can0', bustype='socketcan')
            data = [command_byte] + [0x00] * 7  # 第一個 byte 是命令，其餘填 0
            message = can.Message(arbitration_id=0x420, data=data, is_extended_id=False)
            temp_bus.send(message)
            temp_bus.shutdown()
            
            command_name = "START" if command_byte == 0x01 else "STOP" if command_byte == 0x02 else "UNKNOWN"
            print(f"Sent CAN control command: {command_name} (0x420: {command_byte:02X})")
            return True, f"Successfully sent {command_name} command"
        except Exception as e:
            return False, f"Failed to send CAN command: {str(e)}"

    async def broadcast_data(self):
        """廣播數據到所有連接的客戶端"""
        if not connections:
            return
        broadcast_data = {
            'timestamp': self.decoder.data_store['timestamp']['time'].isoformat() if self.decoder.data_store['timestamp']['time'] else None,
            'gps': self.decoder.data_store['gps'],
            'velocity': self.decoder.data_store['velocity'],
            'accumulator': self.decoder.data_store['accumulator'],
            'inverters': self.decoder.data_store['inverters'],
            'vcu': self.decoder.data_store['vcu'],
            'canlogging': self.decoder.data_store['canlogging'],
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
                    await self.broadcast_data()
            await asyncio.sleep(0.001)
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
            await self.broadcast_data()
        await asyncio.sleep(0.001)

    def create_mock_can_message(self, can_id, data):
        """創建模擬的 CAN 訊息對象"""
        return self.decoder.create_mock_can_message(can_id, data)

    def process_can_message(self, msg: can.Message):
        self.decoder.process_can_message(msg)

# global CAN receiver instance
can_receiver = None




app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/gps", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("gps_dashboard.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("chart_dashboard-v2.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("enhanced_racing_dashboard.html", {"request": request})


@app.get('/api/data')
async def get_data():
    if can_receiver:
        return {
            'timestamp': can_receiver.decoder.data_store['timestamp']['time'].isoformat() if can_receiver.decoder.data_store['timestamp']['time'] else None,
            'gps': can_receiver.decoder.data_store['gps'],
            'velocity': can_receiver.decoder.data_store['velocity'],
            'accumulator': can_receiver.decoder.data_store['accumulator'],
            'inverters': can_receiver.decoder.data_store['inverters'],
            'vcu': can_receiver.decoder.data_store['vcu'],
            'canlogging': can_receiver.decoder.data_store['canlogging'],
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

@app.post('/api/control/refresh-files')
async def refresh_csv_files():
    if can_receiver:
        can_receiver.available_csv_files = can_receiver.scan_csv_files()
        return {
            'status': 'files refreshed',
            'count': len(can_receiver.available_csv_files),
            'files': can_receiver.available_csv_files
        }
    return {'error': 'CAN receiver not initialized'}

@app.post('/api/canlogging/start')
async def start_canlogging():
    """發送開始記錄命令"""
    if can_receiver:
        success, message = can_receiver.send_can_control_command(0x01)
        if success:
            return {'status': 'success', 'message': message}
        else:
            return {'status': 'error', 'message': message}
    return {'error': 'CAN receiver not initialized'}

@app.post('/api/canlogging/stop')
async def stop_canlogging():
    """發送停止記錄命令"""
    if can_receiver:
        success, message = can_receiver.send_can_control_command(0x02)
        if success:
            return {'status': 'success', 'message': message}
        else:
            return {'status': 'error', 'message': message}
    return {'error': 'CAN receiver not initialized'}


if __name__ == '__main__':
    print("Starting NTURT CAN Monitor Web Application...")
    print("Access the web interface at: http://100.107.50.128:5000/")
    print("Access the web interface at: http://localhost:8000/")
    print("For remote access via Tailscale, use your Tailscale IP address.")
    print("Press Ctrl+C to stop the application.")
    
    uvicorn.run(app, host='0.0.0.0', port=PORT)
