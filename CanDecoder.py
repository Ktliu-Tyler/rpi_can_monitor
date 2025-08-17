import can
import struct
from datetime import datetime
import time



class CanDecoder:
    def __init__(self):
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
                'last_update': None},
            'canlogging': {
                'is_recording': False, 'start_time': None, 'start_timestamp': None,
                'last_update': None
            },
            'imu': {
                'lsm6_accel': {'x': None, 'y': None, 'z': None},
                'lsm303_accel': {'x': None, 'y': None, 'z': None},
                'gyro': {'x': None, 'y': None, 'z': None},
                'euler_angles': {'roll': None, 'pitch': None, 'yaw': None},
                'magnetometer': {'x': None, 'y': None, 'z': None},
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
            # GPS 解碼
            elif can_id == 0x400:
                self.decode_gps_basic(data)
            elif can_id == 0x401:
                self.decode_gps_extended(data)
            elif 0x410 <= can_id <= 0x418:
                self.decode_position_covariance(data, can_id - 0x410)
            elif can_id == 0x419:
                self.decode_position_covariance_type(data)

            # IMU 數據解碼
            elif can_id == 0x180:
                self.decode_lsm6_accelerometer(data)
            elif can_id == 0x182:
                self.decode_lsm303_accelerometer(data)
            elif can_id == 0x280:
                self.decode_angular_velocity(data)
            elif can_id == 0x380:
                self.decode_euler_angles(data)
            elif can_id == 0x430:
                self.decode_magnetometer(data)

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
            
            # CAN Logging 狀態解碼
            elif can_id == 0x421:
                self.decode_canlogging_status(data)
            

        except Exception as e:
            print(f"Failed to decode CAN message ID 0x{can_id:03X}: {e}")
    # IMU 解碼函數
    def decode_lsm6_accelerometer(self, data):
        """解碼 LSM6DSOX 加速度計數據 (0x180)"""
        if len(data) >= 6:
            # 解包 3 個 16-bit 有號整數
            ax_raw, ay_raw, az_raw = struct.unpack('<hhh', data[0:6])
            
            # 轉換回 m/s² (scale_factor = 1000 / 9.80665)
            scale_factor = 1000
            ax = ax_raw / scale_factor
            ay = ay_raw / scale_factor
            az = az_raw / scale_factor
            
            current_time = time.time()
            self.data_store['imu']['lsm6_accel']['x'] = ax
            self.data_store['imu']['lsm6_accel']['y'] = ay
            self.data_store['imu']['lsm6_accel']['z'] = az
            self.data_store['imu']['last_update'] = current_time

    def decode_lsm303_accelerometer(self, data):
        """解碼 LSM303AGR 加速度計數據 (0x181)"""
        if len(data) >= 6:
            # 解包 3 個 16-bit 有號整數
            ax_raw, ay_raw, az_raw = struct.unpack('<hhh', data[0:6])
            
            # 轉換回 mm/s² (scale_factor = 1000)
            scale_factor = 1000
            ax = ax_raw / scale_factor
            ay = ay_raw / scale_factor
            az = az_raw / scale_factor
            
            current_time = time.time()
            self.data_store['imu']['lsm303_accel']['x'] = ax
            self.data_store['imu']['lsm303_accel']['y'] = ay
            self.data_store['imu']['lsm303_accel']['z'] = az
            self.data_store['imu']['last_update'] = current_time

    def decode_angular_velocity(self, data):
        """解碼角速度數據 (0x280)"""
        if len(data) >= 6:
            # 解包 3 個 16-bit 有號整數
            gx_raw, gy_raw, gz_raw = struct.unpack('<hhh', data[0:6])
            
            # 轉換回 rad/s (scale_factor = 10 * 57.2958)
            scale_factor = 10 * 57.2958
            gx = gx_raw / scale_factor
            gy = gy_raw / scale_factor
            gz = gz_raw / scale_factor
            
            current_time = time.time()
            self.data_store['imu']['gyro']['x'] = gx
            self.data_store['imu']['gyro']['y'] = gy
            self.data_store['imu']['gyro']['z'] = gz
            self.data_store['imu']['last_update'] = current_time

    def decode_euler_angles(self, data):
        """解碼歐拉角數據 (0x380)"""
        if len(data) >= 6:
            # 解包 3 個 16-bit 有號整數
            roll_raw, pitch_raw, yaw_raw = struct.unpack('<hhh', data[0:6])
            
            # 轉換回度數 (scale_factor = 100)
            roll = roll_raw / 100.0
            pitch = pitch_raw / 100.0
            yaw = yaw_raw / 100.0
            
            current_time = time.time()
            self.data_store['imu']['euler_angles']['roll'] = roll
            self.data_store['imu']['euler_angles']['pitch'] = pitch
            self.data_store['imu']['euler_angles']['yaw'] = yaw
            self.data_store['imu']['last_update'] = current_time

    def decode_magnetometer(self, data):
        """解碼磁力計數據 (0x430)"""
        if len(data) >= 6:
            # 解包 3 個 16-bit 有號整數
            mx_raw, my_raw, mz_raw = struct.unpack('<hhh', data[0:6])
            
            # 轉換回 μT (scale_factor = 10)
            mx = mx_raw / 10.0
            my = my_raw / 10.0
            mz = mz_raw / 10.0
            
            current_time = time.time()
            self.data_store['imu']['magnetometer']['x'] = mx
            self.data_store['imu']['magnetometer']['y'] = my
            self.data_store['imu']['magnetometer']['z'] = mz
            self.data_store['imu']['last_update'] = current_time

    def get_imu_data(self):
        """獲取所有 IMU 數據"""
        return self.data_store['imu'].copy()

    def print_imu_data(self):
        """打印 IMU 數據（用於調試）"""
        imu = self.data_store['imu']
        if imu['last_update']:
            print(f"\n=== IMU Data (Last Update: {datetime.fromtimestamp(imu['last_update']).strftime('%H:%M:%S.%f')[:-3]}) ===")
            
            # LSM6DSOX 加速度計
            if all(v is not None for v in imu['lsm6_accel'].values()):
                print(f"LSM6 Accel:  X={imu['lsm6_accel']['x']:6.3f}, Y={imu['lsm6_accel']['y']:6.3f}, Z={imu['lsm6_accel']['z']:6.3f} m/s²")
            
            # LSM303AGR 加速度計
            if all(v is not None for v in imu['lsm303_accel'].values()):
                print(f"LSM303 Accel: X={imu['lsm303_accel']['x']:6.3f}, Y={imu['lsm303_accel']['y']:6.3f}, Z={imu['lsm303_accel']['z']:6.3f} m/s²")
            
            # 陀螺儀
            if all(v is not None for v in imu['gyro'].values()):
                gx_deg = imu['gyro']['x'] * 57.2958
                gy_deg = imu['gyro']['y'] * 57.2958
                gz_deg = imu['gyro']['z'] * 57.2958
                print(f"Gyroscope:   X={gx_deg:6.1f}, Y={gy_deg:6.1f}, Z={gz_deg:6.1f} deg/s")
            
            # 歐拉角
            if all(v is not None for v in imu['euler_angles'].values()):
                print(f"Euler Angles: Roll={imu['euler_angles']['roll']:6.1f}, Pitch={imu['euler_angles']['pitch']:6.1f}, Yaw={imu['euler_angles']['yaw']:6.1f} deg")
            
            # 磁力計
            if all(v is not None for v in imu['magnetometer'].values()):
                print(f"Magnetometer: X={imu['magnetometer']['x']:6.1f}, Y={imu['magnetometer']['y']:6.1f}, Z={imu['magnetometer']['z']:6.1f} μT")
        else:
            print("No IMU data received yet")



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
            feedback_torque = feedback_torque_raw / 1000.0 * 25
            speed = speed_raw
            
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
            
            if inv_num in self.data_store['inverters']:
                current_time = time.time()
                self.data_store['inverters'][inv_num]['control_word'] = control_word
                self.data_store['inverters'][inv_num]['target_torque'] = target_torque
                self.data_store['inverters'][inv_num]['last_update'] = current_time

    def decode_canlogging_status(self, data):
        """解碼 CAN Logging 狀態 (0x421)"""
        if len(data) >= 1:
            status_byte = data[0]
            current_time = time.time()
            
            if status_byte == 0x01:
                # 正在記錄，解析開始時間
                if len(data) >= 5:
                    # 從 bytes 1-4 重建 timestamp (little-endian)
                    timestamp = (data[4] << 24) | (data[3] << 16) | (data[2] << 8) | data[1]
                    start_time = datetime.fromtimestamp(timestamp)
                    
                    self.data_store['canlogging']['is_recording'] = True
                    self.data_store['canlogging']['start_time'] = start_time
                    self.data_store['canlogging']['start_timestamp'] = timestamp
                else:
                    # 沒有時間資訊，只設定狀態
                    self.data_store['canlogging']['is_recording'] = True
                    
            elif status_byte == 0x00:
                # 未記錄
                self.data_store['canlogging']['is_recording'] = False
                self.data_store['canlogging']['start_time'] = None
                self.data_store['canlogging']['start_timestamp'] = None
            
            self.data_store['canlogging']['last_update'] = current_time

