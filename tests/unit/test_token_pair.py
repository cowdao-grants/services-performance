"""Unit tests for token pair management."""

import random

import pytest

from cow_performance.load_generation.token_pair import (
    Token,
    TokenPair,
    TokenPairRegistry,
    create_mainnet_token_registry,
)


@pytest.fixture(autouse=True)
def deterministic_random():
    """Set random seed for deterministic order generation."""
    random.seed(42)
    yield


class TestToken:
    """Tests for Token class."""

    def test_token_creation(self) -> None:
        """Test creating a valid token."""
        token = Token(
            address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            symbol="WETH",
            decimals=18,
        )
        assert token.symbol == "WETH"
        assert token.decimals == 18
        # Address should be checksummed
        assert token.address == "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    def test_token_invalid_address(self) -> None:
        """Test token creation with invalid address."""
        with pytest.raises(ValueError, match="Invalid token address"):
            Token(
                address="invalid",
                symbol="WETH",
                decimals=18,
            )

    def test_to_wei(self) -> None:
        """Test converting decimal amount to wei."""
        token = Token(
            address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            symbol="WETH",
            decimals=18,
        )
        assert token.to_wei(1.0) == 10**18
        assert token.to_wei(0.5) == 5 * 10**17
        assert token.to_wei(2.5) == 25 * 10**17

    def test_to_wei_usdc(self) -> None:
        """Test converting USDC amount to wei (6 decimals)."""
        usdc = Token(
            address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            symbol="USDC",
            decimals=6,
        )
        assert usdc.to_wei(1.0) == 10**6
        assert usdc.to_wei(100.0) == 100 * 10**6

    def test_from_wei(self) -> None:
        """Test converting wei to decimal amount."""
        token = Token(
            address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            symbol="WETH",
            decimals=18,
        )
        assert token.from_wei(10**18) == 1.0
        assert token.from_wei(5 * 10**17) == 0.5


class TestTokenPair:
    """Tests for TokenPair class."""

    @pytest.fixture
    def weth(self) -> Token:
        """Create WETH token."""
        return Token(
            address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            symbol="WETH",
            decimals=18,
        )

    @pytest.fixture
    def dai(self) -> Token:
        """Create DAI token."""
        return Token(
            address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
            symbol="DAI",
            decimals=18,
        )

    def test_token_pair_creation(self, weth: Token, dai: Token) -> None:
        """Test creating a valid token pair."""
        pair = TokenPair(sell_token=weth, buy_token=dai, weight=1.0)
        assert pair.sell_token.symbol == "WETH"
        assert pair.buy_token.symbol == "DAI"
        assert pair.weight == 1.0

    def test_token_pair_same_tokens(self, weth: Token) -> None:
        """Test creating pair with same token fails."""
        with pytest.raises(ValueError, match="Cannot create token pair with same"):
            TokenPair(sell_token=weth, buy_token=weth)

    def test_token_pair_invalid_weight(self, weth: Token, dai: Token) -> None:
        """Test creating pair with invalid weight fails."""
        with pytest.raises(ValueError, match="weight must be positive"):
            TokenPair(sell_token=weth, buy_token=dai, weight=0)

        with pytest.raises(ValueError, match="weight must be positive"):
            TokenPair(sell_token=weth, buy_token=dai, weight=-1)

    def test_token_pair_reverse(self, weth: Token, dai: Token) -> None:
        """Test reversing a token pair."""
        pair = TokenPair(sell_token=weth, buy_token=dai, weight=2.0)
        reversed_pair = pair.reverse()

        assert reversed_pair.sell_token.symbol == "DAI"
        assert reversed_pair.buy_token.symbol == "WETH"
        assert reversed_pair.weight == 2.0

    def test_token_pair_str(self, weth: Token, dai: Token) -> None:
        """Test string representation of token pair."""
        pair = TokenPair(sell_token=weth, buy_token=dai)
        assert str(pair) == "WETH/DAI"


class TestTokenPairRegistry:
    """Tests for TokenPairRegistry class."""

    @pytest.fixture
    def weth(self) -> Token:
        """Create WETH token."""
        return Token(
            address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            symbol="WETH",
            decimals=18,
        )

    @pytest.fixture
    def dai(self) -> Token:
        """Create DAI token."""
        return Token(
            address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
            symbol="DAI",
            decimals=18,
        )

    @pytest.fixture
    def usdc(self) -> Token:
        """Create USDC token."""
        return Token(
            address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            symbol="USDC",
            decimals=6,
        )

    def test_empty_registry(self) -> None:
        """Test creating empty registry."""
        registry = TokenPairRegistry()
        assert len(registry) == 0

    def test_add_pair(self, weth: Token, dai: Token) -> None:
        """Test adding pair to registry."""
        registry = TokenPairRegistry()
        pair = TokenPair(sell_token=weth, buy_token=dai)
        registry.add_pair(pair)

        assert len(registry) == 1
        pairs = registry.get_all_pairs()
        assert len(pairs) == 1
        assert pairs[0].sell_token.symbol == "WETH"

    def test_select_random_empty(self) -> None:
        """Test selecting from empty registry fails."""
        registry = TokenPairRegistry()
        with pytest.raises(ValueError, match="No token pairs registered"):
            registry.select_random()

    def test_select_random(self, weth: Token, dai: Token, usdc: Token) -> None:
        """Test random selection."""
        registry = TokenPairRegistry()
        registry.add_pair(TokenPair(sell_token=weth, buy_token=dai))
        registry.add_pair(TokenPair(sell_token=dai, buy_token=usdc))

        # Should return one of the pairs
        pair = registry.select_random()
        assert pair.sell_token.symbol in ("WETH", "DAI")

    def test_select_weighted_random(self, weth: Token, dai: Token) -> None:
        """Test weighted random selection."""
        registry = TokenPairRegistry()
        registry.add_pair(TokenPair(sell_token=weth, buy_token=dai, weight=1.0))

        pair = registry.select_weighted_random()
        assert pair.sell_token.symbol == "WETH"

    def test_select_sequential(self, weth: Token, dai: Token, usdc: Token) -> None:
        """Test sequential selection."""
        registry = TokenPairRegistry()
        pair1 = TokenPair(sell_token=weth, buy_token=dai)
        pair2 = TokenPair(sell_token=dai, buy_token=usdc)
        registry.add_pair(pair1)
        registry.add_pair(pair2)

        # Should cycle through pairs
        assert registry.select_sequential().sell_token.symbol == "WETH"
        assert registry.select_sequential().sell_token.symbol == "DAI"
        assert registry.select_sequential().sell_token.symbol == "WETH"

    def test_get_pair_by_symbols(self, weth: Token, dai: Token, usdc: Token) -> None:
        """Test getting pair by symbols."""
        registry = TokenPairRegistry()
        registry.add_pair(TokenPair(sell_token=weth, buy_token=dai))
        registry.add_pair(TokenPair(sell_token=dai, buy_token=usdc))

        pair = registry.get_pair_by_symbols("WETH", "DAI")
        assert pair is not None
        assert pair.sell_token.symbol == "WETH"
        assert pair.buy_token.symbol == "DAI"

        # Non-existent pair
        pair = registry.get_pair_by_symbols("WETH", "USDC")
        assert pair is None


class TestMainnetRegistry:
    """Tests for mainnet token registry."""

    def test_create_mainnet_registry(self) -> None:
        """Test creating mainnet registry."""
        registry = create_mainnet_token_registry()

        # Should have multiple pairs
        assert len(registry) > 0

        # Should be able to select pairs
        pair = registry.select_random()
        assert pair.sell_token.symbol in ("WETH", "DAI", "USDC", "USDT", "GNO")

    def test_mainnet_registry_has_weth_dai(self) -> None:
        """Test mainnet registry has WETH/DAI pair."""
        registry = create_mainnet_token_registry()
        pair = registry.get_pair_by_symbols("WETH", "DAI")
        assert pair is not None
        assert pair.sell_token.symbol == "WETH"
        assert pair.buy_token.symbol == "DAI"
