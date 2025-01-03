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

def processCoins(coins: List[str], client: CoinGeckoClient):
    for coin in coins:
        try:
            io = CoinDataIo(coin)
            if not io.fileExists:
                io.write_to_file(client.get_coin_data(coin))
        except Exception as e:
            print(f"failed to write coin {coin}", e)

def main(out_file: str, cgApiKey: str):
    client = CoinGeckoClient(api_key=cgApiKey)
    tokens = client.get_trending_tokens()
    unique_tokens = sorted({entry[2] for entry in tokens})

    dataSrc = TrendingDataIo(out_file)
    last_trending = dataSrc.get_last_trending()
    formatted_time = getUtcString()

    new_entries = []
    if last_trending:
        new_entries =  [item for item in unique_tokens if item not in last_trending]
        processCoins(new_entries, client)

    if new_entries or not last_trending:
        printstr = str((formatted_time, unique_tokens, new_entries))
        dataSrc.write_to_file(printstr)
        print(f"{formatted_time}: wrote {printstr} to {out_file}")
    else:
        print(f"{formatted_time}: nothing new")

parser = argparse.ArgumentParser(
    description="A script to demonstrate clean argument parsing."
)

parser.add_argument(
    "-o", "--output",
    type=str,
    required=True,
    help="Path to the output file (no default)"
)

parser.add_argument(
    "-cgkey", "--coingecko_key",
    type=str,
    required=True,
    help="coingecko api key"
)

args = parser.parse_args()
try:
    main(args.output, args.coingecko_key)
except Exception as e:
    print(f"Error: {e}")
    print(traceback.format_exc())