import socket
import time
from .config import config

class PLC:
    def __init__(self, name='str dmc'):
        # Lấy cấu hình từ file config như target.py cũ
        self.host = config['host']
        self.port = config['port']
        
        # Khởi tạo biến socket
        self.socket = None
        self.socket_wr = None
        self.is_connected = False
        
        # Mapping Trigger theo đúng logic của target.py
        self.trigger_map = {
            26000: 'str_vol_res',
            27000: 'str_vol',
            28000: 'rtr_vol'
        }
        
        # Bắt đầu kết nối
        self._connect()
    
    def _init_socket(self, time_out=0.5):
        """Khởi tạo socket mới với timeout"""
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
        print('Init Socket...!')
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(time_out)
        self.socket_wr = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_wr.settimeout(time_out)

    def _connect(self):
        """Kết nối đến PLC - retry liên tục cho đến khi thành công"""
        while True:
            try:
                print(f'Attempting to connect to PLC at {self.host}:{self.port}...')
                self._init_socket()
                self.socket.connect((self.host, self.port))
                self.socket_wr.connect((self.host, self.port))
                self.is_connected = True
                print(f"✓ Connected to PLC successfully!")
                break
            except Exception as e:
                print(f"✗ Failed to connect: {e}")
                print("Retrying in 2 seconds...")
                time.sleep(2)
    
    def _handle_connection_error(self, operation_name):
        """Xử lý khi mất kết nối - reconnect cho đến khi thành công"""
        print(f"Connection lost during {operation_name}. Reconnecting...")
        self.is_connected = False
        self._connect()
    
    def _read_single(self, register, register_type='DM'):
        """Đọc một thanh ghi với cơ chế auto-reconnect (Dùng cho Trigger)"""
        while True:
            try:
                data = 'RD ' + register_type + str(register) + '\x0D'
                data_encode = data.encode("UTF-8")
                self.socket.send(data_encode)
                
                # Đợi response từ PLC
                data_recv = self.socket.recv(1024)
                data_decode = data_recv.decode("UTF-8").strip()
                
                # Delay nhỏ ổn định đường truyền
                time.sleep(0.01)
                
                return int(data_decode)
            except (socket.timeout, socket.error, ConnectionError, BrokenPipeError, OSError) as e:
                print(f'Read single failed at register {register}: {e}')
                self._handle_connection_error('read_single')
            except Exception as e:
                print(f'Unexpected error reading register {register}: {e}')
                # Trong trường hợp lỗi lạ không phải kết nối, có thể return 0 hoặc reconnect
                time.sleep(1)
                return 0
    
    def _write_single(self, register, data_write, register_type='DM'):
        """Ghi thanh ghi với auto-reconnect (Không đợi phản hồi để tránh timeout)"""
        while True:
            try:
                send_value = 'WR ' + register_type + str(register) + ' ' + str(data_write) + '\x0D'
                send_value_encode = send_value.encode("UTF-8")
                self.socket_wr.sendall(send_value_encode)
                
                # OPTIMIZATION: Keyence PLC thường không trả response cho lệnh WR qua Upper Link
                # Việc bỏ qua recv() giúp tránh timeout không cần thiết.
                
                time.sleep(0.02) # Delay để PLC kịp xử lý lệnh ghi
                return True
            except (socket.timeout, socket.error, ConnectionError, BrokenPipeError, OSError) as e:
                print(f'Write single failed at register {register}: {e}')
                self._handle_connection_error('write_single')
            except Exception as e:
                print(f'Unexpected error writing register {register}: {e}')
                return False
    
    def _read_sequence(self, start_register, num_read, register_type='DM'):
        """Đọc chuỗi thanh ghi liên tiếp (RDS) với auto-reconnect"""
        while True:
            try:
                data_read = 'RDS ' + register_type + str(start_register) + ' ' + str(num_read) + '\x0D'
                data_encoded = data_read.encode("UTF-8")
                self.socket.sendall(data_encoded)
                
                # Đợi response
                plc_response = self.socket.recv(1024)
                data_from_plc = str(plc_response.decode("UTF-8")).strip()
                
                time.sleep(0.01)
                
                return data_from_plc.split(' ')
            except (socket.timeout, socket.error, ConnectionError, BrokenPipeError, OSError) as e:
                print(f'Read sequence failed at register {start_register}: {e}')
                self._handle_connection_error('read_sequence')
            except Exception as e:
                print(f'Unexpected error reading sequence from {start_register}: {e}')
                return None

    # ===== CÁC HÀM XỬ LÝ DỮ LIỆU (HELPER) =====

    def _word_to_dec(self, word1: str, word2: str) -> int:
        """Ghép 2 word thành 1 số nguyên (Double Word)"""
        return int(word2) * 65536 + int(word1)

    def _read_dmc(self, start_register, num_read=8) -> str:
        """Đọc và giải mã chuỗi ký tự (DMC) từ các thanh ghi"""
        try:
            decimal_data = self._read_sequence(start_register, num_read)
            if decimal_data is None: return ''
            
            string_data = []
            for val in decimal_data:
                try:
                    val_int = int(val)
                    if val_int == 0: continue
                    
                    # Tách High byte và Low byte
                    high_byte = (val_int >> 8) & 0xFF
                    low_byte = val_int & 0xFF
                    
                    if 32 <= high_byte <= 126: string_data.append(chr(high_byte))
                    if 32 <= low_byte <= 126: string_data.append(chr(low_byte))
                except ValueError:
                    continue
            
            return ''.join(string_data)
        except Exception as e:
            print(f'Error reading DMC: {e}')
            return ''

    def _read_datetime(self, start_register, num_read=4):
        """Đọc Date và Time"""
        # Format: [date_w1, date_w2, time_w1, time_w2]
        data_datetime = self._read_sequence(start_register, num_read)
        if data_datetime is None or len(data_datetime) < 4:
            return None, None
            
        data_date = self._word_to_dec(data_datetime[0], data_datetime[1])
        data_time = self._word_to_dec(data_datetime[2], data_datetime[3])
        return data_date, data_time

    def _read_metrics(self, start_register, num_read=12):
        """Đọc các chỉ số đo lường (Voltage, Resistance, Inductance)"""
        data_metrics = self._read_sequence(start_register, num_read)
        if data_metrics is None:
            return []
        
        # Logic từ target.py cũ: Nếu đọc 12 word (STR_VOL_RES) thì chia 10000, còn lại chia 1000
        unit_divide = 10000 if num_read == 12 else 1000
        
        results = []
        # Mỗi giá trị thực chiếm 2 word, nên bước nhảy là 2
        for i in range(0, num_read, 2):
            if i+1 < len(data_metrics):
                val = self._word_to_dec(data_metrics[i], data_metrics[i+1])
                results.append(val / unit_divide)
        return results

    # ===== HÀM CHÍNH =====

    def get_data(self, machine_name):
        """Lấy dữ liệu theo tên máy (Mapping giữ nguyên từ target.py cũ)"""
        try:
            if machine_name == 'str_vol_res':
                # Trigger 26000 -> DMC: 26050, Date: 26040, Metrics: 26064 (12 words)
                dmc = self._read_dmc(start_register=26050, num_read=8)
                d, t = self._read_datetime(start_register=26040, num_read=4)
                metrics = self._read_metrics(start_register=26064, num_read=12)
                return [dmc, d, t] + metrics

            elif machine_name == 'str_vol':
                # Trigger 27000 -> DMC: 27050, Date: 27040, Metrics: 27064 (6 words)
                dmc = self._read_dmc(start_register=27050, num_read=8)
                d, t = self._read_datetime(start_register=27040, num_read=4)
                metrics = self._read_metrics(start_register=27064, num_read=6)
                return [dmc, d, t] + metrics

            elif machine_name == 'rtr_vol':
                # Trigger 28000 -> DMC: 28050, Date: 28040, Metrics: 28064 (6 words)
                dmc = self._read_dmc(start_register=28050, num_read=8)
                d, t = self._read_datetime(start_register=28040, num_read=4)
                metrics = self._read_metrics(start_register=28064, num_read=6)
                return [dmc, d, t] + metrics
            
            else:
                print('Machine name not found!')
                return None
        except Exception as e:
            print(f"Error getting data for {machine_name}: {e}")
            return None

    def process(self):
        """Vòng lặp quét Trigger và đọc dữ liệu"""
        results = {}
        
        # Đảm bảo kết nối còn sống trước khi quét
        if not self.is_connected:
            self._connect()

        # Quét các trigger: 26000, 27000, 28000
        for register, keyname in self.trigger_map.items():
            trigger_value = self._read_single(register)
            
            if trigger_value == 1:
                print(f"Trigger detected at {register} ({keyname})")
                
                # Reset Trigger về 0
                self._write_single(register, 0)
                
                # Đọc dữ liệu chi tiết
                data = self.get_data(keyname)
                
                if data:
                    results[keyname] = data
                    print(f"Data received for {keyname}: {data}")
                else:
                    print(f"Failed to read data for {keyname}")
                    
        return results
    
    def close(self):
        try:
            if self.socket: self.socket.close()
            if self.socket_wr: self.socket_wr.close()
            self.is_connected = False
            print("PLC connection closed")
        except Exception as e:
            print(f"Error closing connection: {e}")