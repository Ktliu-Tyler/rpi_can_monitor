import rclpy
from rclpy.node import Node
import can
import struct
import time
import os
from datetime import datetime

class CanReceiver(Node):
    def __init__(self):
        super().__init__('can_receiver')
        self.bus = can.interface.Bus(channel='can0', bustype='socketcan')
        
        # Display mode parameter
        self.declare_parameter('display_mode', 'scroll')  # 'scroll' or 'dashboard'
        self.display_mode = self.get_parameter('display_mode').get_parameter_value().string_value
        
        # Data storage for dashboard mode
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
                'cell_voltages': {}, 'cell_temperatures': {},
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
        
        # Legacy GPS數據暫存 (for backward compatibility)
        self.gps_lat = None
        self.gps_lon = None
        self.gps_alt = None
        
        # Position covariance 暫存 (9個float64)
        self.position_covariance = [0.0] * 9
        self.position_covariance_type = 0
        
        # 啟動CAN接收線程
        self.timer = self.create_timer(0.001, self.can_receive_callback)  # 1ms
        
        # Dashboard display timer (only for dashboard mode)
        if self.display_mode == 'dashboard':
            self.display_timer = self.create_timer(0.1, self.update_dashboard)  # 100ms
            os.system('clear')  # Clear screen initially
            self.get_logger().info("CAN Receiver Node Started - Dashboard Mode")
        else:
            self.get_logger().info("CAN Receiver Node Started - Scrolling Mode")
        
        self.get_logger().info("Configured for available data: NavSatFix (/fix) + TwistStamped (/vel)")

    def can_receive_callback(self):
        try:
            # 非阻塞方式接收CAN訊息
            message = self.bus.recv(timeout=0)
            if message:
                self.message_count += 1
                self.process_can_message(message)
        except Exception as e:
            pass  # 忽略timeout異常

    def log_message(self, message):
        """根據模式選擇日誌輸出方式"""
        if self.display_mode == 'scroll':
            self.get_logger().info(message)
        # Dashboard mode uses print in update_dashboard function

    def process_can_message(self, msg: can.Message):
        can_id = msg.arbitration_id
        data = msg.data
        
        try:
            # Timestamp 解碼 (參考timer_can_pub.py)
            if can_id == 0x100:  # Timestamp
                self.decode_timestamp(data)
            
            # GPS 解碼
            elif can_id == 0x400:  # GPS基本資訊 (緯度+經度)
                self.decode_gps_basic(data)
            elif can_id == 0x401:  # GPS擴展資訊 (高度)
                self.decode_gps_extended(data)
            elif 0x410 <= can_id <= 0x418:  # Position covariance (9個float64)
                self.decode_position_covariance(data, can_id - 0x410)
            elif can_id == 0x419:  # Position covariance type
                self.decode_position_covariance_type(data)
                
            # 速度資料解碼
            elif can_id == 0x402:  # X方向線性速度
                self.decode_velocity_x(data)
            elif can_id == 0x403:  # Y方向線性速度
                self.decode_velocity_y(data)
            elif can_id == 0x404:  # Z方向線性速度
                self.decode_velocity_z(data)
            elif can_id == 0x405:  # X軸角速度
                self.decode_angular_x(data)
            elif can_id == 0x406:  # Y軸角速度
                self.decode_angular_y(data)
            elif can_id == 0x407:  # Z軸角速度
                self.decode_angular_z(data)
            elif can_id == 0x408:  # 總速度大小
                self.decode_velocity_magnitude(data)
            
            # Accumulator 解碼
            elif can_id == 0x190:  # Cell Voltage
                self.decode_cell_voltage(data)
            elif can_id == 0x390:  # Temperature
                self.decode_accumulator_temperature(data)
            elif can_id == 0x710:  # Heartbeat
                self.decode_accumulator_heartbeat(data)
            elif can_id == 0x290:  # Status
                self.decode_accumulator_status(data)
            elif can_id == 0x490:  # State
                self.decode_accumulator_state(data)
            
            # Inverter 解碼
            elif 0x191 <= can_id <= 0x194:  # Inverter Status (0x190+X, X=1-4)
                inv_num = can_id - 0x190
                self.decode_inverter_status(data, inv_num)
            elif 0x291 <= can_id <= 0x294:  # Inverter State (0x290+X, X=1-4)
                inv_num = can_id - 0x290
                self.decode_inverter_state(data, inv_num)
            elif 0x391 <= can_id <= 0x394:  # Inverter Temperature (0x390+X, X=1-4)
                inv_num = can_id - 0x390
                self.decode_inverter_temperature(data, inv_num)
            elif 0x711 <= can_id <= 0x714:  # Inverter Heartbeat (0x710+X, X=1-4)
                inv_num = can_id - 0x710
                self.decode_inverter_heartbeat(data, inv_num)
            elif 0x210 <= can_id <= 0x214:  # Inverter Control (0x210+X, X=0-4)
                inv_num = can_id - 0x210
                self.decode_inverter_control(data, inv_num)

                
        except Exception as e:
            self.get_logger().error(f"Failed to decode CAN message ID 0x{can_id:03X}: {e}")

    # Timestamp 解碼函數 (參考timer_can_pub.py)
    def decode_timestamp(self, data):
        """解碼 0x100 - Timestamp"""
        if len(data) >= 6:
            # 解碼: ms_since_midnight (4 bytes) + days_since_1984 (2 bytes)
            ms_since_midnight = struct.unpack('<I', data[0:4])[0]
            days_since_1984 = struct.unpack('<H', data[4:6])[0]
            
            # 計算實際時間 (1984年1月1日 00:00:00 UTC的時間戳)
            base_timestamp = 441763200  # 1984-01-01 00:00:00 UTC
            total_seconds = base_timestamp + (days_since_1984 * 86400) + (ms_since_midnight / 1000.0)
            decoded_time = datetime.fromtimestamp(total_seconds)
            
            # Update data store
            current_time = time.time()
            self.data_store['timestamp']['time'] = decoded_time
            self.data_store['timestamp']['last_update'] = current_time
            
            self.log_message(
                f"[TIMESTAMP] MS since midnight: {ms_since_midnight}, "
                f"Days since 1984: {days_since_1984}, "
                f"Decoded time: {decoded_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}"
            )

    # Ecumaster GPS 解碼函數
    def decode_gps_basic(self, data):
        """解碼 0x400 - GPS基本資訊 (緯度+經度)"""
        if len(data) >= 8:
            # 緯度: 32-bit signed, 乘數 1/10^7
            lat_raw = struct.unpack('<i', data[0:4])[0]
            self.gps_lat = lat_raw / 10**7
            
            # 經度: 32-bit signed, 乘數 1/10^7
            lon_raw = struct.unpack('<i', data[4:8])[0]
            self.gps_lon = lon_raw / 10**7
            
            # Update data store
            current_time = time.time()
            self.data_store['gps']['lat'] = self.gps_lat
            self.data_store['gps']['lon'] = self.gps_lon
            self.data_store['gps']['last_update'] = current_time
            
            self.log_message(
                f"[GPS BASIC] Lat: {self.gps_lat:.7f}, Lon: {self.gps_lon:.7f} "
                f"(Raw: lat={lat_raw}, lon={lon_raw})"
            )

    def decode_gps_extended(self, data):
        """解碼 0x401 - GPS擴展資訊 (高度)"""
        if len(data) >= 2:
            # 高度: 16-bit signed, 係數 1
            alt_raw = struct.unpack('<h', data[0:2])[0]
            status_byte = data[2] if len(data) > 2 else 0
            self.gps_alt = float(alt_raw)
            
            # Update data store
            current_time = time.time()
            self.data_store['gps']['alt'] = self.gps_alt
            self.data_store['gps']['status'] = status_byte
            self.data_store['gps']['last_update'] = current_time
            
            self.log_message(
                f"[GPS EXTENDED] Altitude: {self.gps_alt:.1f}m (Raw: {alt_raw})"
                f" Status: {status_byte:#04x}" 
            )

    def decode_position_covariance(self, data, index):
        """解碼 0x410-0x418 - Position covariance (9個float64)"""
        if len(data) >= 8 and 0 <= index < 9:
            # 解碼 float64 (8 bytes)
            covariance_value = struct.unpack('<d', data[0:8])[0]
            self.position_covariance[index] = covariance_value
            
            self.get_logger().info(
                f"[GPS COVARIANCE] Index {index}: {covariance_value:.6e}"
            )

    def decode_position_covariance_type(self, data):
        """解碼 0x419 - Position covariance type"""
        if len(data) >= 1:
            self.position_covariance_type = struct.unpack('<B', data[0:1])[0]
            
            covariance_types = {
                0: "UNKNOWN",
                1: "APPROXIMATED", 
                2: "DIAGONAL_KNOWN",
                3: "KNOWN"
            }
            type_name = covariance_types.get(self.position_covariance_type, "UNKNOWN")
            
            # Update data store
            current_time = time.time()
            self.data_store['covariance']['type'] = self.position_covariance_type
            self.data_store['covariance']['type_name'] = type_name
            self.data_store['covariance']['last_update'] = current_time
            
            self.log_message(
                f"[GPS COVARIANCE TYPE] Type: {self.position_covariance_type} ({type_name})"
            )

    def decode_velocity_x(self, data):
        """解碼 0x402 - X方向線性速度"""
        if len(data) >= 4:
            vx_raw = struct.unpack('<i', data[0:4])[0]
            vx = vx_raw / 1000.0  # mm/s to m/s
            
            # Update data store
            current_time = time.time()
            self.data_store['velocity']['linear_x'] = vx
            self.data_store['velocity']['last_update'] = current_time
            
            self.log_message(f"[VELOCITY X] Linear X: {vx:.3f} m/s (Raw: {vx_raw} mm/s)")

    def decode_velocity_y(self, data):
        """解碼 0x403 - Y方向線性速度"""
        if len(data) >= 4:
            vy_raw = struct.unpack('<i', data[0:4])[0]
            vy = vy_raw / 1000.0  # mm/s to m/s
            
            # Update data store
            current_time = time.time()
            self.data_store['velocity']['linear_y'] = vy
            self.data_store['velocity']['last_update'] = current_time
            
            self.log_message(f"[VELOCITY Y] Linear Y: {vy:.3f} m/s (Raw: {vy_raw} mm/s)")

    def decode_velocity_z(self, data):
        """解碼 0x404 - Z方向線性速度"""
        if len(data) >= 4:
            vz_raw = struct.unpack('<i', data[0:4])[0]
            vz = vz_raw / 1000.0  # mm/s to m/s
            
            # Update data store
            current_time = time.time()
            self.data_store['velocity']['linear_z'] = vz
            self.data_store['velocity']['last_update'] = current_time
            
            self.log_message(f"[VELOCITY Z] Linear Z: {vz:.3f} m/s (Raw: {vz_raw} mm/s)")

    def decode_angular_x(self, data):
        """解碼 0x405 - X軸角速度"""
        if len(data) >= 4:
            wx_raw = struct.unpack('<i', data[0:4])[0]
            wx = wx_raw / 1000.0  # mrad/s to rad/s
            
            # Update data store
            current_time = time.time()
            self.data_store['velocity']['angular_x'] = wx
            self.data_store['velocity']['last_update'] = current_time
            
            self.log_message(f"[ANGULAR X] Angular X: {wx:.3f} rad/s (Raw: {wx_raw} mrad/s)")

    def decode_angular_y(self, data):
        """解碼 0x406 - Y軸角速度"""
        if len(data) >= 4:
            wy_raw = struct.unpack('<i', data[0:4])[0]
            wy = wy_raw / 1000.0  # mrad/s to rad/s
            
            # Update data store
            current_time = time.time()
            self.data_store['velocity']['angular_y'] = wy
            self.data_store['velocity']['last_update'] = current_time
            
            self.log_message(f"[ANGULAR Y] Angular Y: {wy:.3f} rad/s (Raw: {wy_raw} mrad/s)")

    def decode_angular_z(self, data):
        """解碼 0x407 - Z軸角速度"""
        if len(data) >= 4:
            wz_raw = struct.unpack('<i', data[0:4])[0]
            wz = wz_raw / 1000.0  # mrad/s to rad/s
            
            # Update data store
            current_time = time.time()
            self.data_store['velocity']['angular_z'] = wz
            self.data_store['velocity']['last_update'] = current_time
            
            self.log_message(f"[ANGULAR Z] Angular Z: {wz:.3f} rad/s (Raw: {wz_raw} mrad/s)")

    def decode_velocity_magnitude(self, data):
        """解碼 0x408 - 總速度大小"""
        if len(data) >= 4:
            vmag_raw = struct.unpack('<i', data[0:4])[0]
            vmag = vmag_raw / 1000.0  # mm/s to m/s
            speed_kmh = vmag * 3.6  # m/s to km/h
            
            # Update data store
            current_time = time.time()
            self.data_store['velocity']['magnitude'] = vmag
            self.data_store['velocity']['speed_kmh'] = speed_kmh
            self.data_store['velocity']['last_update'] = current_time
            
            self.log_message(
                f"[VELOCITY MAG] Total Speed: {vmag:.3f} m/s ({speed_kmh:.2f} km/h, Raw: {vmag_raw} mm/s)"
            )

    # Accumulator 解碼函數
    def decode_cell_voltage(self, data):
        """解碼 0x190 - Cell Voltage"""
        if len(data) >= 8:
            index = data[0]
            # Cell voltages: 20mV/LSB unsigned
            voltages = []
            for i in range(1, min(8, len(data))):
                voltage = data[i] * 0.02  # 20mV/LSB
                voltages.append(voltage)
            
            # Update data store
            current_time = time.time()
            self.data_store['accumulator']['cell_voltages'][index] = voltages
            self.data_store['accumulator']['last_update'] = current_time
            
            self.log_message(f"[ACCUMULATOR] Cell Voltages (Index {index}): {voltages}V")

    def decode_accumulator_temperature(self, data):
        """解碼 0x390 - Temperature"""
        if len(data) >= 8:
            index = data[0]
            # Temperatures: 0.5°C/LSB unsigned
            temperatures = []
            for i in range(1, min(8, len(data))):
                temp = data[i] * 0.5  # 0.5°C/LSB
                temperatures.append(temp)
            
            # Update data store
            current_time = time.time()
            self.data_store['accumulator']['cell_temperatures'][index] = temperatures
            self.data_store['accumulator']['last_update'] = current_time
            
            self.log_message(f"[ACCUMULATOR] Temperatures (Index {index}): {temperatures}°C")

    def decode_accumulator_heartbeat(self, data):
        """解碼 0x710 - Heartbeat"""
        if len(data) >= 1:
            heartbeat = data[0] == 0x7F
            
            # Update data store
            current_time = time.time()
            self.data_store['accumulator']['heartbeat'] = heartbeat
            self.data_store['accumulator']['last_update'] = current_time
            
            self.log_message(f"[ACCUMULATOR] Heartbeat: {'OK' if heartbeat else 'FAIL'}")

    def decode_accumulator_status(self, data):
        """解碼 0x290 - Status"""
        if len(data) >= 7:
            status = data[0]  # 0=Bad, 1=OK
            temp_raw = struct.unpack('<h', data[1:3])[0]  # signed
            
            # Voltage: 4個字節組合成32位整數 (小端序)，然後除以1024
            voltage_raw = struct.unpack('<I', data[3:7])[0] if len(data) >= 7 else 0  # unsigned 32-bit
            
            temperature = temp_raw * 0.125  # 0.125°C/LSB
            voltage = voltage_raw / 1024.0  # 1/1024V/LSB
            
            # Update data store
            current_time = time.time()
            self.data_store['accumulator']['status'] = status
            self.data_store['accumulator']['temperature'] = temperature
            self.data_store['accumulator']['voltage'] = voltage
            self.data_store['accumulator']['last_update'] = current_time
            
            self.log_message(
                f"[ACCUMULATOR] Status: {'OK' if status else 'BAD'}, "
                f"Temp: {temperature:.1f}°C, Voltage: {voltage:.3f}V "
                f"(Raw: 0x{voltage_raw:08X} = {voltage_raw})"
            )

    def decode_accumulator_state(self, data):
        """解碼 0x490 - State"""
        if len(data) >= 7:
            soc = data[0]  # 1%/LSB
            current_raw = struct.unpack('<h', data[1:3])[0]  # signed
            
            # Capacity: 4個字節組合成32位有符號整數 (10mAh/LSB)
            capacity_raw = struct.unpack('<i', data[3:7])[0] if len(data) >= 7 else 0  # signed 32-bit
            
            current = current_raw * 0.01  # 10mA/LSB
            capacity = capacity_raw * 0.01  # 10mAh/LSB (signed)
            
            # Update data store
            current_time = time.time()
            self.data_store['accumulator']['soc'] = soc
            self.data_store['accumulator']['current'] = current
            self.data_store['accumulator']['capacity'] = capacity
            self.data_store['accumulator']['last_update'] = current_time
            
            self.log_message(
                f"[ACCUMULATOR] SOC: {soc}%, Current: {current:.2f}A, "
                f"Capacity: {capacity:.2f}Ah (Raw: 0x{capacity_raw:08X} = {capacity_raw})"
            )

    # Inverter 解碼函數
    def decode_inverter_status(self, data, inv_num):
        """解碼 0x190+X - Inverter Status"""
        if len(data) >= 6:
            status_word = struct.unpack('<H', data[0:2])[0]
            feedback_torque_raw = struct.unpack('<h', data[2:4])[0]  # signed
            speed_raw = struct.unpack('<h', data[4:6])[0]  # signed
            
            feedback_torque = feedback_torque_raw / 1000.0  # 1/1000 rated torque/LSB
            speed = speed_raw  # RPM/LSB
            
            # Update data store
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['status'] = status_word
                self.data_store['inverters'][inv_num]['torque'] = feedback_torque
                self.data_store['inverters'][inv_num]['speed'] = speed
                self.data_store['inverters'][inv_num]['last_update'] = current_time
            
            inverter_names = {1: 'FL', 2: 'FR', 3: 'RL', 4: 'RR'}
            inv_name = inverter_names.get(inv_num, f'INV{inv_num}')
            
            self.log_message(
                f"[INVERTER {inv_name}] Status: 0x{status_word:04X}, "
                f"Torque: {feedback_torque:.3f}, Speed: {speed}RPM"
            )

    def decode_inverter_state(self, data, inv_num):
        """解碼 0x290+X - Inverter State"""
        if len(data) >= 4:
            dc_voltage_raw = struct.unpack('<H', data[0:2])[0]  # unsigned
            dc_current_raw = struct.unpack('<H', data[2:4])[0]  # unsigned
            
            dc_voltage = dc_voltage_raw / 100.0  # 1/100V/LSB
            dc_current = dc_current_raw / 100.0  # 1/100A/LSB
            
            # Update data store
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['dc_voltage'] = dc_voltage
                self.data_store['inverters'][inv_num]['dc_current'] = dc_current
                self.data_store['inverters'][inv_num]['last_update'] = current_time
            
            inverter_names = {1: 'FL', 2: 'FR', 3: 'RL', 4: 'RR'}
            inv_name = inverter_names.get(inv_num, f'INV{inv_num}')
            
            self.log_message(
                f"[INVERTER {inv_name}] DC Voltage: {dc_voltage:.2f}V, DC Current: {dc_current:.2f}A"
            )

    def decode_inverter_temperature(self, data, inv_num):
        """解碼 0x390+X - Inverter Temperature"""
        if len(data) >= 6:
            inv_mos_temp_raw = struct.unpack('<h', data[0:2])[0]  # signed
            mcu_temp_raw = struct.unpack('<h', data[2:4])[0]  # signed
            motor_temp_raw = struct.unpack('<h', data[4:6])[0]  # signed
            
            inv_mos_temp = inv_mos_temp_raw * 0.1  # 0.1°C/LSB
            mcu_temp = mcu_temp_raw * 0.1  # 0.1°C/LSB
            motor_temp = motor_temp_raw * 0.1  # 0.1°C/LSB
            
            # Update data store
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['mos_temp'] = inv_mos_temp
                self.data_store['inverters'][inv_num]['mcu_temp'] = mcu_temp
                self.data_store['inverters'][inv_num]['motor_temp'] = motor_temp
                self.data_store['inverters'][inv_num]['last_update'] = current_time
            
            inverter_names = {1: 'FL', 2: 'FR', 3: 'RL', 4: 'RR'}
            inv_name = inverter_names.get(inv_num, f'INV{inv_num}')
            
            self.log_message(
                f"[INVERTER {inv_name}] Temps - MOS: {inv_mos_temp:.1f}°C, "
                f"MCU: {mcu_temp:.1f}°C, Motor: {motor_temp:.1f}°C"
            )

    def decode_inverter_heartbeat(self, data, inv_num):
        """解碼 0x710+X - Inverter Heartbeat"""
        if len(data) >= 1:
            heartbeat = data[0] == 0x00
            
            # Update data store
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['heartbeat'] = heartbeat
                self.data_store['inverters'][inv_num]['last_update'] = current_time
            
            inverter_names = {1: 'FL', 2: 'FR', 3: 'RL', 4: 'RR'}
            inv_name = inverter_names.get(inv_num, f'INV{inv_num}')
            
            self.log_message(f"[INVERTER {inv_name}] Heartbeat: {'OK' if heartbeat else f'FAIL'}")

    def decode_inverter_control(self, data, inv_num):
        """解碼 0x210+X - Inverter Control (Control word + Target Torque)"""
        if len(data) >= 4:
            control_word = struct.unpack('<H', data[0:2])[0]  # Control word (unsigned 16-bit)
            target_torque_raw = struct.unpack('<h', data[2:4])[0]  # Target torque (signed 16-bit)
            
            # Target torque: 1/1000 rated torque/LSB (signed)
            target_torque = target_torque_raw / 1000.0
            
            # Update data store
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['control_word'] = control_word
                self.data_store['inverters'][inv_num]['target_torque'] = target_torque
                self.data_store['inverters'][inv_num]['last_update'] = current_time
            
            # 根據 inv_num 確定變頻器名稱 (0=未知, 1=FL, 2=FR, 3=RL, 4=RR)
            inverter_names = {0: 'UNKNOWN', 1: 'FL', 2: 'FR', 3: 'RL', 4: 'RR'}
            inv_name = inverter_names.get(inv_num, f'INV{inv_num}')
            
            self.log_message(
                f"[INVERTER {inv_name} CONTROL] Control Word: 0x{control_word:04X}, "
                f"Target Torque: {target_torque:.3f} (Raw: {target_torque_raw})"
            )

    def format_value(self, value, format_str=None, na_value="N/A"):
        """格式化數值，如果為 None 則顯示 N/A"""
        if value is None:
            return na_value
        if format_str:
            if callable(format_str):
                # If format_str is a function (lambda), call it with the value
                return format_str(value)
            else:
                # If format_str is a string, use it as a format string
                return format_str.format(value)
        return str(value)

    def format_cell_data(self, cell_dict, format_str="{:.1f}"):
        """格式化 cell 資料字典"""
        if not cell_dict:
            return "N/A"
        
        all_values = []
        for index in sorted(cell_dict.keys()):
            values = cell_dict[index]
            all_values.extend(values)
        
        if not all_values:
            return "N/A"
        
        formatted_values = [format_str.format(v) for v in all_values[:8]]  # Limit to 8 values
        return f"[{', '.join(formatted_values)}]"

    def update_dashboard(self):
        """更新儀表板顯示"""
        # Clear screen and move cursor to top
        print("\033[2J\033[H", end='')
        
        # Header
        print("=" * 70)
        print("                      CAN Data Dashboard")
        print("=" * 70)
        
        # GPS Section
        gps = self.data_store['gps']
        cov = self.data_store['covariance']
        print(f"[GPS]          Lat: {self.format_value(gps['lat'], '{:.7f}'):>12} "
              f"Lon: {self.format_value(gps['lon'], '{:.7f}'):>12} "
              f"Alt: {self.format_value(gps['alt'], '{:.1f}m'):>8}")
        print(f"               Status: {self.format_value(gps['status'], '0x{:02X}'):>8} "
              f"Covariance Type: {cov['type_name']:>15}")
        
        # Velocity Section  
        vel = self.data_store['velocity']
        print(f"[Velocity]     Linear X: {self.format_value(vel['linear_x'], '{:.3f} m/s'):>10} "
              f"Y: {self.format_value(vel['linear_y'], '{:.3f} m/s'):>10} "
              f"Z: {self.format_value(vel['linear_z'], '{:.3f} m/s'):>10}")
        print(f"               Angular X: {self.format_value(vel['angular_x'], '{:.3f} rad/s'):>11} "
              f"Y: {self.format_value(vel['angular_y'], '{:.3f} rad/s'):>11} "
              f"Z: {self.format_value(vel['angular_z'], '{:.3f} rad/s'):>11}")
        print(f"               Total Speed: {self.format_value(vel['magnitude'], '{:.3f} m/s'):>11} "
              f"({self.format_value(vel['speed_kmh'], '{:.2f} km/h'):>10})")
        
        # Accumulator Section
        acc = self.data_store['accumulator']
        print(f"[Accumulator]  SOC: {self.format_value(acc['soc'], '{}%'):>4} "
              f"Voltage: {self.format_value(acc['voltage'], '{:.2f}V'):>8} "
              f"Current: {self.format_value(acc['current'], '{:.2f}A'):>8} "
              f"Temp: {self.format_value(acc['temperature'], '{:.1f}°C'):>8}")
        print(f"               Status: {self.format_value(acc['status'], lambda x: 'OK' if x else 'BAD'):>6} "
              f"Heartbeat: {self.format_value(acc['heartbeat'], lambda x: 'OK' if x else 'FAIL'):>6} "
              f"Capacity: {self.format_value(acc['capacity'], '{:.1f}Ah'):>8}")
        print(f"               Cell Voltages: {self.format_cell_data(acc['cell_voltages'], '{:.2f}'):>25}")
        print(f"               Cell Temps: {self.format_cell_data(acc['cell_temperatures'], '{:.1f}'):>28}")
        
        # Inverter Sections
        for inv_id in [1, 2, 3, 4]:
            inv = self.data_store['inverters'][inv_id]
            print(f"[Inverter {inv['name']}]  Status: {self.format_value(inv['status'], '0x{:04X}'):>8} "
                  f"Torque: {self.format_value(inv['torque'], '{:.3f}'):>7} "
                  f"Speed: {self.format_value(inv['speed'], '{}RPM'):>8}")
            print(f"               Control: {self.format_value(inv['control_word'], '0x{:04X}'):>8} "
                  f"Target: {self.format_value(inv['target_torque'], '{:.3f}'):>7} "
                  f"DC: {self.format_value(inv['dc_voltage'], '{:.1f}V'):>6}/"
                  f"{self.format_value(inv['dc_current'], '{:.1f}A'):>6}")
            print(f"               Temps - MOS: {self.format_value(inv['mos_temp'], '{:.1f}°C'):>7} "
                  f"MCU: {self.format_value(inv['mcu_temp'], '{:.1f}°C'):>7} "
                  f"Motor: {self.format_value(inv['motor_temp'], '{:.1f}°C'):>7} "
                  f"HB: {self.format_value(inv['heartbeat'], lambda x: 'OK' if x else 'FAIL'):>4}")
        
        # Footer
        print("=" * 70)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        print(f"Last Update: {current_time}  Messages: {self.message_count}")
        
        # Flush output
        import sys
        sys.stdout.flush()

def main(args=None):
    rclpy.init(args=args)
    node = CanReceiver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Node stopped.")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

