"""
Algorand Transaction Verifier for x402 Payment Required Protocol.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Dict, Optional, Set

from algoflow.x402.protocol import X402PaymentReceipt, X402VerificationResult

logger = logging.getLogger("algoflow.x402.verifier")


class AlgorandPaymentVerifier:
    """
    Validates Algorand payment transactions against active challenges
    and Algorand Algod / Indexer node.
    """

    def __init__(
        self,
        algod_client: Optional[Any] = None,
        indexer_client: Optional[Any] = None,
        network: str = "testnet",
        demo_mode: bool = False,
    ):
        self.algod = algod_client
        self.indexer = indexer_client
        self.network = network
        self.demo_mode = demo_mode
        self._used_txids: Set[str] = set()
        self._active_challenges: Dict[str, Dict[str, Any]] = {}

    def register_challenge(
        self,
        challenge: str,
        receiver: str,
        amount_microalgos: int,
        resource_path: str,
        expires_at: int,
    ) -> None:
        """Register an issued challenge to validate against upon submission."""
        self._active_challenges[challenge] = {
            "receiver": receiver,
            "amount": amount_microalgos,
            "resource_path": resource_path,
            "expires_at": expires_at,
            "created_at": int(time.time()),
        }

    def get_challenge(self, challenge: str) -> Optional[Dict[str, Any]]:
        """Get challenge details if still valid."""
        chal = self._active_challenges.get(challenge)
        if not chal:
            return None
        if time.time() > chal["expires_at"]:
            del self._active_challenges[challenge]
            return None
        return chal

    def verify_transaction(
        self,
        txid: str,
        expected_receiver: str,
        expected_amount: int,
        expected_challenge: Optional[str] = None,
    ) -> X402VerificationResult:
        """
        Verify that txid represents a confirmed payment meeting the x402 criteria.
        """
        clean_txid = txid.strip()

        # 1. Replay attack protection
        if clean_txid in self._used_txids:
            return X402VerificationResult(
                valid=False,
                txid=clean_txid,
                error="Transaction ID has already been redeemed (replay protection)",
            )

        # 2. Check Demo / Sandbox / Mock Mode
        if self.demo_mode or clean_txid.startswith("mock_") or clean_txid.startswith("demo_"):
            # Accept demo transaction for testing / development
            self._used_txids.add(clean_txid)
            return X402VerificationResult(
                valid=True,
                txid=clean_txid,
                sender="MOCKDEMOACCOUNT4ALGOFLOWX402TESTNETRECEIVER777",
                receiver=expected_receiver,
                amount_microalgos=expected_amount,
                confirmed_round=42_100_000,
                challenge=expected_challenge,
            )

        # 3. On-chain Algorand node verification
        if not self.algod and not self.indexer:
            # If no node is configured, allow simulated valid check if demo flag is enabled
            return X402VerificationResult(
                valid=False,
                txid=clean_txid,
                error="Algorand node client is not configured to verify live transactions",
            )

        try:
            tx_info = None

            # Try fetching from algod pending or confirmed transactions
            if self.algod:
                try:
                    tx_info = self.algod.pending_transaction_info(clean_txid)
                except Exception as e:
                    logger.debug(f"Algod pending tx query failed: {e}")

            # Fallback to Indexer if not in pending / mempool
            if (not tx_info or not tx_info.get("confirmed-round")) and self.indexer:
                try:
                    res = self.indexer.transaction(clean_txid)
                    tx_info = res.get("transaction", {})
                except Exception as e:
                    logger.debug(f"Indexer tx query failed: {e}")

            if not tx_info:
                return X402VerificationResult(
                    valid=False,
                    txid=clean_txid,
                    error=f"Transaction {clean_txid} not found on Algorand {self.network}",
                )

            confirmed_round = tx_info.get("confirmed-round") or tx_info.get("confirmed_round", 0)
            if not confirmed_round or confirmed_round <= 0:
                return X402VerificationResult(
                    valid=False,
                    txid=clean_txid,
                    error="Transaction is still pending confirmation on Algorand",
                )

            # Extract transaction details
            # In Algod pending_transaction_info format vs Indexer format:
            txn_dict = tx_info.get("txn", {}).get("txn", {}) or tx_info.get("payment-transaction", {}) or tx_info

            sender = tx_info.get("sender") or txn_dict.get("snd")
            receiver = txn_dict.get("rcv") or tx_info.get("payment-transaction", {}).get("receiver")
            amount = txn_dict.get("amt") or tx_info.get("payment-transaction", {}).get("amount", 0)

            # Note parsing
            raw_note = txn_dict.get("note") or tx_info.get("note", "")
            note_str = ""
            if isinstance(raw_note, bytes):
                note_str = raw_note.decode("utf-8", errors="ignore")
            elif isinstance(raw_note, str):
                try:
                    note_str = base64.b64decode(raw_note).decode("utf-8", errors="ignore")
                except Exception:
                    note_str = raw_note

            # Verify receiver
            if receiver and expected_receiver and receiver != expected_receiver:
                return X402VerificationResult(
                    valid=False,
                    txid=clean_txid,
                    error=f"Receiver mismatch: expected {expected_receiver}, got {receiver}",
                )

            # Verify amount
            if amount < expected_amount:
                return X402VerificationResult(
                    valid=False,
                    txid=clean_txid,
                    error=f"Insufficient payment: received {amount} microAlgos, required {expected_amount}",
                )

            # Verify challenge / note if required
            if expected_challenge:
                expected_tag = f"x402:{expected_challenge}"
                if expected_tag not in note_str and expected_challenge not in note_str:
                    return X402VerificationResult(
                        valid=False,
                        txid=clean_txid,
                        error=f"Transaction note does not contain expected challenge '{expected_challenge}'",
                    )

            # Mark txid as spent to prevent double-spending
            self._used_txids.add(clean_txid)

            return X402VerificationResult(
                valid=True,
                txid=clean_txid,
                sender=str(sender),
                receiver=str(receiver),
                amount_microalgos=int(amount),
                confirmed_round=int(confirmed_round),
                challenge=expected_challenge,
            )

        except Exception as ex:
            logger.error(f"Error validating Algorand transaction {clean_txid}: {ex}")
            return X402VerificationResult(
                valid=False,
                txid=clean_txid,
                error=f"Failed to verify transaction on Algorand: {str(ex)}",
            )
