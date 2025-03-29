import logging
import os
import time
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from typing import List

import pandas as pd
from prices.price_data import PriceDataNotFoundException
from trending.coin_data_io import CoinData, CoinDataIo
from trending.coingecko_client import CoinGeckoClient, RateLimitException
from trending.dex_token import DexDataIo
from trending.trending_data_io import TrendingData, TrendingDataIo

SKIP_FIRST_COINS = 10
COIN_DATA_FILE = "coin_data_dump.xlsx"

# Get module logger
logger = logging.getLogger(__name__)


class CoingeckoAnalysis:

    INTERVALS = [
        timedelta(hours=1),
        timedelta(hours=6),
        timedelta(hours=12),
        timedelta(hours=24),
        timedelta(hours=48),
    ]

    def __init__(self, coingecko_client: CoinGeckoClient, trending_dir: str):
        self.client = coingecko_client
        self.trending_dir = trending_dir
        self.coin_data_io = CoinDataIo(trending_dir)
        self.dex_coin_data_io = DexDataIo(trending_dir)

        coin_field_names = [field.name for field in fields(CoinData)]
        interval_names = [
            f"{round(i.total_seconds() / 3600)}hr_after" for i in self.INTERVALS
        ]
        self.dataframe_cols = coin_field_names + interval_names

    def main(self):
        io = TrendingDataIo(self.trending_dir)
        coinDataFrame = None
        if os.path.exists(COIN_DATA_FILE):
            coinDataFrame = pd.read_excel(io=COIN_DATA_FILE)
        else:
            trendings = io.getTrendings()
            coinDataFrame = self.getTotals(trendings)
            coinDataFrame.to_excel(COIN_DATA_FILE, index=False)

        logger.info(f"Total coins: {len(coinDataFrame)}")
        logger.info(f"DataFrame columns: {coinDataFrame.columns}")
        logger.info(f"1hr price diff: {coinDataFrame['1hr_after'].mean()}")
        logger.info(f"6hr price diff: {coinDataFrame['6hr_after'].mean()}")
        logger.info(f"12hr price diff: {coinDataFrame['12hr_after'].mean()}")
        logger.info(f"24hr price diff: {coinDataFrame['24hr_after'].mean()}")
        logger.info(f"48hr price diff: {coinDataFrame['48hr_after'].mean()}")

    def printNew(self, trendings: List[TrendingData]):
        coinsProcessed = []
        for trending in trendings:
            for coin in trending.new_trendings:
                if coin not in coinsProcessed:
                    logger.info(f"{trending.timestamp} new coin {coin}")
                    coinsProcessed.append(coin)

    def getTotals(self, trendings: List[TrendingData]) -> pd.DataFrame:
        coinsProcessed = trendings[0].trendings
        allCoinData = []
        skipped = 0
        for trending in trendings:
            if self.shouldSkipTrending(trending):
                continue
            for coin in trending.new_trendings:
                if coin in coinsProcessed:
                    continue
                if skipped < SKIP_FIRST_COINS:
                    skipped += 1
                    coinsProcessed.append(coin)
                    continue
                logger.info(f"{trending.timestamp}: processing {coin}")
                coinData = self.processCoin(trending, coin)
                coinsProcessed.append(coin)
                if coinData:
                    if len(coinData) == len(self.dataframe_cols):
                        allCoinData.append(coinData)
                    else:
                        logger.error("Column mismatch in coin data")
                else:
                    logger.warning(f"No data for {coin}")
        return self.createNewDataFrame(allCoinData)

    def shouldSkipTrending(self, trending: TrendingData):
        earliest_process_date = (
            datetime.now(timezone.utc) - self.INTERVALS[-1]
        ).replace(tzinfo=None)
        return trending.timestamp > earliest_process_date

    def createNewDataFrame(self, list_of_lists: List[List]):
        return pd.DataFrame(list_of_lists, columns=(self.dataframe_cols))

    def processCoin(self, trending: TrendingData, coin: str) -> List:
        data = self.coin_data_io.getCoinDataFromFile(coin)
        if abs(trending.timestamp - data.data_snapshot_time) > timedelta(minutes=15):
            logger.warning(f"Coin data too far off trending for {coin}")
            return None
        coin_data = list(data.__dict__.values())
        while True:
            attempts = 0
            try:
                attempts += 1
                pct_diffs = self.find_price_diffs(coin, trending)
                return coin_data + pct_diffs
            except KeyError as e:
                logger.error(f"No coin in map found for {coin}", exc_info=True)
                return None
            except PriceDataNotFoundException as e:
                logger.error(
                    f"No close enough price data found for {coin}", exc_info=True
                )
                return None
            except RateLimitException as e:
                if attempts > 10:
                    logger.error(
                        f"Giving up on {coin} after 10 attempts", exc_info=True
                    )
                    raise Exception(f"giving up on {coin} after 10 attempts")
                logger.warning(f"Rate Limited: retrying on {coin} in 60s")
                time.sleep(60)

    # Find price diff represented by a percentage from the start date
    def find_price_diffs(self, coin: str, trending: TrendingData) -> List[int]:
        currTs = trending.timestamp
        prices = self.client.get_historical_chart(coin, 90)
        if not prices:
            logger.warning(f"Couldn't get prices for {coin}")
            return None
        startPrice = prices.getClosestPrice(currTs)
        if startPrice == 0:
            return None

        timeDiffs = [currTs + interval for interval in self.INTERVALS]
        pctDiffs = []
        for curTime in timeDiffs:
            price = prices.getClosestPrice(curTime)
            delta = price - startPrice
            pctIncrease = round((delta / startPrice) * 100, 3)
            pctDiffs.append(pctIncrease)
            # logger.debug(f"{coin}: from {currTs} to {curTime}, price went from {startPrice} to {price} for a {pctIncrease}% increase")

        return pctDiffs
