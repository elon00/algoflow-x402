"""
AlgoFlow Escrow & Settlement Smart Contracts on Algorand (AVM).
"""

from pathlib import Path

CONTRACTS_DIR = Path(__file__).parent
ESCROW_APPROVAL_PATH = CONTRACTS_DIR / "escrow_contract.teal"
CLEAR_STATE_PATH = CONTRACTS_DIR / "clear_state.teal"
