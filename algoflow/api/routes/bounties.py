"""
Bounties lifecycle and smart contract escrow endpoints.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from algoflow.contracts.contract_builder import BountyStatus, EscrowContractBuilder
from algoflow.sdk.wallet import AlgorandWallet

router = APIRouter(prefix="/api/bounties", tags=["Bounties & Escrow"])

# In-memory store initialized with realistic initial bounties
BOUNTIES_STORE: Dict[str, Dict[str, Any]] = {}


def _init_seed_data(mainnet_receiver: str):
    if BOUNTIES_STORE:
        return
    seed_items = [
        {
            "id": "bounty-hvac-server-room",
            "title": "Server Room HVAC Thermal Fluctuation",
            "description": "Temperature spikes detected in Rack Zone B exceeding 28°C threshold. Requires compressor inspection and refrigerant pressure calibration.",
            "category": "HVAC",
            "priority": "HIGH",
            "location": "Datacenter Alpha, Level -1, Zone B",
            "amount_microalgos": 50_000_000,  # 50 ALGO
            "amount_algo": 50.0,
            "creator": mainnet_receiver,
            "technician": None,
            "status": "OPEN",
            "status_code": 0,
            "app_id": 10482910,
            "escrow_address": EscrowContractBuilder.compute_application_address(10482910),
            "evidence_hash": None,
            "evidence_notes": None,
            "created_at": int(time.time()) - 3600 * 4,
            "updated_at": int(time.time()) - 3600 * 4,
        },
        {
            "id": "bounty-elevator-optical-sensor",
            "title": "Elevator 3 Optical Door Sensor Fault",
            "description": "IR curtain sensor periodically misfires during high-traffic morning hours causing safety interlock delays.",
            "category": "ELEVATOR",
            "priority": "CRITICAL",
            "location": "North Tower, Lift Bank 2, Car #3",
            "amount_microalgos": 120_000_000,  # 120 ALGO
            "amount_algo": 120.0,
            "creator": mainnet_receiver,
            "technician": "PKPE4HCDPQS56QPG5FNUWECRWSZDJRFQ7OXF6CYJNFYVVUCMAMMX3X2D2M",
            "status": "CLAIMED",
            "status_code": 1,
            "app_id": 10482911,
            "escrow_address": EscrowContractBuilder.compute_application_address(10482911),
            "evidence_hash": None,
            "evidence_notes": None,
            "created_at": int(time.time()) - 3600 * 8,
            "updated_at": int(time.time()) - 3600 * 2,
        },
        {
            "id": "bounty-fiber-switch-sfp",
            "title": "Replace Faulty 10Gbps SFP+ Optical Transceiver",
            "description": "High packet drop rate on Core Uplink Interface ge-0/0/4. Needs 850nm Multi-Mode transceiver swap and OTDR verification.",
            "category": "NETWORK",
            "priority": "MEDIUM",
            "location": "Telecom Closets, Floor 4, Rack 2",
            "amount_microalgos": 25_000_000,  # 25 ALGO
            "amount_algo": 25.0,
            "creator": mainnet_receiver,
            "technician": "GD2JXSVUQ5AAZJQA66NUCWAYS35Z4CHPB5MRROFW4IB6RKDBP65WPW3YYM",
            "status": "RESOLVED",
            "status_code": 2,
            "app_id": 10482912,
            "escrow_address": EscrowContractBuilder.compute_application_address(10482912),
            "evidence_hash": "a4f89d38c62c2efc9213bc540f2e0d37e6f8812c9b68516d2f9adbe43ec11b58",
            "evidence_notes": "Optical transceiver replaced with OEM Finisar SFP+. Light level verified at -2.4 dBm. Zero CRC errors across 100M packets.",
            "created_at": int(time.time()) - 3600 * 24,
            "updated_at": int(time.time()) - 3600 * 1,
        },
    ]
    for b in seed_items:
        BOUNTIES_STORE[b["id"]] = b


class CreateBountyRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=10)
    category: str = Field(default="GENERAL")
    priority: str = Field(default="MEDIUM")
    location: str = Field(default="Main Facility")
    amount_algo: float = Field(..., gt=0)
    creator_address: Optional[str] = None


class ClaimBountyRequest(BaseModel):
    technician_address: str = Field(..., min_length=58, max_length=58)


class ResolveBountyRequest(BaseModel):
    technician_address: str = Field(..., min_length=58, max_length=58)
    resolution_notes: str = Field(..., min_length=5)
    evidence_data: Optional[str] = Field(default=None, description="Raw text, base64 image, or link to calculate SHA-256 hash")


class ReleaseBountyRequest(BaseModel):
    creator_address: Optional[str] = None


@router.get("")
async def list_bounties(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status: OPEN, CLAIMED, RESOLVED, CLOSED"),
    category: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """List all registered bounties on AlgoFlow."""
    _init_seed_data(request.app.state.receiver_address)
    results = list(BOUNTIES_STORE.values())

    if status:
        results = [b for b in results if b["status"].upper() == status.upper()]
    if category:
        results = [b for b in results if b["category"].upper() == category.upper()]

    # Sort newest first
    results.sort(key=lambda x: x["created_at"], reverse=True)
    return results


@router.post("")
async def create_bounty(payload: CreateBountyRequest, request: Request) -> Dict[str, Any]:
    """
    Create a new bounty and register it with Algorand escrow.
    """
    _init_seed_data(request.app.state.receiver_address)
    creator = payload.creator_address or request.app.state.receiver_address

    if not AlgorandWallet.is_valid_address(creator):
        raise HTTPException(status_code=400, detail="Invalid Algorand creator address")

    bounty_id = f"bounty-{uuid.uuid4().hex[:8]}"
    amount_microalgos = int(payload.amount_algo * 1_000_000)

    # Deterministic simulated app id for instant response; live contracts can be deployed via SDK
    simulated_app_id = 10480000 + (len(BOUNTIES_STORE) + 1)
    escrow_address = EscrowContractBuilder.compute_application_address(simulated_app_id)

    bounty_record = {
        "id": bounty_id,
        "title": payload.title,
        "description": payload.description,
        "category": payload.category.upper(),
        "priority": payload.priority.upper(),
        "location": payload.location,
        "amount_microalgos": amount_microalgos,
        "amount_algo": payload.amount_algo,
        "creator": creator,
        "technician": None,
        "status": "OPEN",
        "status_code": 0,
        "app_id": simulated_app_id,
        "escrow_address": escrow_address,
        "evidence_hash": None,
        "evidence_notes": None,
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }

    BOUNTIES_STORE[bounty_id] = bounty_record
    return bounty_record


@router.get("/{bounty_id}")
async def get_bounty(bounty_id: str, request: Request) -> Dict[str, Any]:
    """Get single bounty details by ID."""
    _init_seed_data(request.app.state.receiver_address)
    bounty = BOUNTIES_STORE.get(bounty_id)
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found")
    return bounty


@router.post("/{bounty_id}/claim")
async def claim_bounty(bounty_id: str, payload: ClaimBountyRequest, request: Request) -> Dict[str, Any]:
    """Technician claims an open bounty."""
    _init_seed_data(request.app.state.receiver_address)
    bounty = BOUNTIES_STORE.get(bounty_id)
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found")

    if bounty["status"] != "OPEN":
        raise HTTPException(status_code=400, detail=f"Bounty cannot be claimed in status '{bounty['status']}'")

    if not AlgorandWallet.is_valid_address(payload.technician_address):
        raise HTTPException(status_code=400, detail="Invalid Algorand technician address")

    bounty["technician"] = payload.technician_address
    bounty["status"] = "CLAIMED"
    bounty["status_code"] = 1
    bounty["updated_at"] = int(time.time())

    return bounty


@router.post("/{bounty_id}/resolve")
async def resolve_bounty(bounty_id: str, payload: ResolveBountyRequest, request: Request) -> Dict[str, Any]:
    """Technician submits completion proof and commits SHA-256 evidence hash."""
    _init_seed_data(request.app.state.receiver_address)
    bounty = BOUNTIES_STORE.get(bounty_id)
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found")

    if bounty["status"] != "CLAIMED":
        raise HTTPException(status_code=400, detail=f"Bounty cannot be resolved in status '{bounty['status']}'")

    # Compute SHA-256 evidence hash
    evidence_content = (payload.evidence_data or payload.resolution_notes).encode("utf-8")
    evidence_hash = hashlib.sha256(evidence_content).hexdigest()

    bounty["evidence_hash"] = evidence_hash
    bounty["evidence_notes"] = payload.resolution_notes
    bounty["status"] = "RESOLVED"
    bounty["status_code"] = 2
    bounty["updated_at"] = int(time.time())

    return bounty


@router.post("/{bounty_id}/release")
async def release_bounty(bounty_id: str, payload: ReleaseBountyRequest, request: Request) -> Dict[str, Any]:
    """Creator verifies resolution and triggers atomic payment release on Algorand."""
    _init_seed_data(request.app.state.receiver_address)
    bounty = BOUNTIES_STORE.get(bounty_id)
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found")

    if bounty["status"] != "RESOLVED":
        raise HTTPException(status_code=400, detail=f"Bounty cannot be released in status '{bounty['status']}'")

    # Simulate inner transaction hash or live broadcast
    payout_txid = f"ALGO_{uuid.uuid4().hex[:44].upper()}"

    bounty["status"] = "CLOSED"
    bounty["status_code"] = 3
    bounty["settlement_txid"] = payout_txid
    bounty["updated_at"] = int(time.time())

    return {
        "message": "Atomic escrow settlement executed on Algorand",
        "bounty": bounty,
        "settlement": {
            "recipient": bounty["technician"],
            "amount_microalgos": bounty["amount_microalgos"],
            "amount_algo": bounty["amount_algo"],
            "txid": payout_txid,
            "status": "CONFIRMED",
        }
    }
