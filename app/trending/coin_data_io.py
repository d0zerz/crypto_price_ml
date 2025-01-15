import ast
from dataclasses import dataclass
from datetime import datetime
import os
from typing import List

from trending.coingecko_client import CoinGeckoClient

COIN_DATA_DIR = ".coin_data"

class CoinDataIo:
    
    def __init__(self, base_path: str, coin: str):
        self.coin = coin
        self.file_path = f"{base_path}/{COIN_DATA_DIR}/{self.coin}"
      
    def write_to_file(self, raw_coin_data):
        path = self.file_path
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory)

        with open(path, "w") as file:
            file.write(f"{raw_coin_data}\n")

    def fileExists(self) -> bool:
        os.path.exists(self.file_path)
