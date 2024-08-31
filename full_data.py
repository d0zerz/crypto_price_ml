from datetime import datetime
from sentiment.augmento_client import AugmentoClient
from prices.yfinance_client import YfinanceClient

import pandas as pd


class FullData:

    def getFullDataSet(self, fromFile=True) -> pd.DataFrame:
        startDate = datetime(year=2023, month=1, day=1)
        endDate = datetime(year=2023, month=2, day=1)
        financeClient = YfinanceClient()
        sentimentClient = AugmentoClient()
        prices = financeClient.getPriceHistoryFromStorage()
        sentiments = sentimentClient.get_all_sentiments(fromStorage=True)
        full = prices.join(sentiments, how='inner')
        return full