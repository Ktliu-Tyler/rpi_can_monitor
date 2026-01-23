"""
CAN DBC 解碼器模組
使用 cantools 庫解析 DBC 文件並解碼 CAN 訊息
"""

import cantools
from typing import Dict, Any, Optional
import os


class CanDecoderDBC:
    def __init__(self, dbc_file_path: str):
        """
        初始化 DBC 解碼器
        
        Args:
            dbc_file_path: DBC 檔案的路徑
        """
        self.dbc_file_path = dbc_file_path
        self.db = None
        self.load_dbc()
        
    def load_dbc(self):
        """載入 DBC 檔案"""
        try:
            if not os.path.exists(self.dbc_file_path):
                raise FileNotFoundError(f"DBC file not found: {self.dbc_file_path}")
            
            self.db = cantools.database.load_file(self.dbc_file_path)
            print(f"[DBC] Successfully loaded DBC file: {self.dbc_file_path}")
            print(f"[DBC] Found {len(self.db.messages)} messages in DBC")
            
        except Exception as e:
            print(f"[DBC] Error loading DBC file: {e}")
            raise
    
    def decode_message(self, can_id: int, data: bytes) -> Optional[Dict[str, Any]]:
        """
        解碼 CAN 訊息
        
        Args:
            can_id: CAN ID (整數格式)
            data: CAN 數據 (bytes)
            
        Returns:
            解碼後的訊息字典，如果無法解碼則返回 None
        """
        try:
            # 嘗試通過 CAN ID 獲取訊息定義
            message = self.db.get_message_by_frame_id(can_id)
            
            # 如果數據長度小於 DBC 定義的長度，自動補齊到定義的長度
            # 這是因為實際 CAN 訊息可能不會補齊到 8 bytes
            if len(data) < message.length:
                # 用 0x00 補齊到 DBC 定義的長度
                data = data + b'\x00' * (message.length - len(data))
            
            # 解碼訊息
            decoded_data = message.decode(data)
            
            return {
                'message_name': message.name,
                'can_id': can_id,
                'signals': decoded_data
            }
            
        except KeyError:
            # DBC 中沒有此 CAN ID 的定義
            return None
        except Exception as e:
            print(f"[DBC] Error decoding CAN ID 0x{can_id:03X}: {e}")
            return None
    
    def get_message_name(self, can_id: int) -> Optional[str]:
        """
        根據 CAN ID 獲取訊息名稱
        
        Args:
            can_id: CAN ID
            
        Returns:
            訊息名稱，如果找不到則返回 None
        """
        try:
            message = self.db.get_message_by_frame_id(can_id)
            return message.name
        except:
            return None
    
    def get_signal_value(self, decoded_message: Dict[str, Any], signal_name: str) -> Any:
        """
        從解碼後的訊息中獲取特定信號的值
        
        Args:
            decoded_message: decode_message() 返回的字典
            signal_name: 信號名稱
            
        Returns:
            信號值，如果找不到則返回 None
        """
        if decoded_message and 'signals' in decoded_message:
            return decoded_message['signals'].get(signal_name)
        return None
    
    def list_messages(self):
        """列出 DBC 中所有的訊息"""
        if self.db:
            print(f"\n[DBC] Messages in {self.dbc_file_path}:")
            for msg in self.db.messages:
                print(f"  0x{msg.frame_id:03X} - {msg.name} ({len(msg.signals)} signals)")
    
    def list_signals(self, can_id: int):
        """列出特定 CAN ID 的所有信號"""
        try:
            message = self.db.get_message_by_frame_id(can_id)
            print(f"\n[DBC] Signals for 0x{can_id:03X} ({message.name}):")
            for signal in message.signals:
                print(f"  - {signal.name}: {signal.unit if signal.unit else 'no unit'}")
        except Exception as e:
            print(f"[DBC] Error listing signals for 0x{can_id:03X}: {e}")


if __name__ == "__main__":
    # 測試代碼
    import struct
    
    # DBC 文件路徑
    dbc_path = "dbc/NTUR_EP6_260122.dbc"
    
    if os.path.exists(dbc_path):
        # 創建解碼器實例
        decoder = CanDecoderDBC(dbc_path)
        
        # 列出所有訊息
        decoder.list_messages()
        
        # 測試解碼 GPS 訊息 (0x400)
        print("\n" + "="*50)
        print("Testing GPS message decode (0x400):")
        print("="*50)
        
        # 構造測試數據：緯度 25.0148° (250148000), 經度 121.5345° (1215345000)
        lat_raw = int(25.0148 * 10**7)
        lon_raw = int(121.5345 * 10**7)
        test_data = struct.pack('<ii', lat_raw, lon_raw)
        
        decoded = decoder.decode_message(0x400, test_data)
        if decoded:
            print(f"Message: {decoded['message_name']}")
            print(f"Signals: {decoded['signals']}")
        
        # 測試解碼 Inverter 訊息 (0x191)
        print("\n" + "="*50)
        print("Testing Inverter Status message decode (0x191):")
        print("="*50)
        decoder.list_signals(0x191)
        
        # 構造測試數據
        test_data = bytes([0x01, 0x02, 0x10, 0x27, 0xE8, 0x03, 0x00, 0x00])
        decoded = decoder.decode_message(0x191, test_data)
        if decoded:
            print(f"\nMessage: {decoded['message_name']}")
            print(f"Signals: {decoded['signals']}")
    else:
        print(f"DBC file not found: {dbc_path}")
