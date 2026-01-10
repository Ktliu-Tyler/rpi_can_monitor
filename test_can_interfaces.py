#!/usr/bin/env python3
"""
测试CAN接口脚本
检查can0和can1是否正常工作
"""
import can
import time

def test_can_interface(channel):
    """测试指定的CAN接口"""
    try:
        print(f"\n=== 测试 {channel} ===")
        bus = can.interface.Bus(channel=channel, interface='socketcan')
        print(f"✓ {channel} 初始化成功")
        
        # 尝试接收一条消息（超时3秒）
        print(f"等待 {channel} 的消息...")
        msg = bus.recv(timeout=3.0)
        
        if msg:
            print(f"✓ 接收到消息:")
            print(f"  ID: 0x{msg.arbitration_id:03X}")
            print(f"  数据: {' '.join([f'{b:02X}' for b in msg.data])}")
        else:
            print(f"⚠ 3秒内没有接收到消息")
        
        bus.shutdown()
        return True
        
    except Exception as e:
        print(f"✗ {channel} 初始化失败: {e}")
        return False

def main():
    print("=" * 50)
    print("CAN接口测试工具")
    print("=" * 50)
    
    # 测试can0
    can0_ok = test_can_interface('can0')
    
    # 测试can1
    can1_ok = test_can_interface('can1')
    
    print("\n" + "=" * 50)
    print("测试结果:")
    print(f"  can0: {'✓ 正常' if can0_ok else '✗ 失败'}")
    print(f"  can1: {'✓ 正常' if can1_ok else '✗ 失败'}")
    print("=" * 50)
    
    if can0_ok and can1_ok:
        print("\n✓ 所有CAN接口都正常工作！")
        print("  - can0: 用于主要数据（电机、电池等）")
        print("  - can1: 用于GPS数据")
    elif can0_ok:
        print("\n⚠ 只有can0工作，GPS数据可能无法接收")
    elif can1_ok:
        print("\n⚠ 只有can1工作，主要数据可能无法接收")
    else:
        print("\n✗ 所有CAN接口都无法工作")
        print("  请检查:")
        print("  1. CAN接口是否已启用")
        print("  2. 使用 'ip link show' 查看接口状态")
        print("  3. 使用 'sudo ip link set can0 up type can bitrate 500000' 启用can0")
        print("  4. 使用 'sudo ip link set can1 up type can bitrate 500000' 启用can1")

if __name__ == "__main__":
    main()
