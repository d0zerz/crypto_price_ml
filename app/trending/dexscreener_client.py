from datetime import datetime, timezone
import time
from typing import List, Optional
import requests
import logging
from dataclasses import asdict, dataclass

from trending.dex_token import DexToken

# Get module logger
logger = logging.getLogger(__name__)

import logging

@dataclass
class TokenProfile:
    url: str
    chain_id: str
    token_address: str

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
    
    def fetch_with_retry(self, url, max_retries=5):
        retries = 0
        while retries < max_retries:
            try:
                response = requests.get(url)
                response.raise_for_status()  # Raise HTTPError for bad responses
                return response.json()  # Return data if successful
            
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:  # Too Many Requests
                    wait_time = 60
                    logger.info(f"HTTP 429 received. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    retries += 1
                else:
                    raise  # Re-raise other HTTP errors

        logger.error("Max retries reached. Request failed.", exc_info=True)
        return None

    def get_token_pair(self, chain_id: str, token_address: str) -> Optional[DexToken]:
        url = self.PAIR_URL.format(chain_id, token_address)
        pairs = self.fetch_with_retry(url)

        if len(pairs) < 1:
            return None
        
        aggregated_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),            
            "chain_id": chain_id,
            "token_address": token_address,
            "token_name": pairs[0]["baseToken"]["name"],
            "token_symbol": pairs[0]["baseToken"]["symbol"],
            "dex_id": pairs[0]["dexId"],
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
        
        token_pair = DexToken(**aggregated_data)
        logger.info(f"{token_pair}")
        return token_pair

# Example usage
if __name__ == "__main__":
    client = DexScreenerClient()
    profiles = client.get_latest_solana_token_profiles()
    for profile in profiles:
        token_pair = client.get_token_pair(profile.chain_id, profile.token_address)
        logger.info(token_pair)
