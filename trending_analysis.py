import traceback
from trending.coingecko_client import CoinGeckoClient, RateLimitException
from trending.trending_data_io import TrendingData, TrendingDataIo
from datetime import datetime, timedelta, timezone
import time
import argparse
import pandas as pd

class TrendingAnalyzer:

    INTERVALS = [timedelta(hours=1),
                        timedelta(hours=3),
                        timedelta(hours=7),
                        timedelta(hours=12),
                        timedelta(hours=24),
                        timedelta(days=2),
                        timedelta(days=4),
                        timedelta(days=7),
                        timedelta(days=14)
                        ]

    def __init__(self, cgApiKey: str):
        self.client = CoinGeckoClient(api_key=cgApiKey)

    def main(self):
        io = TrendingDataIo("trending.log")
        trendings = io.getTrendings()
        coinsTotaled, diffTotals = self.getTotals(trendings)

        for index, diff in enumerate(diffTotals):
            pctDiff = round(diff / coinsTotaled, 3)
            print(f"{self.INTERVALS[index]} - {pctDiff}")

    def getTotals(self, trendings):
        coinsProcessed = []
        coinsTotaled = 0
        diffTotals = [0 for interval in self.INTERVALS]
        for trending in trendings:
            for coin in trending.new_trendings:
                if coin not in coinsProcessed:
                    self.processCoin(coinsProcessed, coinsTotaled, diffTotals, trending, coin)
        return coinsTotaled, diffTotals

    def processCoin(self, coinsProcessed, coinsTotaled, diffTotals, trending, coin):
        diffs = None
        while diffs is None:
            attempts = 0
            try:
                attempts += 1
                diffs = self.find_price_changes(coin, trending)
                break # if we didn't find a price for a non-rate-limitey reason
            except RateLimitException as e:
                if attempts > 10:
                    raise Exception(f"giving up on {coin} after 10 attempts")
                print(f"Rate Limited:  retrying on {coin} in 60s")
                time.sleep(60)
        
        coinsProcessed.append(coin)
        if diffs:
            for index, diff in enumerate(diffs):
                diffTotals[index] = diffTotals[index] + diff
            coinsTotaled += 1


    def find_price_changes(self, coin: str, trending: TrendingData):
        currTs = trending.timestamp
        startTime = trending.timestamp - timedelta(hours=2)
        endTime = trending.timestamp + timedelta(days=15)
        prices = self.client.get_historical_chart(coin, startTime, endTime)
        if not prices:
            print(f"Couldn't get prices for {coin}")
            return 
        startPrice = prices.getClosestPrice(currTs) 

        timeDiffs = [currTs + interval for interval in self.INTERVALS]
        pctDiffs = []
        for curTime in timeDiffs:
            price = prices.getClosestPrice(curTime)
            delta = price - startPrice
            pctIncrease = round((delta / startPrice) * 100)
            pctDiffs.append(pctIncrease)
            print(f"{coin}: from {currTs} to {curTime}, price went from {startPrice} to {price} for a {pctIncrease}% increase")
        
        return pctDiffs



def main():
    TrendingAnalyzer("CG-YvWpXFroowKjpZhupbfaQkZq").main()

parser = argparse.ArgumentParser(
    description="Analyze trending.log"
)
parser.add_argument(
    "-o", "--output",
    type=str,
    required=False,
    help="Path to the output file (no default)"
)
args = parser.parse_args()

try:
    main()
except Exception as e:
    print(f"Failed to main", e)
    traceback.print_exc()
