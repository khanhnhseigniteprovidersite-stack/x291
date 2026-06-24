import socket
import time
from .config import config


class PLC:
    def __init__(self, name='x291'):
        self.host = config['host']
        self.port = config['port']
        self.machine_defs = config['machines']
        self.socket = None
        self.socket_wr = None
        self.is_connected = False
        self.trigger_map = {
            machine['trigger']: key_name
            for key_name, machine in self.machine_defs.items()
            if machine.get('trigger') is not None
        }
        self._connect()

    def _init_socket(self, time_out=0.5):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        if self.socket_wr:
            try:
                self.socket_wr.close()
            except Exception:
                pass
        print('Init Socket...!')
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(time_out)
        self.socket_wr = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_wr.settimeout(time_out)

    def _connect(self):
        while True:
            try:
                print(f'Attempting to connect to PLC at {self.host}:{self.port}...')
                self._init_socket()
                self.socket.connect((self.host, self.port))
                self.socket_wr.connect((self.host, self.port))
                self.is_connected = True
                print('✓ Connected to PLC successfully!')
                break
            except Exception as e:
                print(f'✗ Failed to connect: {e}')
                print('Retrying in 2 seconds...')
                time.sleep(2)

    def _handle_connection_error(self, operation_name):
        print(f'Connection lost during {operation_name}. Reconnecting...')
        self.is_connected = False
        self._connect()

    def _read_single(self, register, register_type='DM'):
        while True:
            try:
                data = 'RD ' + register_type + str(register) + '\x0D'
                self.socket.send(data.encode('UTF-8'))
                data_decode = self.socket.recv(1024).decode('UTF-8').strip()
                time.sleep(0.01)
                return int(data_decode)
            except (socket.timeout, socket.error, ConnectionError, BrokenPipeError, OSError) as e:
                print(f'Read single failed at register {register}: {e}')
                self._handle_connection_error('read_single')
            except Exception as e:
                print(f'Unexpected error reading register {register}: {e}')
                time.sleep(1)
                return 0

    def _write_single(self, register, data_write, register_type='DM'):
        while True:
            try:
                send_value = 'WR ' + register_type + str(register) + ' ' + str(data_write) + '\x0D'
                self.socket_wr.sendall(send_value.encode('UTF-8'))
                time.sleep(0.02)
                return True
            except (socket.timeout, socket.error, ConnectionError, BrokenPipeError, OSError) as e:
                print(f'Write single failed at register {register}: {e}')
                self._handle_connection_error('write_single')
            except Exception as e:
                print(f'Unexpected error writing register {register}: {e}')
                return False

    def _read_sequence(self, start_register, num_read, register_type='DM'):
        while True:
            try:
                data_read = 'RDS ' + register_type + str(start_register) + ' ' + str(num_read) + '\x0D'
                self.socket.sendall(data_read.encode('UTF-8'))
                data_from_plc = self.socket.recv(1024).decode('UTF-8').strip()
                time.sleep(0.01)
                return data_from_plc.split(' ')
            except (socket.timeout, socket.error, ConnectionError, BrokenPipeError, OSError) as e:
                print(f'Read sequence failed at register {start_register}: {e}')
                self._handle_connection_error('read_sequence')
            except Exception as e:
                print(f'Unexpected error reading sequence from {start_register}: {e}')
                return None

    def _word_to_dec(self, word1: str, word2: str = None) -> int:
        if word2 is None:
            return int(word1)
        return int(word2) * 65536 + int(word1)

    def _decode_string_words(self, decimal_data) -> str:
        string_data = []
        for val in decimal_data or []:
            try:
                val_int = int(val)
                if val_int == 0:
                    continue
                high_byte = (val_int >> 8) & 0xFF
                low_byte = val_int & 0xFF
                if 32 <= high_byte <= 126:
                    string_data.append(chr(high_byte))
                if 32 <= low_byte <= 126:
                    string_data.append(chr(low_byte))
            except ValueError:
                continue
        return ''.join(string_data).strip()

    def _read_string(self, start_register, num_read) -> str:
        return self._decode_string_words(self._read_sequence(start_register, num_read))

    def _read_number(self, start_register, num_read):
        data = self._read_sequence(start_register, num_read)
        if not data:
            return None
        try:
            if num_read == 1:
                return self._word_to_dec(data[0])
            return self._word_to_dec(data[0], data[1])
        except Exception as e:
            print(f'Error converting numeric data at {start_register}: {e}')
            return None

    def _read_field(self, field):
        start_register = field.get('start')
        if start_register is None:
            return ''
        num_read = field.get('words', 1)
        if field.get('type') == 'string':
            return self._read_string(start_register, num_read)
        value = self._read_number(start_register, num_read)
        divisor = field.get('divisor', 1)
        if value is not None and divisor not in (0, 1):
            return value / divisor
        return value

    def get_data(self, machine_name):
        try:
            machine = self.machine_defs.get(machine_name)
            if not machine:
                print('Machine name not found!')
                return None
            return [self._read_field(field) for field in machine['fields']]
        except Exception as e:
            print(f'Error getting data for {machine_name}: {e}')
            return None

    def process(self):
        results = {}
        if not self.is_connected:
            self._connect()

        for register, keyname in self.trigger_map.items():
            trigger_value = self._read_single(register)
            if trigger_value == 1:
                print(f'Trigger detected at {register} ({keyname})')
                self._write_single(register, 0)
                data = self.get_data(keyname)
                if data:
                    results[keyname] = data
                    print(f'Data received for {keyname}: {data}')
                else:
                    print(f'Failed to read data for {keyname}')
        return results

    def close(self):
        try:
            if self.socket:
                self.socket.close()
            if self.socket_wr:
                self.socket_wr.close()
            self.is_connected = False
            print('PLC connection closed')
        except Exception as e:
            print(f'Error closing connection: {e}')
