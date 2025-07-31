import can
import struct
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime

app = FastAPI()

from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory=".", html=True), name="static")

# 允許本地網頁跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 最新狀態緩衝區
latest_status = {
    "timestamp": None,
    "gps": {
        "lat": None, "lon": None, "alt": None, "speed": None,
        "frame_idx": None, "empty_frame_idx": None, "status": None, "mode": None
    },
    "velocity": {"x": None, "y": None, "z": None, "magnitude": None},
    "accumulator": {"voltage": None, "temperature": None, "soc": None, "current": None, "capacity": None, "status": None},
    "inverter": {},
}

def decode_status(status):
    status_map = {
        0x01: "STATUS_READY",
        0x02: "STATUS_ENABLED",
        0x04: "STATUS_FAULT"
    }
    result = []
    for bitmask, label in status_map.items():
        if status & bitmask:
            result.append(label)
    return result

# CAN 解碼函數（僅保留重點，後續可擴充）
def decode_can_message(msg):
    can_id = msg.arbitration_id
    data = msg.data
    # Timestamp
    if can_id == 0x100 and len(data) >= 6:
        ms_since_midnight = struct.unpack('<I', data[0:4])[0]
        days_since_1984 = struct.unpack('<H', data[4:6])[0]
        base_timestamp = 441763200
        total_seconds = base_timestamp + (days_since_1984 * 86400) + (ms_since_midnight / 1000.0)
        latest_status["timestamp"] = datetime.fromtimestamp(total_seconds).isoformat()
    # GPS基本資訊
    elif can_id == 0x400 and len(data) >= 8:
        lat_raw = struct.unpack('<i', data[0:4])[0]
        lon_raw = struct.unpack('<i', data[4:8])[0]
        latest_status["gps"]["lat"] = lat_raw / 1e7
        latest_status["gps"]["lon"] = lon_raw / 1e7
    # GPS擴展資訊
    elif can_id == 0x401 and len(data) >= 8:
        speed_raw = struct.unpack('<h', data[0:2])[0]
        alt_raw = struct.unpack('<h', data[2:4])[0]
        latest_status["gps"]["speed"] = speed_raw * 0.036
        latest_status["gps"]["alt"] = float(alt_raw)
        # 衛星數量: data[4]
        # GPS frame index 和 status
        if len(data) >= 7:
            frame_status_byte = data[5]
            status_byte = data[6]
            latest_status["gps"]["frame_idx"] = frame_status_byte & 0x0F
            latest_status["gps"]["empty_frame_idx"] = (frame_status_byte >> 4) & 0x0F
            latest_status["gps"]["status"] = status_byte & 0x07
            latest_status["gps"]["mode"] = (status_byte >> 3) & 0x1F
        else:
            latest_status["gps"]["frame_idx"] = None
            latest_status["gps"]["empty_frame_idx"] = None
            latest_status["gps"]["status"] = None
            latest_status["gps"]["mode"] = None
    # 速度方向
    elif can_id == 0x404 and len(data) >= 4:
        vx_raw = struct.unpack('<i', data[0:4])[0]
        latest_status["velocity"]["x"] = vx_raw / 1000.0
    elif can_id == 0x405 and len(data) >= 4:
        vy_raw = struct.unpack('<i', data[0:4])[0]
        latest_status["velocity"]["y"] = vy_raw / 1000.0
    elif can_id == 0x406 and len(data) >= 4:
        vz_raw = struct.unpack('<i', data[0:4])[0]
        latest_status["velocity"]["z"] = vz_raw / 1000.0
    elif can_id == 0x40A and len(data) >= 4:
        vmag_raw = struct.unpack('<i', data[0:4])[0]
        latest_status["velocity"]["magnitude"] = vmag_raw / 1000.0
    # Inverter 狀態
    elif 0x191 <= can_id <= 0x194 and len(data) >= 8:
        inv_num = can_id - 0x190
        # status_word = struct.unpack('<H', data[0:2])[0]
        status_wordHV = data[0]
        status_wordINV = data[1]  # Assuming status is a single byte
        status_HV = decode_status(int(status_wordHV, 16))
        status_INV = decode_status(int(status_wordINV, 16))
        status_word = f"HV({status_HV}) INV({status_INV})"
        feedback_torque_raw = struct.unpack('<h', data[2:4])[0]
        speed_raw = struct.unpack('<h', data[4:6])[0]
        feedback_torque = feedback_torque_raw / 1000.0
        speed = speed_raw
        if inv_num not in latest_status["inverter"]:
            latest_status["inverter"][inv_num] = {}
        latest_status["inverter"][inv_num]["status_word"] = status_word
        latest_status["inverter"][inv_num]["torque"] = feedback_torque
        latest_status["inverter"][inv_num]["speed"] = speed
    elif 0x291 <= can_id <= 0x294 and len(data) >= 6:
        inv_num = can_id - 0x290
        dc_voltage_raw = struct.unpack('<H', data[0:2])[0]
        dc_current_raw = struct.unpack('<H', data[2:4])[0]
        dc_voltage = dc_voltage_raw / 100.0
        dc_current = dc_current_raw / 100.0
        if inv_num not in latest_status["inverter"]:
            latest_status["inverter"][inv_num] = {}
        latest_status["inverter"][inv_num]["dc_voltage"] = dc_voltage
        latest_status["inverter"][inv_num]["dc_current"] = dc_current
    elif 0x391 <= can_id <= 0x394 and len(data) >= 6:
        inv_num = can_id - 0x390
        inv_mos_temp_raw = struct.unpack('<h', data[0:2])[0]
        mcu_temp_raw = struct.unpack('<h', data[2:4])[0]
        motor_temp_raw = struct.unpack('<h', data[4:6])[0]
        inv_mos_temp = inv_mos_temp_raw * 0.1
        mcu_temp = mcu_temp_raw * 0.1
        motor_temp = motor_temp_raw * 0.1
        if inv_num not in latest_status["inverter"]:
            latest_status["inverter"][inv_num] = {}
        latest_status["inverter"][inv_num]["mos_temp"] = inv_mos_temp
        latest_status["inverter"][inv_num]["mcu_temp"] = mcu_temp
        latest_status["inverter"][inv_num]["motor_temp"] = motor_temp
    elif 0x711 <= can_id <= 0x714 and len(data) >= 1:
        inv_num = can_id - 0x710
        heartbeat = data[0] == 0x7F
        if inv_num not in latest_status["inverter"]:
            latest_status["inverter"][inv_num] = {}
        latest_status["inverter"][inv_num]["heartbeat"] = heartbeat
    # Accumulator Voltage
    elif can_id == 0x190 and len(data) >= 8:
        voltages = [data[i] * 0.02 for i in range(1, min(8, len(data)))]
        latest_status["accumulator"]["voltage"] = voltages
    # Accumulator Temperature
    elif can_id == 0x390 and len(data) >= 8:
        temperatures = [data[i] * 0.5 for i in range(1, min(8, len(data)))]
        latest_status["accumulator"]["temperature"] = temperatures
    # Accumulator State
    elif can_id == 0x490 and len(data) >= 6:
        soc = data[0]
        current_raw = struct.unpack('<h', data[1:3])[0]
        capacity_raw = struct.unpack('<h', data[3:5])[0] if len(data) >= 5 else 0
        latest_status["accumulator"]["soc"] = soc
        latest_status["accumulator"]["current"] = current_raw * 0.01
        latest_status["accumulator"]["capacity"] = capacity_raw * 0.01
    # Accumulator Status
    elif can_id == 0x290 and len(data) >= 4:
        status = data[0]
        temp_raw = struct.unpack('<h', data[1:3])[0]
        voltage_raw = struct.unpack('<H', data[3:5])[0] if len(data) >= 5 else 0
        latest_status["accumulator"]["status"] = "OK" if status else "BAD"
    # Inverter State/Temp/Status 可依需求擴充

# CAN 監聽協程
async def can_listener():
    bus = can.interface.Bus(channel='can0', bustype='socketcan')
    while True:
        msg = bus.recv(timeout=0.01)
        if msg:
            decode_can_message(msg)
        await asyncio.sleep(0.001)  # 降低CPU佔用

# WebSocket 推送協程
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_json(latest_status)
        await asyncio.sleep(0.04)  # 每0.5秒推送一次

# 啟動時自動啟動CAN監聽
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(can_listener())

# 提供簡單首頁
@app.get("/")
def get():
    return HTMLResponse("""
    <html><body>
    <h2>CAN Monitor Server Running</h2>
    <p>WebSocket endpoint: <code>/ws</code></p>
    </body></html>
    """)

if __name__ == "__main__":
    uvicorn.run("can_monitor_server:app", host="0.0.0.0", port=8000, reload=False)
