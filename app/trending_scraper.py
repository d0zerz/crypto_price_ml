import os
import traceback
from typing import List
from trending.coingecko_client import CoinGeckoClient
from trending.coin_data_io import CoinDataIo
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
        self.trending_data_io = TrendingDataIo(self.output_directory)
        
    def main(self):
        tokens = self.coingecko.get_trending_tokens()
        formatted_time = getUtcString()
        unique_tokens = sorted({entry[0] for entry in tokens})
        last_trending = self.trending_data_io.get_last_trending()
        new_entries = []
        if last_trending:
            new_entries =  [item for item in unique_tokens if item not in last_trending]
            self.processCoins(new_entries)

        if new_entries or not last_trending:
            printstr = str((formatted_time, unique_tokens, new_entries))
            self.trending_data_io.write_to_file(printstr)
            print(f"{formatted_time}: wrote {printstr} to {self.output_directory}")
        else:
            print(f"{formatted_time}: nothing new")
    
    def processCoins(self, coins: List[str]):
        for coin in coins:
            try:
                if not self.coin_data_io.fileExists(coin):
                    self.coin_data_io.write_to_file(coin, self.coingecko.get_coin_data(coin))
            except Exception as e:
                print(f"failed to write coin {coin}", e)
                raise e


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