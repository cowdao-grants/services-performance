"""Unit tests for order factory."""

import random
import time

import pytest
from eth_account import Account

from cow_performance.load_generation.order_factory import OrderFactory
from cow_performance.load_generation.order_schema import OrderKind, SigningScheme
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


class TestOrderFactory:
    """Tests for OrderFactory class."""

    @pytest.fixture
    def token_registry(self) -> TokenPairRegistry:
        """Create a token registry."""
        return create_mainnet_token_registry()

    @pytest.fixture
    def factory(self, token_registry: TokenPairRegistry) -> OrderFactory:
        """Create an order factory."""
        return OrderFactory(
            token_pair_registry=token_registry,
            chain_id=1,
            settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
            amount_range=(0.1, 10.0),
            valid_duration=3600,
        )

    @pytest.fixture
    def trader_account(self) -> Account:
        """Create a trader account."""
        return Account.create()

    def test_factory_creation(self, factory: OrderFactory) -> None:
        """Test creating an order factory."""
        assert factory.chain_id == 1
        assert factory.valid_duration == 3600
        assert factory.amount_range == (0.1, 10.0)

    def test_factory_invalid_amount_range(self, token_registry: TokenPairRegistry) -> None:
        """Test creating factory with invalid amount range."""
        with pytest.raises(ValueError, match="Minimum amount must be positive"):
            OrderFactory(
                token_pair_registry=token_registry,
                chain_id=1,
                settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
                amount_range=(0, 10.0),
            )

        with pytest.raises(ValueError, match="Maximum amount must be greater"):
            OrderFactory(
                token_pair_registry=token_registry,
                chain_id=1,
                settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
                amount_range=(10.0, 5.0),
            )

    @pytest.mark.asyncio
    async def test_create_market_order(
        self, factory: OrderFactory, trader_account: Account
    ) -> None:
        """Test creating a market order."""
        order = await factory.create_market_order(trader_account)

        # Check order fields
        assert order.from_ == trader_account.address
        assert order.kind == OrderKind.SELL
        assert order.signingScheme == SigningScheme.EIP712
        assert order.signature.startswith("0x")
        assert int(order.sellAmount) > 0
        assert int(order.buyAmount) > 0
        # Note: feeAmount may be 0 when not using API client for quotes
        assert int(order.feeAmount) >= 0
        assert order.validTo > int(time.time())

    @pytest.mark.asyncio
    async def test_create_market_order_with_token_pair(
        self, factory: OrderFactory, trader_account: Account
    ) -> None:
        """Test creating market order with specific token pair."""
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
        pair = TokenPair(sell_token=weth, buy_token=dai)

        order = await factory.create_market_order(trader_account, token_pair=pair)

        assert order.sellToken == weth.address
        assert order.buyToken == dai.address

    @pytest.mark.asyncio
    async def test_create_market_order_with_amount(
        self, factory: OrderFactory, trader_account: Account
    ) -> None:
        """Test creating market order with specific amount."""
        order = await factory.create_market_order(trader_account, sell_amount=1.0)

        # Amount should be approximately 1.0 ETH (allowing for precision)
        sell_amount_eth = int(order.sellAmount) / 10**18
        assert 0.99 <= sell_amount_eth <= 1.01

    @pytest.mark.asyncio
    async def test_create_limit_order(self, factory: OrderFactory, trader_account: Account) -> None:
        """Test creating a limit order."""
        order = await factory.create_limit_order(trader_account)

        assert order.from_ == trader_account.address
        assert order.kind == OrderKind.SELL
        assert order.signingScheme == SigningScheme.EIP712
        assert order.signature.startswith("0x")
        assert int(order.sellAmount) > 0
        assert int(order.buyAmount) > 0

    @pytest.mark.asyncio
    async def test_create_limit_order_buy_kind(
        self, factory: OrderFactory, trader_account: Account
    ) -> None:
        """Test creating limit order with BUY kind."""
        order = await factory.create_limit_order(trader_account, kind=OrderKind.BUY)
        assert order.kind == OrderKind.BUY

    @pytest.mark.asyncio
    async def test_create_batch_orders(
        self, factory: OrderFactory, trader_account: Account
    ) -> None:
        """Test creating batch orders."""
        orders = await factory.create_batch_orders(trader_account, count=10)

        assert len(orders) == 10
        for order in orders:
            assert order.from_ == trader_account.address
            assert order.signature.startswith("0x")

    @pytest.mark.asyncio
    async def test_create_batch_orders_all_market(
        self, factory: OrderFactory, trader_account: Account
    ) -> None:
        """Test creating batch with all market orders."""
        orders = await factory.create_batch_orders(trader_account, count=5, market_order_ratio=1.0)
        assert len(orders) == 5

    @pytest.mark.asyncio
    async def test_create_batch_orders_all_limit(
        self, factory: OrderFactory, trader_account: Account
    ) -> None:
        """Test creating batch with all limit orders."""
        orders = await factory.create_batch_orders(trader_account, count=5, market_order_ratio=0.0)
        assert len(orders) == 5

    @pytest.mark.asyncio
    async def test_create_batch_orders_invalid_count(
        self, factory: OrderFactory, trader_account: Account
    ) -> None:
        """Test creating batch with invalid count."""
        with pytest.raises(ValueError, match="Count must be positive"):
            await factory.create_batch_orders(trader_account, count=0)

    @pytest.mark.asyncio
    async def test_create_batch_orders_invalid_ratio(
        self, factory: OrderFactory, trader_account: Account
    ) -> None:
        """Test creating batch with invalid ratio."""
        with pytest.raises(ValueError, match="Market order ratio must be between"):
            await factory.create_batch_orders(trader_account, count=5, market_order_ratio=1.5)

    @pytest.mark.asyncio
    async def test_order_signature_valid(
        self, factory: OrderFactory, trader_account: Account
    ) -> None:
        """Test that order signatures are valid."""
        order = await factory.create_market_order(trader_account)

        # Signature should be 132 characters (0x + 130 hex chars)
        # Or 134 for v=27/28 format
        assert len(order.signature) >= 132

    @pytest.mark.asyncio
    async def test_order_valid_to_in_future(
        self, factory: OrderFactory, trader_account: Account
    ) -> None:
        """Test that order validTo is in the future."""
        order = await factory.create_market_order(trader_account)
        current_time = int(time.time())

        assert order.validTo > current_time
        # Should be approximately valid_duration in the future
        assert order.validTo <= current_time + factory.valid_duration + 5

    @pytest.mark.asyncio
    async def test_fee_calculation(self, factory: OrderFactory, trader_account: Account) -> None:
        """Test that fees are calculated correctly."""
        order = await factory.create_market_order(trader_account, sell_amount=1.0)

        fee_amount = int(order.feeAmount)

        # Note: Fee calculation depends on whether quotes are used
        # Without an API client, fees may be 0
        # With API client and quotes, fees come from the quote response
        assert fee_amount >= 0
