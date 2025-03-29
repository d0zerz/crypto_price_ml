from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import os
import shutil
import logging
from typing import Any, Dict, List

# Get module logger
logger = logging.getLogger(__name__)

FUTURE_TIMES = [
    {
        "label": "T10m",
        "interval": timedelta(minutes=10)
    },
    {
        "label": "T30m",
        "interval": timedelta(minutes=30)
    },
    {
        "label": "T1hr",
        "interval": timedelta(hours=1)
    },
    {
        "label": "T3hr",
        "interval": timedelta(hours=3)
    },
    {
        "label": "T8hr",
        "interval": timedelta(hours=8)
    },
    {
        "label": "T24h",
        "interval": timedelta(hours=24)
    },    
    ]

FUTURE_TIME_LABELS = [el["label"] for el in FUTURE_TIMES]

@dataclass
class DexToken:
    timestamp: datetime
    chain_id: str
    token_address: str
    token_name: str
    token_symbol: str
    dex_id: str
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
            dex_id=data.get("dex_id",""),
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
ARCHIVE_DIR = ".archive"

class DexDataIo:

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.dir_cache = None

    def get_file_path(self, coin: str) -> str:
        return f"{self.base_path}/{DEX_COIN_DATA_DIR}/dex_{coin}"
    
    def token_exists(self, token_address):
        return os.path.exists(self._get_token_file_path(token_address))

    def _get_token_file_path(self, token_address, suffix: str=""):
        suf = ".json"
        if suffix:
            suf = f"_{suffix}.json"
        file_path = self.get_file_path(token_address) + suf
        return file_path

    def archive_token_files(self, token):
        directory = f"{self.base_path}/{DEX_COIN_DATA_DIR}"
        if not os.path.isdir(directory):
            logger.error(f"Error: {directory} is not a Directory ", exc_info=True)
            return
        
        # Create the archive directory if it doesn't exist
        archive_dir = os.path.join(directory, ARCHIVE_DIR)
        os.makedirs(archive_dir, exist_ok=True)
        
        # Find and move all matching _T*.json files
        for file in os.listdir(directory):
            if file.startswith(f"dex_{token}") and file.endswith(".json"):
                src_path = os.path.join(directory, file)
                dest_path = os.path.join(archive_dir, file)
                try:
                    shutil.move(src_path, dest_path)
                except Exception as e:
                    logger.error(f"Failed to archive {file}: {e}", exc_info=True)

    def write_to_file(self, token: DexToken, suffix: str = None):
        file_path=self._get_token_file_path(token.token_address, suffix)
        if os.path.exists(self._get_token_file_path(file_path)):
            return

        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(asdict(token), f, indent=4)
    
    # no futures
    def load_all_dex_coins(self, future_label = None) -> List[DexToken]:
        if future_label:
            return self._load_dex_coin_data("dex_", f'_{future_label}.json')
        else:
            return self._load_dex_coin_data("dex_", None)
    
    def load_all_futures(self, token_address):
        return self._load_dex_coin_data(f"dex_{token_address}", '.json')
    
    def load_future(self, token_address, future_name) -> DexToken:
        futures = self._load_dex_coin_data(f"dex_{token_address}", f'_{future_name}.json')
        assert len(futures) < 2
        if not futures or len(futures) == 0:
            return None
        return futures[0]

    def _is_a_time_file(self, filename: str) -> bool:
        for interval in FUTURE_TIMES:
            if filename.endswith(f'{interval["label"]}.json'):
                return True
        return False

    def _get_dir_list(self, directory):
        if not self.dir_cache:
            self.dir_cache = os.listdir(directory)
        return self.dir_cache
    

    def _load_dex_coin_data(self, starts_with: str, time_mod: str = None) -> List[DexToken]:
        coin_data_list = []
        directory = os.path.join(self.base_path, DEX_COIN_DATA_DIR)

        if not os.path.exists(directory):
            return []

        ends_with = f"{time_mod}" if time_mod else ".json"
        for filename in self._get_dir_list(directory):
            should_exclude = time_mod is None and self._is_a_time_file(filename)
            if not should_exclude and (filename.startswith(starts_with) and filename.endswith(ends_with)):
                file_path = os.path.join(directory, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        coin_data = DexToken.from_json(data)
                        coin_data_list.append(coin_data)
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    logger.error(f"Error loading {filename}: {e}", exc_info=True)

        return coin_data_list