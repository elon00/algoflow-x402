"""
AFLOW Tokenomics and ASA Management Routes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from algoflow.sdk.token import QmoosaAlgoTokenManager
from algoflow.sdk.wallet import AlgorandWallet

router = APIRouter(prefix="/api/token", tags=["Qmoosa Algo Tokenomics & ASA"])

_token_manager: Optional[QmoosaAlgoTokenManager] = None


def get_token_manager(request: Request) -> QmoosaAlgoTokenManager:
    global _token_manager
    if _token_manager is None:
        client = getattr(request.app.state, "algorand_client", None)
        _token_manager = QmoosaAlgoTokenManager(client=client)
    return _token_manager


class MintRewardRequest(BaseModel):
    recipient_address: str = Field(..., min_length=58, max_length=58)
    amount_qalgo: float = Field(..., gt=0)
    bounty_id: str


@router.get("/metrics")
async def get_token_metrics(request: Request) -> Dict[str, Any]:
    """
    Get live AFLOW token metrics, unlimited elastic supply ceiling, and burn metrics.
    """
    manager = get_token_manager(request)
    return manager.get_token_metrics()


@router.get("/opt-in/{address}")
async def get_opt_in_info(address: str, request: Request) -> Dict[str, Any]:
    """
    Get opt-in instructions and Algorand URI for Pera / Defly / Daffi wallets.
    """
    if not AlgorandWallet.is_valid_address(address):
        raise HTTPException(status_code=400, detail="Invalid Algorand address format")

    manager = get_token_manager(request)
    metrics = manager.get_token_metrics()

    return {
        "address": address,
        "asset_id": metrics["asset_id"],
        "unit_name": metrics["unit_name"],
        "asset_name": metrics["asset_name"],
        "opt_in_uri": f"algorand://{address}?amount=0&asset={metrics['asset_id']}",
        "instructions": [
            f"1. Open your Algorand wallet (Pera Wallet, Defly, or AlgoSigner).",
            f"2. Opt into Asset ID #{metrics['asset_id']} ({metrics['unit_name']}).",
            f"3. Minimum account balance requires 0.1 ALGO buffer per opted ASA.",
        ],
    }


@router.post("/mint-reward")
async def mint_reward(payload: MintRewardRequest, request: Request) -> Dict[str, Any]:
    """
    Mint / disburse QALGO work reward tokens to a technician upon verified resolution.
    """
    if not AlgorandWallet.is_valid_address(payload.recipient_address):
        raise HTTPException(status_code=400, detail="Invalid Algorand recipient address")

    manager = get_token_manager(request)
    result = manager.mint_work_reward(
        recipient=payload.recipient_address,
        amount_whole=payload.amount_qalgo,
    )
    result["bounty_id"] = payload.bounty_id
    return result


class AllowanceRequest(BaseModel):
    recipient_address: str = Field(..., min_length=58, max_length=58)
    role: str = Field(default="SERVICE_PROVIDER", description="'SERVICE_PROVIDER', 'USER', or 'TRANSACTION_SUBSIDY'")


@router.post("/faucet")
async def claim_participant_allowance(payload: AllowanceRequest, request: Request) -> Dict[str, Any]:
    """
    [PARTICIPANT FAUCET]
    Disburses starter QALGO tokens to users and service providers for transactions and fees.
    """
    if not AlgorandWallet.is_valid_address(payload.recipient_address):
        raise HTTPException(status_code=400, detail="Invalid Algorand recipient address")

    manager = get_token_manager(request)
    return manager.disburse_participant_allowance(
        recipient_address=payload.recipient_address,
        role=payload.role,
    )


class ExchangeServiceRequest(BaseModel):
    user_address: str = Field(..., min_length=58, max_length=58)
    service_key: str = Field(..., description="'IOT_DIAGNOSTICS', 'AI_TRIAGE', 'AUDIT_TRAIL', 'PRIORITY_SLA'")


@router.get("/services")
async def list_services(request: Request) -> List[Dict[str, Any]]:
    """
    List all project services that can be unlocked by exchanging QALGO tokens.
    """
    manager = get_token_manager(request)
    return manager.get_service_catalog()


@router.post("/exchange")
async def exchange_token_for_service(payload: ExchangeServiceRequest, request: Request) -> Dict[str, Any]:
    """
    [TOKEN USE-CASE EXCHANGE]
    Exchanges / redeems QALGO tokens for operational services (IoT diagnostics, AI triage, audit trails).
    """
    if not AlgorandWallet.is_valid_address(payload.user_address):
        raise HTTPException(status_code=400, detail="Invalid Algorand user address")

    manager = get_token_manager(request)
    try:
        return manager.redeem_service(
            service_key=payload.service_key,
            user_address=payload.user_address,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


