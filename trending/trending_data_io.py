import ast
from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class TrendingData:
    timestamp: datetime # UTC or bust
    trendings: List[str]
    new_trendings: List[str]

class TrendingDataIo:
    def __init__(self, file_path: str):
        self.file_path = file_path
        
        
    def write_to_file(self, token_str):
        with open(self.file_path, "a") as file:
            file.write(f"{token_str}\n")

    def getTrendings(self) -> List[TrendingData]:
        with open(self.file_path, "r") as file:
            lines = file.readlines()
            trendings = []
            for line in lines:
                lineArr = ast.literal_eval(line.strip())
                date_obj = datetime.strptime(lineArr[0], "%Y-%m-%d %H:%M:%S")
                trendings.append(TrendingData(date_obj, lineArr[1], lineArr[2]))
            return trendings

    def read_last_trending_line(self):
        with open(self.file_path, "r") as file:
            lines = file.readlines()
            last_line = lines[-1] if lines else None  # Handle empty files gracefully
            if last_line:
                return ast.literal_eval(last_line.strip())
            else:
                return None

    def get_last_trending(self) -> list:
        try:
            last_line = self.read_last_trending_line()
            if (last_line and len(last_line) > 1):
                return last_line[1]
            else:
                return []
        except Exception as e:
            print(f"failed to get last trending {e}")
            return []