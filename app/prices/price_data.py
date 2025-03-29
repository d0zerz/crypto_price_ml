import logging
from datetime import datetime, timedelta

import pandas as pd

# Get module logger
logger = logging.getLogger(__name__)


class PriceDataNotFoundException(Exception):
    def __init__(self, message):
        super().__init__(message)


class PriceData:
    # DataFrame has format:
    # timestamp: datetime
    # price_vs_btc: float

    def __init__(self, coin: str, df: pd.DataFrame):
        self.coin = coin
        self.df = df
        df.to_excel(f".coin_data/{coin}_dump.xlsx")

    def getClosestPrice(self, target: datetime):
        targetTs = pd.Timestamp(target)
        closest_pos = self.df.index.get_indexer([targetTs], method="nearest")[0]
        # Access the closest row
        closest_row = self.df.iloc[closest_pos]
        closest_time = self.df.index[closest_pos]
        # print(f"closest time: {closest_time} to {target} val {closest_row['price_vs_btc']:.15f}")
        if abs(closest_time - target) > timedelta(minutes=30):
            raise PriceDataNotFoundException("Couldn't find price under 30m old")
        return closest_row["price_vs_btc"]
