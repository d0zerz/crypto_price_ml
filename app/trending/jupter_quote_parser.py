import os
from typing import Any, Dict, Optional

from pandas import pd

# Get module logger
logger = logging.getLogger(__name__)

import logging

FILENAME = "jupiter_quotes.xlsx"

class JupiterQuoteParser:
    def __init__(self, file_path: str):
        self._df = pd.read_excel(os.path.join(file_path, FILENAME))
        self._df.columns = [col.strip() for col in self._df.columns]
        self._df['token_address'] = self._df['token_address'].astype(str)
        self._df['start_time'] = pd.to_datetime(self._df['start_time'])
        self._df.set_index('token_address', inplace=True)
    
    def get_row_by_token_address(self, token_address: str):
        token_address = str(token_address)
        try:
            return self._df.loc[token_address].to_dict()
        except KeyError:
            return None