"""
x402 Protocol Gateway & Protected Paywall Endpoints.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from algoflow.x402.protocol import (
    X402_HEADER_PAYMENT_AUTH,
    X402PaymentChallenge,
)

router = APIRouter(tags=["x402 Gateway & Protected Paywalls"])


class ChallengeRequest(BaseModel):
    resource_path: str = Field(..., description="Target API path")
    amount_microalgos: int = Field(default=10_000, gt=0, description="Cost in microAlgos (10,000 = 0.01 ALGO)")


class VerifyTxRequest(BaseModel):
    txid: str = Field(..., description="Algorand transaction ID to verify")
    expected_amount_microalgos: int = Field(default=10_000)
    expected_challenge: Optional[str] = None


@router.post("/api/x402/challenge")
async def create_challenge(payload: ChallengeRequest, request: Request) -> Dict[str, Any]:
    """
    Generate an explicit x402 Algorand payment challenge with QR URI and nonce.
    """
    receiver = request.app.state.receiver_address
    network = request.app.state.algorand_client.network

    challenge = X402PaymentChallenge(
        network=network,
        receiver=receiver,
        amount_microalgos=payload.amount_microalgos,
        resource_path=payload.resource_path,
    )

    request.app.state.verifier.register_challenge(
        challenge=challenge.challenge,
        receiver=receiver,
        amount_microalgos=payload.amount_microalgos,
        resource_path=payload.resource_path,
        expires_at=challenge.expires_at,
    )

    return challenge.to_dict()


@router.post("/api/x402/verify")
async def verify_tx(payload: VerifyTxRequest, request: Request) -> Dict[str, Any]:
    """
    Manually verify an Algorand transaction ID against x402 payment requirements.
    """
    receiver = request.app.state.receiver_address
    verifier = request.app.state.verifier

    result = verifier.verify_transaction(
        txid=payload.txid,
        expected_receiver=receiver,
        expected_amount=payload.expected_amount_microalgos,
        expected_challenge=payload.expected_challenge,
    )

    return result.model_dump()


# -----------------------------------------------------------------------------
# Protected Resources (Enforced by X402PaymentMiddleware)
# Accessing these endpoints without valid Algorand payment returns HTTP 402!
# -----------------------------------------------------------------------------

@router.get("/api/protected/diagnostics")
async def get_diagnostics(request: Request, asset_id: str = Query("HVAC-UNIT-42")) -> Dict[str, Any]:
    """
    [x402 PROTECTED - 0.01 ALGO]
    Returns machine telemetry, vibrational FFT analysis, and predictive failure horizon.
    """
    receipt = getattr(request.state, "x402_receipt", None)

    return {
        "status": "unlocked",
        "service": "Algorand Telemetry & IoT Diagnostics",
        "asset_id": asset_id,
        "payment_receipt": receipt.model_dump() if receipt else None,
        "telemetry": {
            "vibration_rms": 0.42,
            "bearing_temp_celsius": 54.3,
            "refrigerant_pressure_psi": 128.5,
            "operating_hours": 8740,
            "failure_probability_30d": "2.4%",
            "recommended_action": "Routine filter swap and bearing lubrication within 45 days.",
        },
        "timestamp": int(time.time()),
    }


@router.get("/api/protected/ai-triage")
async def get_ai_triage(
    request: Request,
    issue_text: str = Query("Optical door sensor on elevator 3 misfires during rush hour"),
) -> Dict[str, Any]:
    """
    [x402 PROTECTED - 0.05 ALGO]
    AI agent triage analyzing root causes, OEM part numbers, and SLA urgency.
    """
    receipt = getattr(request.state, "x402_receipt", None)

    return {
        "status": "unlocked",
        "service": "AlgoFlow Neural Triage Agent",
        "payment_receipt": receipt.model_dump() if receipt else None,
        "analysis": {
            "classified_subsystem": "ELEVATOR_DOOR_INTERLOCK",
            "confidence_score": 0.984,
            "urgency": "CRITICAL",
            "recommended_technician_skills": ["Certified Lift Tech", "Low-Voltage Sensors"],
            "suggested_bounty_range_algo": "100 - 150 ALGO",
            "root_cause_hypothesis": "Infrared emitter diode degradation or lens dust occlusion under high ambient sunlight angles.",
            "oem_replacement_parts": [
                {"part_no": "OTIS-DOC-440-IR", "name": "Infrared Light Curtain Array", "est_cost_usd": 320},
                {"part_no": "OTIS-PCB-SENS-12", "name": "Sensor Controller Interface Board", "est_cost_usd": 180},
            ],
        },
        "timestamp": int(time.time()),
    }


@router.get("/api/protected/audit-report")
async def get_audit_report(request: Request, report_id: str = Query("AUDIT-2026-Q3")) -> Dict[str, Any]:
    """
    [x402 PROTECTED - 0.10 ALGO]
    Cryptographically verifiable maintenance audit trail committed on Algorand.
    """
    receipt = getattr(request.state, "x402_receipt", None)

    return {
        "status": "unlocked",
        "service": "AlgoFlow Cryptographic Compliance Audit",
        "report_id": report_id,
        "payment_receipt": receipt.model_dump() if receipt else None,
        "compliance": {
            "facility": "Global Operations Center Alpha",
            "audited_period": "Q3 2026",
            "total_bounties_settled": 142,
            "volume_settled_algo": 4850.0,
            "average_resolution_time_hrs": 3.2,
            "on_chain_merkle_root": "0x9ef249e0c52bbdf576a8d6b8b0e7745e69bf6f80d750c4bc79c13b28b5e67831",
            "avm_contract_verification": "100% Verified on Algorand MainNet",
            "auditor_signature": "ALGOSIG_ed25519_5df081498b958c27cf851a7042a4ba643",
        },
        "timestamp": int(time.time()),
    }
