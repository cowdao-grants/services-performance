"""Integration tests for order generation module."""

import json
import random

import pytest
from eth_account import Account

from cow_performance.load_generation import (
    OrderFactory,
    OrderKind,
    SignedOrder,
    create_default_templates,
    create_mainnet_token_registry,
    create_polygon_token_registry,
    validate_signed_order,
)


@pytest.fixture(autouse=True)
def deterministic_random():
    """
    Set random seed for deterministic order generation.

    This fixture runs automatically for all tests (autouse=True), ensuring
    that order generation produces the same results on every test run.
    This makes tests reproducible and easier to debug.
    """
    random.seed(42)
    yield
    # Reset to random state after test (optional)


@pytest.fixture
def mainnet_factory() -> OrderFactory:
    """Create an order factory for mainnet."""
    token_registry = create_mainnet_token_registry()
    return OrderFactory(
        token_pair_registry=token_registry,
        chain_id=1,
        settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
        amount_range=(0.1, 10.0),
        valid_duration=3600,
    )


@pytest.fixture
def polygon_factory() -> OrderFactory:
    """Create an order factory for Polygon."""
    token_registry = create_polygon_token_registry()
    return OrderFactory(
        token_pair_registry=token_registry,
        chain_id=137,
        settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
        amount_range=(0.1, 10.0),
        valid_duration=3600,
    )


@pytest.fixture
def trader_accounts() -> list[Account]:
    """Create multiple trader accounts for testing."""
    return [Account.create() for _ in range(5)]


@pytest.mark.integration
class TestBulkOrderGeneration:
    """Tests for generating large batches of orders."""

    async def test_generate_100_orders_all_valid(
        self, mainnet_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """
        Test generating 100 orders and validate all are well-formed.

        This test verifies that the order factory can generate a large batch
        of orders without errors and all orders pass validation.
        """
        all_orders = []

        # Generate 100 orders using different trader accounts
        for i in range(100):
            trader = trader_accounts[i % len(trader_accounts)]

            # Mix of market and limit orders
            if i % 2 == 0:
                order = await mainnet_factory.create_market_order(trader)
            else:
                order = await mainnet_factory.create_limit_order(trader)

            all_orders.append(order)

        # Verify all orders were created
        assert len(all_orders) == 100

        # Validate each order
        for i, order in enumerate(all_orders):
            # Check order has all required fields
            assert order.sellToken, f"Order {i} missing sellToken"
            assert order.buyToken, f"Order {i} missing buyToken"
            assert order.sellAmount, f"Order {i} missing sellAmount"
            assert order.buyAmount, f"Order {i} missing buyAmount"
            assert order.validTo > 0, f"Order {i} has invalid validTo"
            assert order.appData, f"Order {i} missing appData"
            assert order.feeAmount, f"Order {i} missing feeAmount"
            assert order.from_, f"Order {i} missing from"
            assert order.signature, f"Order {i} missing signature"

            # Check amounts are positive
            assert int(order.sellAmount) > 0, f"Order {i} has non-positive sellAmount"
            assert int(order.buyAmount) > 0, f"Order {i} has non-positive buyAmount"
            # Note: feeAmount can be 0 for market orders (fee included in buyAmount via surplus)
            assert int(order.feeAmount) >= 0, f"Order {i} has negative feeAmount"

            # Check signature format
            assert order.signature.startswith("0x"), f"Order {i} signature missing 0x prefix"
            assert len(order.signature) >= 132, f"Order {i} signature too short"

            # Run full validation
            errors = validate_signed_order(order)
            assert len(errors) == 0, f"Order {i} validation failed: {errors}"

    async def test_generate_orders_all_token_pairs(
        self, mainnet_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """
        Test order generation with all supported token pairs.

        Verifies that orders can be generated for each token pair in the registry.
        """
        token_pairs = mainnet_factory.token_pair_registry.get_all_pairs()
        trader = trader_accounts[0]

        orders_by_pair = {}

        # Generate at least one order for each token pair
        for pair in token_pairs:
            order = await mainnet_factory.create_market_order(
                trader,
                token_pair=pair,
            )

            pair_key = f"{pair.sell_token.symbol}/{pair.buy_token.symbol}"
            orders_by_pair[pair_key] = order

            # Verify order uses the correct tokens
            assert order.sellToken == pair.sell_token.address
            assert order.buyToken == pair.buy_token.address

        # Verify we generated orders for all pairs
        assert len(orders_by_pair) == len(token_pairs)

        # Validate all orders
        for pair_key, order in orders_by_pair.items():
            errors = validate_signed_order(order)
            assert len(errors) == 0, f"Order for {pair_key} validation failed: {errors}"

    async def test_batch_orders_generation(
        self, mainnet_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """Test batch order generation with different ratios."""
        trader = trader_accounts[0]

        # Test with different market/limit ratios
        for ratio in [0.0, 0.25, 0.5, 0.75, 1.0]:
            orders = await mainnet_factory.create_batch_orders(
                trader,
                count=20,
                market_order_ratio=ratio,
            )

            assert len(orders) == 20

            # All orders should be valid
            for order in orders:
                errors = validate_signed_order(order)
                assert len(errors) == 0


@pytest.mark.integration
class TestOrderSerialization:
    """Tests for order serialization and deserialization."""

    async def test_order_serialization_deserialization(
        self, mainnet_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """
        Verify generated orders can be serialized and deserialized.

        This test ensures orders can be converted to JSON and back without
        losing information or breaking validation.
        """
        trader = trader_accounts[0]

        # Generate various types of orders
        market_order = await mainnet_factory.create_market_order(trader)
        limit_order = await mainnet_factory.create_limit_order(trader)
        buy_order = await mainnet_factory.create_market_order(trader, kind=OrderKind.BUY)

        orders = [market_order, limit_order, buy_order]

        for order in orders:
            # Serialize to JSON (as would be sent to API)
            order_dict = order.model_dump(by_alias=True, exclude_none=True)
            order_json = json.dumps(order_dict)

            # Verify JSON is valid
            assert len(order_json) > 0

            # Deserialize back
            parsed_dict = json.loads(order_json)
            deserialized_order = SignedOrder.model_validate(parsed_dict)

            # Verify all fields match
            assert deserialized_order.sellToken == order.sellToken
            assert deserialized_order.buyToken == order.buyToken
            assert deserialized_order.sellAmount == order.sellAmount
            assert deserialized_order.buyAmount == order.buyAmount
            assert deserialized_order.validTo == order.validTo
            assert deserialized_order.appData == order.appData
            assert deserialized_order.feeAmount == order.feeAmount
            assert deserialized_order.kind == order.kind
            assert deserialized_order.partiallyFillable == order.partiallyFillable
            assert deserialized_order.sellTokenBalance == order.sellTokenBalance
            assert deserialized_order.buyTokenBalance == order.buyTokenBalance
            assert deserialized_order.from_ == order.from_
            assert deserialized_order.signingScheme == order.signingScheme
            assert deserialized_order.signature == order.signature

            # Deserialized order should still be valid
            errors = validate_signed_order(deserialized_order)
            assert len(errors) == 0

    async def test_order_json_format_matches_api_spec(
        self, mainnet_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """
        Verify order JSON matches CoW Protocol API specification.

        The API expects specific field names (e.g., 'from' not 'from_').
        """
        trader = trader_accounts[0]
        order = await mainnet_factory.create_market_order(trader)

        # Serialize with aliases (API format)
        order_dict = order.model_dump(by_alias=True, exclude_none=True)

        # Check required fields with correct names
        required_fields = [
            "sellToken",
            "buyToken",
            "sellAmount",
            "buyAmount",
            "validTo",
            "appData",
            "feeAmount",
            "kind",
            "partiallyFillable",
            "sellTokenBalance",
            "buyTokenBalance",
            "from",  # Note: should be 'from', not 'from_'
            "signature",
            "signingScheme",
        ]

        for field in required_fields:
            assert field in order_dict, f"Missing required field: {field}"

        # Verify 'from_' is not in the output (should be aliased to 'from')
        assert "from_" not in order_dict


@pytest.mark.integration
class TestMultiNetworkSupport:
    """Tests for generating orders on different networks."""

    async def test_mainnet_orders_generation(
        self, mainnet_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """Test generating orders for Ethereum mainnet."""
        trader = trader_accounts[0]

        # Generate multiple orders
        orders = await mainnet_factory.create_batch_orders(trader, count=10)

        for order in orders:
            # All orders should be valid
            errors = validate_signed_order(order)
            assert len(errors) == 0

            # Check some mainnet-specific tokens might appear
            # (WETH, DAI, USDC, etc.)
            assert order.sellToken.startswith("0x")
            assert order.buyToken.startswith("0x")

    async def test_polygon_orders_generation(
        self, polygon_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """Test generating orders for Polygon."""
        trader = trader_accounts[0]

        # Generate multiple orders
        orders = await polygon_factory.create_batch_orders(trader, count=10)

        for order in orders:
            # All orders should be valid
            errors = validate_signed_order(order)
            assert len(errors) == 0


@pytest.mark.integration
class TestOrderTemplates:
    """Integration tests for order templates."""

    async def test_all_default_templates_generate_valid_orders(
        self, mainnet_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """
        Test that all default templates generate valid orders.

        Verifies each template in the default registry can create valid orders.
        """
        template_registry = create_default_templates()
        trader = trader_accounts[0]

        template_names = template_registry.list_templates()

        # Should have multiple templates
        assert len(template_names) > 0

        for template_name in template_names:
            # Generate order from template
            order = await template_registry.create_order_from_template(
                template_name=template_name,
                factory=mainnet_factory,
                trader_account=trader,
            )

            # Validate order
            errors = validate_signed_order(order)
            assert len(errors) == 0, f"Template {template_name} generated invalid order: {errors}"

    async def test_template_with_overrides(
        self, mainnet_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """Test template orders with parameter overrides."""
        template_registry = create_default_templates()
        trader = trader_accounts[0]

        # Use small_market template with overrides
        order = await template_registry.create_order_from_template(
            template_name="small_market",
            factory=mainnet_factory,
            trader_account=trader,
            overrides={"kind": OrderKind.BUY, "sell_amount": 0.5},
        )

        # Check override was applied
        assert order.kind == OrderKind.BUY

        # Order should still be valid
        errors = validate_signed_order(order)
        assert len(errors) == 0


@pytest.mark.integration
class TestOrderVariety:
    """Tests for order generation variety and randomness."""

    async def test_orders_have_variety(
        self, mainnet_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """
        Test that generated orders have variety in their parameters.

        Verifies that multiple orders don't all have identical amounts or pairs.
        """
        trader = trader_accounts[0]

        # Generate 50 orders
        orders = await mainnet_factory.create_batch_orders(trader, count=50)

        # Collect unique values
        sell_amounts = {order.sellAmount for order in orders}
        buy_amounts = {order.buyAmount for order in orders}
        token_pairs = {(order.sellToken, order.buyToken) for order in orders}

        # Should have variety in amounts (not all the same)
        assert len(sell_amounts) > 10, "Orders lack variety in sell amounts"
        assert len(buy_amounts) > 10, "Orders lack variety in buy amounts"

        # Should use multiple token pairs
        assert len(token_pairs) > 1, "Orders use only one token pair"

    async def test_orders_use_different_traders(
        self, mainnet_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """Test generating orders from different trader accounts."""
        orders = []

        for trader in trader_accounts:
            order = await mainnet_factory.create_market_order(trader)
            orders.append(order)

        # Each order should have different owner
        owners = {order.from_ for order in orders}
        assert len(owners) == len(trader_accounts)

        # All orders should be valid
        for order in orders:
            errors = validate_signed_order(order)
            assert len(errors) == 0


@pytest.mark.integration
@pytest.mark.slow
class TestStressOrderGeneration:
    """Stress tests for order generation."""

    async def test_generate_1000_orders_performance(
        self, mainnet_factory: OrderFactory, trader_accounts: list[Account]
    ) -> None:
        """
        Stress test: Generate 1000 orders and ensure all are valid.

        This test verifies the factory can handle high-volume generation.
        """
        import time

        trader = trader_accounts[0]

        start_time = time.time()

        # Generate 1000 orders
        all_orders = []
        for _ in range(10):
            batch = await mainnet_factory.create_batch_orders(trader, count=100)
            all_orders.extend(batch)

        elapsed_time = time.time() - start_time

        # Verify all orders were created
        assert len(all_orders) == 1000

        # Sample validation (check every 10th order to save time)
        for i in range(0, 1000, 10):
            order = all_orders[i]
            errors = validate_signed_order(order)
            assert len(errors) == 0, f"Order {i} validation failed"

        # Log performance (orders per second)
        orders_per_second = 1000 / elapsed_time
        print(
            f"\nGenerated 1000 orders in {elapsed_time:.2f}s ({orders_per_second:.2f} orders/sec)"
        )

        # Should be reasonably fast (at least 10 orders/sec)
        assert (
            orders_per_second > 10
        ), f"Order generation too slow: {orders_per_second:.2f} orders/sec"
