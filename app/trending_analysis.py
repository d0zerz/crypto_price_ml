import argparse
import logging
from dataclasses import fields
from ml.dex_model import DexModel
import traceback
from trending.coingecko_analysis import CoingeckoAnalysis
from trending.dex_analysis import DexAnalysis
import os
from utils.logging_config import configure_logging

from trending.coingecko_client import CoinGeckoClient

# Get module logger
logger = logging.getLogger(__name__)

def main(trending_dir: str):
    dex_df = DexAnalysis(trending_dir).main()
    DexModel().train_crypto_models(dex_df)

    #cg_key = os.getenv("COINGECKO_KEY")
    #client = CoinGeckoClient(api_key=cg_key)
    #CoingeckoAnalysis(client, trending_dir).main()

parser = argparse.ArgumentParser(description="Analyze trending.log")
parser.add_argument(
    "-t",
    "--trending",
    type=str,
    required=True,
    help="Path to the trending directory",
)
args = parser.parse_args()

try:
    # Configure logging
    configure_logging(log_dir=args.trending, logfile="analysis.log")
    main(args.trending)
except Exception as e:
    logger.error(f"Failed to execute main function", exc_info=True)
