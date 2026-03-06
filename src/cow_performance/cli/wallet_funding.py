"""Wallet funding utilities for Anvil fork mode.

This module provides functionality to fund trader wallets with ETH and tokens
before running performance tests. This requires Anvil running in fork mode.
"""

from typing import Any

from eth_account.signers.local import LocalAccount
from web3 import Web3

from cow_performance.load_generation import TraderPool

# Token addresses on mainnet
TOKEN_ADDRESSES = {
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "GNO": "0x6810e776880C02933D47DB1b9fc05908e5386b96",
}

# Storage slot positions for balanceOf mappings
TOKEN_BALANCE_SLOTS = {
    "WETH": 3,
    "DAI": 2,
    "USDC": 9,
    "USDT": 2,
    "GNO": 0,
}

# ERC20 ABI for approve function
ERC20_ABI = [
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
]


def fund_wallet_with_eth(web3: Web3, wallet_address: str, amount_eth: float) -> None:
    """Fund a wallet with ETH from Anvil's default account.

    Args:
        web3: Web3 instance connected to Anvil
        wallet_address: Address to fund
        amount_eth: Amount of ETH to send

    Raises:
        ValueError: If funding fails
    """
    # Get Anvil's default account (has plenty of ETH)
    default_account = web3.eth.accounts[0]

    # Send ETH
    tx_hash = web3.eth.send_transaction(
        {
            "from": default_account,
            "to": wallet_address,
            "value": web3.to_wei(amount_eth, "ether"),
        }
    )
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt["status"] != 1:
        raise ValueError(f"Failed to fund wallet {wallet_address} with ETH")


def fund_wallet_with_token(
    web3: Web3, wallet_address: str, token_symbol: str, amount: float
) -> None:
    """Fund a wallet with ERC20 tokens using Anvil's storage manipulation.

    This directly sets the balance in the token contract's storage, which works
    in Anvil fork mode.

    Args:
        web3: Web3 instance connected to Anvil
        wallet_address: Address to fund
        token_symbol: Token symbol (WETH, DAI, USDC, USDT, or GNO)
        amount: Amount of tokens (in standard units, e.g., 10.0 for 10 DAI)

    Raises:
        ValueError: If token is not supported or funding fails
    """
    if token_symbol not in TOKEN_ADDRESSES:
        supported = ", ".join(TOKEN_ADDRESSES.keys())
        raise ValueError(f"Unsupported token: {token_symbol}. Supported: {supported}")

    token_address = TOKEN_ADDRESSES[token_symbol]
    balance_slot = TOKEN_BALANCE_SLOTS[token_symbol]

    # Convert amount to token's smallest unit based on decimals
    if token_symbol in ("USDC", "USDT"):
        amount_wei = int(amount * 10**6)  # USDC and USDT have 6 decimals
    else:
        amount_wei = int(amount * 10**18)  # WETH, DAI, and GNO have 18 decimals

    # Calculate storage slot for the wallet's balance
    # mapping(address => uint256) balanceOf -> slot = keccak256(address || slot)
    wallet_address_padded = wallet_address.lower().replace("0x", "").zfill(64)
    slot_padded = hex(balance_slot)[2:].zfill(64)
    storage_key = web3.keccak(bytes.fromhex(wallet_address_padded + slot_padded))

    # Convert amount to hex (32 bytes)
    amount_hex = hex(amount_wei)[2:].zfill(64)

    # Set the storage value using Anvil's anvil_setStorageAt
    web3.provider.make_request("anvil_setStorageAt", [token_address, storage_key.hex(), f"0x{amount_hex}"])  # type: ignore[arg-type]


def approve_token(
    web3: Web3, trader_account: LocalAccount, token_symbol: str, spender: str, amount: float
) -> None:
    """Approve a spender to use tokens.

    Args:
        web3: Web3 instance
        trader_account: The trader's eth_account.Account instance
        token_symbol: Token symbol (WETH, DAI, USDC, USDT, or GNO)
        spender: Address to approve (usually VaultRelayer)
        amount: Amount to approve (in standard units)

    Raises:
        ValueError: If token is not supported or approval fails
    """
    if token_symbol not in TOKEN_ADDRESSES:
        supported = ", ".join(TOKEN_ADDRESSES.keys())
        raise ValueError(f"Unsupported token: {token_symbol}. Supported: {supported}")

    token_address = TOKEN_ADDRESSES[token_symbol]

    # Convert amount to token's smallest unit based on decimals
    if token_symbol in ("USDC", "USDT"):
        amount_wei = int(amount * 10**6)  # USDC and USDT have 6 decimals
    else:
        amount_wei = int(amount * 10**18)  # WETH, DAI, and GNO have 18 decimals

    # Create contract instance
    token_contract = web3.eth.contract(
        address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
    )

    # Build transaction
    nonce = web3.eth.get_transaction_count(trader_account.address)
    tx = token_contract.functions.approve(spender, amount_wei).build_transaction(
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
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt["status"] != 1:
        raise ValueError(
            f"Failed to approve {token_symbol} for {spender} from {trader_account.address}"
        )


def fund_trader_pool(
    web3: Web3,
    trader_pool: TraderPool,
    eth_balance: float,
    token_balances: dict[str, float],
    vault_relayer: str,
) -> None:
    """Fund all traders in a pool with ETH and tokens.

    Args:
        web3: Web3 instance connected to Anvil
        trader_pool: Pool of traders to fund
        eth_balance: ETH amount per trader
        token_balances: Dict of token symbol to amount per trader
        vault_relayer: VaultRelayer address for approvals

    Raises:
        ValueError: If funding or approval fails
    """
    for trader in trader_pool.get_all_traders():
        # Fund with ETH
        if eth_balance > 0:
            fund_wallet_with_eth(web3, trader.address, eth_balance)

        # Fund with tokens and approve
        for token_symbol, amount in token_balances.items():
            if amount > 0:
                # Fund wallet with tokens
                fund_wallet_with_token(web3, trader.address, token_symbol, amount)

                # Approve VaultRelayer to spend tokens (approve 10x the amount)
                trader_account = trader.get_account()
                approve_token(web3, trader_account, token_symbol, vault_relayer, amount * 10)


def create_trader_pool_from_config(
    wallet_config: Any,  # WalletConfig type
    num_traders: int,
) -> TraderPool:
    """Create a trader pool based on wallet configuration.

    Args:
        wallet_config: Wallet configuration object
        num_traders: Number of traders needed (from orchestration config)

    Returns:
        TraderPool with the specified traders

    Raises:
        ValueError: If configuration is invalid
    """
    # If private keys are specified, use them
    if wallet_config.private_keys:
        if len(wallet_config.private_keys) < num_traders:
            raise ValueError(
                f"Not enough private keys provided: need {num_traders}, got {len(wallet_config.private_keys)}"
            )
        # Use first num_traders keys
        private_keys = wallet_config.private_keys[:num_traders]
        return TraderPool(num_traders=num_traders, private_keys=private_keys)

    # If generate_count is specified and > 0, generate that many
    if wallet_config.generate_count > 0:
        actual_count = min(wallet_config.generate_count, num_traders)
        return TraderPool(num_traders=actual_count)

    # Otherwise, use default generation
    return TraderPool(num_traders=num_traders)
