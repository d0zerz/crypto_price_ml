from dataclasses import asdict, fields
import os
from typing import List
from trending.dex_token import DexDataIo
from trending.dex_token import DexToken, FUTURE_TIMES, OLD_FUTURE_TIMES
from datetime import datetime, timedelta, timezone
import time
import pandas as pd

COIN_DATA_FILE = "dex_coin_data_dump.xlsx"

class DexAnalysis:

    def __init__(self, trending_dir: str):
        self.trending_dir = trending_dir
        self.dex_coin_data_io = DexDataIo(trending_dir)

        coin_field_names = [field.name for field in fields(DexToken)]

    def main(self):
        coinDataFrame = None
        read_enabled = False
        if (os.path.exists(COIN_DATA_FILE) and read_enabled):
            coinDataFrame = pd.read_excel(io=COIN_DATA_FILE)
        else:
            coinDataFrame = self.processFiles()
            coinDataFrame["timestamp"] = coinDataFrame["timestamp"].dt.tz_localize(None)
            coinDataFrame.to_excel(COIN_DATA_FILE, index=False)

        print(f"total coins: {len(coinDataFrame)}")
        print(coinDataFrame.columns)
    

    def getCoinFutures(self, coin: DexToken) -> dict:
        price_diffs = {}
        for future_time in OLD_FUTURE_TIMES:
            future_label = future_time["label"]
            future = self.dex_coin_data_io.load_future(token_address=coin.token_address, future_name=future_label)
            if future:
                price_diff = round(100 * (future.price_native - coin.price_native) / coin.price_native, 3)
                price_diffs[f"{future_label}_diff_pct"] = price_diff
        return price_diffs

    def processFiles(self) -> pd.DataFrame:
        rows = []
        for coin in self.dex_coin_data_io.load_all_dex_coins():
            token_data = asdict(coin)  # Convert dataclass to dict
            futures_data = self.getCoinFutures(coin)
            token_data.update(futures_data)  # Merge extra data into the dictionary
            rows.append(token_data)  # Append to list
            print(f"{coin.token_symbol} | {coin.token_address}")
        return pd.DataFrame(rows)
        