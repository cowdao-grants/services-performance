"""
Oracle address registry for conditional orders.

This module provides Chainlink oracle addresses used by stop-loss orders
to determine when price conditions are met on Ethereum mainnet.
Additional networks can be added to the registry as needed.
"""

from web3 import Web3

# Mainnet Chainlink oracle addresses (Ethereum mainnet - chain ID 1)
# These oracles provide USD prices for various tokens
MAINNET_ORACLES: dict[str, str] = {
    "WETH": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",  # ETH/USD
    "DAI": "0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9",  # DAI/USD
    "USDC": "0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6",  # USDC/USD
    "USDT": "0x3E7d1eAB13ad0104d2750B8863b489D65364e32D",  # USDT/USD
    "WBTC": "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",  # BTC/USD
    "LINK": "0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c",  # LINK/USD
    "UNI": "0x553303d460EE0afB37EdFf9bE42922D8FF63220e",  # UNI/USD
    "AAVE": "0x547a514d5e3769680Ce22B2361c10Ea13619e8a9",  # AAVE/USD
}

# Network registry - expandable for future networks
ORACLE_REGISTRY: dict[int, dict[str, str]] = {
    1: MAINNET_ORACLES,  # Ethereum Mainnet
}


class OracleRegistry:
    """
    Registry for Chainlink price oracle addresses.

    This class provides methods to retrieve oracle addresses for specific
    tokens on different networks. Oracles are used by stop-loss orders
    to determine when price conditions are met.
    """

    def __init__(self, chain_id: int):
        """
        Initialize the oracle registry for a specific chain.

        Args:
            chain_id: Chain ID (1 for mainnet, 11155111 for Sepolia, etc.)

        Raises:
            ValueError: If chain ID is not supported
        """
        self.chain_id = chain_id

        if chain_id not in ORACLE_REGISTRY:
            raise ValueError(
                f"Unsupported chain ID: {chain_id}. "
                f"Supported chains: {list(ORACLE_REGISTRY.keys())}"
            )

        self.oracles = ORACLE_REGISTRY[chain_id]

    def get_oracle_for_token(self, token_symbol: str) -> str:
        """
        Get Chainlink oracle address for a specific token.

        Args:
            token_symbol: Token symbol (e.g., "WETH", "USDC", "DAI")

        Returns:
            Checksummed oracle contract address

        Raises:
            ValueError: If token symbol is not found
        """
        if token_symbol not in self.oracles:
            raise ValueError(
                f"No oracle found for token: {token_symbol}. "
                f"Available tokens: {list(self.oracles.keys())}"
            )

        address = self.oracles[token_symbol]
        return Web3.to_checksum_address(address)

    def get_oracle_for_token_address(self, token_address: str) -> str | None:
        """
        Get oracle address by token address (if available).

        This is a convenience method that attempts to find an oracle
        by matching token addresses from a known token registry.

        Args:
            token_address: Token contract address

        Returns:
            Oracle address if found, None otherwise
        """
        # This is a simplified implementation
        # In a production system, you'd maintain a mapping of token addresses to oracles
        token_address = Web3.to_checksum_address(token_address)

        # For now, return None as we don't have a comprehensive address mapping
        # Users should use get_oracle_for_token() with the symbol instead
        return None

    def has_oracle_for_token(self, token_symbol: str) -> bool:
        """
        Check if an oracle exists for a given token.

        Args:
            token_symbol: Token symbol (e.g., "WETH", "USDC")

        Returns:
            True if oracle exists, False otherwise
        """
        return token_symbol in self.oracles

    def get_available_tokens(self) -> list[str]:
        """
        Get list of tokens with available oracles.

        Returns:
            List of token symbols
        """
        return list(self.oracles.keys())

    def get_all_oracles(self) -> dict[str, str]:
        """
        Get all oracle addresses for the current chain.

        Returns:
            Dictionary mapping token symbols to oracle addresses
        """
        return {
            symbol: Web3.to_checksum_address(address) for symbol, address in self.oracles.items()
        }


def get_oracle_address(token_symbol: str, chain_id: int) -> str:
    """
    Convenience function to get oracle address for a token on a specific chain.

    Args:
        token_symbol: Token symbol (e.g., "WETH", "USDC")
        chain_id: Chain ID

    Returns:
        Checksummed oracle contract address

    Raises:
        ValueError: If token or chain is not supported
    """
    registry = OracleRegistry(chain_id)
    return registry.get_oracle_for_token(token_symbol)


def get_supported_oracle_chains() -> list[int]:
    """
    Get list of chain IDs with oracle support.

    Returns:
        List of supported chain IDs
    """
    return list(ORACLE_REGISTRY.keys())
