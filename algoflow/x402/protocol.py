"""
x402 Algorand Protocol Specification & Data Models.
Standard: https://github.com/x402/standards / RFC HTTP 402 for Algorand
"""

from __future__ import annotations

import secrets
import time
import urllib.parse
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

# Standard HTTP 402 Headers for Algorand
X402_HEADER_VERSION = "X-402-Version"
X402_HEADER_BLOCKCHAIN = "X-402-Blockchain"
X402_HEADER_NETWORK = "X-402-Network"
X402_HEADER_RECEIVER = "X-402-Receiver"
X402_HEADER_AMOUNT = "X-402-Amount"
X402_HEADER_ASSET_ID = "X-402-Asset-ID"
X402_HEADER_CHALLENGE = "X-402-Challenge"
X402_HEADER_EXPIRES = "X-402-Expires-At"
X402_HEADER_PAYMENT_AUTH = "X-402-Payment-Authorization"
X402_HEADER_SETTLEMENT_STATUS = "X-402-Settlement-Status"
X402_HEADER_TXID = "X-402-TxID"

PROTOCOL_VERSION = "1.0.0"
BLOCKCHAIN_ALGORAND = "algorand"


class X402PaymentChallenge(BaseModel):
    """
    Challenge payload returned inside the HTTP 402 response body and headers.
    """
    version: str = Field(default=PROTOCOL_VERSION)
    blockchain: str = Field(default=BLOCKCHAIN_ALGORAND)
    network: str = Field(default="testnet")
    receiver: str
    amount_microalgos: int
    asset_id: int = Field(default=0, description="0 for native ALGO, ASA ID for tokens")
    challenge: str = Field(default_factory=lambda: f"algo402_{secrets.token_hex(16)}")
    resource_path: str
    created_at: int = Field(default_factory=lambda: int(time.time()))
    expires_at: int = Field(default_factory=lambda: int(time.time()) + 900)  # 15 minutes
    memo_prefix: str = Field(default="x402:")

    @property
    def required_note(self) -> str:
        """The required string that must be present in the Algorand transaction note field."""
        return f"{self.memo_prefix}{self.challenge}"

    @property
    def payment_uri(self) -> str:
        """
        Algorand standard URI:
        algorand://<receiver>?amount=<microalgos>&note=<url_encoded_note>
        Supported by Pera Wallet, Defly, Daffi, AlgoSigner.
        """
        encoded_note = urllib.parse.quote(self.required_note)
        uri = f"algorand://{self.receiver}?amount={self.amount_microalgos}&note={encoded_note}"
        if self.asset_id != 0:
            uri += f"&asset={self.asset_id}"
        return uri

    def to_headers(self) -> Dict[str, str]:
        """Convert challenge into HTTP 402 response headers."""
        return {
            "WWW-Authenticate": f'X-402-Algorand realm="AlgoFlow x402 Gateway"',
            X402_HEADER_VERSION: self.version,
            X402_HEADER_BLOCKCHAIN: self.blockchain,
            X402_HEADER_NETWORK: self.network,
            X402_HEADER_RECEIVER: self.receiver,
            X402_HEADER_AMOUNT: str(self.amount_microalgos),
            X402_HEADER_ASSET_ID: str(self.asset_id),
            X402_HEADER_CHALLENGE: self.challenge,
            X402_HEADER_EXPIRES: str(self.expires_at),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Dictionary representation suitable for JSON responses."""
        return {
            "status": 402,
            "title": "Payment Required",
            "detail": f"This resource requires a microtransaction of {self.amount_microalgos} microAlgos ({self.amount_microalgos / 1_000_000} ALGO).",
            "protocol": {
                "version": self.version,
                "blockchain": self.blockchain,
                "network": self.network,
            },
            "payment": {
                "receiver": self.receiver,
                "amount_microalgos": self.amount_microalgos,
                "amount_algo": self.amount_microalgos / 1_000_000,
                "asset_id": self.asset_id,
                "challenge": self.challenge,
                "required_note": self.required_note,
                "payment_uri": self.payment_uri,
                "expires_at": self.expires_at,
            },
            "instructions": [
                f"1. Send {self.amount_microalgos} microAlgos to {self.receiver} on Algorand {self.network}.",
                f"2. Include the exact string '{self.required_note}' in the transaction Note field.",
                f"3. Resend this HTTP request including header 'X-402-Payment-Authorization: txid=<YOUR_TXID>' or 'Authorization: X-402 txid=<YOUR_TXID>'.",
            ],
        }


class X402VerificationResult(BaseModel):
    """
    Result of verifying an Algorand payment transaction.
    """
    valid: bool
    txid: Optional[str] = None
    sender: Optional[str] = None
    receiver: Optional[str] = None
    amount_microalgos: Optional[int] = None
    confirmed_round: Optional[int] = None
    challenge: Optional[str] = None
    error: Optional[str] = None


class X402PaymentReceipt(BaseModel):
    """
    Settlement receipt returned when payment is accepted.
    """
    settlement_status: str = "confirmed"
    txid: str
    sender: str
    receiver: str
    amount_microalgos: int
    amount_algo: float
    confirmed_round: int
    verified_at: int = Field(default_factory=lambda: int(time.time()))

    def to_headers(self) -> Dict[str, str]:
        return {
            X402_HEADER_SETTLEMENT_STATUS: self.settlement_status,
            X402_HEADER_TXID: self.txid,
            "X-402-Sender": self.sender,
            "X-402-Confirmed-Round": str(self.confirmed_round),
        }
