import psutil
import os
import time
def close_excel_file(file_path):
    file_name = os.path.basename(file_path)
    for proc in psutil.process_iter(['name', 'pid']):
        try:
            # Kiểm tra các tiến trình Excel
            if proc.info['name'] == 'EXCEL.EXE':
                # Kiểm tra các file mà tiến trình đang mở
                for file in proc.open_files():
                    if file_name in file.path:
                        print(f"File {file_name} opening. Closing Excel process...")
                        proc.terminate()
                        time.sleep(2)
                        return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

if __name__ == '__main__':
    # Ví dụ sử dụng
    file_path = "data.xlsx"
    close_excel_file(file_path)
