import argparse
from dataclasses import fields
from ml.dex_model import DexModel
import traceback
from trending.coingecko_analysis import CoingeckoAnalysis
from trending.dex_analysis import DexAnalysis
import os

from trending.coingecko_client import CoinGeckoClient

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
    required=False,
    default="trending.log",
    help="Path to the trending directory",
)
args = parser.parse_args()

try:
    main(args.trending)
except Exception as e:
    print(f"Failed to main", e)
    traceback.print_exc()
