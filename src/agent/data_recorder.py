import csv
import os
from typing import Dict, List, Any, Optional

class DataRecorder:
    """CSV数据写入器，负责将字典数据写入CSV文件"""

    def __init__(self, file_path: str, max_rows: int = 10000):
        """
        初始化CSV写入器

        Args:
            file_path: 完整文件路径，如 /home/xxx/data.csv
            max_rows: 每个文件最大行数
        """
        self.file_path = file_path
        self.max_rows = max_rows
        self.file_counter = 0
        self.current_row_count = 0
        self.current_writer = None
        self.current_file = None
        self.fieldnames = None

        # 确保目录存在
        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    def _get_next_filename(self) -> str:
        """生成下一个文件名，格式为 data.1.csv, data.2.csv, ..."""
        if self.file_counter == 0:
            filename = self.file_path
        else:
            # 分割文件路径和扩展名
            base_path, ext = os.path.splitext(self.file_path)
            filename = f"{base_path}.{self.file_counter}{ext}"

        self.file_counter += 1
        return filename

    def _create_csv_writer(self, filename: str, fieldnames: List[str]) -> csv.DictWriter:
        """创建CSV写入器"""
        file_obj = open(filename, 'w', newline='', encoding='utf-8')
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        return writer, file_obj

    def _extract_fieldnames(self, data: Dict[str, Any]) -> List[str]:
        """从数据中提取所有字段名"""
        fieldnames = ['start_time', 'stop_time']

        core_data = data.get('all', {})
        for core_id, metrics in core_data.items():
            for metric_name, metric_value in metrics.items():
                if isinstance(metric_value, dict) and 'count' in metric_value and 'countPercent' in metric_value:
                    fieldnames.append(f"{core_id}_{metric_name}_count")
                    fieldnames.append(f"{core_id}_{metric_name}_countPercent")
                else:
                    fieldnames.append(f"{core_id}_{metric_name}")

        return fieldnames

    def _ensure_writer_ready(self, data: Dict[str, Any]) -> None:
        """确保写入器准备就绪"""
        if self.current_writer is None or self.current_row_count >= self.max_rows:
            if self.current_file:
                self.current_file.close()

            if self.fieldnames is None:
                self.fieldnames = self._extract_fieldnames(data)

            filename = self._get_next_filename()
            self.current_writer, self.current_file = self._create_csv_writer(filename, self.fieldnames)
            self.current_row_count = 0

    def insert(self, data: Dict[str, Any]) -> None:
        """插入一行数据"""
        flattened_data = {
            'start_time': data.get('start_time', ''),
            'stop_time': data.get('stop_time', '')
        }

        core_data = data.get('all', {})
        for core_id, metrics in core_data.items():
            for metric_name, value in metrics.items():
                if isinstance(value, dict) and 'count' in value and 'countPercent' in value:
                    flattened_data[f"{core_id}_{metric_name}_count"] = value.get('count', '')
                    flattened_data[f"{core_id}_{metric_name}_countPercent"] = value.get('countPercent', '')
                else:
                    flattened_data[f"{core_id}_{metric_name}"] = value

        self._ensure_writer_ready(data)
        self.current_writer.writerow(flattened_data)
        self.current_row_count += 1

    def close(self) -> None:
        """关闭当前文件"""
        if self.current_file:
            self.current_file.close()
            self.current_file = None
            self.current_writer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()