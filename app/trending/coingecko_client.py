import traceback
from typing import Optional
import requests
import pandas as pd
from datetime import datetime

from prices.price_data import PriceData

class RateLimitException(Exception):
    def __init__(self, message):
        super().__init__(message)

class CoinGeckoClient:
    def __init__(self, api_key: str):
        """
        Initializes the CoinGeckoClient with an API key.

        :param api_key: Your CoinGecko API key
        """
        self.api_key = api_key
        self.base_url = "https://api.coingecko.com/api/v3"
        self.headers = {
            "accept": "application/json",
            "x-cg-demo-api-key": self.api_key
        }

    def _get_url(self, suffix_path):
        return f"{self.base_url}{suffix_path}"
    
    def _do_http(self, url, params={}, raw=False) -> dict:
        try:
            response = requests.get(url, params=params, headers=self.headers)
            if (response.status_code == 429):
                raise RateLimitException("")

            response.raise_for_status()  # Raise an error for bad status codes
            if raw:
                return response.text
            else:
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            # traceback.print_exc()
            return []

    def get_historical_chart(self, coin: str, startDate: datetime, endDate: datetime) -> Optional[PriceData]:

        url = self._get_url(f"/coins/{coin.lower()}/market_chart/range")
        vsCurrency = "usd" if coin == "btc" else "btc"
        params = {
            'vs_currency': vsCurrency,
            'from': int(startDate.timestamp()),
            'to': int(endDate.timestamp())
            }
        data = self._do_http(url, params={})
        if not data:
            return None
        prices = data["prices"]
        pricesDf = pd.DataFrame(prices, columns=["timestamp", "price_vs_btc"])
        pricesDf['timestamp'] = pd.to_datetime(pricesDf['timestamp'], unit='ms')
        pricesDf.set_index('timestamp', inplace=True)
        return PriceData(coin, pricesDf)

    def get_trending_tokens(self):
        url = self._get_url("/search/trending")
        data = self._do_http(url, params={})

        # Parse and display trending tokens
        trending_tokens = []
        for item in data.get("coins", []):
            id = item["item"]["coin_id"]
            name = item["item"]["name"]
            symbol = item["item"]["symbol"]
            market_cap = item["item"]["data"]["market_cap"]
            rank = item["item"]["market_cap_rank"]
            trending_tokens.append((id, name, symbol, market_cap, rank))
        return trending_tokens
    
    def get_coin_data(self, coin: str):
         url = self._get_url(f"/coins/{coin.lower()}")
         data = self._do_http(url, raw=True)
         return data