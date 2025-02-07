
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any, Dict, List

FUTURE_TIMES = [
    {
        "label": "T30m",
        "interval": timedelta(minutes=30)
    },
    {
        "label": "T2hr",
        "interval": timedelta(hours=2)
    },
    {
        "label": "T6hr",
        "interval": timedelta(hours=6)
    },
    {
        "label": "T24hr",
        "interval": timedelta(hours=24)
    },
    {
        "label": "T2d",
        "interval": timedelta(days=2)
    },
    {
        "label": "T6d",
        "interval": timedelta(days=6)
    },    
    ]

@dataclass
class DexToken:
    timestamp: datetime
    chain_id: str
    token_address: str
    token_name: str
    token_symbol: str
    price_usd: float
    price_native: float
    buys_m5: int
    buys_h1: int
    buys_h6: int
    buys_h24: int
    sells_m5: int
    sells_h1: int
    sells_h6: int
    sells_h24: int
    volume_h24: float
    price_change_h24: float
    liquidity_usd: float
    market_cap: float

    def isDue(self, interval: timedelta):
        return datetime.now(timezone.utc) >= self.timestamp + interval

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "DexToken":
        """Creates a DexToken instance from a JSON dictionary."""
        ts = datetime.fromisoformat(data["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return cls(
            timestamp=ts,
            chain_id=data["chain_id"],
            token_address=data["token_address"],
            token_name=data["token_name"],
            token_symbol=data["token_symbol"],
            price_usd=data["price_usd"],
            price_native=data["price_native"],
            buys_m5=data["buys_m5"],
            buys_h1=data["buys_h1"],
            buys_h6=data["buys_h6"],
            buys_h24=data["buys_h24"],
            sells_m5=data["sells_m5"],
            sells_h1=data["sells_h1"],
            sells_h6=data["sells_h6"],
            sells_h24=data["sells_h24"],
            volume_h24=data["volume_h24"],
            price_change_h24=data["price_change_h24"],
            liquidity_usd=data["liquidity_usd"],
            market_cap=data["market_cap"],
        )

DEX_COIN_DATA_DIR = ".dex_coin_data"

class DexDataIo:

    def __init__(self, base_path: str):
        self.base_path = base_path

    def get_file_path(self, coin: str) -> str:
        return f"{self.base_path}/{DEX_COIN_DATA_DIR}/dex_{coin}"
    
    def write_to_file(self, token: DexToken, suffix: str = None):
        suf = ".json"
        if suffix:
            suf = f"_{suffix}.json"
        file_path = self.get_file_path(token.token_address) + suf
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)

        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(asdict(token), f, indent=4)
    
    def load_all_dex_coins(self, time_mod: str = "") -> List[DexToken]:
        return self._load_dex_coin_data("dex_", f"{time_mod}.json")

    def _load_dex_coin_data(self, starts_with: str, ends_with: str) -> List[DexToken]:
        """Load all CoinData objects from files matching 'dex_{COIN_NAME}.json'."""
        coin_data_list = []
        directory = os.path.join(self.base_path, DEX_COIN_DATA_DIR)

        if not os.path.exists(directory):
            return []

        for filename in os.listdir(directory):
            if filename.startswith(starts_with) and filename.endswith(ends_with):
                file_path = os.path.join(directory, filename)

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        coin_data = DexToken.from_json(data)
                        coin_data_list.append(coin_data)
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    print(f"Error loading {filename}: {e}")

        return coin_data_list