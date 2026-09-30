"""
Integration tests for FastAPI endpoints and x402 payment enforcement.
"""

import pytest
from fastapi.testclient import TestClient
from algoflow.api.app import create_app
from algoflow.x402.protocol import (
    X402_HEADER_AMOUNT,
    X402_HEADER_BLOCKCHAIN,
    X402_HEADER_NETWORK,
    X402_HEADER_PAYMENT_AUTH,
    X402_HEADER_RECEIVER,
    X402_HEADER_SETTLEMENT_STATUS,
    X402_HEADER_TXID,
)


@pytest.fixture
def client():
    app = create_app(network_name="mainnet", demo_mode=True)
    return TestClient(app)


def test_api_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["blockchain"] == "Algorand"
    assert data["network"] == "mainnet"


def test_api_network(client):
    res = client.get("/api/network")
    assert res.status_code == 200
    data = res.json()
    assert data["network"] == "mainnet"
    assert "node_info" in data


def test_bounties_lifecycle(client):
    # 1. List initial bounties
    res = client.get("/api/bounties")
    assert res.status_code == 200
    bounties = res.json()
    assert len(bounties) >= 3

    # 2. Create new bounty
    create_payload = {
        "title": "Air Handling Unit Damper Actuator Calibration",
        "description": "Pressure differential sensor requires recalibration and damper servo replacement.",
        "category": "HVAC",
        "priority": "HIGH",
        "location": "North Substation Building 4",
        "amount_algo": 40.0,
    }
    create_res = client.post("/api/bounties", json=create_payload)
    assert create_res.status_code == 200
    created = create_res.json()
    bounty_id = created["id"]
    assert created["amount_algo"] == 40.0
    assert created["amount_microalgos"] == 40_000_000
    assert created["status"] == "OPEN"
    assert created["app_id"] > 0

    # 3. Technician claims bounty
    tech_address = "PKPE4HCDPQS56QPG5FNUWECRWSZDJRFQ7OXF6CYJNFYVVUCMAMMX3X2D2M"
    claim_res = client.post(f"/api/bounties/{bounty_id}/claim", json={"technician_address": tech_address})
    assert claim_res.status_code == 200
    claimed = claim_res.json()
    assert claimed["status"] == "CLAIMED"
    assert claimed["technician"] == tech_address

    # 4. Technician submits resolution
    resolve_res = client.post(f"/api/bounties/{bounty_id}/resolve", json={
        "technician_address": tech_address,
        "resolution_notes": "Actuator replaced and calibrated to ±0.2% tolerance.",
    })
    assert resolve_res.status_code == 200
    resolved = resolve_res.json()
    assert resolved["status"] == "RESOLVED"
    assert resolved["evidence_hash"] is not None
    assert len(resolved["evidence_hash"]) == 64  # SHA-256 hex length

    # 5. Creator releases atomic payout
    release_res = client.post(f"/api/bounties/{bounty_id}/release", json={})
    assert release_res.status_code == 200
    released = release_res.json()
    assert released["bounty"]["status"] == "CLOSED"
    assert "settlement" in released


def test_x402_payment_required_challenge(client):
    # GET protected route with NO payment headers
    res = client.get("/api/protected/diagnostics?asset_id=PUMP-99")
    assert res.status_code == 402

    # Verify standard x402 headers
    assert res.headers.get(X402_HEADER_BLOCKCHAIN) == "algorand"
    assert res.headers.get(X402_HEADER_NETWORK) == "mainnet"
    assert res.headers.get(X402_HEADER_AMOUNT) == "10000"
    assert res.headers.get("WWW-Authenticate") is not None

    body = res.json()
    assert body["status"] == 402
    assert body["title"] == "Payment Required"
    assert "payment" in body
    assert body["payment"]["payment_uri"].startswith("algorand://")


def test_x402_payment_unlock_with_txid(client):
    # Send request with mock Algorand transaction ID
    headers = {
        X402_HEADER_PAYMENT_AUTH: "txid=mock_txid_algorand_confirmed_402_test"
    }
    res = client.get("/api/protected/diagnostics?asset_id=PUMP-99", headers=headers)
    assert res.status_code == 200

    # Verify settlement headers in response
    assert res.headers.get(X402_HEADER_SETTLEMENT_STATUS) == "confirmed"
    assert res.headers.get(X402_HEADER_TXID) == "mock_txid_algorand_confirmed_402_test"

    body = res.json()
    assert body["status"] == "unlocked"
    assert "telemetry" in body
    assert body["payment_receipt"]["settlement_status"] == "confirmed"
