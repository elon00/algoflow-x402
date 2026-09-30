"""
FastAPI Application Factory for AlgoFlow x402.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from algoflow.api.routes import bounties, network, token, x402_gateway
from algoflow.sdk.client import AlgorandNetworkClient
from algoflow.x402.middleware import X402PaymentMiddleware
from algoflow.x402.verifier import AlgorandPaymentVerifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("algoflow.api")

STATIC_DIR = Path(__file__).parent.parent / "static"

# Standard default Algorand treasury address (valid 58-character Algorand address format)
DEFAULT_RECEIVER_ADDRESS = os.getenv(
    "RECEIVER_ADDRESS",
    "MW6XFO4NJPVM4DW2VO3NGD3NBSOMEBVLQOVLNGAJOHASMDLGZBUJPOWWIA",
)


def create_app(
    network_name: Optional[str] = None,
    demo_mode: Optional[bool] = None,
    receiver_address: Optional[str] = None,
) -> FastAPI:
    """
    Creates and configures the AlgoFlow x402 FastAPI application.
    """
    active_network = (network_name or os.getenv("ALGORAND_NETWORK", "mainnet")).lower()
    is_demo = demo_mode if demo_mode is not None else (os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes"))
    receiver = receiver_address or DEFAULT_RECEIVER_ADDRESS

    app = FastAPI(
        title="AlgoFlow x402",
        description="Algorand-native autonomous bounty escrow and x402 Payment Required microsettlement engine",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Enable CORS for cross-domain Web3 apps and frontends
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-402-Version",
            "X-402-Blockchain",
            "X-402-Network",
            "X-402-Receiver",
            "X-402-Amount",
            "X-402-Asset-ID",
            "X-402-Challenge",
            "X-402-Expires-At",
            "X-402-Settlement-Status",
            "X-402-TxID",
            "WWW-Authenticate",
        ],
    )

    # Initialize Algorand client
    algo_client = AlgorandNetworkClient(network=active_network)
    app.state.algorand_client = algo_client
    app.state.receiver_address = receiver
    app.state.demo_mode = is_demo

    # Initialize x402 Payment Verifier
    verifier = AlgorandPaymentVerifier(
        algod_client=algo_client.algod_client,
        indexer_client=algo_client.indexer_client,
        network=active_network,
        demo_mode=is_demo,
    )
    app.state.verifier = verifier

    # Attach x402 Payment Middleware
    app.add_middleware(
        X402PaymentMiddleware,
        verifier=verifier,
        receiver_address=receiver,
        network=active_network,
        protected_routes={
            "/api/protected/diagnostics": 10_000,   # 0.01 ALGO
            "/api/protected/ai-triage": 50_000,      # 0.05 ALGO
            "/api/protected/audit-report": 100_000,  # 0.10 ALGO
        },
    )

    # Register Routers
    app.include_router(network.router)
    app.include_router(bounties.router)
    app.include_router(x402_gateway.router)
    app.include_router(token.router)

    # Health check
    @app.get("/api/health", tags=["System"])
    async def health():
        return {
            "status": "healthy",
            "project": "AlgoFlow x402",
            "blockchain": "Algorand",
            "network": app.state.algorand_client.network,
            "demo_mode": app.state.demo_mode,
            "receiver_address": app.state.receiver_address,
        }

    # Mount static assets
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_index():
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
