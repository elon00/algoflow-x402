"""
Algorand Wallet & Cryptographic Key Management.
"""

from __future__ import annotations

from typing import Optional, Tuple
from algosdk import account, encoding, mnemonic


class AlgorandWallet:
    """
    Utilities for creating, recovering, and signing with Algorand accounts.
    """

    @classmethod
    def generate(cls) -> Tuple[str, str, str]:
        """
        Generate a new fresh Algorand account.
        Returns (private_key, address, 25_word_mnemonic)
        """
        private_key, address = account.generate_account()
        passphrase = mnemonic.from_private_key(private_key)
        return private_key, address, passphrase

    @classmethod
    def from_mnemonic(cls, passphrase: str) -> Tuple[str, str]:
        """
        Recover private key and address from a 25-word Algorand mnemonic.
        """
        clean_words = " ".join(passphrase.strip().split())
        private_key = mnemonic.to_private_key(clean_words)
        address = account.address_from_private_key(private_key)
        return private_key, address

    @classmethod
    def is_valid_address(cls, addr: str) -> bool:
        """
        Verify if an address string is a valid Algorand 58-character public key.
        """
        if not addr or not isinstance(addr, str):
            return False
        return encoding.is_valid_address(addr.strip())

    @classmethod
    def format_address(cls, addr: str) -> str:
        """Truncate address for display: ABCD...WXYZ"""
        if not addr:
            return ""
        if len(addr) <= 12:
            return addr
        return f"{addr[:6]}...{addr[-6:]}"
