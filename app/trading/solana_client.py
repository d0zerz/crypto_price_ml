import time
from typing import Optional
import base58
import solana
from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction_status import TransactionConfirmationStatus, TransactionStatus
from solders.system_program import transfer, TransferParams
from solana.rpc.async_api import AsyncClient
from spl.token.async_client import AsyncToken
from spl.token.constants import ASSOCIATED_TOKEN_PROGRAM_ID, TOKEN_PROGRAM_ID
from spl.token.client import Token
from spl.token.instructions import get_associated_token_address

class SolanaClient:
    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com", keypair_b58: str = None):
        self.client = Client(rpc_url)
        self.keypair = Keypair.from_base58_string(keypair_b58)
        print(f"Loaded Wallet: pub:[{self.keypair.pubkey()}]")
    
    def create_send_transaction(self, recipient: str, amount: int) -> Transaction:
        """Creates a transaction for transferring SOL."""
        sender_pubkey = self.keypair.pubkey()
        recipient_pubkey = Pubkey.from_string(recipient)

        latest_blockhash = self.client.get_latest_blockhash(Confirmed).value.blockhash
        txn = Transaction(fee_payer=sender_pubkey, recent_blockhash=latest_blockhash)
        txn.add(
            transfer(
                TransferParams(
                    from_pubkey=sender_pubkey,
                    to_pubkey=recipient_pubkey,
                    lamports=amount  # Amount in lamports (1 SOL = 1,000,000,000 lamports)
                )
            )
        )
        return txn
    
    def get_pubkey(self) -> Pubkey:
        return self.keypair.pubkey()
    
    def get_token(self, token_mint: str) -> Token:
        return Token(self.client, token_mint, TOKEN_PROGRAM_ID, None)
    
    def get_token_balance(self, token_mint) -> int:
        token_mint_pubkey = Pubkey.from_string(token_mint)

        # Get the associated token account
        associated_token_account = get_associated_token_address(self.keypair.pubkey(), token_mint_pubkey)

        # Fetch account balance
        response = self.client.get_token_account_balance(associated_token_account)
        
        if response.value is None:
            return 0  # No balance found (account might not exist)
        
        return int(response.value.amount) 

    def sign_transaction(self, transaction: Transaction) -> Transaction:
        transaction.sign(self.keypair)
        return transaction

    def send_and_finalize(self, transaction: Transaction) -> Optional[TransactionStatus]:
        return self.wait_for_finalization(self.send_transaction(transaction))

    def send_transaction(self, transaction: Transaction) -> Signature:
        """Sends a signed transaction to the Solana blockchain."""
        try:
            response = self.client.send_transaction(transaction.serialize(), opts=TxOpts(skip_preflight=True, skip_confirmation=True, preflight_commitment="processed"))
            return response.value
        except Exception as e:
            print("failed to send transaction", e)
            return None
        
    def wait_for_finalization(self, tx_sig: Signature, max_retries=30, sleep_time=2) -> Optional[TransactionStatus]:
        status = None
        for _ in range(max_retries):
            response = self.client.get_signature_statuses([tx_sig])
            status = response.value[0]

            if status and status.confirmation_status == TransactionConfirmationStatus.Finalized:
                return status  # Transaction is finalized

            time.sleep(sleep_time)  # Wait before retrying

        return status  # Timed out

def genWallet():
    new_wallet = Keypair()
    key_b58 = base58.b58encode(bytes(new_wallet)).decode("utf-8")
    print(f"\nNew Wallet: pub:[{new_wallet.pubkey()}] b58:[{key_b58}] ")


key = "5YVMBvakSYmSjWsPfTL8HWb6VyMGfu7aYCcxCtD2cL224pj8SdzHGKSAie1SzoiRwrqfyzkiaRvNutpd3FtRUbhS"
key2 = "4ZizVbvXp7GiBmNFbDRsjKSAjYjhQTLqVrGJ3uorHzinq43CSrKv44GHQUcCN8Et3qkMWebMc6Rrf3cjs2A1cXmC"
mainkey = "65tbUL3cv9dwWej1j3FSmoHQxW8XHZxw9xCRjpppHwK9FWcL7AxzZxzmhGUpjSdFBmBebKF2LKB4pyrUwvBmxRuM"
client = SolanaClient("https://solana-mainnet.core.chainstack.com/04d6aa866fd95b892af65d4ee4aa6d2a", mainkey)

#genWallet()
def sendTx():
    transaction = client.create_send_transaction("4KN4BfKFEmAxAxjFcTL86U76S23k7uq6EpNJM9oM3t7j", 1_000_000)
    signed_transaction = client.sign_transaction(transaction)
    print("sending transaction")
    status = client.send_and_finalize(signed_transaction)
    if status:
        print(f"transaction finalized {status}")
    else:
        print(f"tx failed {transaction}")

amount = client.get_token_balance("1au1hAEZpM3G4MvkzBBr9xib1GiGzEMAqnsjuCzQSja")
token = client.get_token("9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump")

print(f"{amount} of shitcoint")
print(f"{token.get_decimals} of shitcoint")

#sender = new_wallet["public_key"]
#recipient = "RecipientPublicKeyHere"
#amount = 1000000  # 0.001 SOL (1 SOL = 1,000,000,000 lamports)

#transaction = wallet.create_transaction(sender, recipient, amount)
#signed_transaction = wallet.sign_transaction(transaction, new_wallet["private_key"])
#tx_signature = wallet.send_transaction(signed_transaction)
#print("Transaction Signature:", tx_signature)
