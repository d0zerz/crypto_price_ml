from datetime import datetime, timezone
import json
import os
from typing import List
import requests
from dataclasses import asdict, dataclass

@dataclass
class TokenProfile:
    url: str
    chain_id: str
    token_address: str

@dataclass
class TokenPairAggregated:
    timestamp: str
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

    def write_to_file(self, file_path: str):
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=4)

    @classmethod
    def load_from_file(cls, file_path: str):
        with open(file_path, "r") as file:
            data = json.load(file)
        return cls(**data)
        

class DexScreenerClient:
    BASE_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
    PAIR_URL = "https://api.dexscreener.com/token-pairs/v1/{}/{}/"

    def get_latest_solana_token_profiles(self) -> List[TokenProfile]:
        response = requests.get(self.BASE_URL)
        response.raise_for_status()
        
        token_profiles = []
        for data in response.json():
            chain_id=data["chainId"]
            if chain_id == "solana":
                token_profiles.append(
                    TokenProfile(
                        url=data["url"],
                        chain_id=data["chainId"],
                        token_address=data["tokenAddress"],
                    )
                )
        return token_profiles
    
    def get_token_pair(self, chain_id: str, token_address: str) -> TokenPairAggregated:
        url = self.PAIR_URL.format(chain_id, token_address)
        response = requests.get(url)
        response.raise_for_status()
        pairs = response.json()
        
        aggregated_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "token_name": pairs[0]["baseToken"]["name"],
            "token_symbol": pairs[0]["baseToken"]["symbol"],
            "price_usd": 0,
            "price_native": 0,
            "buys_m5": 0, "buys_h1": 0, "buys_h6": 0, "buys_h24": 0,
            "sells_m5": 0, "sells_h1": 0, "sells_h6": 0, "sells_h24": 0,
            "volume_h24": 0,
            "price_change_h24": 0,
            "liquidity_usd": 0,
            "market_cap": 0
        }
        
        for pair in pairs:
            aggregated_data["price_usd"] += float(pair.get("priceUsd", 0))
            aggregated_data["price_native"] += float(pair.get("priceNative", 0))
            for timeframe in ["m5", "h1", "h6", "h24"]:
                if timeframe in pair.get("txns", {}):
                    aggregated_data[f"buys_{timeframe}"] += pair["txns"][timeframe].get("buys", 0)
                    aggregated_data[f"sells_{timeframe}"] += pair["txns"][timeframe].get("sells", 0)
            aggregated_data["volume_h24"] += pair.get("volume", {}).get("h24", 0)
            aggregated_data["price_change_h24"] += pair.get("priceChange", {}).get("h24", 0)
            aggregated_data["liquidity_usd"] += pair.get("liquidity", {}).get("usd", 0)
            aggregated_data["market_cap"] += pair.get("marketCap", 0)
        
        return TokenPairAggregated(**aggregated_data)

# Example usage
if __name__ == "__main__":
    client = DexScreenerClient()
    profiles = client.get_latest_solana_token_profiles()
    for profile in profiles:
        token_pair = client.get_token_pair(profile.chain_id, profile.token_address)
        print(token_pair)
