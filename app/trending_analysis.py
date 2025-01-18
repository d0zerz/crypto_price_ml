import os
import traceback
from typing import List
from trending.coingecko_client import CoinGeckoClient, RateLimitException
from trending.trending_data_io import TrendingData, TrendingDataIo
from trending.coin_data_io import CoinData, CoinDataIo
from datetime import datetime, timedelta, timezone
import time
import argparse
import pandas as pd


class TrendingAnalyzer:

    INTERVALS = [
        timedelta(hours=1),
        timedelta(hours=3),
        timedelta(hours=7),
        timedelta(hours=12),
        timedelta(hours=24),
    ]

    def __init__(self, cgApiKey: str, trending_dir: str):
        self.client = CoinGeckoClient(api_key=cgApiKey)
        self.trending_dir = trending_dir
        self.coin_data_io = CoinDataIo(trending_dir)

    def main(self):
        io = TrendingDataIo(self.trending_dir)
        trendings = io.getTrendings()
        coinsTotaled, diffTotals = self.getTotals(trendings)

        print(f"total coins: {coinsTotaled}")
        for index, diff in enumerate(diffTotals):
            pctDiff = round(diff / coinsTotaled, 2)
            minsAhead = self.INTERVALS[index].total_seconds() / 60
            print(f"{minsAhead} minutes later: {pctDiff}% increase ")

    def printNew(self, trendings: List[TrendingData]):
        coinsProcessed = []
        for trending in trendings:
            for coin in trending.new_trendings:
                if coin not in coinsProcessed:
                    print(f"{trending.timestamp} new coin {coin}")
                    coinsProcessed.append(coin)

    def getTotals(self, trendings: List[TrendingData]):
        coinsProcessed = []
        coinsTotaled = 0
        diffTotals = [0 for i in self.INTERVALS]
        for trending in trendings:
            earliest_process_date = (
                datetime.now(timezone.utc) - self.INTERVALS[-1]
            ).replace(tzinfo=None)
            if trending.timestamp > earliest_process_date:
                continue
            for coin in trending.new_trendings:
                if coin not in coinsProcessed:
                    print(f"{trending.timestamp}: processing {coin}")
                    diffs = self.processCoin(trending, coin)
                    coinsProcessed.append(coin)
                    print(f"processed {coin} with {diffs}")
                    if diffs:
                        for index, diff in enumerate(diffs):
                            diffTotals[index] = diffTotals[index] + diff
                        coinsTotaled += 1
        return coinsTotaled, diffTotals

    def processCoin(self, trending: TrendingData, coin: str) -> List[int]:
        data = self.coin_data_io.getCoinDataFromFile(coin)
        print(data)
        while True:
            attempts = 0
            try:
                attempts += 1
                return self.find_price_diffs(coin, trending)
            except KeyError as e:
                print(f"no coin in map found for {coin}")
                return None
            except RateLimitException as e:
                if attempts > 10:
                    raise Exception(f"giving up on {coin} after 10 attempts")
                print(f"Rate Limited:  retrying on {coin} in 60s")
                time.sleep(60)

    # Find price diff from
    def find_price_diffs(self, coin: str, trending: TrendingData) -> List[int]:
        currTs = trending.timestamp
        prices = self.client.get_historical_chart(coin, 90)
        if not prices:
            print(f"Couldn't get prices for {coin}")
            return None
        startPrice = prices.getClosestPrice(currTs)
        if startPrice == 0:
            return None

        timeDiffs = [currTs + interval for interval in self.INTERVALS]
        pctDiffs = []
        for curTime in timeDiffs:
            price = prices.getClosestPrice(curTime)
            delta = price - startPrice
            pctIncrease = round((delta / startPrice) * 100)
            pctDiffs.append(pctIncrease)
            # print(f"{coin}: from {currTs} to {curTime}, price went from {startPrice} to {price} for a {pctIncrease}% increase")

        return pctDiffs


def main(trending_dir: str):
    cg_key = os.getenv("COINGECKO_KEY")
    TrendingAnalyzer(cg_key, trending_dir).main()


parser = argparse.ArgumentParser(description="Analyze trending.log")
parser.add_argument(
    "-t",
    "--trending",
    type=str,
    required=False,
    default="trending.log",
    help="Path to the trending directory",
)
args = parser.parse_args()

try:
    main(args.trending)
except Exception as e:
    print(f"Failed to main", e)
    traceback.print_exc()
