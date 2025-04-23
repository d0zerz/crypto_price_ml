import asyncio
import concurrent.futures
import json
import logging
import os
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
from ml.dex_model import MARKET_CAP_MIN, TARGETS, DexModel
from openpyxl import load_workbook
from trading.jupiter_client import JupiterClient, Quote
from trading.solana_client import SolanaClient
from trading.token_trader import TokenTrader
from trending.dex_token import DexToken
from trading.strategies.base_strategy import BaseSellStrategy
from trading.strategies.quick_drop_strategy import QuickDropSellStrategy

# Get module logger
logger = logging.getLogger(__name__)

SOL_BASE = "So11111111111111111111111111111111111111112"
BUY_SLIPPAGE = 200
SELL_SLIPPAGE = 500


class DexTrader:
    """
    A class for sampling exchange rates at specified intervals over a duration.
    Stores results in an Excel file with minutes elapsed as columns and tokens as rows.
    """

    def __init__(
        self,
        output_directory: str,
        buy_amount: int = 10_000_000,
        on_chain: bool = False,
        sell_strategy: BaseSellStrategy = None
    ):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=60)
        self.excel_lock = threading.Lock()
        self.buy_amount = buy_amount
        self.output_directory = output_directory
        self.output_file = self.file_path = os.path.join(output_directory,"jupiter_trades.xlsx")
        self.on_chain = on_chain
        self.dex_model = DexModel()
        self.sell_strategy = sell_strategy or QuickDropSellStrategy()
        self.solana_client = SolanaClient(
            rpc_url=os.getenv("SOL_NODE"),
            keypair_b58=os.getenv("MAIN_WALLET")
        )
        self.token_trader = TokenTrader(
            solana_client=self.solana_client,
            buy_amount=buy_amount
        )

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
        if not predictions:
            return 0
        tolerance = 0
        if (predictions[TARGETS[3]] is True):
            return 60
        if (predictions[TARGETS[2]]):
            return 20
        if (predictions[TARGETS[1]]):
            return 6
        if (predictions[TARGETS[0]]):
            return 1
        return 0
    
    def should_sell(self, samples: List[float]) -> bool:
        return self.sell_strategy.should_sell(samples)

    async def _run_buy_loop(self, token: DexToken, buy_everything: bool = False) -> pd.DataFrame:
        token_address = token.token_address
        predictions = self._get_predictions(token=token)
        if not predictions and not buy_everything:
            print(f"Not buying {token_address}")
            return None
        minutes_expected = self.get_expected_minutes(predictions)
        if minutes_expected == 0 and not buy_everything:
            print(f"Not buying {token_address} predictions {predictions}")
            return None

        # Buy the token
        swap_info = await self.token_trader.buy_token(token_address)
        if not swap_info:
            logger.info(f"No swap info returned from buy_token call for {token_address}, bailing")
            return None

        token_balance = int(swap_info["outAmount"])

        start_time = datetime.now()
        logger.info(f"Sampling sell quotes at {start_time} for {token_balance} of {token_address}")

        next_sample_time = start_time

        sampling_data = {
            "start_time": start_time,
            "token": token_address,
            "sol_amount": self.buy_amount,
            "token_amount": token_balance,
            "real": False,
            "would": json.dumps(predictions),
            "buys_m5": token.buys_m5,
            "buys_h1": token.buys_h1,
            "sells_m5": token.sells_m5,
            "sells_h1": token.sells_h1,
            "volume_h24": token.volume_h24,
            "price_change_h24": token.price_change_h24,
            "liquidity_usd": token.liquidity_usd,
            "market_cap": token.market_cap,
        }

        samplerate_seconds = 15

        # exchange rate is in shit / sol
        exchange_rates = []
        sold = False

        async with JupiterClient(self.solana_client.keypair) as jup_client:
            while not sold:
                current_time = datetime.now()

                if current_time >= next_sample_time:
                    quote = await jup_client.get_sell_shitcoin_quote(
                        token_address, token_balance
                    )
                    exchange_rate = quote.exchange_rate()
                    exchange_rates.append(exchange_rate)

                    next_sample_time = next_sample_time + timedelta(seconds=samplerate_seconds)
                    if self.should_sell(exchange_rates):
                        logger.info(f"selling {token_address} at {exchange_rate}")
                        sampling_data["sell_time"] = datetime.now()
                        sampling_data["sell_price"] = exchange_rate
                        sell_info = await self.token_trader.continuous_sell_loop(token_address=token_address, sell_amount=token_balance)
                        if sell_info:
                            sampling_data["sold_for_sol_amount"] = sell_info["outAmount"]
                        else:
                            sampling_data["sold_for_sol_amount"] = 0
                        sold = True

                await asyncio.sleep(1)

            sampling_data["samples"] = str(exchange_rates)
            return pd.DataFrame(sampling_data, index=[0])

    def _run_async_sampling(self, token: DexToken):

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logger.info(f"Starting buy loop for {token.token_address}")
            results_df = loop.run_until_complete(self._run_buy_loop(token, buy_everything=False))
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

def main():
    dex_trader = DexTrader(output_directory="", buy_amount=int(1_000_000_000 / 100))
    raw_token= """
{
    "timestamp": "2025-04-21T17:17:19.607509+00:00",
    "chain_id": "solana",
    "token_address": "RABiTeVtD5jRHHHT61hJxtKmR5taXCRU2NNMvNUuAmm",
    "token_name": "Rabbit",
    "token_symbol": "RABBIT",
    "dex_id": "raydium",
    "price_usd": 0.006774,
    "price_native": 5.044e-05,
    "buys_m5": 16,
    "buys_h1": 429,
    "buys_h6": 832,
    "buys_h24": 832,
    "sells_m5": 0,
    "sells_h1": 3,
    "sells_h6": 8,
    "sells_h24": 8,
    "volume_h24": 14467.76,
    "price_change_h24": 635,
    "liquidity_usd": 44375.25,
    "market_cap": 6774392
}
        """
    token = DexToken.from_json(json.loads(raw_token))
    dex_trader.start_trading(token)
    time.sleep(1000)


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )  
    # Run the main function
    main()