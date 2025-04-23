import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Optional

from solders.transaction import VersionedTransaction

from trading.jupiter_client import JupiterClient, Quote
from trading.solana_client import SolanaClient

logger = logging.getLogger(__name__)

SOL_BASE = "So11111111111111111111111111111111111111112"
BUY_SLIPPAGE = 200
SELL_SLIPPAGE = 500


class TokenTrader:
    """Handles buying and selling of tokens using Jupiter and Solana clients."""
    
    def __init__(
        self,
        solana_client: SolanaClient,
        buy_amount: int = 100_000_000
    ):
        self.solana_client = solana_client
        self.buy_amount = buy_amount
        self.keypair = solana_client.keypair

    async def buy_token(self, token_address: str) -> Optional[str]:
        try:
            # Get the swap transaction
            async with JupiterClient(self.keypair) as client:
                quote = await client.get_quote(input_mint=SOL_BASE, output_mint=token_address, amount=self.buy_amount)
                if not quote.is_safe_quote():
                    logger.info("Unsafe quote, bailing on buy")
                    return None

                swap_info = await client.do_ultra_swap(
                    input_mint=SOL_BASE,
                    output_mint=token_address,
                    amount=self.buy_amount
                )
                
                if not swap_info:
                    logger.error(f"Failed to buy {token_address}")
                    return None
                    
                logger.info(f"Bought {token_address} transaction: {swap_info}")
                return swap_info
            
        except Exception as e:
            logger.error(f"Error buying token {token_address}: {str(e)}", exc_info=True)
            return None

    async def continuous_sell_loop(self, token_address: str, sell_amount: int=0, check_interval: int = 2) -> Dict:
        """
        Continuously check for token balance and sell if found.
        Exits when balance reaches 0.
        
        Args:
            token_address: The address of the token to monitor
            check_interval: How often to check balance in seconds (default 5)
        """
        logger.info(f"Starting continuous sell loop for token {token_address}")
        max_retries = 10
        retries = 0
        swap_info = None
        amount_sold = 0
        async with JupiterClient(self.keypair) as client:
            while retries < max_retries:
                try:
                    # Check token balance
                    if sell_amount == 0:
                        sell_amount = await client.get_token_balance(token_address)
                    
                    if sell_amount <= 0:
                        logger.info(f"Token {token_address} balance is 0, exiting loop")
                        swap_info["outAmount"] = amount_sold
                        return swap_info
                        
                    logger.info(f"Selling {sell_amount} of {token_address}")

                    swap_info = await client.do_ultra_swap(
                        input_mint=token_address,
                        output_mint=SOL_BASE,
                        amount=sell_amount
                    )
                
                    if swap_info:
                        out_amount = int(swap_info["outAmount"])
                        if out_amount > 0:
                            logger.info(f"Sold {sell_amount} of {token_address} for {out_amount} SOL")
                            amount_sold = amount_sold + out_amount
                            sell_amount = 0 # force requery of balance to ensure it's actually sold
                except Exception as e:
                    logger.error(f"Error in sell loop for {token_address}: {str(e)}", exc_info=True)
                finally:
                    await asyncio.sleep(check_interval)
                    retries = retries + 1
        logger.info(f"Giving up on selling {token_address}")
        return None


async def main():
    # Initialize Solana client
    solana_client = SolanaClient(
        rpc_url=os.getenv("SOL_NODE"),
        keypair_b58=os.getenv("MAIN_WALLET")
    )
    
    # Initialize trader
    trader = TokenTrader(
        solana_client=solana_client,
        buy_amount=10_000_000  # 0.01 SOL
    )
    
    # Example token to trade
    token_address = "9Z9uqAKAAfBCtaAgEDTCaRXVs9a357WhWmxK2Rjbpump"  
    #7egnpemRWvPMcSXfRYM2LhoTiWfprHMNKLUTEyRS6KXM
    #Hvj6K3hebsoGkqyxGjmPmBfipRcbfxgbai1H1uB5YZQh
    try:
        # Buy token
        #logger.info(f"Attempting to buy {token_address}")
        #buy_status = await trader.buy_token(token_address)
        #if not buy_status:
        #    logger.error("Failed to buy token")
       #     return
            
        logger.info("Successfully bought token, starting sell loop")
        #await asyncio.sleep(15)
        # Start sell loop
        await trader.continuous_sell_loop(token_address)
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )  
    # Run the main function
    asyncio.run(main()) 
