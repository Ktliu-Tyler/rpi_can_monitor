import can
import csv
import os
import time
import struct
from datetime import datetime, timedelta

import subprocess

vcu_instruction = False
trip_distance = 0.0
base_dir_d = "/home/pi/Desktop/RPI_Desktop/LOGS_distance"

def check_vcu_running():
    return vcu_instruction

def start_can_interface():
    try:
        subprocess.run(
            ["sudo", "ip", "link", "set", "can0", "up", "type", "can", "bitrate", "1000000"],
            check=True
        )
        print("CAN0 interface started.")
    except subprocess.CalledProcessError:
        print("Failed to start CAN0 interface.")
    
    try:
        subprocess.run(
            ["sudo", "ip", "link", "set", "can1", "up", "type", "can", "bitrate", "1000000"],
            check=True
        )
        print("CAN1 interface started.")
    except subprocess.CalledProcessError:
        print("Failed to start CAN1 interface.")

def connect_can(bus_channel='can0'):
    while True:
        try:
            return can.interface.Bus(channel=bus_channel, bustype='socketcan')
        except OSError:
            print("CAN not available, retrying in 5 sec...")
            time.sleep(5)

def new_csv_writer(base_dir, base_name):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(base_dir, f"{base_name}_{timestamp}.csv")
    f = open(filename, 'w', newline='')
    writer = csv.writer(f)
    writer.writerow(["Time Stamp", "ID", "Extended", "Dir", "Bus", "LEN", "D1",
                     "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10",
                     "D11", "D12"])
    return f, writer

def load_trip_distance(base_dir):
    """Load cumulative trip distance from file"""
    distance_file = os.path.join(base_dir, "trip_distance_cumulative.csv")
    print(f"Loading trip distance from: {distance_file}")
    if os.path.exists(distance_file):
        try:
            with open(distance_file, 'r') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                print(f"File header: {header}")
                last_row = None
                for row in reader:
                    print(f"Reading row: {row}")
                    last_row = row
                if last_row and len(last_row) >= 2:
                    distance = float(last_row[1])
                    print(f"Loaded distance: {distance} km")
                    return distance
        except Exception as e:
            print(f"Failed to load trip distance: {e}")
    else:
        print(f"Distance file does not exist, creating new file with 0.0 km")
        # Create new file with initial 0.0 km
        try:
            with open(distance_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Distance_km"])
                writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "0.000000"])
            print(f"Created new distance file: {distance_file}")
        except Exception as e:
            print(f"Failed to create distance file: {e}")
    return 0.0

def save_trip_distance(base_dir, distance):
    """Save cumulative trip distance to file"""
    # Ensure directory exists with proper permissions
    try:
        os.makedirs(base_dir, exist_ok=True)
        print(f"Directory ensured: {base_dir}")
    except Exception as e:
        print(f"Failed to create directory {base_dir}: {e}")
        return
    
    distance_file = os.path.join(base_dir, "trip_distance_cumulative.csv")
    print(f"\n=== Saving trip distance ===")
    print(f"File: {distance_file}")
    print(f"Distance: {distance:.6f} km")
    try:
        # Create file and write header if it doesn't exist
        file_exists = os.path.exists(distance_file)
        
        # If file exists, rewrite it completely to avoid append issues
        if file_exists:
            # Read existing data first
            existing_data = []
            try:
                with open(distance_file, 'r') as f:
                    reader = csv.reader(f)
                    existing_data = list(reader)
                print(f"Read {len(existing_data)} existing rows")
            except:
                existing_data = [["Timestamp", "Distance_km"]]
                print("Failed to read existing data, starting fresh")
        else:
            existing_data = [["Timestamp", "Distance_km"]]
            print("File doesn't exist, creating new file")
        
        # Write all data including new entry
        with open(distance_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(existing_data)
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"{distance:.6f}"]
            writer.writerow(new_row)
            print(f"Wrote new row: {new_row}")
        
        print(f"✓ Successfully saved trip distance to {distance_file}")
        print(f"=========================\n")
    except PermissionError as e:
        print(f"✗ Permission denied saving trip distance.")
        print(f"Error: {e}")
        print(f"Try running: sudo chmod -R 755 {base_dir}")
        print(f"=========================\n")
    except Exception as e:
        print(f"✗ Failed to save trip distance: {e}")
        print(f"=========================\n")

def main():
    base_dir = "/home/pi/Desktop/RPI_Desktop/LOGS"
    base_dir_d = "/home/pi/Desktop/RPI_Desktop/LOGS_distance"
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(base_dir_d, exist_ok=True)

    bus0 = connect_can('can0')
    bus1 = connect_can('can1')
    
    
    recording = False
    recording_start_time = datetime.now()
    file, writer = new_csv_writer(base_dir, "can_log")
    rotate_at = recording_start_time + timedelta(minutes=20)
    last_status_send = 0
    
    # Trip distance tracking variables
    global trip_distance
    trip_distance = load_trip_distance(base_dir_d)  # Cumulative trip distance (km)
    last_distance_send = time.time()
    left_wheel_speed = None  # inv_num 3 (ID 0x193)
    right_wheel_speed = None  # inv_num 4 (ID 0x194)
    last_speed_update_time = None
    
    print(f"Loaded cumulative trip distance: {trip_distance:.3f} km")
    
    print("CAN Logger started for CAN0 and CAN1 and wait for recording!")
    # print(f"Recording started at {recording_start_time}")
    print("Wait for VCU running!")
    print("You can still use control commands (0x420: 01=start, 02=stop)...")

    global vcu_instruction
    vcu_last = check_vcu_running()
    while True:
        # Receive messages from both CAN buses
        msg0 = bus0.recv(timeout=0.001)  # Use shorter timeout
        msg1 = bus1.recv(timeout=0.001)
        
        # Check VCU instruction (from can0)
        if msg0 is not None and hasattr(msg0, 'arbitration_id') and msg0.arbitration_id == 0x281 and len(msg0.data) > 0:
            vcu_instruction = msg0.data[0] & 0x20
        # Also check VCU instruction from can1
        if msg1 is not None and hasattr(msg1, 'arbitration_id') and msg1.arbitration_id == 0x281 and len(msg1.data) > 0:
            vcu_instruction = msg1.data[0] & 0x20

        vcu_running = check_vcu_running()
        # VCU state edge: False -> True, force start new recording file
        if vcu_running and not vcu_last:
            print("VCU state changed from False to True, forcing new recording file!")
            if file:
                file.close()
            recording_start_time = datetime.now()
            file, writer = new_csv_writer(base_dir, "can_log_vcu")
            rotate_at = recording_start_time + timedelta(minutes=20)
            recording = True
            print(f"Recording started at {recording_start_time}")
        # VCU state edge: True -> False, automatically stop recording
        elif not vcu_running and vcu_last:
            print("VCU state changed from True to False, automatically stopping recording!")
            # Save trip distance when VCU stops
            save_trip_distance(base_dir_d, trip_distance)
            print(f"Trip distance saved: {trip_distance:.3f} km")
            if recording and file:
                file.close()
                file = None
                writer = None
            recording = False
            recording_start_time = None
            print(f"Recording stopped at {datetime.now()}")
            print("Waiting for VCU or manual start...")
        vcu_last = vcu_running

        # VCU True: auto recording only, cannot be interrupted by 0x420
        if vcu_running:
            if not recording:
                print("VCU running, auto start recording!")
                recording_start_time = datetime.now()
                file, writer = new_csv_writer(base_dir, "can_log")
                rotate_at = recording_start_time + timedelta(minutes=20)
                recording = True
                print(f"Recording started at {recording_start_time}")
        else:
            # VCU False: recording can be controlled by 0x420 (check both CAN buses)
            for msg in [msg0, msg1]:
                if msg is not None and hasattr(msg, 'arbitration_id') and msg.arbitration_id == 0x420:
                    data_bytes = list(msg.data)
                    if len(data_bytes) > 0:
                        first_byte = data_bytes[0]
                        if first_byte == 0x01:
                            if not recording:
                                print("Start recording command received!")
                                recording_start_time = datetime.now()
                                file, writer = new_csv_writer(base_dir, "can_log")
                                rotate_at = recording_start_time + timedelta(minutes=20)
                                recording = True
                                print(f"Recording started at {recording_start_time}")
                            else:
                                print("Already recording, ignoring start command")
                        elif first_byte == 0x02:
                            if recording:
                                print("Stop recording command received!")
                                if file:
                                    file.close()
                                    file = None
                                    writer = None
                                recording = False
                                recording_start_time = None
                                print(f"Recording stopped at {datetime.now()}")
                                print("Waiting for next start command...")
                            else:
                                print("Not recording, ignoring stop command")
                    break  # Only process control command once

        try:
            # 2. Keep original CAN command control (already handled in main logic, here only handle file writing and status messages)
            current_time = time.time()
            if current_time - last_status_send >= 1.0:
                try:
                    if recording and recording_start_time:
                        timestamp = int(recording_start_time.timestamp())
                        data = [0x01]
                        data.extend([
                            (timestamp >> 0) & 0xFF,
                            (timestamp >> 8) & 0xFF,
                            (timestamp >> 16) & 0xFF,
                            (timestamp >> 24) & 0xFF,
                            0x00, 0x00, 0x00
                        ])
                        status_msg = can.Message(arbitration_id=0x421, data=data, is_extended_id=False)
                        bus0.send(status_msg)  # Send status from can0
                    else:
                        data = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
                        status_msg = can.Message(arbitration_id=0x421, data=data, is_extended_id=False)
                        bus0.send(status_msg)  # Send status from can0
                    last_status_send = current_time
                except Exception as e:
                    print(f"Failed to send status message: {e}")

            # Process speed data for trip distance calculation (can0)
            if msg0 is not None and hasattr(msg0, 'arbitration_id'):
                if msg0.arbitration_id == 0x193 and len(msg0.data) >= 6:  # Left wheel (inv_num 3)
                    speed_raw = struct.unpack('<h', bytes(msg0.data[4:6]))[0]
                    left_wheel_speed = speed_raw
                    current_time = time.time()
                    print(f"[0x193] Left wheel speed: {left_wheel_speed} RPM")
                    
                    # When both wheel speeds are updated, calculate trip distance
                    if right_wheel_speed is not None and last_speed_update_time is not None:
                        avg_rpm = (abs(left_wheel_speed) + abs(right_wheel_speed)) / 2
                        speed_kmps = avg_rpm * 0.00709 / 3600  # km/s
                        time_delta = current_time - last_speed_update_time
                        distance_increment = speed_kmps * time_delta
                        trip_distance += distance_increment
                        print(f"Distance updated: +{distance_increment*1000:.3f}m, Total: {trip_distance:.6f}km")
                    
                    last_speed_update_time = current_time
                    
                elif msg0.arbitration_id == 0x194 and len(msg0.data) >= 6:  # Right wheel (inv_num 4)
                    speed_raw = struct.unpack('<h', bytes(msg0.data[4:6]))[0]
                    right_wheel_speed = speed_raw
                    current_time = time.time()
                    print(f"[0x194] Right wheel speed: {right_wheel_speed} RPM")
                    
                    # When both wheel speeds are updated, calculate trip distance
                    if left_wheel_speed is not None and last_speed_update_time is not None:
                        avg_rpm = (abs(left_wheel_speed) + abs(right_wheel_speed)) / 2
                        speed_kmps = avg_rpm * 0.00709 / 3600  # km/s
                        time_delta = current_time - last_speed_update_time
                        distance_increment = speed_kmps * time_delta
                        trip_distance += distance_increment
                        print(f"Distance updated: +{distance_increment*1000:.3f}m, Total: {trip_distance:.6f}km")
                    
                    last_speed_update_time = current_time
            
            # Record can0 messages
            if recording and writer and msg0 is not None and hasattr(msg0, 'arbitration_id'):
                timestamp = int(time.time() * 1000000)
                can_id = f"{msg0.arbitration_id:08X}"
                extended = 'true' if msg0.is_extended_id else 'false'
                direction = 'Rx' if not msg0.is_remote_frame else 'Tx'
                bus_num = 0  # can0
                dlc = msg0.dlc
                data_bytes = [f"{byte:02X}" for byte in msg0.data]
                data_bytes += ['00'] * (8 - len(data_bytes))
                writer.writerow([timestamp, can_id, extended, direction, bus_num, dlc] + data_bytes)

            # Record can1 messages
            if recording and writer and msg1 is not None and hasattr(msg1, 'arbitration_id'):
                timestamp = int(time.time() * 1000000)
                can_id = f"{msg1.arbitration_id:08X}"
                extended = 'true' if msg1.is_extended_id else 'false'
                direction = 'Rx' if not msg1.is_remote_frame else 'Tx'
                bus_num = 1  # can1
                dlc = msg1.dlc
                data_bytes = [f"{byte:02X}" for byte in msg1.data]
                data_bytes += ['00'] * (8 - len(data_bytes))
                writer.writerow([timestamp, can_id, extended, direction, bus_num, dlc] + data_bytes)
            
            # Send trip distance to CAN1 every 1 second (ID 0x440)
            if current_time - last_distance_send >= 1.0:
                try:
                    # Convert trip distance to millimeters (mm) and pack as 32-bit integer
                    distance_mm = int(trip_distance * 1000000)  # km -> mm
                    data = list(struct.pack('<I', distance_mm & 0xFFFFFFFF))  # 4 bytes, little-endian
                    data += [0x00] * (8 - len(data))  # Pad to 8 bytes
                    
                    distance_msg = can.Message(
                        arbitration_id=0x440,
                        data=data,
                        is_extended_id=False
                    )
                    bus1.send(distance_msg)
                    
                    # Also record this message to CSV
                    if recording and writer:
                        timestamp = int(time.time() * 1000000)
                        can_id = f"{distance_msg.arbitration_id:08X}"
                        extended = 'false'
                        direction = 'Tx'
                        bus_num = 1  # can1
                        dlc = len(distance_msg.data)
                        data_bytes = [f"{byte:02X}" for byte in distance_msg.data]
                        writer.writerow([timestamp, can_id, extended, direction, bus_num, dlc] + data_bytes)
                    
                    last_distance_send = current_time
                except Exception as e:
                    print(f"Failed to send distance message: {e}")

            # Check if log file rotation is needed
            if recording and writer and datetime.now() >= rotate_at:
                print("Rotating log file...")
                file.close()
                recording_start_time = datetime.now()
                file, writer = new_csv_writer(base_dir, "can_log")
                rotate_at = recording_start_time + timedelta(minutes=20)
                print(f"New log file created at {recording_start_time}")

        except can.CanError as e:
            print(f"CAN Error: {e}")
            if recording and file:
                file.close()
                file = None
                writer = None
                recording = False
                recording_start_time = None
            # Reconnect both CAN buses
            try:
                bus0 = connect_can('can0')
                print("CAN0 connection restored")
            except:
                print("Failed to restore CAN0")
            try:
                bus1 = connect_can('can1')
                print("CAN1 connection restored")
            except:
                print("Failed to restore CAN1")
        except Exception as e:
            print(f"Unexpected error: {e}")
            if recording and file:
                file.close()
                file = None
                writer = None
                recording = False
                recording_start_time = None

if __name__ == "__main__":
    try: 
        main()
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        # Save trip distance on exit
        try:
            save_trip_distance(base_dir_d, trip_distance)
            print(f"Trip distance saved on exit: {trip_distance:.3f} km")
        except Exception as e:
            print(f"Failed to save trip distance on exit: {e}")
    except Exception as e:
        print(f"Program error: {e}")
        with open("/tmp/can_logger_error.log", "w") as f:
            f.write(f"Error at {datetime.now()}: {str(e)}")
    finally:
        print("CAN Logger stopped")


