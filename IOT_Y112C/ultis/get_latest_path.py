import json

def save_latest_path(file_path, json_file='file_paths.json'):
    try:
        print(f'Trying to save excel file path...')
        with open(json_file, 'r+') as f:
            data = json.load(f)
            data['file_paths'].append(file_path)
            f.seek(0)
            json.dump(data, f, indent=4)
            print('Excel file path saved sccessfully: ', file_path.replace("\\", "/"))
    except FileNotFoundError:
        print('No existed Json file: Creating json file')
        with open(json_file, 'w') as f:
            data = {'file_paths': [file_path]}
            json.dump(data, f, indent=4)
            print('Json file created successfully')
            print('Excel file path saved sccessfully: ', file_path.replace("\\", "/"))

def load_latest_path(json_file):
    try:
        print('Getting previous file path...')
        with open(json_file, 'r') as f:
            data = json.load(f)
            file_paths = data.get('file_paths', [])
            return file_paths[-1] if file_paths else '' 
    
    except FileNotFoundError:
        print("File not found or unable to load file paths.")
        return ''

# Sử dụng hàm để lưu đường dẫn file vào file JSON
file_path = '/path/to/your/file.txt'
json_file = 'file_paths.json'
file_paths = load_latest_path('file_paths.json')
print(file_paths)