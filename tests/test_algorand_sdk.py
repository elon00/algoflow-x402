"""
Tests for Algorand SDK, wallet generation, and client connectivity.
"""

from algoflow.sdk.client import AlgorandNetworkClient
from algoflow.sdk.wallet import AlgorandWallet


def test_wallet_generation_and_recovery():
    priv, addr, mnemonic_phrase = AlgorandWallet.generate()

    assert len(addr) == 58
    assert AlgorandWallet.is_valid_address(addr) is True
    assert len(mnemonic_phrase.split()) == 25

    # Recover account from mnemonic
    recovered_priv, recovered_addr = AlgorandWallet.from_mnemonic(mnemonic_phrase)
    assert recovered_addr == addr
    assert recovered_priv == priv


def test_wallet_format_address():
    short = AlgorandWallet.format_address("VGP4NPGYFKYPU52CKFEZ73KSVU5SIMAXPRV6B7GFBHYFHSVLQBHZJAKYOY")
    assert short.startswith("VGP4NP")
    assert short.endswith("JAKYOY")
    assert "..." in short


def test_mainnet_client_configuration():
    client = AlgorandNetworkClient(network="mainnet")
    assert client.network == "mainnet"
    assert "mainnet" in client.algod_url
    info = client.get_network_info()
    assert info["genesis_id"] == "mainnet-v1.0"
