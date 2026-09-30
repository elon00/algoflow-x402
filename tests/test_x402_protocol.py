"""
Tests for x402 Algorand Protocol Specification & Payment Verifier.
"""

import time
import pytest
from algoflow.x402.protocol import (
    X402_HEADER_AMOUNT,
    X402_HEADER_BLOCKCHAIN,
    X402_HEADER_CHALLENGE,
    X402_HEADER_NETWORK,
    X402_HEADER_RECEIVER,
    X402PaymentChallenge,
)
from algoflow.x402.verifier import AlgorandPaymentVerifier


def test_x402_challenge_creation():
    receiver = "MW6XFO4NJPVM4DW2VO3NGD3NBSOMEBVLQOVLNGAJOHASMDLGZBUJPOWWIA"
    challenge = X402PaymentChallenge(
        network="mainnet",
        receiver=receiver,
        amount_microalgos=50_000,
        resource_path="/api/protected/ai-triage",
    )

    assert challenge.blockchain == "algorand"
    assert challenge.network == "mainnet"
    assert challenge.amount_microalgos == 50_000
    assert challenge.receiver == receiver
    assert "algo402_" in challenge.challenge
    assert challenge.required_note.startswith("x402:algo402_")
    assert challenge.payment_uri.startswith("algorand://")
    assert "amount=50000" in challenge.payment_uri

    headers = challenge.to_headers()
    assert headers[X402_HEADER_BLOCKCHAIN] == "algorand"
    assert headers[X402_HEADER_NETWORK] == "mainnet"
    assert headers[X402_HEADER_AMOUNT] == "50000"
    assert headers[X402_HEADER_RECEIVER] == receiver
    assert headers[X402_HEADER_CHALLENGE] == challenge.challenge


def test_verifier_replay_protection():
    verifier = AlgorandPaymentVerifier(demo_mode=True)
    receiver = "MW6XFO4NJPVM4DW2VO3NGD3NBSOMEBVLQOVLNGAJOHASMDLGZBUJPOWWIA"

    # First verification of mock tx succeeds
    result1 = verifier.verify_transaction(
        txid="mock_tx_123456",
        expected_receiver=receiver,
        expected_amount=10_000,
    )
    assert result1.valid is True
    assert result1.txid == "mock_tx_123456"

    # Second verification of the exact same txid MUST fail due to replay prevention
    result2 = verifier.verify_transaction(
        txid="mock_tx_123456",
        expected_receiver=receiver,
        expected_amount=10_000,
    )
    assert result2.valid is False
    assert "already been redeemed" in result2.error


def test_verifier_challenge_lifecycle():
    verifier = AlgorandPaymentVerifier(demo_mode=True)
    chal_id = "algo402_test123"
    verifier.register_challenge(
        challenge=chal_id,
        receiver="TESTRECEIVER",
        amount_microalgos=20_000,
        resource_path="/api/protected/diagnostics",
        expires_at=int(time.time()) + 60,
    )

    chal = verifier.get_challenge(chal_id)
    assert chal is not None
    assert chal["amount"] == 20_000
    assert chal["resource_path"] == "/api/protected/diagnostics"
