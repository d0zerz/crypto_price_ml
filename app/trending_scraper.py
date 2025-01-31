import os
import traceback
from typing import List
from trending.coingecko_client import CoinGeckoClient
from trending.dexscreener_client import DexScreenerClient
from trending.coin_data_io import CoinDataIo
from trending.coin_data_io import COIN_DATA_DIR
from trending.trending_data_io import TrendingDataIo
from datetime import datetime, timezone
import argparse

def getUtcString():
    utc_now = datetime.now(timezone.utc)
    return utc_now.strftime("%Y-%m-%d %H:%M:%S")

class TrendingScraper:

    def __init__(self, output_directory: str):
        self.output_directory = output_directory
        self.coingecko = CoinGeckoClient(api_key=os.getenv("COINGECKO_KEY"))
        self.coin_data_io = CoinDataIo(output_directory)

    def processCoinGeckoTrendings(self):
        tokens = self.coingecko.get_trending_tokens()
        unique_tokens = sorted({entry[0] for entry in tokens})
        trending_data_io = TrendingDataIo(self.output_directory)
        new_entries = self.processTrending(unique_tokens=unique_tokens, trending_data_io=trending_data_io)
        for coin in new_entries:
            try:
                if not self.coin_data_io.fileExists(coin):
                    self.coin_data_io.write_to_file(coin, self.coingecko.get_coin_data(coin))
            except Exception as e:
                print(f"failed to write coin {coin}", e)
                raise e
    
    def processDexTrendings(self):
        client = DexScreenerClient()
        trending_data_io = TrendingDataIo(self.output_directory, "dex_trending.log")
        unique_tokens = []
        for tokenProfile in client.get_latest_solana_token_profiles():
            token_pair = client.get_token_pair(tokenProfile.chain_id, tokenProfile.token_address)
            token_pair.write_to_file(f"{self.output_directory}/{COIN_DATA_DIR}/dex_{token_pair.token_symbol}.json")
            unique_tokens.append(token_pair.token_symbol)

        self.processTrending(unique_tokens, trending_data_io)

    def processTrending(self, unique_tokens: List, trending_data_io: TrendingDataIo):
        last_trending = trending_data_io.get_last_trending()
        formatted_time = getUtcString()
        new_entries = []
        if last_trending:
            new_entries =  [item for item in unique_tokens if item not in last_trending]

        if new_entries or not last_trending:
            printstr = str((formatted_time, unique_tokens, new_entries))
            trending_data_io.write_to_file(printstr)
            print(f"{formatted_time}: wrote {printstr} to {self.output_directory}")
        else:
            print(f"{formatted_time}: nothing new")
        return new_entries

    def main(self):
        self.processCoinGeckoTrendings()
        self.processDexTrendings()

parser = argparse.ArgumentParser(
    description=""
)

parser.add_argument(
    "-o", "--output",
    type=str,
    required=True,
    help="Path to the output directory (no default)"
)

args = parser.parse_args()
try:
    TrendingScraper(args.output).main()
except Exception as e:
    print(f"Error: {e}")
    print(traceback.format_exc())