"""Unit tests for order templates."""

import random
from decimal import Decimal

import pytest
from eth_account import Account

from cow_performance.load_generation.order_factory import OrderFactory
from cow_performance.load_generation.order_schema import OrderKind
from cow_performance.load_generation.order_templates import (
    OrderTemplate,
    OrderTemplateRegistry,
    create_default_templates,
)
from cow_performance.load_generation.token_pair import (
    Token,
    TokenPair,
    create_mainnet_token_registry,
)


@pytest.fixture(autouse=True)
def deterministic_random():
    """Set random seed for deterministic order generation."""
    random.seed(42)
    yield


class TestOrderTemplate:
    """Tests for OrderTemplate class."""

    def test_template_creation(self) -> None:
        """Test creating a valid template."""
        template = OrderTemplate(
            name="test_template",
            description="Test template",
            order_type="market",
            kind=OrderKind.SELL,
            sell_amount_range=(1.0, 10.0),
        )
        assert template.name == "test_template"
        assert template.order_type == "market"

    def test_template_invalid_order_type(self) -> None:
        """Test creating template with invalid order type."""
        with pytest.raises(ValueError, match="Invalid order type"):
            OrderTemplate(
                name="test",
                description="Test",
                order_type="invalid",
            )

    def test_template_invalid_amount_range(self) -> None:
        """Test creating template with invalid amount range."""
        with pytest.raises(ValueError, match="Minimum sell amount must be positive"):
            OrderTemplate(
                name="test",
                description="Test",
                order_type="market",
                sell_amount_range=(0, 10.0),
            )

    def test_template_matches_token_pair(self) -> None:
        """Test token pair filtering."""
        template = OrderTemplate(
            name="test",
            description="Test",
            order_type="market",
            token_pair_filter="WETH/*",
        )

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

        assert template.matches_token_pair(TokenPair(sell_token=weth, buy_token=dai))
        assert template.matches_token_pair(TokenPair(sell_token=weth, buy_token=usdc))
        assert not template.matches_token_pair(TokenPair(sell_token=dai, buy_token=weth))

    def test_template_matches_any_pair(self) -> None:
        """Test template without filter matches any pair."""
        template = OrderTemplate(
            name="test",
            description="Test",
            order_type="market",
            token_pair_filter=None,
        )

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

        assert template.matches_token_pair(TokenPair(sell_token=weth, buy_token=dai))
        assert template.matches_token_pair(TokenPair(sell_token=dai, buy_token=weth))


class TestOrderTemplateRegistry:
    """Tests for OrderTemplateRegistry class."""

    def test_registry_creation(self) -> None:
        """Test creating empty registry."""
        registry = OrderTemplateRegistry()
        assert registry.list_templates() == []

    def test_register_template(self) -> None:
        """Test registering a template."""
        registry = OrderTemplateRegistry()
        template = OrderTemplate(
            name="test",
            description="Test",
            order_type="market",
        )
        registry.register(template)

        assert "test" in registry.list_templates()
        assert registry.get("test") == template

    def test_get_nonexistent_template(self) -> None:
        """Test getting non-existent template."""
        registry = OrderTemplateRegistry()
        assert registry.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_create_order_from_template(self) -> None:
        """Test creating order from template."""
        registry = OrderTemplateRegistry()
        template = OrderTemplate(
            name="test_market",
            description="Test market order",
            order_type="market",
            sell_amount_range=(1.0, 2.0),
        )
        registry.register(template)

        token_registry = create_mainnet_token_registry()
        factory = OrderFactory(
            token_pair_registry=token_registry,
            chain_id=1,
            settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
        )
        trader = Account.create()

        order = await registry.create_order_from_template(
            template_name="test_market",
            factory=factory,
            trader_account=trader,
        )

        assert order.from_ == trader.address
        assert order.kind == OrderKind.SELL

    @pytest.mark.asyncio
    async def test_create_order_with_overrides(self) -> None:
        """Test creating order with parameter overrides."""
        registry = OrderTemplateRegistry()
        template = OrderTemplate(
            name="test",
            description="Test",
            order_type="market",
            kind=OrderKind.SELL,
        )
        registry.register(template)

        token_registry = create_mainnet_token_registry()
        factory = OrderFactory(
            token_pair_registry=token_registry,
            chain_id=1,
            settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
        )
        trader = Account.create()

        order = await registry.create_order_from_template(
            template_name="test",
            factory=factory,
            trader_account=trader,
            overrides={"kind": OrderKind.BUY},
        )

        assert order.kind == OrderKind.BUY

    @pytest.mark.asyncio
    async def test_create_order_template_not_found(self) -> None:
        """Test creating order with non-existent template."""
        registry = OrderTemplateRegistry()
        token_registry = create_mainnet_token_registry()
        factory = OrderFactory(
            token_pair_registry=token_registry,
            chain_id=1,
            settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
        )
        trader = Account.create()

        with pytest.raises(ValueError, match="Template not found"):
            await registry.create_order_from_template(
                template_name="nonexistent",
                factory=factory,
                trader_account=trader,
            )


class TestDefaultTemplates:
    """Tests for default templates."""

    def test_create_default_templates(self) -> None:
        """Test creating default templates."""
        registry = create_default_templates()
        templates = registry.list_templates()

        # Should have multiple templates
        assert len(templates) > 0

        # Should have common templates
        assert "small_market" in templates
        assert "medium_market" in templates
        assert "large_market" in templates

    def test_default_template_properties(self) -> None:
        """Test default template properties."""
        registry = create_default_templates()

        small = registry.get("small_market")
        assert small is not None
        assert small.order_type == "market"
        assert small.sell_amount_range == (0.1, 1.0)

        limit = registry.get("conservative_limit")
        assert limit is not None
        assert limit.order_type == "limit"
        assert limit.limit_price == Decimal("0.99")

    @pytest.mark.asyncio
    async def test_use_default_template(self) -> None:
        """Test using a default template to create order."""
        registry = create_default_templates()
        token_registry = create_mainnet_token_registry()
        factory = OrderFactory(
            token_pair_registry=token_registry,
            chain_id=1,
            settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
        )
        trader = Account.create()

        order = await registry.create_order_from_template(
            template_name="small_market",
            factory=factory,
            trader_account=trader,
        )

        assert order.from_ == trader.address
        assert int(order.sellAmount) > 0
