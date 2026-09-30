"""
Tests for Qmoosa Algo (QALGO) Token, Unlimited Supply Model, Faucet, and Service Exchange.
"""

import pytest
from fastapi.testclient import TestClient
from algoflow.api.app import create_app
from algoflow.sdk.token import (
    MAX_AVM_SUPPLY_UNITS,
    TOKEN_ASSET_NAME,
    TOKEN_DECIMALS,
    TOKEN_UNIT_NAME,
    QmoosaAlgoTokenManager,
)


@pytest.fixture
def client():
    app = create_app(network_name="mainnet", demo_mode=True)
    return TestClient(app)


def test_token_unlimited_supply_spec():
    manager = QmoosaAlgoTokenManager()
    metrics = manager.get_token_metrics()

    assert metrics["unit_name"] == "QALGO"
    assert metrics["asset_name"] == "Qmoosa Algo Utility & Settlement"
    assert metrics["decimals"] == 6
    assert metrics["max_supply_units"] == MAX_AVM_SUPPLY_UNITS
    assert metrics["supply_model"] == "UNLIMITED_ELASTIC"
    assert metrics["max_supply_whole"] > 18_000_000_000_000  # >18 Trillion whole tokens


def test_participant_allowance_faucet(client):
    test_user = "MW6XFO4NJPVM4DW2VO3NGD3NBSOMEBVLQOVLNGAJOHASMDLGZBUJPOWWIA"
    payload = {
        "recipient_address": test_user,
        "role": "SERVICE_PROVIDER",
    }
    res = client.post("/api/token/faucet", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["recipient"] == test_user
    assert data["amount_qalgo"] == 25.0
    assert data["unit_name"] == "QALGO"
    assert data["status"] == "DISBURSED"
    assert "QALGO_SUB_" in data["txid"]


def test_token_services_catalog_and_exchange(client):
    # 1. Get services catalog
    res = client.get("/api/token/services")
    assert res.status_code == 200
    services = res.json()
    assert len(services) >= 4

    keys = [s["service_key"] for s in services]
    assert "IOT_DIAGNOSTICS" in keys
    assert "AI_TRIAGE" in keys
    assert "AUDIT_TRAIL" in keys

    # 2. Exchange tokens for a service
    test_user = "MW6XFO4NJPVM4DW2VO3NGD3NBSOMEBVLQOVLNGAJOHASMDLGZBUJPOWWIA"
    exchange_payload = {
        "user_address": test_user,
        "service_key": "AI_TRIAGE",
    }
    ex_res = client.post("/api/token/exchange", json=exchange_payload)
    assert ex_res.status_code == 200
    ex_data = ex_res.json()
    assert ex_data["status"] == "CONFIRMED"
    assert ex_data["qalgo_exchanged"] == 50.0
    assert ex_data["tokens_burned"] == 25.0  # 50% burned
    assert "QALGO_ACCESS_" in ex_data["access_token"]
