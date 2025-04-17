import asyncio
import concurrent.futures
import json
import logging
import os
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import List

import pandas as pd
from ml.dex_model import MARKET_CAP_MIN, TARGETS, DexModel
from openpyxl import load_workbook
from trading.jupiter_client import JupiterClient, Quote
from trending.dex_token import DexToken

# Get module logger
logger = logging.getLogger(__name__)

import logging

SOL_BASE = "So11111111111111111111111111111111111111112"
BUY_SLIPPAGE = 200
SELL_SLIPPAGE = 1000


class DexTrader:
    """
    A class for sampling exchange rates at specified intervals over a duration.
    Stores results in an Excel file with minutes elapsed as columns and tokens as rows.
    """

    def __init__(
        self,
        jup_client: JupiterClient,
        output_directory: str,
        buy_amount: int = 100_000_000,
    ):
        self.jup_client = jup_client
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=60)
        self.excel_lock = threading.Lock()
        self.buy_amount = buy_amount
        self.output_directory = output_directory
        self.output_file = self.file_path = f"{output_directory}/jupiter_trades.xlsx"
        self.dex_model = DexModel()

    def _get_predictions(self, token: DexToken) -> dict:
        if token.market_cap < MARKET_CAP_MIN:  # MARKET_CAP_MIN
            logger.info(f"Market cap too low for {token}")
            return False
        if token.liquidity_usd <= 0 or token.volume_h24 <= 0:
            logger.info(f"Invalid data for {token}")
            return False

        buysell_m5_ratio = token.buys_m5 / 1 if token.sells_m5 == 0 else token.sells_m5
        buysell_h1_ratio = token.buys_h1 / 1 if token.sells_h1 == 0 else token.sells_h1
        market_cap_liquidity_ratio = token.market_cap / token.liquidity_usd
        market_cap_volume_ratio = token.market_cap / token.volume_h24
        price_change_h24 = token.price_change_h24
        data = {
            "buysell_m5_ratio": buysell_m5_ratio,
            "buysell_h1_ratio": buysell_h1_ratio,
            "market_cap_liquidity_ratio": market_cap_liquidity_ratio,
            "market_cap_volume_ratio": market_cap_volume_ratio,
            "price_change_h24": price_change_h24,
        }
        return self.dex_model.get_predictions(data)

    # loss that's tolerable in negative percent
    def get_sell_loss_threshold(self, predictions: dict, minutes_elapsed, minutes_expected):
        tolerance = 0
        if (predictions[TARGETS[3]]):
            tolerance = tolerance + 10
        if (predictions[TARGETS[2]]):
            tolerance = tolerance + 5
        if (predictions[TARGETS[1]]):
            tolerance = tolerance + 3
        if (predictions[TARGETS[0]]):
            tolerance = tolerance + 1
        if minutes_elapsed > minutes_expected:
            tolerance = tolerance * .5
        if minutes_elapsed > minutes_expected * 2:
            tolerance = tolerance * .25
        if minutes_elapsed > 60:
            tolerance
        return -1 * tolerance

    # loss that's tolerable in negative percent
    def get_expected_minutes(self, predictions: dict):
        tolerance = 0
        if (predictions[TARGETS[3]]):
            return 60
        if (predictions[TARGETS[2]]):
            return 20
        if (predictions[TARGETS[1]]):
            return 6
        if (predictions[TARGETS[0]]):
            return 1
        return 0
    
    def should_sell(self, samples: List[float]) -> bool:
        if not samples or len(samples) < 2:
            return False
            
        # Get the all-time high (lowest number since it's inverted)
        ath = min(samples)
        current_price = samples[-1]
        initial_price = samples[0]
        
        # Calculate percentage drop from ATH
        pct_drop = ((current_price - ath) / ath) * 100
        
        # Strategy 1: Sell if dropped 20% from ATH
        if pct_drop > 25:
            logger.info(f"Selling due to 25% drop from ATH: {pct_drop:.2f}%")
            return True

        # Strategy 2: Check for plateau after large increase
        if len(samples) >= 5:  # Need enough samples to detect plateau
            recent_samples = samples[-5:]
            increase_over_last_5 = ((recent_samples[-1] - recent_samples[0]) / recent_samples[0]) * -100
            # If range is small compared to average (less than 2%), it's a plateau
            if increase_over_last_5 < 2:
                if len(samples) >= 15:
                    increase = ((current_price - initial_price) / initial_price) * -100
                    if increase > 20: 
                        logger.info(f"Selling due to plateau after {increase:.2f}% increase")
                        return True
                        
        # Strategy 3: Sell if overall increase is 200%
        overall_increase = ((current_price - initial_price) / current_price) * -100
        if overall_increase >= 100:
            logger.info(f"Selling due to bigwin increase: {overall_increase:.2f}%")
            return True
                        
        return False

    async def _run_buy_loop(self, token: DexToken) -> pd.DataFrame:
        token_address = token.token_address
        predictions = self._get_predictions(token=token)
        if not predictions:
            print(f"Not buying {token_address}")
            return None
        minutes_expected = self.get_expected_minutes(predictions)
        if minutes_expected == 0:
            print(f"Not buying {token_address} predictions {predictions}")
            return None

        buy_quote: Quote = await self.jup_client.get_buy_shitcoin_quote(
            token_address, self.buy_amount
        )
        shitcoins_bought_quoted = buy_quote.out_amount
        logger.info(
            f"Buying {shitcoins_bought_quoted} {token_address} at {buy_quote.exchange_rate()}"
        )
        start_time = datetime.now()
        logger.info(f"Sampling sell quotes at {start_time} for {token_address}")

        next_sample_time = start_time

        sampling_data = {
            "start_time": start_time,
            "token": token_address,
            "sol_amount": self.buy_amount,
            "token_amount": shitcoins_bought_quoted,
            "real": False,
            "would": json.dumps(predictions),
        }

        samplerate_seconds = 15

        # exchange rate is in shit / sol
        exchange_rates = []
        sold = False

        while not sold:
            current_time = datetime.now()

            if current_time >= next_sample_time:
                quote = await self.jup_client.get_sell_shitcoin_quote(
                    token_address, shitcoins_bought_quoted
                )
                exchange_rate = quote.exchange_rate()
                exchange_rates.append(exchange_rate)

                next_sample_time = next_sample_time + timedelta(seconds=samplerate_seconds)
                if self.should_sell(exchange_rates):
                    logger.info(f"selling {token_address} at {exchange_rate}")
                    sampling_data["sell_time"] = datetime.now()
                    sampling_data["sell_price"] = exchange_rate
                    sold = True

            await asyncio.sleep(1)

        sampling_data["samples"] = str(exchange_rates)
        return pd.DataFrame(sampling_data, index=[0])

    def _run_async_sampling(self, token: DexToken):

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logger.info(f"Starting buy loop for {token.token_address}")
            results_df = loop.run_until_complete(self._run_buy_loop(token))
            if results_df is not None and not results_df.empty:
                with self.excel_lock:
                    self.append_to_excel(self.output_file, results_df, "buys")
                    logger.info(
                        f"Sampling completed on thread {threading.get_ident()}. Results saved to {self.output_file}"
                    )
        except Exception as e:
            logger.error(
                f"Error in sampling task thread {threading.get_ident()}: {str(e)}",
                exc_info=True,
            )
            traceback.print_exc()
        finally:
            loop.close()

    def append_to_excel(self, filename, df, sheet_name):
        # Check if file exists
        if not os.path.exists(filename):
            # If file doesn't exist, write new file
            with pd.ExcelWriter(filename, engine="openpyxl", mode="w") as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            return

        # Load existing workbook and sheet
        book = load_workbook(filename)

        if sheet_name in book.sheetnames:

            # Load existing column headers
            existing_df = pd.read_excel(filename, sheet_name=sheet_name, nrows=0)
            existing_columns = existing_df.columns.tolist()

            # Ensure new df columns match existing columns
            df = df.reindex(columns=existing_columns)

            sheet = book[sheet_name]
            last_row = sheet.max_row
            with pd.ExcelWriter(
                filename, engine="openpyxl", mode="a", if_sheet_exists="overlay"
            ) as writer:
                df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False,
                    header=False,
                    startrow=last_row,
                )
        else:
            # If the sheet does not exist, create a new one
            with pd.ExcelWriter(filename, engine="openpyxl", mode="a") as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)

    def start_trading(self, token: DexToken):
        if not token:
            return self
        self.executor.submit(self._run_async_sampling, token)
        return self
