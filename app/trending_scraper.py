import argparse
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import List

from trading.jupiter_client import JupiterClient
from trading.jupiter_trader import DexTrader
from trading.solana_client import SolanaClient
from trading.strategies.ath_strategy import ATHSellStrategy
from trending.coin_data_io import CoinDataIo
from trending.coingecko_client import CoinGeckoClient
from trending.dex_token import FUTURE_TIMES, DexDataIo
from trending.dexscreener_client import DexScreenerClient
from trending.jupiter_quote_scraper import JupiterQuoteScraper
from trending.trending_data_io import TrendingDataIo
from utils.logging_config import configure_logging

# Get module logger
logger = logging.getLogger(__name__)


def getUtcString():
    utc_now = datetime.now(timezone.utc)
    return utc_now.strftime("%Y-%m-%d %H:%M:%S")


def safe_call(func, *args, **kwargs):
    try:
        logger.info(f"Calling: {func.__name__} with args: {args}, kwargs: {kwargs}")
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        return None


class TrendingScraper:

    def __init__(self, output_directory: str, sol_client: SolanaClient):
        self.output_directory = output_directory
        self.coingecko = CoinGeckoClient(api_key=os.getenv("COINGECKO_KEY"))
        jup_client = JupiterClient(sol_client.keypair)
        self.jup_client = jup_client
        self.coin_data_io = CoinDataIo(output_directory)
        self.dex_coin_data_io = DexDataIo(output_directory)
        self.dex_client = DexScreenerClient()
        self.jup_quote_scraper = JupiterQuoteScraper(jup_client, output_directory, 60)
        self.dex_trader = DexTrader(output_directory=output_directory, buy_amount=int(1_000_000_000 / 100), sell_strategy=ATHSellStrategy())
        self.scraping = True
        self.scrape_interval_seconds = 30
        self.run_trading = os.getenv("REAL_TRADING", "False").lower() in ("true")
        self.run_quote_scraping = os.getenv("QUOTE_SCRAPING", "False").lower() in ("true")
        self.first_run = True

    def processDexTrendings(self):
        unique_tokens = []
        for tokenProfile in self.dex_client.get_latest_solana_token_profiles():
            if not self.dex_coin_data_io.token_exists(tokenProfile.token_address):
                dex_token = self.dex_client.get_token_pair(
                    tokenProfile.chain_id, tokenProfile.token_address
                )
                self.dex_coin_data_io.write_to_file(dex_token)
                unique_tokens.append(dex_token.token_address)
                if self.run_trading and not self.first_run:
                    self.dex_trader.start_trading(dex_token)

        if unique_tokens and self.run_quote_scraping:
            self.jup_quote_scraper.start_sampling(unique_tokens)
        else:
            logger.info("Nothing new")

    def run_scrape_loop(self):
        next_sample_time = datetime.now()

        while self.scraping:
            current_time = datetime.now()
            if current_time >= next_sample_time:
                safe_call(self.processDexTrendings)
                total_time = time.time() - int(current_time.timestamp())
                logger.info(f"Done Scraping, took {total_time:.4f}s")
                next_sample_time = next_sample_time + timedelta(
                    seconds=self.scrape_interval_seconds
                )
                self.first_run = False
            time.sleep(1)

    def main(self):
        start_time = time.time()
        logger.info("Starting Scraping")
        self.run_scrape_loop()
        total_time = time.time() - start_time
        logger.info(f"Done Scraping, took {total_time:.4f}s")


parser = argparse.ArgumentParser(description="")

parser.add_argument(
    "-o",
    "--output",
    type=str,
    required=True,
    help="Path to the output directory (no default)",
)

args = parser.parse_args()
try:
    # Configure logging
    configure_logging(log_dir=args.output, logfile="scraper.log")
    sol_client = SolanaClient(os.getenv("SOL_NODE"), os.getenv("MAIN_WALLET"))
    TrendingScraper(args.output, sol_client).main()
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
