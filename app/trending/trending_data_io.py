import ast
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

# Get module logger
logger = logging.getLogger(__name__)

@dataclass
class TrendingData:
    timestamp: datetime # UTC or bust
    trendings: List[str]
    new_trendings: List[str]

class TrendingDataIo:
    def __init__(self, trending_directory: str, logfile: str = "trending.log"):
        self.file_path = f"{trending_directory}/{logfile}"
        
    def write_to_file(self, token_str):
        with open(self.file_path, "a", encoding="utf-8") as file:
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
            logger.error("\nfailed to get last trending {e}", exc_info=True)
            return []