"""Guarded Algorand MainNet deployment for Qmoosa AlgoFlow x402.

This script never prints or persists the mnemonic/private key. It creates the
QALGO ASA on Algorand MainNet and emits a JSON deployment manifest containing
only public identifiers.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from algosdk import account, mnemonic

from algoflow.sdk.client import AlgorandNetworkClient
from algoflow.sdk.token import QmoosaAlgoTokenManager

OUT = Path("deployment-mainnet.json")


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    phrase = required_env("ALGORAND_DEPLOYER_MNEMONIC")
    confirmation = required_env("MAINNET_DEPLOY_CONFIRMATION")
    if confirmation != "DEPLOY_QMOOSA_ALGOFLOW_MAINNET":
        raise SystemExit("Refusing deployment: MAINNET_DEPLOY_CONFIRMATION is incorrect.")

    private_key = mnemonic.to_private_key(phrase)
    deployer = account.address_from_private_key(private_key)

    client = AlgorandNetworkClient(network="mainnet")
    status = client.get_status()
    if not status.get("connected"):
        raise SystemExit(f"MainNet node unavailable: {status}")

    params = client.get_suggested_params()
    genesis_id = getattr(params, "gen", None)
    if genesis_id and genesis_id != "mainnet-v1.0":
        raise SystemExit(f"Refusing deployment on unexpected genesis ID: {genesis_id}")

    balance = client.get_account_balance(deployer)
    if balance.get("amount_microalgos", 0) < 500_000:
        raise SystemExit(
            f"Deployer {deployer} needs at least 0.5 ALGO available for ASA creation, "
            "minimum-balance growth, and fees."
        )

    token = QmoosaAlgoTokenManager(client=client, asset_id=None)
    create_txn = token.build_create_asa_transaction(
        creator_address=deployer,
        reserve_address=deployer,
        manager_address=deployer,
    )
    signed = create_txn.sign(private_key)
    txid = client.send_transaction(signed)
    confirmed = client.wait_for_confirmation(txid, max_rounds=12)
    asset_id = confirmed.get("asset-index")
    if not asset_id:
        raise SystemExit(f"ASA creation confirmed without asset-index: {confirmed}")

    manifest = {
        "network": "mainnet",
        "deployer": deployer,
        "qalgo_asset_id": asset_id,
        "asset_creation_txid": txid,
        "confirmed_round": confirmed.get("confirmed-round"),
        "algod": client.algod_url,
        "explorer_asset_url": f"https://explorer.perawallet.app/asset/{asset_id}",
        "explorer_tx_url": f"https://explorer.perawallet.app/tx/{txid}",
    }
    OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
