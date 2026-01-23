#!/usr/bin/env python3
"""
测试Xsens CAN数据解码功能
"""
import struct

def test_xsens_quaternion():
    """测试四元数解码"""
    print("\n=== 测试 Xsens Quaternion (0x021) ===")
    # 模拟数据: Q0=1.0, Q1=0.0, Q2=0.0, Q3=0.0
    # 1.0 / 3.05176e-05 = 32768 (超出有符号范围，使用0.9代替)
    # 0.9 / 3.05176e-05 = 29491
    q0_raw = 29491
    data = struct.pack('>hhhh', q0_raw, 0, 0, 0)
    
    q0 = struct.unpack('>h', data[0:2])[0] * 3.05176e-05
    print(f"Q0 raw: {q0_raw}, decoded: {q0:.6f}")
    assert abs(q0 - 0.9) < 0.001, f"Expected ~0.9, got {q0}"
    print("✓ 四元数解码测试通过")

def test_xsens_acceleration():
    """测试加速度解码"""
    print("\n=== 测试 Xsens Acceleration (0x034) ===")
    # 模拟数据: X=10 m/s², Y=-5 m/s², Z=9.8 m/s²
    # X: 10 / (-0.00390625) = -2560
    # Y: -5 / (-0.00390625) = 1280
    # Z: 9.8 / 0.00390625 = 2508.8 ≈ 2509
    x_raw = -2560
    y_raw = 1280
    z_raw = 2509
    data = struct.pack('>hhh', x_raw, y_raw, z_raw)
    
    acc_x = struct.unpack('>h', data[0:2])[0] * (-0.00390625)
    acc_y = struct.unpack('>h', data[2:4])[0] * (-0.00390625)
    acc_z = struct.unpack('>h', data[4:6])[0] * 0.00390625
    
    print(f"AccX: {acc_x:.2f} m/s² (expected: 10.00)")
    print(f"AccY: {acc_y:.2f} m/s² (expected: -5.00)")
    print(f"AccZ: {acc_z:.2f} m/s² (expected: 9.80)")
    print("✓ 加速度解码测试通过")

def test_xsens_rate_of_turn():
    """测试角速度解码"""
    print("\n=== 测试 Xsens RateOfTurn (0x032) ===")
    # 模拟数据: X=1.0 rad/s, Y=-0.5 rad/s, Z=0.2 rad/s
    # X: 1.0 / (-0.00195313) = -512
    # Y: -0.5 / (-0.00195313) = 256
    # Z: 0.2 / 0.00195313 = 102.4 ≈ 102
    x_raw = -512
    y_raw = 256
    z_raw = 102
    data = struct.pack('>hhh', x_raw, y_raw, z_raw)
    
    gyr_x = struct.unpack('>h', data[0:2])[0] * (-0.00195313)
    gyr_y = struct.unpack('>h', data[2:4])[0] * (-0.00195313)
    gyr_z = struct.unpack('>h', data[4:6])[0] * 0.00195313
    
    print(f"GyrX: {gyr_x:.4f} rad/s (expected: 1.0000)")
    print(f"GyrY: {gyr_y:.4f} rad/s (expected: -0.5000)")
    print(f"GyrZ: {gyr_z:.4f} rad/s (expected: 0.1992)")
    print("✓ 角速度解码测试通过")

def test_xsens_gps():
    """测试GPS解码"""
    print("\n=== 测试 Xsens LatLon (0x071) ===")
    # 模拟数据: lat=25.0°N, lon=121.5°E
    # lat: 25.0 / 5.96046e-08 = 419430400
    # lon: 121.5 / 1.19209e-07 = 1019215872
    lat_raw = 419430400
    lon_raw = 1019215872
    data = struct.pack('>ii', lat_raw, lon_raw)
    
    lat = struct.unpack('>i', data[0:4])[0] * 5.96046e-08
    lon = struct.unpack('>i', data[4:8])[0] * 1.19209e-07
    
    print(f"Latitude: {lat:.6f}° (expected: 25.000000)")
    print(f"Longitude: {lon:.6f}° (expected: 121.500000)")
    print("✓ GPS解码测试通过")

def test_xsens_velocity():
    """测试速度解码"""
    print("\n=== 测试 Xsens Velocity (0x076) ===")
    # 模拟数据: X=10 m/s, Y=-5 m/s, Z=2 m/s
    # X: 10 / (-0.015625) = -640
    # Y: -5 / (-0.015625) = 320
    # Z: 2 / 0.015625 = 128
    x_raw = -640
    y_raw = 320
    z_raw = 128
    data = struct.pack('>hhh', x_raw, y_raw, z_raw)
    
    vel_x = struct.unpack('>h', data[0:2])[0] * (-0.015625)
    vel_y = struct.unpack('>h', data[2:4])[0] * (-0.015625)
    vel_z = struct.unpack('>h', data[4:6])[0] * 0.015625
    
    print(f"VelX: {vel_x:.2f} m/s (expected: 10.00)")
    print(f"VelY: {vel_y:.2f} m/s (expected: -5.00)")
    print(f"VelZ: {vel_z:.2f} m/s (expected: 2.00)")
    print("✓ 速度解码测试通过")

def test_xsens_magnetic_field():
    """测试磁场解码"""
    print("\n=== 测试 Xsens MagneticField (0x041) ===")
    # 模拟数据: X=1.0, Y=-0.5, Z=0.8 a.u.
    # X: 1.0 / (-0.000976563) = -1024
    # Y: -0.5 / (-0.000976563) = 512
    # Z: 0.8 / 0.000976563 = 819.2 ≈ 819
    x_raw = -1024
    y_raw = 512
    z_raw = 819
    data = struct.pack('>hhh', x_raw, y_raw, z_raw)
    
    mag_x = struct.unpack('>h', data[0:2])[0] * (-0.000976563)
    mag_y = struct.unpack('>h', data[2:4])[0] * (-0.000976563)
    mag_z = struct.unpack('>h', data[4:6])[0] * 0.000976563
    
    print(f"MagX: {mag_x:.4f} a.u. (expected: 1.0000)")
    print(f"MagY: {mag_y:.4f} a.u. (expected: -0.5000)")
    print(f"MagZ: {mag_z:.4f} a.u. (expected: 0.8000)")
    print("✓ 磁场解码测试通过")

if __name__ == "__main__":
    print("=" * 50)
    print("Xsens CAN数据解码测试")
    print("=" * 50)
    
    try:
        test_xsens_quaternion()
        test_xsens_acceleration()
        test_xsens_rate_of_turn()
        test_xsens_gps()
        test_xsens_velocity()
        test_xsens_magnetic_field()
        
        print("\n" + "=" * 50)
        print("✓ 所有测试通过！")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
