import os
from datetime import datetime

def get_file_path(folder_path):
    print('Getting new file path...')
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"{timestamp}"
    count = 0
    
    while os.path.exists(os.path.join(folder_path, f"{filename}")):
        count += 1
        filename = f"{timestamp}_{count}"
    
    # unique_filename = f"{filename}_{count}" if count >= 1 else filename
    file_path = os.path.join(folder_path, filename)
    print('New file path: ', file_path.replace('\\', '/'))
    return file_path

if __name__ == '__main__':
    # Sử dụng hàm để tạo tên file duy nhất
    folder_path = "path/to/your/folder"
    file_path = get_file_path(folder_path)
    print(file_path)