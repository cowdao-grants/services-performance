"""
Handler address registry for ComposableCow conditional orders.

This module provides handler contract addresses for different order types
on Ethereum mainnet. Additional networks can be added to the registry as needed.
"""

from web3 import Web3

# Mainnet handler addresses (Ethereum mainnet - chain ID 1)
MAINNET_HANDLERS: dict[str, str] = {
    "twap": "0x6cF1e9cA41f7611dEf408122793c358a3d11E5a5",
    "stop_loss": "0x412c36e5011cd2517016d243a2dfb37f73a242e7",
    "good_after_time": "0xdaf33924925e03c9cc3a10d434016d6cfad0add5",
}

# Mainnet ComposableCow address
MAINNET_COMPOSABLE_COW = "0xfdaFc9d1902f4e0b84f65F49f244b32b31013b74"

# Network registry - expandable for future networks
HANDLER_REGISTRY: dict[int, dict[str, str]] = {
    1: MAINNET_HANDLERS,  # Ethereum Mainnet
}

COMPOSABLE_COW_REGISTRY: dict[int, str] = {
    1: MAINNET_COMPOSABLE_COW,
}


def get_handler_address(handler_type: str, chain_id: int) -> str:
    """
    Get handler contract address for a specific order type and network.

    Args:
        handler_type: Type of handler ("twap", "stop_loss", "good_after_time")
        chain_id: Chain ID (1 for mainnet, 11155111 for Sepolia, etc.)

    Returns:
        Checksummed handler contract address

    Raises:
        ValueError: If handler type or chain ID is not supported
    """
    if chain_id not in HANDLER_REGISTRY:
        raise ValueError(
            f"Unsupported chain ID: {chain_id}. "
            f"Supported chains: {list(HANDLER_REGISTRY.keys())}"
        )

    handlers = HANDLER_REGISTRY[chain_id]

    if handler_type not in handlers:
        raise ValueError(
            f"Unknown handler type: {handler_type}. " f"Supported types: {list(handlers.keys())}"
        )

    address = handlers[handler_type]
    return Web3.to_checksum_address(address)


def get_composable_cow_address(chain_id: int) -> str:
    """
    Get ComposableCow contract address for a specific network.

    Args:
        chain_id: Chain ID (1 for mainnet, 11155111 for Sepolia, etc.)

    Returns:
        Checksummed ComposableCow contract address

    Raises:
        ValueError: If chain ID is not supported
    """
    if chain_id not in COMPOSABLE_COW_REGISTRY:
        raise ValueError(
            f"Unsupported chain ID: {chain_id}. "
            f"Supported chains: {list(COMPOSABLE_COW_REGISTRY.keys())}"
        )

    address = COMPOSABLE_COW_REGISTRY[chain_id]
    return Web3.to_checksum_address(address)


def get_supported_handler_types() -> list[str]:
    """
    Get list of supported handler types.

    Returns:
        List of supported handler type strings
    """
    # Return handler types from mainnet (all chains have the same types)
    return list(MAINNET_HANDLERS.keys())


def get_supported_chain_ids() -> list[int]:
    """
    Get list of supported chain IDs.

    Returns:
        List of supported chain IDs
    """
    return list(HANDLER_REGISTRY.keys())
