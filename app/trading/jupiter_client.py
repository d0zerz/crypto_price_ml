import asyncio
import base64
import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional
from trading.solana_client import SolanaClient

import aiohttp
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair

# Get module logger
logger = logging.getLogger(__name__)

SOL_BASE = "So11111111111111111111111111111111111111112"
QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
SWAP_URL = "https://quote-api.jup.ag/v6/swap"
ULTRA_ORDER_URL = "https://lite-api.jup.ag/ultra/v1/order"
ULTRA_EXECTURE_URL = "https://lite-api.jup.ag/ultra/v1/execute"
BALANCES_URL = "https://lite-api.jup.ag/ultra/v1/balances"


@dataclass
class Quote:
    in_amount: int
    out_amount: int
    in_mint: str
    out_mint: str
    other_amount_threshold: int
    price_impact_pct: float
    slippage: Optional[float] = None

    def exchange_rate(self) -> float:
        return self.in_amount / self.out_amount
    
    def get_fee_pct(self) -> float:
        return (self.out_amount - self.other_amount_threshold) / self.out_amount * 100
    
    def is_safe_quote(self) -> bool:
        fee_pct = self.get_fee_pct()
        return self.price_impact_pct < 0.05 and fee_pct < 2


class JupiterClient:
    def __init__(self, keypair: Keypair):
        self.keypair = keypair
        self.session = None 

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def get_buy_shitcoin_quote(self, output_mint: str, amount: int) -> Quote:
        return await self.get_quote(SOL_BASE, output_mint, amount)

    async def get_sell_shitcoin_quote(self, input_mint: str, amount: int) -> Quote:
        return await self.get_quote(input_mint, SOL_BASE, amount)

    async def get_token_balance(self, token_address):
        url = f"{BALANCES_URL}/{str(self.keypair.pubkey())}"
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to fetch balances: {error_text}")
                    return None

                balances = await response.json()

                # Filter out SOL
                filtered = {mint: info for mint, info in balances.items() if mint == token_address}
                if token_address in filtered :
                    return int(filtered[token_address]["amount"])
                else:
                    return 0

        except Exception as e:
            logger.exception(f"Exception fetching balances: {e}")
            return 0

    async def get_quote(self, input_mint: str, output_mint: str, amount: int, slippage_bps: int = 200) -> Quote:
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": str(slippage_bps)
        }

        try:
            response = await self.session.get(QUOTE_URL, params=params)
            if response.status != 200:
                logger.error(f"Failed to get quote: {await response.text()}")
                return None

            quote_data = await response.json()
            return Quote(
                in_amount=int(quote_data["inAmount"]),
                out_amount=int(quote_data["outAmount"]),
                in_mint=quote_data["inputMint"],
                out_mint=quote_data["outputMint"],
                slippage=float(quote_data.get("slippageBps", 0)) / 10000,
                other_amount_threshold=int(quote_data.get("otherAmountThreshold", 0)),
                price_impact_pct=float(quote_data.get("priceImpactPct", 0)),
            )
        except Exception as e:
            logger.error(f"Error getting quote: {str(e)}", exc_info=True)
            return None

    async def do_ultra_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: int
    ) -> Optional[Dict]:
        '''
            Returns a dict with:
            inAmount
            outAmount
            inputMint
            outputMint
            '''
        try:
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "taker": str(self.keypair.pubkey()),
            }

            async with self.session.get(ULTRA_ORDER_URL, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to get ultra order: {error_text}")
                    return None
                swap_response = await response.json()
                decoded_bytes = base64.b64decode(swap_response["transaction"])
                request_id = swap_response["requestId"]
                tx = VersionedTransaction.from_bytes(decoded_bytes)
                 # Sign the transaction
                message_bytes = bytes(tx.message)
                signed_tx = VersionedTransaction(tx.message, [self.keypair])

                # Serialize and base64 encode the signed transaction
                signed_tx_b64 = base64.b64encode(bytes(signed_tx)).decode("utf-8")
                

                async with self.session.post(ULTRA_EXECTURE_URL,
                    json={
                        "signedTransaction": signed_tx_b64,
                        "requestId": request_id,
                    },
                    headers={"Content-Type": "application/json"},
                ) as execute_response:
                    if execute_response.status != 200:
                        err = await execute_response.text()
                        logger.error(f"Failed to execute swap: {err}")
                        return None
                    execute_json = await response.json()
                    logger.info(f"Execute Response for {input_mint} to {output_mint} \n {json.dumps(execute_json, indent=2)}")

                    return execute_json

        except Exception as e:
            logger.error(f"Error Processing ultra order: {str(e)}", exc_info=True)
            return None


# Example usage (async context needed):
async def main():
    sol_client = SolanaClient(os.getenv("SOL_NODE"), os.getenv("MAIN_WALLET") )
    async with JupiterClient(sol_client.keypair) as trader:
        shitcoin = "3R57bfrKPx8evebAEXo62GG8FmJxPSW3Q2GRqFELpump"
        
        # Get quote for selling shitcoin
        quote = await trader.get_quote(shitcoin, SOL_BASE, 614000000)
        if quote:
            logger.debug(f"shit to sol exchange rate: {quote.exchange_rate()}")
        
        # Get quote for buying shitcoin
        quote = await trader.get_quote(SOL_BASE, shitcoin, 1227000000)
        if quote:
            logger.debug(f"sol to shit exchange rate: {quote.exchange_rate()}")

        res = await trader.do_ultra_swap("HaXLWSt2VwL8jokTsDnPM1FYDhkXrUWXdBXLyD6Ad7MG", SOL_BASE, 29377256)
        print(res)
        await asyncio.sleep(10)



if __name__ == "__main__":
    asyncio.run(main())
