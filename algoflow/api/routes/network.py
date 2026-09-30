"""
Network status and wallet management routes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from algoflow.sdk.wallet import AlgorandWallet

router = APIRouter(prefix="/api/network", tags=["Network & Wallet"])


class SwitchNetworkRequest(BaseModel):
    network: str = Field(..., description="'mainnet' or 'testnet'")


@router.get("")
async def get_network_status(request: Request) -> Dict[str, Any]:
    """
    Get live Algorand node status, current round height, and explorer endpoints.
    """
    client = request.app.state.algorand_client
    info = client.get_network_info()
    node_status = client.get_status()

    return {
        "status": "online" if node_status.get("connected") else "offline",
        "network": client.network,
        "round": node_status.get("last_round"),
        "time_since_last_round_ms": node_status.get("time_since_last_round"),
        "node_info": info,
        "is_mainnet": client.network == "mainnet",
    }


@router.post("/switch")
async def switch_network(payload: SwitchNetworkRequest, request: Request) -> Dict[str, Any]:
    """
    Switch active blockchain network between MainNet and TestNet.
    """
    target = payload.network.lower()
    if target not in ("mainnet", "testnet", "localnet"):
        raise HTTPException(status_code=400, detail="Invalid network. Supported: mainnet, testnet, localnet")

    from algoflow.sdk.client import AlgorandNetworkClient
    new_client = AlgorandNetworkClient(network=target)
    request.app.state.algorand_client = new_client
    request.app.state.verifier.network = target
    request.app.state.verifier.algod = new_client.algod_client
    request.app.state.verifier.indexer = new_client.indexer_client

    return {
        "message": f"Switched active network to {target.upper()}",
        "network": target,
        "status": new_client.get_status(),
    }


@router.get("/wallet/generate")
async def generate_wallet() -> Dict[str, Any]:
    """
    Generate a brand new Algorand 25-word mnemonic and public address.
    """
    priv_key, address, words = AlgorandWallet.generate()
    return {
        "address": address,
        "mnemonic": words,
        "warning": "Store this mnemonic securely! Never share mainnet keys with unauthorized parties.",
    }


@router.get("/wallet/balance/{address}")
async def get_balance(address: str, request: Request) -> Dict[str, Any]:
    """
    Query real-time on-chain balance on active Algorand network.
    """
    if not AlgorandWallet.is_valid_address(address):
        raise HTTPException(status_code=400, detail="Invalid Algorand address format")

    client = request.app.state.algorand_client
    return client.get_account_balance(address)
