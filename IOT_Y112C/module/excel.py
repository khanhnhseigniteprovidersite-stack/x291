from pathlib import Path
import pandas as pd
import warnings
from .config import config

warnings.filterwarnings('ignore', category=FutureWarning)

NO_COLUMN = "NO."


class CSVDataManager:
    def __init__(self, folder_path: str = "."):
        folder_path = str(folder_path).replace('\\', '/')
        self.folder_path = Path(folder_path)
        if self.folder_path.suffix:
            self.folder_path = self.folder_path.parent

        self._ensure_folder_exists(self.folder_path)
        print(f'Working folder: {self.folder_path.absolute()}')

        self.machine_defs = config["machines"]
        self.files = {}
        self.update_data = {}

        for key_name, machine in self.machine_defs.items():
            file_path = self.folder_path / machine["file_name"]
            headers = self._headers(machine)
            self.files[key_name] = file_path
            self._init_file(file_path, headers, machine["title"])
            self.update_data[key_name] = self._build_updater(key_name)

    def _headers(self, machine):
        return [NO_COLUMN] + [field["header"] for field in machine["fields"]]

    def _build_updater(self, key_name):
        def updater(data):
            self.update_machine_data(key_name, data)
        return updater

    def _ensure_folder_exists(self, path: Path):
        try:
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                print(f"📁 Created missing directory: {path}")
        except Exception as e:
            print(f"Error creating directory {path}: {e}")

    def _init_file(self, file_path: Path, headers, title: str):
        self._ensure_folder_exists(file_path.parent)
        if not file_path.exists():
            print(f'Creating new file: {file_path.name}')
            df = pd.DataFrame(columns=headers)
            self._write_csv(file_path, df, title)

    def _read_csv(self, file_path: Path) -> pd.DataFrame:
        try:
            return pd.read_csv(
                file_path,
                skiprows=1,
                encoding='utf-8-sig',
                dtype={NO_COLUMN: 'Int64', 'DATE': str, 'TIME': str},
            )
        except FileNotFoundError:
            return pd.DataFrame()
        except Exception as e:
            print(f"Error reading {file_path.name}: {e}")
            return pd.DataFrame()

    def _write_csv(self, file_path: Path, df: pd.DataFrame, title: str):
        try:
            self._ensure_folder_exists(file_path.parent)
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                f.write(f'# {title}\n')
                df.to_csv(f, index=False)
        except Exception as e:
            print(f"Error writing {file_path.name}: {e}")

    def _clean_date_time(self, val):
        try:
            if pd.isna(val) or val == "":
                return ""
            return str(int(float(val)))
        except Exception:
            return str(val)

    def update_machine_data(self, key_name, data):
        if key_name not in self.machine_defs:
            print(f"Machine name not found: {key_name}")
            return

        machine = self.machine_defs[key_name]
        file_path = self.files[key_name]
        headers = self._headers(machine)
        input_cols = [field["header"] for field in machine["fields"]]
        df = self._read_csv(file_path)

        if df.empty:
            df = pd.DataFrame(columns=headers)

        try:
            current_max_no = pd.to_numeric(df[NO_COLUMN], errors='coerce').max()
            next_no = 1 if pd.isna(current_max_no) else int(current_max_no) + 1
        except Exception:
            next_no = 1

        if isinstance(data, list) and data and isinstance(data[0], (list, dict)):
            records_list = data
        else:
            records_list = [data]

        new_rows = []
        for record in records_list:
            row_values = [""] * len(headers)
            row_values[0] = next_no
            next_no += 1

            if isinstance(record, dict):
                for index, col in enumerate(input_cols, start=1):
                    if col in record:
                        row_values[index] = record[col]
            else:
                for index, value in enumerate(record, start=1):
                    if index < len(row_values):
                        row_values[index] = value

            for index, col in enumerate(headers):
                if col in ("DATE", "TIME"):
                    row_values[index] = self._clean_date_time(row_values[index])

            new_rows.append(row_values)

        if not new_rows:
            return

        df_new = pd.DataFrame(new_rows, columns=headers)
        df = pd.concat([df, df_new], ignore_index=True)
        for col in ("DATE", "TIME"):
            if col in df.columns:
                df[col] = df[col].apply(self._clean_date_time)

        self._write_csv(file_path, df, machine["title"])
        print(f"✓ Updated {len(new_rows)} line(s) into {file_path.name}")

    def display_summary(self):
        print("\n" + "=" * 60)
        print("📊 DATA SUMMARY")
        for path in self.files.values():
            if path.exists():
                df = self._read_csv(path)
                print(f"📄 {path.name}: {len(df)} rows")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    manager = CSVDataManager("data")
    manager.update_data['cover_assembly']([
        "084VN099000124C010NZZZ24", "56-N72XAVGDA0460720009", "20241016", "172901"
    ])
    manager.display_summary()
