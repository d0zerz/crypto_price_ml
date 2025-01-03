import ast
from dataclasses import dataclass
from datetime import datetime
import os
from typing import List

from trending.coingecko_client import CoinGeckoClient

COIN_DATA_DIR = ".coin_data"

class CoinDataIo:
    
    def __init__(self, coin: str):
        self.coin = coin

    def file_path(self):
        return f"{COIN_DATA_DIR}/{self.coin}"
        
    def write_to_file(self, raw_coin_data):
        with open(self.file_path(), "a") as file:
            file.write(f"{raw_coin_data}\n")

    def fileExists(self) -> bool:
        os.path.exists(self.file_path())
