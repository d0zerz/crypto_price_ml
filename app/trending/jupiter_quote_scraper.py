import asyncio
import concurrent.futures
import logging
import os
import signal
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import List

import pandas as pd
from openpyxl import load_workbook
from trading.jupiter_client import JupiterClient

# Get module logger
logger = logging.getLogger(__name__)

class JupiterQuoteScraper:
    """
    A class for sampling exchange rates at specified intervals over a duration.
    Stores results in an Excel file with minutes elapsed as columns and tokens as rows.
    """
    
    def __init__(self, jup_client: JupiterClient, output_directory: str, duration_minutes: int=1):
        """
        Initialize the sampler.
        
        Args:
            caller_instance: The instance that has the getJupQuotePrice method
            duration_hours: Duration to run the sampling in hours
        """
        self.jup_client = jup_client
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=60)
        self.duration_minutes = duration_minutes
        self.excel_lock = threading.Lock()
        self.shutdown_flag = threading.Event()
        self.buy_amount = 500_000_000
        self.output_directory = output_directory
        self.output_file = self.file_path = f"{output_directory}/jupiter_quotes.xlsx"
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        logger.info(f"Received signal {signum}. Starting graceful shutdown...")
        self.shutdown_flag.set()

    def get_interval(self, elapsed_minutes):
            if elapsed_minutes < 10:
                return 1  # Every 1 minute for first 10 minutes
            elif elapsed_minutes < 30:
                return 2  # Every 2 minutes from 10-30 minutes
            elif elapsed_minutes < 60:
                return 5  # Every 5 minutes from 30-60 minutes
            else:
                return 10  # Every 10 minutes after an hour    

    async def _sample_exchange_rates(self, tokens: List[str]):
        """
        Returns:
            DataFrame with minutes elapsed as columns and tokens as rows
        """
        all_rates = {}
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=self.duration_minutes)
        next_sample_time = start_time

        logger.info(f"Starting exchange rate sampling at {start_time} for tokens {tokens}, thread {threading.get_ident()} ending at {end_time}")
        
        while next_sample_time <= end_time:
            current_time = datetime.now()
            
            # If it's time to take a sample
            if current_time >= next_sample_time:
                # Calculate elapsed time in minutes for column name
                elapsed_minutes = round((current_time - start_time).total_seconds() / 60)
                column_name = f"M{elapsed_minutes:04}"
                rates = {}
                for token in tokens:
                    try:
                        quote = await self.jup_client.get_buy_shitcoin_quote(token, self.buy_amount)
                        rates[token] = quote.exchange_rate()
                    except Exception as e:
                        logger.info(f"quoteErr:{token} | {str(e)}")
                
                # Store the rates with elapsed minutes as key
                all_rates[column_name] = rates
                
                current_interval = self.get_interval(elapsed_minutes)
                next_sample_time = next_sample_time + timedelta(minutes=current_interval)
                
            if self.shutdown_flag.is_set():
                logger.info(f"Shutting down scraping thread {threading.get_ident()} at {column_name} {current_time}")
                break
            await asyncio.sleep(1)
        
        # Create DataFrame from the collected data
        # First, identify all unique tokens
        all_tokens = set()
        for rates in all_rates.values():
            all_tokens.update(rates.keys())
        
        # Initialize DataFrame with tokens as index
        df = pd.DataFrame(index=sorted(all_tokens))
        df.index.name = 'token_address'
        df['start_time'] = start_time
        
        # Fill in the data for each elapsed minute point
        sorted_columns = sorted(all_rates.keys())
        
        for minute in sorted_columns:
            rates = all_rates[minute]
            for token in all_tokens:
                df.loc[token, minute] = rates.get(token, None)
        
        return df
    
    def _run_async_sampling(self, tokens: List[str]):

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results_df = loop.run_until_complete(self._sample_exchange_rates(tokens))
            with self.excel_lock:
                self.append_to_excel(self.output_file, results_df, 'quotes')
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
                df.to_excel(writer, sheet_name=sheet_name, index=True)
            return

        # Load existing workbook and sheet
        book = load_workbook(filename)

        if sheet_name in book.sheetnames:
            sheet = book[sheet_name]
            last_row = sheet.max_row
            with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=True, header=False, startrow=last_row)
        else:
            # If the sheet does not exist, create a new one
            with pd.ExcelWriter(filename, engine='openpyxl', mode='a') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=True)

    def start_sampling(self, tokens: List[str]):
        if not tokens:
            return self
        self.executor.submit(self._run_async_sampling, tokens)
        return self
    