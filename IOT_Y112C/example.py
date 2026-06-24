import socket
import threading
import time
from .config import Config
import PyQt5
from PyQt5.QtCore import QThread

class PLC(QThread):
    def __init__(self, motor_state):
        super().__init__()
        self.motor_state = motor_state
        self.host = Config.plc_device['host']
        self.port = Config.plc_device['port']
        self.socket = None
        self.socket_wr = None
        self.is_connected = False
        self._connect()
    
    def _init_socket(self, time_out=0.5):
        """Khởi tạo socket mới"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        if self.socket_wr:
            try:
                self.socket_wr.close()
            except:
                pass
        print(f'Init Socket {self.motor_state}...!')
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(time_out)
        self.socket_wr = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_wr.settimeout(time_out)

    def _connect(self):
        """Kết nối đến PLC - retry cho đến khi thành công"""
        while True:
            try:
                print(f'Attempting to connect to PLC at {self.host}:{self.port}...')
                self._init_socket()
                self.socket.connect((self.host, self.port))
                self.socket_wr.connect((self.host, self.port))
                self.is_connected = True
                print(f"✓ PLC_{self.motor_state} Connected to PLC successfully!")
                break
            except Exception as e:
                print(f"✗ PLC_{self.motor_state} Failed to connect: {e}")
                print(f"PLC_{self.motor_state} Retrying in 0.5 seconds...")
                time.sleep(0.5)
    
    def _handle_connection_error(self, operation_name):
        """Xử lý khi mất kết nối - reconnect cho đến khi thành công"""
        print(f"Connection lost during {operation_name}. Reconnecting...")
        self.is_connected = False
        self._connect()
    
    def _read_single(self, register=1000, register_type='EM'):
        """Đọc một thanh ghi với auto-reconnect"""
        while True:
            try:
                data = 'RD ' + register_type + str(register) + '\x0D'
                data_encode = data.encode("UTF-8")
                self.socket.send(data_encode)
                
                # Đợi response từ PLC
                data_recv = self.socket.recv(1024)
                data_decode = data_recv.decode("UTF-8").strip()
                
                # Delay nhỏ giữa các lần read
                time.sleep(0.0001)  # 10ms delay
                
                return int(data_decode)
            except (socket.timeout, socket.error, ConnectionError, BrokenPipeError, OSError) as e:
                print(f'PLC_{self.motor_state} Read single failed at register {register}: {e}')
                self._handle_connection_error('read_single')
            except Exception as e:
                print(f'PLC_{self.motor_state} Unexpected error reading register {register}: {e}')
                return None
    
    def _write_single(self, register=1000, data_write=None, register_type='EM'):
        """Ghi một thanh ghi với auto-reconnect - Optimized for Keyence PLC"""
        while True:
            try:
                send_value = 'WR ' + register_type + str(register) + ' ' + str(data_write) + '\x0D'
                send_value_encode = send_value.encode("UTF-8")
                self.socket_wr.sendall(send_value_encode)
                
                # KEYENCE PLC KHÔNG TRẢ RESPONSE CHO LỆNH WRITE
                # Không gọi recv() để tránh timeout
                
                # Delay để Keyence PLC kịp xử lý
                # Keyence cần delay dài hơn các PLC khác
                time.sleep(0.0001)  # 100ms delay cho Keyence
                
                return True
            except (socket.timeout, socket.error, ConnectionError, BrokenPipeError, OSError) as e:
                print(f'PLC_{self.motor_state} Write single failed at register {register}: {e}')
                self._handle_connection_error('write_single')
            except Exception as e:
                print(f'PLC_{self.motor_state} Unexpected error writing register {register}: {e}')
                return False
    
    def _read_sequence(self, start_register=26050, num_read=8, register_type='EM'):
        """Đọc nhiều thanh ghi liên tiếp với auto-reconnect"""
        while True:
            try:
                data_read = 'RDS ' + register_type + str(start_register) + ' ' + str(num_read) + '\x0D'
                data_encoded = data_read.encode("UTF-8")
                self.socket.sendall(data_encoded)
                
                # Đợi response từ PLC
                plc_response = self.socket.recv(1024)
                data_from_plc = str(plc_response.decode("UTF-8")).strip()
                
                # Delay nhỏ giữa các lần read
                time.sleep(0.0001)  # 10ms delay
                
                return data_from_plc.split(' ')
            except (socket.timeout, socket.error, ConnectionError, BrokenPipeError, OSError) as e:
                print(f'PLC_{self.motor_state} Read sequence failed at register {start_register}: {e}')
                self._handle_connection_error('read_sequence')
            except Exception as e:
                print(f'PLC_{self.motor_state} Unexpected error reading sequence from {start_register}: {e}')
                return None
    
    def _close(self):
        """Đóng kết nối socket"""
        try:
            if self.socket:
                self.socket.close()
            if self.socket_wr:
                self.socket_wr.close()
            self.is_connected = False
            print(f"PLC_{self.motor_state} PLC connection closed")
        except Exception as e:
            print(f"PLC_{self.motor_state} Error closing connection: {e}")


if __name__ == '__main__':
    plc = PLC('VL')
    import time
    # time.sleep(15)
    plc._close()