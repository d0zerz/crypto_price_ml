
from datetime import datetime
import yfinance as yf
import pandas as pd

PICKLE_FILE_LOCATION="prices/yfinance_price_history.pickle"

class YfinanceClient:
    def getPriceHistoryFromStorage(self) -> pd.DataFrame:
        return self._loadPickleFile(PICKLE_FILE_LOCATION)

    def getPriceHistoryFromAPI(self, start: datetime, end: datetime) -> pd.DataFrame:
        ticker = yf.Ticker("BTC-USD")
        btc = ticker.history(period="max", start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        btc.columns = [c.lower() for c in btc.columns]
        del btc["dividends"]
        del btc["stock splits"]
        return btc

    def dumpPriceHistoryToFile(self, filename: str):
        df = self.getPriceHistoryFromAPI(start=datetime(year=2014, month=1, day=1), 
                                         end=datetime(year=2025, month=1, day=1))
        df.to_pickle(filename)
    
    def _loadPickleFile(self, filename) -> pd.DataFrame:
        return pd.read_pickle(filename)


# YfinanceClient().dumpPriceHistoryToFile("yfinance_price_history.pickle")
    
#history = YfinanceClient().getPriceHistoryFromStorage()
