import asyncio
import base64
import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional

import base58
from jupiter_python_sdk.jupiter import Jupiter, Jupiter_DCA
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts
from solders import message
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

# Get module logger
logger = logging.getLogger(__name__)

SOL_BASE = "So11111111111111111111111111111111111111112"

@dataclass
class Quote:
    in_amount: int
    out_amount: int
    in_mint: str
    out_mint: str
    slippage: Optional[float] = None  # Assuming slippage is optional
    estimated_fee: Optional[int] = None  # Assuming estimated fee is optional

    def exchange_rate(self) -> float:
        return self.in_amount / self.out_amount
    
class JupiterClient:
    def __init__(self, private_key_str: str, rpc_url: str):
        self.private_key = Keypair.from_base58_string(private_key_str)
        self.async_client = AsyncClient(rpc_url)
        self.jupiter = Jupiter(
            async_client=self.async_client,
            keypair=self.private_key,
            quote_api_url="https://api.jup.ag/swap/v1/quote?",
            swap_api_url="https://api.jup.ag/swap/v1/swap",
            open_order_api_url="https://jup.ag/api/limit/v1/createOrder",
            cancel_orders_api_url="https://jup.ag/api/limit/v1/cancelOrders",
            query_open_orders_api_url="https://jup.ag/api/limit/v1/openOrders?wallet=",
            query_order_history_api_url="https://jup.ag/api/limit/v1/orderHistory",
            query_trade_history_api_url="https://jup.ag/api/limit/v1/tradeHistory"
        )

    async def get_buy_shitcoin_quote(self, output_mint: str, amount: int) -> Quote:
        return await self.get_quote(SOL_BASE, output_mint, amount)

    async def get_sell_shitcoin_quote(self, output_mint: str, amount: int) -> Quote:
        return await self.get_quote(output_mint, SOL_BASE, amount)

    async def get_quote(self, input_mint: str, output_mint: str, amount: int) -> Quote:
        quote_data = await self.jupiter.quote(input_mint=input_mint, output_mint=output_mint, amount=amount)
        
        # Extract relevant fields from the response
        in_amount = int(quote_data.get('inAmount', 0))  # Ensure conversion to integer
        out_amount = int(quote_data.get('outAmount', 0))
        in_mint = quote_data.get('inputMint', '')
        out_mint = quote_data.get('outputMint', '')
        
        # Optional fields (if present)
        slippage = float(quote_data.get('slippageBps', 0.0))
        
        # Return the populated Quote dataclass
        return Quote(
            in_amount=in_amount,
            out_amount=out_amount,
            in_mint=in_mint,
            out_mint=out_mint,
            slippage=slippage
        )

    async def get_swap(self, input_mint: str, output_mint: str, amount: int, slippage_bps: int = 1) -> VersionedTransaction:
        transaction_data = await self.jupiter.swap(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            slippage_bps=slippage_bps
        )

        decoded_bytes = base64.b64decode(transaction_data)

        # Step 2: Deserialize the Solana Transaction
        transaction = VersionedTransaction.from_bytes(decoded_bytes)
        
        return transaction

    async def open_limit_order(self, input_mint: str, output_mint: str, in_amount: int, out_amount: int):
        transaction_data = await self.jupiter.open_order(
            input_mint=input_mint,
            output_mint=output_mint,
            in_amount=in_amount,
            out_amount=out_amount
        )
        
        return await self._sign_and_send(transaction_data['transaction_data'], extra_signature=transaction_data['signature2'])

    
    async def _sign_and_send(self, transaction_data: str, extra_signature=None):
        raw_transaction = VersionedTransaction.from_bytes(base64.b64decode(transaction_data))
        signature = self.private_key.sign_message(message.to_bytes_versioned(raw_transaction.message))
        signatures = [signature]
        if extra_signature:
            signatures.append(extra_signature)
        
        signed_txn = VersionedTransaction.populate(raw_transaction.message, signatures)
        opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)
        result = await self.async_client.send_raw_transaction(txn=bytes(signed_txn), opts=opts)
        transaction_id = json.loads(result.to_json())['result']
        logger.info(f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}")
        return transaction_id

# Example usage (async context needed):
async def main():
    trader = JupiterClient(os.getenv("MAIN_WALLET"), os.getenv("SOL_NODE"))
    shitcoin = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
    amount = 1232661704592
    quote = await trader.get_quote(shitcoin, SOL_BASE, 614000000)
    logger.debug(f"shit to sol exchange rate: {quote.exchange_rate()}")

    quote = await trader.get_quote(SOL_BASE, shitcoin, 1227000000)
    logger.debug(f"sol to shit exchange rate: {quote.exchange_rate()}")

   # tx = await trader.get_swap(shitcoin,SOL_BASE, amount)
    #logger.debug(f"Transaction: {tx}")
#asyncio.run(main())