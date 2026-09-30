"""
FastAPI & ASGI Middleware for x402 Algorand Payment Required Protocol.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Callable, Dict, List, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from algoflow.x402.protocol import (
    X402_HEADER_PAYMENT_AUTH,
    X402_HEADER_SETTLEMENT_STATUS,
    X402_HEADER_TXID,
    X402PaymentChallenge,
    X402PaymentReceipt,
)
from algoflow.x402.verifier import AlgorandPaymentVerifier

logger = logging.getLogger("algoflow.x402.middleware")


class X402PaymentMiddleware(BaseHTTPMiddleware):
    """
    ASGI Middleware enforcing HTTP 402 Payment Required microtransactions
    on specified Algorand protected routes.
    """

    def __init__(
        self,
        app,
        verifier: AlgorandPaymentVerifier,
        receiver_address: str,
        network: str = "mainnet",
        protected_routes: Optional[Dict[str, int]] = None,
    ):
        super().__init__(app)
        self.verifier = verifier
        self.receiver_address = receiver_address
        self.network = network
        # Route regex / prefix mapping to microAlgos pricing
        # e.g., {"/api/protected/diagnostics": 10_000, "/api/protected/ai-triage": 50_000}
        self.protected_routes = protected_routes or {
            "/api/protected/diagnostics": 10_000,   # 0.01 ALGO
            "/api/protected/ai-triage": 50_000,      # 0.05 ALGO
            "/api/protected/audit-report": 100_000,  # 0.10 ALGO
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Find if the path is protected
        price_microalgos = None
        for prefix, cost in self.protected_routes.items():
            if path.startswith(prefix):
                price_microalgos = cost
                break

        if price_microalgos is None:
            # Route is not protected by x402, proceed normally
            return await call_next(request)

        # Inspect authorization headers
        auth_header = request.headers.get(X402_HEADER_PAYMENT_AUTH) or request.headers.get("Authorization", "")
        txid = self._extract_txid(auth_header)

        if not txid:
            # Issue a new HTTP 402 challenge
            challenge = X402PaymentChallenge(
                network=self.network,
                receiver=self.receiver_address,
                amount_microalgos=price_microalgos,
                resource_path=path,
            )
            self.verifier.register_challenge(
                challenge=challenge.challenge,
                receiver=self.receiver_address,
                amount_microalgos=price_microalgos,
                resource_path=path,
                expires_at=challenge.expires_at,
            )

            headers = challenge.to_headers()
            return JSONResponse(
                status_code=402,
                content=challenge.to_dict(),
                headers=headers,
            )

        # We have a TXID, verify on Algorand
        verification = self.verifier.verify_transaction(
            txid=txid,
            expected_receiver=self.receiver_address,
            expected_amount=price_microalgos,
        )

        if not verification.valid:
            logger.warning(f"x402 payment verification failed for txid {txid}: {verification.error}")
            return JSONResponse(
                status_code=402,
                content={
                    "status": 402,
                    "title": "Payment Verification Failed",
                    "detail": verification.error or "Invalid or unconfirmed Algorand transaction",
                    "txid": txid,
                    "network": self.network,
                    "required_receiver": self.receiver_address,
                    "required_amount_microalgos": price_microalgos,
                },
            )

        # Payment verified! Attach receipt to request state
        receipt = X402PaymentReceipt(
            txid=txid,
            sender=verification.sender or "UNKNOWN",
            receiver=verification.receiver or self.receiver_address,
            amount_microalgos=verification.amount_microalgos or price_microalgos,
            amount_algo=(verification.amount_microalgos or price_microalgos) / 1_000_000,
            confirmed_round=verification.confirmed_round or 0,
        )
        request.state.x402_receipt = receipt

        # Call endpoint
        response = await call_next(request)

        # Inject settlement headers in response
        for k, v in receipt.to_headers().items():
            response.headers[k] = v

        return response

    def _extract_txid(self, header_value: str) -> Optional[str]:
        """
        Extracts txid from header:
        - 'txid=VGP4...'
        - 'X-402 txid=VGP4...'
        - 'VGP4...' (direct 52-char Algorand base32 txid)
        """
        if not header_value:
            return None

        # Look for txid=<alphanumeric>
        match = re.search(r"txid=([A-Za-z0-9_\-]+)", header_value)
        if match:
            return match.group(1)

        # Check if entire string or bearer token is a txid
        parts = header_value.strip().split()
        candidate = parts[-1] if parts else ""
        if len(candidate) == 52 or candidate.startswith("mock_") or candidate.startswith("demo_"):
            return candidate

        return None
