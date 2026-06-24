import os
import pandas as pd
from pathlib import Path
from typing import List
import warnings
import time
import math

warnings.filterwarnings('ignore', category=FutureWarning)

# ===== CẤU HÌNH =====

FILE1_NAME = "STR_1.csv"
FILE2_NAME = "STR_2.csv"
FILE3_NAME = "RTR.csv"

# Headers ĐẦY ĐỦ cho file CSV
FILE1_HEADERS = [
    "NO.", "DMC", "DATE", "TIME",
    "U-V Resistance (mΩ)", "V-W Resistance (mΩ)", "W-U Resistance (mΩ)",
    "U-V Inductance (μH)", "V-W Inductance (μH)", "W-U Inductance (μH)"
]

FILE2_HEADERS = [
    "NO.", "DMC", "DATE", "TIME", 
    "U-V voltage (Vrms)", "V-W voltage (Vrms)", "W-U voltage (Vrms)"
]

FILE3_HEADERS = [
    "NO.", "DMC", "DATE", "TIME", 
    "U-V voltage (Vrms)", "V-W voltage (Vrms)", "W-U voltage (Vrms)"
]

# Mapping cột dữ liệu ĐẦU VÀO từ PLC (KHÔNG CÓ "NO.")
COLS_STR_VOL_RES = [
    "DMC", "DATE", "TIME",
    "U-V Resistance (mΩ)", "V-W Resistance (mΩ)", "W-U Resistance (mΩ)",
    "U-V Inductance (μH)", "V-W Inductance (μH)", "W-U Inductance (μH)"
]

COLS_STR_VOL = [
    "DMC", "DATE", "TIME", 
    "U-V voltage (Vrms)", "V-W voltage (Vrms)", "W-U voltage (Vrms)"
]

COLS_RTR_VOL = [
    "DMC", "DATE", "TIME", 
    "U-V voltage (Vrms)", "V-W voltage (Vrms)", "W-U voltage (Vrms)"
]

TITLE_FILE1 = "STR Performance Inspection"
TITLE_FILE2 = "Induced voltage measurement (Completed STR)"
TITLE_FILE3 = "Induced voltage measurement (RTR)"


class CSVDataManager:
    def __init__(self, folder_path: str = "."):
        folder_path = str(folder_path).replace('\\', '/')
        self.folder_path = Path(folder_path)
        
        # Nếu path đầu vào là file cụ thể (có đuôi mở rộng), lấy parent folder
        if self.folder_path.suffix: 
            self.folder_path = self.folder_path.parent
        
        # [CẬP NHẬT 1]: Luôn đảm bảo folder tồn tại ngay khi khởi tạo
        self._ensure_folder_exists(self.folder_path)
        
        print(f'Working folder: {self.folder_path.absolute()}')
        
        self.file1_path = self.folder_path / FILE1_NAME
        self.file2_path = self.folder_path / FILE2_NAME
        self.file3_path = self.folder_path / FILE3_NAME
        
        self._init_file(self.file1_path, FILE1_HEADERS, TITLE_FILE1)
        self._init_file(self.file2_path, FILE2_HEADERS, TITLE_FILE2)
        self._init_file(self.file3_path, FILE3_HEADERS, TITLE_FILE3)

        self.update_data = {
            'str_vol_res': self.update_str_vol_res,
            'str_vol': self.update_str_vol,
            'rtr_vol': self.update_rtr_vol
        }

    def _ensure_folder_exists(self, path: Path):
        """Hàm kiểm tra và tạo folder nếu chưa tồn tại"""
        try:
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                print(f"📁 Created missing directory: {path}")
        except Exception as e:
            print(f"Error creating directory {path}: {e}")

    def _init_file(self, file_path: Path, headers: List[str], title: str):
        # [CẬP NHẬT 2]: Trước khi tạo file mới, chắc chắn folder cha tồn tại
        self._ensure_folder_exists(file_path.parent)
        
        if not file_path.exists():
            print(f'Creating new file: {file_path.name}')
            df = pd.DataFrame(columns=headers)
            self._write_csv(file_path, df, title)

    def _read_csv(self, file_path: Path) -> pd.DataFrame:
        try:
            # Đọc file, ép kiểu NO., DATE, TIME về object/string để tránh lỗi format
            df = pd.read_csv(file_path, skiprows=1, encoding='utf-8-sig', dtype={'NO.': 'Int64', 'DATE': str, 'TIME': str})
            return df
        except FileNotFoundError:
            # Nếu file chưa có, trả về rỗng, không cần in lỗi ồn ào
            return pd.DataFrame()
        except Exception as e:
            print(f"Error reading {file_path.name}: {e}")
            return pd.DataFrame()
    
    def _write_csv(self, file_path: Path, df: pd.DataFrame, title: str):
        try:
            # [CẬP NHẬT 3 - QUAN TRỌNG NHẤT]: 
            # Trước khi ghi, kiểm tra thư mục chứa file. Nếu bị xóa, tự tạo lại ngay.
            self._ensure_folder_exists(file_path.parent)

            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                f.write(f'# {title}\n')
                df.to_csv(f, index=False)
        except Exception as e:
            print(f"Error writing {file_path.name}: {e}")

    def _clean_date_time(self, val):
        """Hàm loại bỏ .0 ở ngày tháng"""
        try:
            if pd.isna(val) or val == "":
                return ""
            return str(int(float(val)))
        except:
            return str(val)

    def _update_generic(self, file_path, data, headers, input_cols, title):
        """Hàm cập nhật chung cho cả 3 file"""
        df = self._read_csv(file_path)
        
        if df.empty:
            df = pd.DataFrame(columns=headers)
        
        # Tính toán NO. tiếp theo
        try:
            current_max_no = pd.to_numeric(df["NO."], errors='coerce').max()
            if pd.isna(current_max_no):
                next_no = 1
            else:
                next_no = int(current_max_no) + 1
        except:
            next_no = 1

        # Xử lý input data thành list
        records_list = data if isinstance(data, list) and (len(data) > 0 and isinstance(data[0], (list, dict))) else [data]
        if isinstance(data, list) and len(data) > 0 and not isinstance(data[0], (list, dict)):
             records_list = [data]

        new_rows = []
        for record in records_list:
            # Tạo row mới với tất cả key là header, giá trị mặc định ""
            new_row = {col: "" for col in headers}
            new_row["NO."] = next_no
            next_no += 1
            
            # Map dữ liệu vào
            if isinstance(record, dict):
                for col in input_cols:
                    if col in record:
                        new_row[col] = record[col]
            else: # List
                for i, col in enumerate(input_cols):
                    if i < len(record):
                        new_row[col] = record[i]
            
            # Clean Date/Time
            if "DATE" in new_row: new_row["DATE"] = self._clean_date_time(new_row["DATE"])
            if "TIME" in new_row: new_row["TIME"] = self._clean_date_time(new_row["TIME"])
            
            new_rows.append(new_row)

        if not new_rows:
            return

        # Nối và ghi file
        df_new = pd.DataFrame(new_rows, columns=headers)
        df = pd.concat([df, df_new], ignore_index=True)
        
        # Quét lại format Date/Time toàn bộ file để chắc chắn
        if "DATE" in df.columns: df["DATE"] = df["DATE"].apply(self._clean_date_time)
        if "TIME" in df.columns: df["TIME"] = df["TIME"].apply(self._clean_date_time)

        self._write_csv(file_path, df, title)
        print(f"✓ Updated {len(new_rows)} line(s) into {file_path.name}")

    # ===== CÁC HÀM GỌI TỪ MAIN =====

    def update_str_vol_res(self, data):
        self._update_generic(self.file1_path, data, FILE1_HEADERS, COLS_STR_VOL_RES, TITLE_FILE1)

    def update_str_vol(self, data):
        self._update_generic(self.file2_path, data, FILE2_HEADERS, COLS_STR_VOL, TITLE_FILE2)

    def update_rtr_vol(self, data):
        self._update_generic(self.file3_path, data, FILE3_HEADERS, COLS_RTR_VOL, TITLE_FILE3)

    def display_summary(self):
        print("\n" + "="*60)
        print("📊 DATA SUMMARY")
        for path in [self.file1_path, self.file2_path, self.file3_path]:
            if path.exists():
                df = self._read_csv(path)
                print(f"📄 {path.name}: {len(df)} rows")
        print("="*60 + "\n")

if __name__ == "__main__":
    # Test block
    manager = CSVDataManager("data")
    data_test = ["DMC_TEST", "20251218", "103045", 1.1, 1.2, 1.3, 0.1, 0.2, 0.3]
    manager.update_data['str_vol_res'](data_test)
    manager.display_summary()