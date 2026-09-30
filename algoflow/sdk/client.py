"""
Algorand Network Client for MainNet, TestNet, and LocalNet.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, Optional, Tuple

from algosdk import transaction
from algosdk.v2client import algod, indexer

logger = logging.getLogger("algoflow.sdk.client")

# Public Community Endpoints (AlgoNode provides 100% free high-availability endpoints)
NETWORKS = {
    "mainnet": {
        "algod_url": "https://mainnet-api.algonode.cloud",
        "algod_token": "",
        "indexer_url": "https://mainnet-idx.algonode.cloud",
        "indexer_token": "",
        "genesis_id": "mainnet-v1.0",
        "genesis_hash": "wGHE2Pwdvd7S12BL5Fa+zJVmx3vObtcMzDx0m0KWR30=",
        "explorer_url": "https://explorer.perawallet.app",
        "alt_explorer": "https://allo.info",
    },
    "testnet": {
        "algod_url": "https://testnet-api.algonode.cloud",
        "algod_token": "",
        "indexer_url": "https://testnet-idx.algonode.cloud",
        "indexer_token": "",
        "genesis_id": "testnet-v1.0",
        "genesis_hash": "SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=",
        "explorer_url": "https://testnet.explorer.perawallet.app",
        "alt_explorer": "https://lora.algokit.io/testnet",
        "faucet_url": "https://bank.testnet.algorand.network",
    },
    "localnet": {
        "algod_url": "http://localhost:4001",
        "algod_token": "a" * 64,
        "indexer_url": "http://localhost:8980",
        "indexer_token": "",
        "genesis_id": "devnet-v1",
        "genesis_hash": "",
        "explorer_url": "http://localhost:3000",
    },
}


class AlgorandNetworkClient:
    """
    Manages connection to Algorand nodes (Algod & Indexer),
    transaction submission, and round synchronization.
    """

    def __init__(
        self,
        network: Optional[str] = None,
        algod_url: Optional[str] = None,
        algod_token: Optional[str] = None,
        indexer_url: Optional[str] = None,
        indexer_token: Optional[str] = None,
    ):
        # Default network is configurable via ALGORAND_NETWORK env var; defaults to mainnet as requested
        self.network = (network or os.getenv("ALGORAND_NETWORK", "mainnet")).lower()
        cfg = NETWORKS.get(self.network, NETWORKS["mainnet"])

        self.algod_url = algod_url or os.getenv("ALGOD_URL") or cfg["algod_url"]
        self.algod_token = algod_token or os.getenv("ALGOD_TOKEN", cfg.get("algod_token", ""))
        self.indexer_url = indexer_url or os.getenv("INDEXER_URL") or cfg.get("indexer_url", "")
        self.indexer_token = indexer_token or os.getenv("INDEXER_TOKEN", cfg.get("indexer_token", ""))

        self.algod_client: Optional[algod.AlgodClient] = None
        self.indexer_client: Optional[indexer.IndexerClient] = None

        self._init_clients()

    def _init_clients(self) -> None:
        try:
            self.algod_client = algod.AlgodClient(self.algod_token, self.algod_url)
        except Exception as e:
            logger.warning(f"Could not initialize Algod client ({self.algod_url}): {e}")

        if self.indexer_url:
            try:
                self.indexer_client = indexer.IndexerClient(self.indexer_token, self.indexer_url)
            except Exception as e:
                logger.warning(f"Could not initialize Indexer client ({self.indexer_url}): {e}")

    def get_network_info(self) -> Dict[str, Any]:
        """Returns network configuration, explorer URLs, and node endpoints."""
        cfg = NETWORKS.get(self.network, NETWORKS["mainnet"])
        return {
            "network": self.network,
            "algod_url": self.algod_url,
            "indexer_url": self.indexer_url,
            "genesis_id": cfg.get("genesis_id", ""),
            "genesis_hash": cfg.get("genesis_hash", ""),
            "explorer_url": cfg.get("explorer_url", ""),
            "alt_explorer": cfg.get("alt_explorer", ""),
            "faucet_url": cfg.get("faucet_url", None),
        }

    def get_status(self) -> Dict[str, Any]:
        """Queries node health, current round, and consensus version."""
        if not self.algod_client:
            return {"connected": False, "error": "Algod not initialized"}

        try:
            status = self.algod_client.status()
            return {
                "connected": True,
                "network": self.network,
                "last_round": status.get("last-round"),
                "time_since_last_round": status.get("time-since-last-round"),
                "catchup_time": status.get("catchup-time"),
                "has_sync_issues": status.get("has-sync-issues", False),
            }
        except Exception as e:
            return {
                "connected": False,
                "network": self.network,
                "error": str(e),
            }

    def get_account_balance(self, address: str) -> Dict[str, Any]:
        """Retrieves account balance in microAlgos and ALGO."""
        if not self.algod_client:
            return {"address": address, "amount_microalgos": 0, "amount_algo": 0.0}

        try:
            info = self.algod_client.account_info(address)
            microalgos = info.get("amount", 0)
            min_balance = info.get("min-balance", 100_000)
            return {
                "address": address,
                "amount_microalgos": microalgos,
                "amount_algo": round(microalgos / 1_000_000, 6),
                "min_balance_microalgos": min_balance,
                "round": info.get("round", 0),
                "created_apps_count": len(info.get("created-apps", [])),
            }
        except Exception as e:
            logger.warning(f"Failed to fetch account info for {address}: {e}")
            return {
                "address": address,
                "amount_microalgos": 0,
                "amount_algo": 0.0,
                "error": str(e),
            }

    def compile_teal(self, source_code: str) -> Tuple[bytes, str]:
        """
        Compiles TEAL source code using Algod node.
        Returns (bytecode_bytes, hash_base32)
        """
        if not self.algod_client:
            raise RuntimeError("Algod client is required to compile TEAL")

        resp = self.algod_client.compile(source_code)
        raw_result = resp.get("result", "")
        bytecode = base64.b64decode(raw_result)
        contract_hash = resp.get("hash", "")
        return bytecode, contract_hash

    def get_suggested_params(self) -> transaction.SuggestedParams:
        """Fetches dynamic transaction fee and round parameters."""
        if not self.algod_client:
            raise RuntimeError("Algod client not available for suggested params")
        return self.algod_client.suggested_params()

    def send_transaction(self, signed_tx: Any) -> str:
        """Broadcasts signed transaction to Algorand network."""
        if not self.algod_client:
            raise RuntimeError("Algod client not available to send transaction")
        return self.algod_client.send_transaction(signed_tx)

    def wait_for_confirmation(self, txid: str, max_rounds: int = 5) -> Dict[str, Any]:
        """Blocks until the transaction is confirmed or timeout."""
        if not self.algod_client:
            raise RuntimeError("Algod client not available")
        return transaction.wait_for_confirmation(self.algod_client, txid, max_rounds)
