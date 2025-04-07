import logging
import os
import time
from dataclasses import asdict, fields
from datetime import datetime, timedelta, timezone
from typing import List

import pandas as pd
from ml.dex_model import DexModel
from trending.dex_token import DexDataIo, DexToken
from trending.jupter_quote_parser import JupiterQuoteParser

# Get module logger
logger = logging.getLogger(__name__)

COIN_DATA_FILE = "dex_jup_coin_data_dump.xlsx"
FUTURE_COLS = [""]


class DexJupiterQuoteAnalysis:

    def __init__(self, trending_dir: str):
        self.trending_dir = trending_dir
        self.dex_coin_data_io = DexDataIo(trending_dir)
        self.quotes = JupiterQuoteParser(self.trending_dir)

    def main(self):
        coinDataFrame = None
        read_enabled = True
        if os.path.exists(COIN_DATA_FILE) and read_enabled:
            coinDataFrame = pd.read_excel(io=COIN_DATA_FILE)
        else:
            coinDataFrame = self.processFiles()
            coinDataFrame["timestamp"] = coinDataFrame["timestamp"].dt.tz_localize(None)
            coinDataFrame.to_excel(COIN_DATA_FILE, index=True, header=True)

        logger.info(f"total coins: {len(coinDataFrame)}")
        return coinDataFrame

    def getCoinFutures(self, coin: DexToken) -> dict:
        price_diffs = {}
        future = self.quotes.get_row_by_token_address(coin.token_address)
        if not future:
            return price_diffs
        start_price = future["M0000"]
        for future_time in ["M0001","M0006","M0020","M0060",]:  # FUTURE_TIMES:
            future_label = future_time
            price_diff = round(
                100 * (future[future_time] - start_price) / start_price,
                3,
            )
            price_diffs[f"{future_label}_diff_pct"] = price_diff
        return price_diffs

    def processFiles(self) -> pd.DataFrame:
        rows = []
        all_coins = self.dex_coin_data_io.load_all_dex_coins()
        logger.info(f"getting futures for {len(all_coins)} coins")
        for coin in all_coins:
            token_data = asdict(coin)
            futures_data = self.getCoinFutures(coin)
            token_data.update(futures_data)
            rows.append(token_data)
            logger.info(f"{coin.token_symbol} | {coin.token_address}")
        return pd.DataFrame(rows)