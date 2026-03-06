"""
ComposableCow contract interaction for submitting conditional orders.

This module provides functions to submit TWAP, Stop-Loss, and Good-After-Time
orders to the ComposableCow contract on-chain.
"""

from typing import Any, cast

from web3 import Web3
from web3.types import HexStr

from .conditional_order_schema import ConditionalOrder
from .safe_wallet import SafeWallet

# ComposableCow contract ABI (minimal - just what we need)
COMPOSABLE_COW_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "handler", "type": "address"},
                    {"name": "salt", "type": "bytes32"},
                    {"name": "staticInput", "type": "bytes"},
                ],
                "name": "params",
                "type": "tuple",
            },
            {"name": "dispatch", "type": "bool"},
        ],
        "name": "create",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {
                "components": [
                    {"name": "handler", "type": "address"},
                    {"name": "salt", "type": "bytes32"},
                    {"name": "staticInput", "type": "bytes"},
                ],
                "name": "params",
                "type": "tuple",
            },
        ],
        "name": "getTradeableOrderWithSignature",
        "outputs": [
            {
                "components": [
                    {"name": "sellToken", "type": "address"},
                    {"name": "buyToken", "type": "address"},
                    {"name": "receiver", "type": "address"},
                    {"name": "sellAmount", "type": "uint256"},
                    {"name": "buyAmount", "type": "uint256"},
                    {"name": "validTo", "type": "uint32"},
                    {"name": "appData", "type": "bytes32"},
                    {"name": "feeAmount", "type": "uint256"},
                    {"name": "kind", "type": "bytes32"},
                    {"name": "partiallyFillable", "type": "bool"},
                    {"name": "sellTokenBalance", "type": "bytes32"},
                    {"name": "buyTokenBalance", "type": "bytes32"},
                ],
                "name": "order",
                "type": "tuple",
            },
            {"name": "signature", "type": "bytes"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {
                "components": [
                    {"name": "handler", "type": "address"},
                    {"name": "salt", "type": "bytes32"},
                    {"name": "staticInput", "type": "bytes"},
                ],
                "name": "params",
                "type": "tuple",
            },
        ],
        "name": "remove",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


def submit_conditional_order(
    web3: Web3,
    composable_cow_address: str,
    safe_wallet: SafeWallet,
    conditional_order: ConditionalOrder,
    dispatch: bool = True,
) -> bytes:
    """
    Submit a conditional order to ComposableCow contract.

    This function executes a Safe transaction to call ComposableCow.create(),
    which registers the conditional order for watch-tower monitoring.

    Args:
        web3: Web3 instance
        composable_cow_address: ComposableCow contract address
        safe_wallet: Safe wallet that owns the order
        conditional_order: The conditional order to submit (TWAP, Stop-Loss, etc.)
        dispatch: If True, immediately dispatch the order (default: True)

    Returns:
        Transaction hash of the Safe transaction

    Raises:
        ValueError: If order owner doesn't match Safe wallet address
    """
    # Verify order owner matches Safe wallet
    if conditional_order.owner.lower() != safe_wallet.address.lower():
        raise ValueError(
            f"Order owner {conditional_order.owner} does not match "
            f"Safe wallet {safe_wallet.address}"
        )

    # Get ComposableCow contract
    composable_cow = web3.eth.contract(
        address=Web3.to_checksum_address(composable_cow_address),
        abi=COMPOSABLE_COW_ABI,
    )

    # Encode the create() call
    create_call_data = composable_cow.encodeABI(
        fn_name="create",
        args=[
            {
                "handler": Web3.to_checksum_address(conditional_order.params.handler),
                "salt": Web3.to_bytes(hexstr=cast(HexStr, conditional_order.params.salt)),
                "staticInput": Web3.to_bytes(
                    hexstr=cast(HexStr, conditional_order.params.staticInput)
                ),
            },
            dispatch,
        ],
    )

    # Execute via Safe wallet
    tx_hash = safe_wallet.exec_transaction(
        to=composable_cow_address,
        value=0,
        data=create_call_data,
        operation=0,  # CALL
    )

    return tx_hash


def get_tradeable_order(
    web3: Web3,
    composable_cow_address: str,
    owner: str,
    conditional_order_params: dict[str, Any],
) -> tuple[dict[str, Any], bytes] | None:
    """
    Get the current tradeable order for a conditional order.

    This queries ComposableCow to see if the conditional order is currently
    tradeable (i.e., conditions are met).

    Args:
        web3: Web3 instance
        composable_cow_address: ComposableCow contract address
        owner: Owner address (Safe wallet)
        conditional_order_params: Conditional order parameters (handler, salt, staticInput)

    Returns:
        Tuple of (order, signature) if tradeable, None otherwise
    """
    composable_cow = web3.eth.contract(
        address=Web3.to_checksum_address(composable_cow_address),
        abi=COMPOSABLE_COW_ABI,
    )

    try:
        result = composable_cow.functions.getTradeableOrderWithSignature(
            Web3.to_checksum_address(owner),
            {
                "handler": Web3.to_checksum_address(conditional_order_params["handler"]),
                "salt": Web3.to_bytes(hexstr=cast(HexStr, conditional_order_params["salt"])),
                "staticInput": Web3.to_bytes(
                    hexstr=cast(HexStr, conditional_order_params["staticInput"])
                ),
            },
        ).call()

        # result is (order, signature)
        if result:
            order, signature = result
            return (order, signature)
    except Exception:
        # Order not tradeable or doesn't exist
        return None

    return None


def remove_conditional_order(
    web3: Web3,
    composable_cow_address: str,
    safe_wallet: SafeWallet,
    conditional_order_params: dict[str, Any],
) -> bytes:
    """
    Remove a conditional order from ComposableCow.

    Args:
        web3: Web3 instance
        composable_cow_address: ComposableCow contract address
        safe_wallet: Safe wallet that owns the order
        conditional_order_params: Conditional order parameters to remove

    Returns:
        Transaction hash of the Safe transaction
    """
    composable_cow = web3.eth.contract(
        address=Web3.to_checksum_address(composable_cow_address),
        abi=COMPOSABLE_COW_ABI,
    )

    # Encode the remove() call
    remove_call_data = composable_cow.encodeABI(
        fn_name="remove",
        args=[
            Web3.to_checksum_address(safe_wallet.address),
            {
                "handler": Web3.to_checksum_address(conditional_order_params["handler"]),
                "salt": Web3.to_bytes(hexstr=cast(HexStr, conditional_order_params["salt"])),
                "staticInput": Web3.to_bytes(
                    hexstr=cast(HexStr, conditional_order_params["staticInput"])
                ),
            },
        ],
    )

    # Execute via Safe wallet
    tx_hash = safe_wallet.exec_transaction(
        to=composable_cow_address,
        value=0,
        data=remove_call_data,
        operation=0,  # CALL
    )

    return tx_hash
