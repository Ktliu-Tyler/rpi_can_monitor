# Xsens IMU CAN 数据集成说明

## 概述
本次更新在塔台系统中添加了Xsens IMU的CAN数据读取和后端发送功能。所有Xsens数据通过 **can1** 接口发送。

## 新增的CAN ID和数据类型

### IMU数据
| CAN ID | 十进制 | 名称 | 数据内容 | 单位 |
|--------|--------|------|----------|------|
| 0x021 | 33 | Quaternion | Q0, Q1, Q2, Q3 | 无量纲 |
| 0x031 | 49 | DeltaV | X, Y, Z, Exponent | m/s |
| 0x032 | 50 | RateOfTurn | gyrX, gyrY, gyrZ | rad/s |
| 0x033 | 51 | DeltaQ | DQ0, DQ1, DQ2, DQ3 | 无量纲 |
| 0x034 | 52 | Acceleration | accX, accY, accZ | m/s² |
| 0x041 | 65 | MagneticField | magX, magY, magZ | a.u. |

### GPS数据
| CAN ID | 十进制 | 名称 | 数据内容 | 单位 |
|--------|--------|------|----------|------|
| 0x071 | 113 | LatLon | latitude, longitude | deg |
| 0x072 | 114 | AltitudeEllipsoid | altitude | m |
| 0x076 | 118 | Velocity | velX, velY, velZ | m/s |

## 数据结构

在 `data_store` 中添加了新的 `xsens` 部分：

```python
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
```

## WebSocket 数据格式

通过 WebSocket (`/ws`) 广播的数据中现在包含 `xsens` 字段：

```json
{
    "timestamp": "2026-01-23T12:34:56.789",
    "xsens": {
        "quaternion": {"q0": 0.9, "q1": 0.1, "q2": 0.0, "q3": 0.0},
        "acceleration": {"acc_x": 10.0, "acc_y": -5.0, "acc_z": 9.8},
        "rate_of_turn": {"gyr_x": 1.0, "gyr_y": -0.5, "gyr_z": 0.2},
        "gps": {"lat": 25.0, "lon": 121.5, "alt": 100.0},
        "velocity": {"vel_x": 10.0, "vel_y": -5.0, "vel_z": 2.0},
        "magnetic_field": {"mag_x": 1.0, "mag_y": -0.5, "mag_z": 0.8},
        "delta_v": {"x": 0.1, "y": -0.05, "z": 0.02, "exponent": 0},
        "delta_q": {"dq0": 0.01, "dq1": 0.0, "dq2": 0.0, "dq3": 0.0},
        "last_update": 1706012096.789
    },
    ...
}
```

## HTTP API

`/api/data` 端点也包含 `xsens` 数据：

```bash
curl http://localhost:8888/api/data
```

## 解码细节

### 字节序
所有Xsens数据使用 **Big-Endian** 字节序（根据DBC文件规范）。

### 数据精度
- **Quaternion (0x021)**: 16位有符号，scale = 3.05176e-05
- **Acceleration (0x034)**: 16位有符号，X/Y scale = -0.00390625, Z scale = 0.00390625
- **RateOfTurn (0x032)**: 16位有符号，X/Y scale = -0.00195313, Z scale = 0.00195313
- **GPS LatLon (0x071)**: 32位有符号，lat scale = 5.96046e-08, lon scale = 1.19209e-07
- **Velocity (0x076)**: 16位有符号，X/Y scale = -0.015625, Z scale = 0.015625
- **MagneticField (0x041)**: 16位有符号，X/Y scale = -0.000976563, Z scale = 0.000976563

### 符号说明
- X/Y轴数据使用负scale是因为DBC文件中的定义
- Z轴数据使用正scale
- 注意：不同的scale值会影响数据的正负性

## 测试

运行测试脚本验证解码功能：

```bash
cd /home/pi/Desktop/RPI_Desktop/GUI-dev
python3 test_xsens_decode.py
```

测试覆盖：
- ✓ 四元数解码
- ✓ 加速度解码
- ✓ 角速度解码
- ✓ GPS经纬度解码
- ✓ 速度解码
- ✓ 磁场解码

## 注意事项

1. **CAN接口**: 所有Xsens数据通过 **can1** 接口接收
2. **实时性**: 数据通过 WebSocket 以约20 FPS的频率广播
3. **CSV播放**: CSV模式下也支持Xsens数据的回放
4. **时间戳**: 每次更新都会记录 `last_update` 时间戳

## 前端集成示例

在前端 JavaScript 中接收Xsens数据：

```javascript
const ws = new WebSocket('ws://localhost:8888/ws');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    // 访问Xsens数据
    const quaternion = data.xsens.quaternion;
    const acceleration = data.xsens.acceleration;
    const gps = data.xsens.gps;
    
    console.log('Quaternion:', quaternion);
    console.log('Acceleration:', acceleration);
    console.log('GPS:', gps);
    
    // 更新UI
    updateIMUDisplay(quaternion, acceleration);
    updateGPSDisplay(gps);
};
```

## 更新日期
2026-01-23

## 参考文档
- DBC文件: `Xsens_MTi_600_series_reverse.dbc`
- 测试脚本: `test_xsens_decode.py`
- 主程序: `GUIvehical-v6_dev.py`
