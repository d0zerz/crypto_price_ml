from datetime import datetime
import pandas as pd

class PriceData:
    # DataFrame has format:
    # timestamp: datetime
    # price_vs_btc: float

    def __init__(self, coin: str, df: pd.DataFrame):
        self.coin = coin
        self.df = df
        pass

    def getClosestPrice(self, target: datetime):
        targetTs = pd.Timestamp(target)
        closest_pos = self.df.index.get_indexer([target], method='nearest')[0]
        # Access the closest row
        closest_row = self.df.iloc[closest_pos]
        return closest_row['price_vs_btc']