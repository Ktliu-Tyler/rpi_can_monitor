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

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# WebSocket connections
connections: List[WebSocket] = []

class CanReceiverWebApp:
    def __init__(self):
        try:
            self.bus = can.interface.Bus(channel='can0', bustype='socketcan')
        except Exception as e:
            print(f"Warning: Could not initialize CAN bus: {e}")
            self.bus = None
        
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
        """啟動CAN接收循環"""
        while self.running:
            try:
                if self.bus:
                    message = self.bus.recv(timeout=0.001)
                    if message:
                        self.message_count += 1
                        self.process_can_message(message)
                        await self.broadcast_data()
                await asyncio.sleep(0.001)  # 1ms
            except Exception as e:
                await asyncio.sleep(0.1)

    async def broadcast_data(self):
        """廣播數據到所有連接的客戶端"""
        if not connections:
            return
            
        broadcast_data = {
            'timestamp': self.data_store['timestamp']['time'].isoformat() if self.data_store['timestamp']['time'] else None,
            'gps': self.data_store['gps'],
            'velocity': self.data_store['velocity'],
            'accumulator': self.data_store['accumulator'],
            'inverters': self.data_store['inverters'],
            'message_count': self.message_count,
            'update_time': datetime.now().isoformat()
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

    def process_can_message(self, msg: can.Message):
        can_id = msg.arbitration_id
        data = msg.data
        
        try:
            # Timestamp 解碼
            if can_id == 0x100:
                self.decode_timestamp(data)
            
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
            
            # Accumulator 解碼
            elif can_id == 0x190:
                self.decode_cell_voltage(data)
            elif can_id == 0x390:
                self.decode_accumulator_temperature(data)
            elif can_id == 0x710:
                self.decode_accumulator_heartbeat(data)
            elif can_id == 0x290:
                self.decode_accumulator_status(data)
            elif can_id == 0x490:
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

        except Exception as e:
            print(f"Failed to decode CAN message ID 0x{can_id:03X}: {e}")

    # 以下是所有解碼函數（與原始代碼相同，但移除了 log_message 調用）
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
                temp = data[i] -32  # 0.5°C/LSB
                temperatures.append(temp)
            
            # 更新一維陣列中對應位置的數值
            current_time = time.time()
            for i, temp in enumerate(temperatures):
                array_index = index + i
                if array_index < 105:  # 確保不超出陣列範圍
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
            status_word = struct.unpack('<H', data[0:2])[0]
            feedback_torque_raw = struct.unpack('<h', data[2:4])[0]
            speed_raw = struct.unpack('<h', data[4:6])[0]
            
            feedback_torque = feedback_torque_raw / 1000.0
            speed = speed_raw
            
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['status'] = status_word
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
            target_torque = target_torque_raw / 1000.0
            
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['control_word'] = control_word
                self.data_store['inverters'][inv_num]['target_torque'] = target_torque
                self.data_store['inverters'][inv_num]['last_update'] = current_time

# 全局變量
can_receiver = None

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get('/api/data')
async def get_data():
    if can_receiver:
        return {
            'timestamp': can_receiver.data_store['timestamp']['time'].isoformat() if can_receiver.data_store['timestamp']['time'] else None,
            'gps': can_receiver.data_store['gps'],
            'velocity': can_receiver.data_store['velocity'],
            'accumulator': can_receiver.data_store['accumulator'],
            'inverters': can_receiver.data_store['inverters'],
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
            # 保持連接活躍
            await websocket.receive_text()
    except:
        print('Client disconnected')
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

if __name__ == '__main__':
    print("Starting NTURT CAN Monitor Web Application...")
    print("Access the web interface at: http://localhost:5000")
    print("For remote access via Tailscale, use your Tailscale IP address.")
    print("Press Ctrl+C to stop the application.")
    
    uvicorn.run(app, host='0.0.0.0', port=5000)


# 7/27 1:29