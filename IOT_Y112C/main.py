from module.__init__ import *
from ultis.__init__ import *
import time
import os
if __name__ == '__main__':
    plc = PLC()
    file_path = load_latest_path('file_paths.json')
    if not os.path.exists(file_path):
        file_path = get_file_path(config['folder_path']).replace('.xlsx', '')
        save_latest_path(file_path)
        time.sleep(1)

    close_excel_file(file_path)
    time.sleep(5)
    print('Init Excel Manager...!')
    excel = CSVDataManager(file_path)
    plc._write_single(config['ready_register'], 1, register_type='DM')
    print('Program Ready!')
    while True:
        change_signal = plc._read_single(config['change_file_register'], register_type='DM')
        if change_signal == 1:
            plc._write_single(config['change_file_register'], 0, register_type='DM')
            file_path = get_file_path(config['folder_path'])
            save_latest_path(file_path)
            excel = CSVDataManager(file_path)
            time.sleep(2)

        data_update_dict = plc.process()
        if data_update_dict:
            close_excel_file(file_path)
            for key_name, data in data_update_dict.items():
                excel.update_data[key_name](data)
        plc._write_single(config['ready_register'], 1, register_type='DM')
        time.sleep(0.5)