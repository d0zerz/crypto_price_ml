import asyncio
import concurrent.futures
import logging
import os
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import List

import pandas as pd
from ml.dex_model import MARKET_CAP_MIN, DexModel
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
    def __init__(self, jup_client: JupiterClient, output_directory: str, buy_amount: int = 100_000_000):
        self.jup_client = jup_client
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=60)
        self.excel_lock = threading.Lock()
        self.buy_amount = buy_amount
        self.output_directory = output_directory
        self.output_file = self.file_path = f"{output_directory}/jupiter_trades.xlsx"
        self.dex_model = DexModel()

    def _get_prediction(self, token: DexToken) -> bool:
        if token.market_cap < 1000000: # MARKET_CAP_MIN
            logger.info(f"Market cap too low for {token}")
            return False
        if token.liquidity_usd <=0 or token.volume_h24 <=0:
            logger.info(f"Invalid data for {token}")
            return False

        buysell_m5_ratio = token.buys_m5 / 1 if token.sells_m5 == 0 else token.sells_m5
        buysell_h1_ratio = token.buys_h1 / 1 if token.sells_h1 == 0 else token.sells_h1
        market_cap_liquidity_ratio = token.market_cap / token.liquidity_usd
        market_cap_volume_ratio = token.market_cap / token.volume_h24
        price_change_h24 = token.price_change_h24
        data = {
            'buysell_m5_ratio': buysell_m5_ratio, 
            'buysell_h1_ratio': buysell_h1_ratio,
            'market_cap_liquidity_ratio': market_cap_liquidity_ratio, 
            'market_cap_volume_ratio': market_cap_volume_ratio, 
            'price_change_h24': price_change_h24
        }
        return self.dex_model.predict_target(data)


    async def _run_buy_loop(self, token: DexToken):
        token_address = token.token_address
        prediction = self._get_prediction(token=token)
        #if not prediction:
        #    print(f"Not buying {token_address}")
        #    return None

        buy_quote: Quote = await self.jup_client.get_buy_shitcoin_quote(token_address, self.buy_amount)
        shitcoins_bought_quoted = buy_quote.out_amount
        logger.info(f"Buying {shitcoins_bought_quoted} {token_address} at {buy_quote.exchange_rate()}")
        start_time = datetime.now()
        logger.info(f"Sampling sell quotes at {start_time} for {token_address}")
        
        next_sample_time = start_time

        sampling_data = {
            "start_time" : start_time,
            "token" : token_address,
            "sol_amount" : self.buy_amount,
            "token_amount" : shitcoins_bought_quoted,
            "real" : False,
            "would" : prediction
        }

        samples = {}

        sample_counter = 0
        samplerate_seconds = 30
        # exchange rate is in shit / sol
        last_exchange_rate = - 1
        sold = False
        while not sold:
            current_time = datetime.now()
            
            # If it's time to take a sample
            if current_time >= next_sample_time:
                # Calculate elapsed time in minutes for column name
                column_name = f"S{sample_counter:03}"
                quote = await self.jup_client.get_sell_shitcoin_quote(token_address, shitcoins_bought_quoted)
                exchange_rate = quote.exchange_rate()

                samples[column_name] = exchange_rate
                next_sample_time = next_sample_time + timedelta(seconds=samplerate_seconds)
                if (last_exchange_rate > 0 and exchange_rate > last_exchange_rate):
                    logger.info(f"selling {token_address} at {exchange_rate}")
                    sampling_data["sell_time"] = datetime.now()
                    sold = True

                last_exchange_rate = exchange_rate
                sample_counter = sample_counter + 1
                
            await asyncio.sleep(1)
        
        while sample_counter < 99:
            samples[f"S{sample_counter:03}"] = ""
            sample_counter = sample_counter + 1
        sampling_data.update(samples)
        return pd.DataFrame(sampling_data, index=[0])
    
    def _run_async_sampling(self, token: DexToken):

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logger.info(f"Started buy loop for {token.token_address}")
            results_df = loop.run_until_complete(self._run_buy_loop(token))
            if not results_df.empty:
                with self.excel_lock:
                    self.append_to_excel(self.output_file, results_df, 'buys')
                    logger.info(f"Sampling completed on thread {threading.get_ident()}. Results saved to {self.output_file}")
        except Exception as e:
            logger.error(f"Error in sampling task thread {threading.get_ident()}: {str(e)}", exc_info=True)
            traceback.print_exc()
        finally:
            loop.close()

    def append_to_excel(self, filename, df, sheet_name):
        # Check if file exists
        if not os.path.exists(filename):
            # If file doesn't exist, write new file
            with pd.ExcelWriter(filename, engine='openpyxl', mode='w') as writer:
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
            with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False, header=False, startrow=last_row)
        else:
            # If the sheet does not exist, create a new one
            with pd.ExcelWriter(filename, engine='openpyxl', mode='a') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)

    def start_trading(self, token: DexToken):
        if not token:
            return self
        self.executor.submit(self._run_async_sampling, token)
        return self
    