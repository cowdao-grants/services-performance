"""
Token pair management for order generation.

This module provides data structures and utilities for managing token pairs,
including token metadata (address, decimals, symbol) and selection strategies.
"""

import random
from dataclasses import dataclass

from web3 import Web3


@dataclass
class Token:
    """
    Represents an ERC-20 token with its metadata.

    Attributes:
        address: Ethereum address of the token contract
        symbol: Token symbol (e.g., "WETH", "DAI")
        decimals: Number of decimal places for the token
    """

    address: str
    symbol: str
    decimals: int

    def __post_init__(self) -> None:
        """Validate token address after initialization."""
        if not Web3.is_address(self.address):
            raise ValueError(f"Invalid token address: {self.address}")
        self.address = Web3.to_checksum_address(self.address)

    def to_wei(self, amount: float) -> int:
        """
        Convert a decimal amount to wei.

        Args:
            amount: Amount in decimal form (e.g., 1.5 for 1.5 tokens)

        Returns:
            Amount in wei (smallest unit)
        """
        return int(amount * (10**self.decimals))

    def from_wei(self, amount: int) -> float:
        """
        Convert wei amount to decimal.

        Args:
            amount: Amount in wei

        Returns:
            Amount in decimal form
        """
        result: float = float(amount) / (10**self.decimals)
        return result


@dataclass
class TokenPair:
    """
    Represents a trading pair of two tokens.

    Attributes:
        sell_token: Token to sell
        buy_token: Token to buy
        weight: Weight for weighted random selection (default: 1.0)
    """

    sell_token: Token
    buy_token: Token
    weight: float = 1.0

    def __post_init__(self) -> None:
        """Validate token pair after initialization."""
        if self.sell_token.address == self.buy_token.address:
            raise ValueError("Cannot create token pair with same sell and buy token")
        if self.weight <= 0:
            raise ValueError("Token pair weight must be positive")

    def reverse(self) -> "TokenPair":
        """
        Create a reversed token pair (swap buy and sell tokens).

        Returns:
            New TokenPair with swapped tokens
        """
        return TokenPair(
            sell_token=self.buy_token,
            buy_token=self.sell_token,
            weight=self.weight,
        )

    def __str__(self) -> str:
        """String representation of the token pair."""
        return f"{self.sell_token.symbol}/{self.buy_token.symbol}"


class TokenPairRegistry:
    """
    Registry for managing available token pairs and selection strategies.

    This class provides methods for storing, retrieving, and selecting token pairs
    using different strategies (random, weighted, sequential).
    """

    def __init__(self, token_pairs: list[TokenPair] | None = None) -> None:
        """
        Initialize the token pair registry.

        Args:
            token_pairs: List of token pairs to register (default: empty list)
        """
        self._pairs: list[TokenPair] = token_pairs or []
        self._index = 0

    def add_pair(self, pair: TokenPair) -> None:
        """
        Add a token pair to the registry.

        Args:
            pair: Token pair to add
        """
        self._pairs.append(pair)

    def get_all_pairs(self) -> list[TokenPair]:
        """
        Get all registered token pairs.

        Returns:
            List of all token pairs
        """
        return self._pairs.copy()

    def select_random(self) -> TokenPair:
        """
        Select a random token pair.

        Returns:
            Randomly selected token pair

        Raises:
            ValueError: If no token pairs are registered
        """
        if not self._pairs:
            raise ValueError("No token pairs registered")
        return random.choice(self._pairs)

    def select_weighted_random(self) -> TokenPair:
        """
        Select a token pair using weighted random selection.

        Pairs with higher weights are more likely to be selected.

        Returns:
            Randomly selected token pair based on weights

        Raises:
            ValueError: If no token pairs are registered
        """
        if not self._pairs:
            raise ValueError("No token pairs registered")

        weights = [pair.weight for pair in self._pairs]
        return random.choices(self._pairs, weights=weights, k=1)[0]

    def select_sequential(self) -> TokenPair:
        """
        Select token pairs sequentially (round-robin).

        Returns:
            Next token pair in sequence

        Raises:
            ValueError: If no token pairs are registered
        """
        if not self._pairs:
            raise ValueError("No token pairs registered")

        pair = self._pairs[self._index]
        self._index = (self._index + 1) % len(self._pairs)
        return pair

    def get_pair_by_symbols(self, sell_symbol: str, buy_symbol: str) -> TokenPair | None:
        """
        Get a token pair by token symbols.

        Args:
            sell_symbol: Symbol of the sell token
            buy_symbol: Symbol of the buy token

        Returns:
            Token pair if found, None otherwise
        """
        for pair in self._pairs:
            if pair.sell_token.symbol == sell_symbol and pair.buy_token.symbol == buy_symbol:
                return pair
        return None

    def __len__(self) -> int:
        """Get number of registered token pairs."""
        return len(self._pairs)


def create_mainnet_token_registry() -> TokenPairRegistry:
    """
    Create a token pair registry with common Ethereum mainnet pairs.

    Optimized for liquidity on UniswapV2 - focuses on pairs with deep liquidity
    to ensure baseline solver can find solutions.

    Returns:
        TokenPairRegistry with pre-configured mainnet token pairs
    """
    # Define mainnet tokens
    weth = Token(
        address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        symbol="WETH",
        decimals=18,
    )
    dai = Token(
        address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
        symbol="DAI",
        decimals=18,
    )
    usdc = Token(
        address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        symbol="USDC",
        decimals=6,
    )
    usdt = Token(
        address="0xdAC17F958D2ee523a2206206994597C13D831ec7",
        symbol="USDT",
        decimals=6,
    )

    # Create token pairs with weights optimized for baseline solver
    # Only include pairs with deep liquidity on UniswapV2
    pairs = [
        # WETH pairs (highest weight - most liquid)
        TokenPair(sell_token=weth, buy_token=dai, weight=5.0),
        TokenPair(sell_token=dai, buy_token=weth, weight=5.0),
        TokenPair(sell_token=weth, buy_token=usdc, weight=5.0),
        TokenPair(sell_token=usdc, buy_token=weth, weight=5.0),
        TokenPair(sell_token=weth, buy_token=usdt, weight=4.0),
        TokenPair(sell_token=usdt, buy_token=weth, weight=4.0),
        # Stablecoin pairs (medium-high weight - very liquid)
        TokenPair(sell_token=dai, buy_token=usdc, weight=4.0),
        TokenPair(sell_token=usdc, buy_token=dai, weight=4.0),
        TokenPair(sell_token=dai, buy_token=usdt, weight=3.0),
        TokenPair(sell_token=usdt, buy_token=dai, weight=3.0),
        TokenPair(sell_token=usdc, buy_token=usdt, weight=3.0),
        TokenPair(sell_token=usdt, buy_token=usdc, weight=3.0),
    ]

    return TokenPairRegistry(token_pairs=pairs)


def create_polygon_token_registry() -> TokenPairRegistry:
    """
    Create a token pair registry with common Polygon pairs.

    Returns:
        TokenPairRegistry with pre-configured Polygon token pairs
    """
    # Define Polygon tokens
    wmatic = Token(
        address="0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        symbol="WMATIC",
        decimals=18,
    )
    dai = Token(
        address="0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
        symbol="DAI",
        decimals=18,
    )
    usdc = Token(
        address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        symbol="USDC",
        decimals=6,
    )
    usdt = Token(
        address="0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        symbol="USDT",
        decimals=6,
    )

    # Create token pairs
    pairs = [
        TokenPair(sell_token=wmatic, buy_token=dai, weight=3.0),
        TokenPair(sell_token=dai, buy_token=wmatic, weight=3.0),
        TokenPair(sell_token=wmatic, buy_token=usdc, weight=3.0),
        TokenPair(sell_token=usdc, buy_token=wmatic, weight=3.0),
        TokenPair(sell_token=dai, buy_token=usdc, weight=2.0),
        TokenPair(sell_token=usdc, buy_token=dai, weight=2.0),
        TokenPair(sell_token=dai, buy_token=usdt, weight=2.0),
        TokenPair(sell_token=usdt, buy_token=dai, weight=2.0),
    ]

    return TokenPairRegistry(token_pairs=pairs)
