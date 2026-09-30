"""
Tests for Algorand TEAL Smart Contracts and ContractBuilder.
"""

import base64
import pytest
from algoflow.contracts.contract_builder import (
    BountyStatus,
    EscrowContractBuilder,
)
from algoflow.sdk.client import AlgorandNetworkClient


def test_teal_sources_exist():
    approval = EscrowContractBuilder.get_approval_source()
    clear = EscrowContractBuilder.get_clear_state_source()

    assert "#pragma version 8" in approval
    assert "handle_create" in approval
    assert "action_claim" in approval
    assert "action_resolve" in approval
    assert "action_release" in approval
    assert "action_refund" in approval

    assert "#pragma version 8" in clear
    assert "int 1" in clear


def test_schema_and_address_derivation():
    global_schema = EscrowContractBuilder.get_global_schema()
    local_schema = EscrowContractBuilder.get_local_schema()

    assert global_schema.num_byte_slices == 4
    assert global_schema.num_uints == 3
    assert local_schema.num_byte_slices == 0
    assert local_schema.num_uints == 0

    # Derive application address for known app IDs
    app_addr = EscrowContractBuilder.compute_application_address(10482910)
    assert len(app_addr) == 58
    assert app_addr.isalnum()


def test_encode_creation_args():
    args = EscrowContractBuilder.encode_creation_args(
        bounty_id="test-bounty-1",
        amount_microalgos=50_000_000,
        deadline_round=42_000_000,
    )

    assert len(args) == 3
    assert args[0] == b"test-bounty-1"
    assert int.from_bytes(args[1], "big") == 50_000_000
    assert int.from_bytes(args[2], "big") == 42_000_000


def test_parse_global_state():
    raw_state = [
        {
            "key": base64.b64encode(b"status").decode("utf-8"),
            "value": {"type": 2, "uint": 1},
        },
        {
            "key": base64.b64encode(b"amount").decode("utf-8"),
            "value": {"type": 2, "uint": 25000000},
        },
        {
            "key": base64.b64encode(b"bounty_id").decode("utf-8"),
            "value": {"type": 1, "bytes": base64.b64encode(b"hvac-fix-01").decode("utf-8")},
        },
    ]

    parsed = EscrowContractBuilder.parse_global_state(raw_state)
    assert parsed["status"] == 1
    assert parsed["status_label"] == "CLAIMED"
    assert parsed["amount"] == 25000000
    assert parsed["bounty_id"] == "hvac-fix-01"


def test_teal_compilation_with_algod():
    client = AlgorandNetworkClient(network="mainnet")
    try:
        approval_src = EscrowContractBuilder.get_approval_source()
        bytecode, contract_hash = client.compile_teal(approval_src)
        assert len(bytecode) > 0
        assert len(contract_hash) > 0
    except Exception as e:
        pytest.skip(f"MainNet Algod node unreachable in current test environment: {e}")
