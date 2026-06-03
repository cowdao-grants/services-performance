"""
Pytest fixtures for end-to-end tests.

These fixtures provide connections to the running docker-compose environment.
"""

import os
import time
from typing import Any

import pytest
import requests
from eth_account import Account
from web3 import Web3

# Service endpoints (assuming docker-compose is running)
ANVIL_RPC_URL = os.getenv("ANVIL_RPC_URL", "http://localhost:8545")
ORDERBOOK_API_URL = os.getenv("ORDERBOOK_API_URL", "http://localhost:8080")

# Contract addresses on mainnet
SETTLEMENT_CONTRACT = "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"  # For order signing
VAULT_RELAYER = "0xC92E8bdf79f0507f65a392b0ab4667716BFE0110"  # For token approvals

# Token addresses on mainnet
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"

# ERC20 ABI (minimal)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]


@pytest.fixture(scope="session")
def web3() -> Web3:
    """
    Web3 connection to the local Anvil fork.

    Returns:
        Web3 instance connected to Anvil
    """
    w3 = Web3(Web3.HTTPProvider(ANVIL_RPC_URL))
    assert w3.is_connected(), f"Failed to connect to Anvil at {ANVIL_RPC_URL}"
    return w3


@pytest.fixture(scope="session")
def chain_id(web3: Web3) -> int:
    """Get the chain ID from the connected network."""
    return web3.eth.chain_id


@pytest.fixture(scope="session")
def orderbook_api_url() -> str:
    """Orderbook API URL."""
    return ORDERBOOK_API_URL


@pytest.fixture
def funded_trader(web3: Web3) -> Account:
    """
    Create a trader account and fund it with ETH and tokens.

    The Anvil fork allows us to impersonate accounts and manipulate state.
    """
    # Create new account
    account = Account.create()

    # Fund with ETH from Anvil's default account
    # Anvil's default accounts have plenty of ETH
    default_account = web3.eth.accounts[0]

    tx_hash = web3.eth.send_transaction(
        {
            "from": default_account,
            "to": account.address,
            "value": web3.to_wei(10, "ether"),
        }
    )
    web3.eth.wait_for_transaction_receipt(tx_hash)

    return account


def impersonate_account(web3: Web3, address: str) -> None:
    """
    Impersonate an account on Anvil fork.

    This allows us to send transactions as any address.
    """
    web3.provider.make_request("anvil_impersonateAccount", [address])


def stop_impersonating_account(web3: Web3, address: str) -> None:
    """Stop impersonating an account."""
    web3.provider.make_request("anvil_stopImpersonatingAccount", [address])


def fund_trader_with_token(
    web3: Web3, trader_address: str, token_address: str, amount: int
) -> None:
    """
    Fund a trader with ERC20 tokens using Anvil's storage manipulation.

    This directly sets the balance in the token contract's storage,
    which is more reliable than transferring from whales.
    """
    # For standard ERC20 tokens, the balance is stored in a mapping at slot 0
    # mapping(address => uint256) balanceOf -> slot = keccak256(address || slot)

    # Calculate storage slot for the trader's balance
    # This works for most ERC20 tokens that use the standard storage layout
    trader_address_padded = trader_address.lower().replace("0x", "").zfill(64)
    slot_padded = "0".zfill(64)

    # For WETH, balanceOf mapping is at slot 3
    # For DAI, balanceOf mapping is at slot 2
    # For USDC, balanceOf mapping is at slot 9
    balance_slot_positions = {
        WETH: 3,
        DAI: 2,
        USDC: 9,
    }

    balance_slot = balance_slot_positions.get(token_address)
    if balance_slot is None:
        raise ValueError(f"Unknown token {token_address}, don't know balance slot position")

    slot_padded = hex(balance_slot)[2:].zfill(64)
    storage_key = web3.keccak(bytes.fromhex(trader_address_padded + slot_padded))

    # Convert amount to hex (32 bytes)
    amount_hex = hex(amount)[2:].zfill(64)

    # Set the storage value using Anvil's anvil_setStorageAt
    web3.provider.make_request(
        "anvil_setStorageAt", [token_address, storage_key.hex(), f"0x{amount_hex}"]
    )


def approve_token(
    web3: Web3, trader_account: Account, token_address: str, spender: str, amount: int
) -> None:
    """
    Approve a spender to use tokens.

    Args:
        web3: Web3 instance
        trader_account: The trader's account
        token_address: The token to approve
        spender: The address to approve (usually settlement contract)
        amount: Amount to approve
    """
    token_contract = web3.eth.contract(address=token_address, abi=ERC20_ABI)

    # Build transaction
    nonce = web3.eth.get_transaction_count(trader_account.address)
    tx = token_contract.functions.approve(spender, amount).build_transaction(
        {
            "from": trader_account.address,
            "nonce": nonce,
            "gas": 100000,
            "gasPrice": web3.eth.gas_price,
        }
    )

    # Sign and send
    signed_tx = web3.eth.account.sign_transaction(tx, trader_account.key)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
    web3.eth.wait_for_transaction_receipt(tx_hash)


@pytest.fixture
def funded_weth_trader(web3: Web3, funded_trader: Account) -> Account:
    """
    Create a trader funded with WETH.

    Funds with 10 WETH and approves settlement contract.
    """
    amount = web3.to_wei(10, "ether")

    # Fund with WETH
    fund_trader_with_token(web3, funded_trader.address, WETH, amount)

    # Approve VaultRelayer
    approve_token(web3, funded_trader, WETH, VAULT_RELAYER, amount * 10)

    return funded_trader


@pytest.fixture
def funded_dai_trader(web3: Web3, funded_trader: Account) -> Account:
    """
    Create a trader funded with DAI.

    Funds with 10,000 DAI and approves settlement contract.
    """
    amount = 10_000 * 10**18  # 10,000 DAI

    # Fund with DAI
    fund_trader_with_token(web3, funded_trader.address, DAI, amount)

    # Approve settlement contract
    approve_token(web3, funded_trader, DAI, VAULT_RELAYER, amount * 10)

    return funded_trader


def wait_for_orderbook_ready(max_retries: int = 30) -> None:
    """
    Wait for the orderbook API to be ready.

    Args:
        max_retries: Maximum number of retry attempts

    Raises:
        RuntimeError: If orderbook doesn't become ready
    """
    for i in range(max_retries):
        try:
            response = requests.get(f"{ORDERBOOK_API_URL}/api/v1/version", timeout=5)
            if response.status_code == 200:
                return
        except requests.exceptions.RequestException:
            pass

        if i < max_retries - 1:
            time.sleep(2)

    raise RuntimeError(
        f"Orderbook API not ready after {max_retries} attempts at {ORDERBOOK_API_URL}"
    )


@pytest.fixture(scope="session", autouse=True)
def ensure_services_ready():
    """
    Ensure all services are ready before running tests.

    This runs once per test session.
    """
    print("\nWaiting for services to be ready...")
    wait_for_orderbook_ready()
    print("Services are ready!")


@pytest.fixture
def orderbook_client(orderbook_api_url: str) -> Any:
    """
    HTTP client for orderbook API.

    Returns a synchronous wrapper around the async OrderbookClient for compatibility
    with existing synchronous tests.
    """
    import asyncio

    from cow_performance.api import OrderbookClient as AsyncOrderbookClient

    class SyncOrderbookClientWrapper:
        """Synchronous wrapper for async OrderbookClient."""

        def __init__(self, base_url: str):
            self.async_client = AsyncOrderbookClient(base_url, timeout=10)

        def submit_order(self, signed_order: dict) -> dict:
            """Submit a signed order to the orderbook."""
            return asyncio.run(self.async_client.submit_order(signed_order))

        def get_order(self, order_uid: str) -> dict:
            """Get order details by UID."""
            return asyncio.run(self.async_client.get_order(order_uid))

        def get_trades(self, order_uid: str) -> list[dict]:
            """Get trades for an order."""
            return asyncio.run(self.async_client.get_trades(order_uid))

        def upload_app_data(self, app_data_hash: str, app_data_doc: str | dict) -> dict:
            """Upload appData document to the orderbook."""
            return asyncio.run(self.async_client.upload_app_data(app_data_hash, app_data_doc))

    return SyncOrderbookClientWrapper(orderbook_api_url)
