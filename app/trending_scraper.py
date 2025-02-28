import asyncio
import os
import traceback
from typing import List

from requests import HTTPError
from trading.jupiter_client import JupiterClient
from trending.coingecko_client import CoinGeckoClient
from trending.dexscreener_client import DexScreenerClient
from trending.coin_data_io import CoinDataIo
from trending.dex_token import DexDataIo, FUTURE_TIMES, DexToken
from trending.trending_data_io import TrendingDataIo
from trending.jupiter_quote_scraper import JupiterQuoteScraper
from datetime import datetime, timezone
import time
import argparse

def getUtcString():
    utc_now = datetime.now(timezone.utc)
    return utc_now.strftime("%Y-%m-%d %H:%M:%S")

import traceback

def safe_call(func, *args, **kwargs):
    try:
        print(f"Calling: {func.__name__} with args: {args}, kwargs: {kwargs}")
        return func(*args, **kwargs)
    except Exception as e:
        print(f"Error occurred: {e}")
        traceback.print_exc()
        return None

class TrendingScraper:

    def __init__(self, output_directory: str, jup_client: JupiterClient):
        self.output_directory = output_directory
        self.coingecko = CoinGeckoClient(api_key=os.getenv("COINGECKO_KEY"))
        self.jup_client = jup_client
        self.coin_data_io = CoinDataIo(output_directory)
        self.dex_coin_data_io = DexDataIo(output_directory)
        self.dex_client = DexScreenerClient()
        self.jup_quote_scraper = JupiterQuoteScraper(jup_client, output_directory, 60)

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
        #trending_data_io = TrendingDataIo(self.output_directory, "dex_trending.log")
        unique_tokens = []
        for tokenProfile in self.dex_client.get_latest_solana_token_profiles():
            if not self.dex_coin_data_io.token_exists(tokenProfile.token_address):
                token_pair = self.dex_client.get_token_pair(tokenProfile.chain_id, tokenProfile.token_address)
                # asyncio.run(self.runExchangeData(token_pair))
                self.dex_coin_data_io.write_to_file(token_pair)
                unique_tokens.append(token_pair.token_address)

        #self.processTrending(unique_tokens, trending_data_io)
        if unique_tokens:
            self.jup_quote_scraper.start_sampling(unique_tokens)

    def archiveDexTokens(self):
        last_future_label = FUTURE_TIMES[-1]["label"]
        for coin in self.dex_coin_data_io.load_all_dex_coins(last_future_label):
            self.dex_coin_data_io.archive_token_files(coin.token_address)

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
        start_time = time.time()
        print(f"{getUtcString()} Starting Scraping")
        # safe_call(self.processCoinGeckoTrendings)
        # safe_call(self.populateDexFutures) DEPRECATED
        safe_call(self.processDexTrendings)
        #safe_call(self.archiveDexTokens)
        total_time = time.time() - start_time
        print(f"{getUtcString()} Done Scraping, took {total_time:.4f}s")

        self.jup_quote_scraper.wait_for_completion()
        total_time = time.time() - start_time
        print(f"{getUtcString()} Done Quote Scraping, took {total_time:.4f}s")

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
    client = JupiterClient(os.getenv("MAIN_WALLET"), os.getenv("SOL_NODE"))
    TrendingScraper(args.output, client).main()
except Exception as e:
    print(f"Error: {e}")
    print(traceback.format_exc())