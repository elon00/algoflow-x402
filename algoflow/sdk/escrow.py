"""
Bounty Escrow Service: Deploys, funds, claims, and settles bounties on Algorand.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Optional, Tuple

from algosdk import account, transaction
from algosdk.transaction import (
    ApplicationCreateTxn,
    ApplicationNoOpTxn,
    PaymentTxn,
    calculate_group_id,
)

from algoflow.contracts.contract_builder import (
    BountyStatus,
    EscrowContractBuilder,
)
from algoflow.sdk.client import AlgorandNetworkClient

logger = logging.getLogger("algoflow.sdk.escrow")


class BountyEscrowService:
    """
    High-level service managing Algorand bounty escrow smart contracts.
    """

    def __init__(self, client: Optional[AlgorandNetworkClient] = None):
        self.client = client or AlgorandNetworkClient()
        self._compiled_approval: Optional[bytes] = None
        self._compiled_clear: Optional[bytes] = None

    def ensure_compiled(self) -> Tuple[bytes, bytes]:
        """Ensures TEAL contracts are compiled into bytecode."""
        if self._compiled_approval and self._compiled_clear:
            return self._compiled_approval, self._compiled_clear

        approval_src = EscrowContractBuilder.get_approval_source()
        clear_src = EscrowContractBuilder.get_clear_state_source()

        approval_bytes, _ = self.client.compile_teal(approval_src)
        clear_bytes, _ = self.client.compile_teal(clear_src)

        self._compiled_approval = approval_bytes
        self._compiled_clear = clear_bytes
        return approval_bytes, clear_bytes

    def deploy_bounty(
        self,
        creator_private_key: str,
        bounty_id: str,
        amount_microalgos: int,
        deadline_round: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Deploy and initialize a new Bounty Escrow application on Algorand.
        """
        creator_address = account.address_from_private_key(creator_private_key)
        params = self.client.get_suggested_params()

        # If deadline not set, default to 100,000 rounds (~4 days on Algorand)
        if not deadline_round:
            deadline_round = params.first + 100_000

        approval_bytes, clear_bytes = self.ensure_compiled()
        app_args = EscrowContractBuilder.encode_creation_args(
            bounty_id=bounty_id,
            amount_microalgos=amount_microalgos,
            deadline_round=deadline_round,
        )

        global_schema = EscrowContractBuilder.get_global_schema()
        local_schema = EscrowContractBuilder.get_local_schema()

        txn = ApplicationCreateTxn(
            sender=creator_address,
            sp=params,
            on_complete=transaction.OnComplete.NoOpOC,
            approval_program=approval_bytes,
            clear_program=clear_bytes,
            global_schema=global_schema,
            local_schema=local_schema,
            app_args=app_args,
        )

        signed_txn = txn.sign(creator_private_key)
        txid = self.client.send_transaction(signed_txn)
        confirmed = self.client.wait_for_confirmation(txid)

        app_id = confirmed.get("application-index")
        escrow_address = EscrowContractBuilder.compute_application_address(app_id)

        logger.info(f"Bounty {bounty_id} created with App ID {app_id} at {escrow_address}")

        return {
            "app_id": app_id,
            "escrow_address": escrow_address,
            "txid": txid,
            "confirmed_round": confirmed.get("confirmed-round"),
            "amount_microalgos": amount_microalgos,
            "creator": creator_address,
        }

    def fund_escrow(
        self,
        creator_private_key: str,
        app_id: int,
        amount_microalgos: int,
    ) -> Dict[str, Any]:
        """
        Atomic Group Transaction:
        Txn 0: PaymentTxn (Funds the smart contract address with ALGO + MBR)
        Txn 1: ApplicationNoOpTxn (Calls 'fund' method on the contract)
        """
        creator_address = account.address_from_private_key(creator_private_key)
        escrow_address = EscrowContractBuilder.compute_application_address(app_id)
        params = self.client.get_suggested_params()

        # Minimum Balance Requirement (MBR) for contract account: 100,000 microAlgos
        # + bounty amount + fee buffer for inner payment transactions
        total_transfer = amount_microalgos + 100_000 + 2_000

        txn_pay = PaymentTxn(
            sender=creator_address,
            sp=params,
            receiver=escrow_address,
            amt=total_transfer,
        )

        txn_app = ApplicationNoOpTxn(
            sender=creator_address,
            sp=params,
            index=app_id,
            app_args=[b"fund"],
        )

        # Atomic group
        gid = calculate_group_id([txn_pay, txn_app])
        txn_pay.group = gid
        txn_app.group = gid

        signed_pay = txn_pay.sign(creator_private_key)
        signed_app = txn_app.sign(creator_private_key)

        txid = self.client.send_transaction([signed_pay, signed_app])
        confirmed = self.client.wait_for_confirmation(signed_app.get_txid())

        return {
            "txid": txid,
            "confirmed_round": confirmed.get("confirmed-round"),
            "funded_amount": total_transfer,
            "escrow_address": escrow_address,
        }

    def claim_bounty(
        self,
        technician_private_key: str,
        app_id: int,
    ) -> Dict[str, Any]:
        """
        Technician claims the bounty by calling 'claim'.
        """
        tech_address = account.address_from_private_key(technician_private_key)
        params = self.client.get_suggested_params()

        txn = ApplicationNoOpTxn(
            sender=tech_address,
            sp=params,
            index=app_id,
            app_args=[b"claim"],
        )

        signed_txn = txn.sign(technician_private_key)
        txid = self.client.send_transaction(signed_txn)
        confirmed = self.client.wait_for_confirmation(txid)

        return {
            "txid": txid,
            "confirmed_round": confirmed.get("confirmed-round"),
            "technician": tech_address,
            "app_id": app_id,
        }

    def submit_evidence(
        self,
        technician_private_key: str,
        app_id: int,
        evidence_hash_hex: str,
    ) -> Dict[str, Any]:
        """
        Technician submits completion proof / evidence hash (SHA-256).
        """
        tech_address = account.address_from_private_key(technician_private_key)
        params = self.client.get_suggested_params()
        evidence_bytes = bytes.fromhex(evidence_hash_hex)

        txn = ApplicationNoOpTxn(
            sender=tech_address,
            sp=params,
            index=app_id,
            app_args=[b"resolve", evidence_bytes],
        )

        signed_txn = txn.sign(technician_private_key)
        txid = self.client.send_transaction(signed_txn)
        confirmed = self.client.wait_for_confirmation(txid)

        return {
            "txid": txid,
            "confirmed_round": confirmed.get("confirmed-round"),
            "evidence_hash": evidence_hash_hex,
            "app_id": app_id,
        }

    def release_payment(
        self,
        creator_private_key: str,
        app_id: int,
        technician_address: str,
    ) -> Dict[str, Any]:
        """
        Creator verifies completion and calls 'release'.
        Smart contract executes an inner payment transaction to transfer the escrowed microAlgos
        directly to the technician.
        """
        creator_address = account.address_from_private_key(creator_private_key)
        params = self.client.get_suggested_params()

        # Fee pooling: cover the fee of the inner transaction (params.fee * 2)
        params.fee = max(params.fee, 1000) * 2
        params.flat_fee = True

        txn = ApplicationNoOpTxn(
            sender=creator_address,
            sp=params,
            index=app_id,
            app_args=[b"release"],
            accounts=[technician_address],
        )

        signed_txn = txn.sign(creator_private_key)
        txid = self.client.send_transaction(signed_txn)
        confirmed = self.client.wait_for_confirmation(txid)

        return {
            "txid": txid,
            "confirmed_round": confirmed.get("confirmed-round"),
            "status": "SETTLED",
            "app_id": app_id,
            "payout_recipient": technician_address,
        }

    def get_bounty_state(self, app_id: int) -> Dict[str, Any]:
        """
        Query Algorand node for application state and decode variables.
        """
        if not self.client.algod_client:
            return {"app_id": app_id, "error": "Algod client not available"}

        try:
            info = self.client.algod_client.application_info(app_id)
            params = info.get("params", {})
            raw_global = params.get("global-state", [])
            decoded = EscrowContractBuilder.parse_global_state(raw_global)
            decoded["app_id"] = app_id
            decoded["escrow_address"] = EscrowContractBuilder.compute_application_address(app_id)
            return decoded
        except Exception as e:
            return {
                "app_id": app_id,
                "error": str(e),
            }
