import base64
import requests
from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.rpc.types import TxOpts

# Get module logger
logger = logging.getLogger(__name__)

import logging

# Constants and configurations
API_URLS = {
    "BASE_HOST": "https://api.raydium.io/v2",
    "PRIORITY_FEE": "/priority-fee",
    "SWAP_HOST": "https://api.raydium.io/v2"
}

# Setup Solana connection and wallet
connection = Client("https://api.mainnet-beta.solana.com")
owner = Keypair()  # Load your keypair appropriately
NATIVE_MINT = PublicKey("So11111111111111111111111111111111111111112")

def fetch_token_account_data():
    # Mock function: Replace with actual implementation
    return {"tokenAccounts": []}

def api_swap():
    input_mint = str(NATIVE_MINT)
    output_mint = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"  # RAY
    amount = 10000
    slippage = 0.5  # in percent
    tx_version = "V0"
    is_v0_tx = tx_version == "V0"
    
    token_accounts = fetch_token_account_data()["tokenAccounts"]
    input_token_acc = next((a for a in token_accounts if str(a["mint"]) == input_mint), None)
    output_token_acc = next((a for a in token_accounts if str(a["mint"]) == output_mint), None)

    if not input_token_acc:
        logger.info("Do not have input token account")
        return

    # Get statistical transaction fee from API
    fee_response = requests.get(f"{API_URLS['BASE_HOST']}{API_URLS['PRIORITY_FEE']}").json()
    priority_fee = str(fee_response["data"]["default"]["h"])

    # Get swap computation data
    swap_url = f"{API_URLS['SWAP_HOST']}/compute/swap-base-in?inputMint={input_mint}&outputMint={output_mint}&amount={amount}&slippageBps={slippage * 100}&txVersion={tx_version}"
    swap_response = requests.get(swap_url).json()

    # Request swap transaction
    swap_transactions = requests.post(
        f"{API_URLS['SWAP_HOST']}/transaction/swap-base-in",
        json={
            "computeUnitPriceMicroLamports": priority_fee,
            "swapResponse": swap_response,
            "txVersion": tx_version,
            "wallet": str(owner.public_key),
            "wrapSol": input_mint == str(NATIVE_MINT),
            "unwrapSol": output_mint == str(NATIVE_MINT),
            "inputAccount": input_token_acc["publicKey"] if input_token_acc else None,
            "outputAccount": output_token_acc["publicKey"] if output_token_acc else None,
        },
    ).json()

    # Process transactions
    all_tx_buf = [base64.b64decode(tx["transaction"]) for tx in swap_transactions["data"]]
    all_transactions = [Transaction.deserialize(tx_buf) for tx_buf in all_tx_buf]

    logger.info(f"Total {len(all_transactions)} transactions")
    
    for idx, tx in enumerate(all_transactions, start=1):
        logger.info(f"{idx} transaction sending...")
        tx.sign(owner)
        tx_id = connection.send_transaction(tx, owner, opts=TxOpts(skip_preflight=True))
        logger.info(f"{idx} transaction confirmed, txId: {tx_id}")

if __name__ == "__main__":
    api_swap()
