import ast
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from dateutil.parser import isoparse
from trending.coingecko_client import CoinGeckoClient

# Get module logger
logger = logging.getLogger(__name__)

COIN_DATA_DIR = ".coin_data"


@dataclass
class CoinData:
    data_snapshot_time: datetime
    coin_id: str
    coin_symbol: str
    platform_id: Optional[str] = None
    current_price_btc: Optional[float] = None
    current_price_usd: Optional[float] = None
    ath_btc: Optional[float] = None
    ath_date: Optional[datetime] = None
    market_cap_btc: Optional[float] = None
    total_volume_btc: Optional[float] = None
    high_24h_btc: Optional[float] = None
    low_24h_btc: Optional[float] = None
    price_change_pct_1hr_btc: Optional[float] = None
    price_change_pct_24hr_btc: Optional[float] = None
    price_change_pct_7d_btc: Optional[float] = None
    price_change_pct_14d_btc: Optional[float] = None
    price_change_pct_30d_btc: Optional[float] = None
    price_change_pct_60d_btc: Optional[float] = None
    price_change_pct_200d_btc: Optional[float] = None
    price_change_pct_1yr_btc: Optional[float] = None

    @classmethod
    def from_coingecko_json(cls, coingecko_coin: dict) -> "CoinData":
        data = coingecko_coin.get("data", {})
        market_data = data.get("market_data", {})
        return cls(
            data_snapshot_time=(
                isoparse(coingecko_coin["timestamp"]).replace(tzinfo=None)
                if "timestamp" in coingecko_coin
                else None
            ),
            coin_id=data.get("id"),
            coin_symbol=data.get("symbol"),
            platform_id=data.get("asset_platform_id"),
            current_price_btc=market_data.get("current_price", {}).get("btc"),
            current_price_usd=market_data.get("current_price", {}).get("usd"),
            ath_btc=market_data.get("ath", {}).get("btc"),
            ath_date=(
                isoparse(market_data["ath_date"]["btc"]).replace(tzinfo=None)
                if "ath_date" in market_data and "btc" in market_data["ath_date"]
                else None
            ),
            market_cap_btc=market_data.get("market_cap", {}).get("btc"),
            total_volume_btc=market_data.get("total_volume", {}).get("btc"),
            high_24h_btc=market_data.get("high_24h", {}).get("btc"),
            low_24h_btc=market_data.get("low_24h", {}).get("btc"),
            price_change_pct_1hr_btc=market_data.get(
                "price_change_percentage_1h_in_currency", {}
            ).get("btc"),
            price_change_pct_24hr_btc=market_data.get(
                "price_change_percentage_24h_in_currency", {}
            ).get("btc"),
            price_change_pct_7d_btc=market_data.get(
                "price_change_percentage_7d_in_currency", {}
            ).get("btc"),
            price_change_pct_14d_btc=market_data.get(
                "price_change_percentage_14d_in_currency", {}
            ).get("btc"),
            price_change_pct_30d_btc=market_data.get(
                "price_change_percentage_30d_in_currency", {}
            ).get("btc"),
            price_change_pct_60d_btc=market_data.get(
                "price_change_percentage_60d_in_currency", {}
            ).get("btc"),
            price_change_pct_200d_btc=market_data.get(
                "price_change_percentage_200d_in_currency", {}
            ).get("btc"),
            price_change_pct_1yr_btc=market_data.get(
                "price_change_percentage_1y_in_currency", {}
            ).get("btc"),
        )


class CoinDataIo:

    def __init__(self, base_path: str):
        self.base_path = base_path

    def get_file_path(self, coin: str) -> str:
        return f"{self.base_path}/{COIN_DATA_DIR}/{coin}"

    def write_to_file(self, coin: str, raw_coin_data: str):
        path = self.get_file_path(coin)
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory)

        with open(path, "w", encoding="utf-8") as file:
            file.write(f"{raw_coin_data}\n")

    def fileExists(self, coin) -> bool:
        os.path.exists(self.get_file_path(coin))

    def getCoinDataFromFile(self, coin: str) -> CoinData:
        file_path = self.get_file_path(coin)
        try:
            # Read the file and load JSON content
            with open(file_path, "r", encoding="utf-8") as file:
                json_data = json.load(file)
            return CoinData.from_coingecko_json(json_data)
        except Exception as e:
            logger.error(f"Failed to get coin data for {coin}", exc_info=True)
            raise
