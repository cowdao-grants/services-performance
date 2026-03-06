"""
Unit tests for conditional order factory.
"""

import pytest

from cow_performance.load_generation import create_mainnet_token_registry
from cow_performance.load_generation.abi_encoding import decode_twap_data
from cow_performance.load_generation.conditional_order_factory import (
    ConditionalOrderFactory,
)
from cow_performance.load_generation.conditional_order_schema import SigningScheme
from cow_performance.load_generation.handlers import MAINNET_HANDLERS


class TestConditionalOrderFactory:
    """Tests for ConditionalOrderFactory."""

    @pytest.fixture
    def token_registry(self):
        """Create mainnet token registry fixture."""
        return create_mainnet_token_registry()

    @pytest.fixture
    def factory(self, token_registry):
        """Create conditional order factory fixture."""
        return ConditionalOrderFactory(
            token_pair_registry=token_registry,
            chain_id=1,
            safe_wallet_address="0x1234567890123456789012345678901234567890",
            amount_range=(1.0, 100.0),
        )

    def test_factory_initialization(self, factory):
        """Test factory initializes correctly."""
        assert factory.chain_id == 1
        assert factory.safe_wallet_address == "0x1234567890123456789012345678901234567890"
        assert factory.amount_range == (1.0, 100.0)

    def test_factory_invalid_amount_range(self, token_registry):
        """Test factory validation of amount range."""
        with pytest.raises(ValueError, match="Maximum amount must be greater"):
            ConditionalOrderFactory(
                token_pair_registry=token_registry,
                chain_id=1,
                safe_wallet_address="0x1234567890123456789012345678901234567890",
                amount_range=(100.0, 10.0),  # Invalid: max < min
            )

    def test_create_twap_order(self, factory):
        """Test TWAP order generation."""
        order = factory.create_twap_order(
            total_amount=90.0, num_parts=3, interval_seconds=240, start_delay_seconds=10
        )

        # Verify order structure
        assert order.owner == factory.safe_wallet_address
        assert order.signingScheme == SigningScheme.EIP1271
        assert order.params.handler == MAINNET_HANDLERS["twap"]
        assert len(order.params.salt) == 66  # 0x + 64 hex chars
        assert order.params.staticInput.startswith("0x")

        # Decode and verify staticInput
        decoded = decode_twap_data(order.params.staticInput)
        assert decoded["n"] == 3
        assert decoded["t"] == 240
        assert decoded["span"] == 240

    def test_create_twap_order_with_random_parameters(self, factory):
        """Test TWAP order generation with random parameters."""
        order = factory.create_twap_order()

        # Should generate valid order with defaults
        assert order.params.handler == MAINNET_HANDLERS["twap"]
        assert order.signingScheme == SigningScheme.EIP1271

        # Decode to verify structure
        decoded = decode_twap_data(order.params.staticInput)
        assert decoded["n"] >= 2  # Default is 3
        assert decoded["t"] > 0

    def test_create_twap_order_invalid_num_parts(self, factory):
        """Test TWAP order validation of num_parts."""
        with pytest.raises(ValueError, match="at least 2 parts"):
            factory.create_twap_order(num_parts=1)

    def test_create_stop_loss_order(self, factory):
        """Test Stop-Loss order generation."""
        order = factory.create_stop_loss_order(
            sell_amount=1.0, strike_percentage=90.0, valid_duration=3600
        )

        # Verify order structure
        assert order.owner == factory.safe_wallet_address
        assert order.signingScheme == SigningScheme.EIP1271
        assert order.params.handler.lower() == MAINNET_HANDLERS["stop_loss"].lower()
        assert len(order.params.salt) == 66
        assert order.params.staticInput.startswith("0x")

    def test_create_stop_loss_order_with_random_parameters(self, factory):
        """Test Stop-Loss order generation with random parameters."""
        order = factory.create_stop_loss_order()

        # Should generate valid order
        assert order.params.handler.lower() == MAINNET_HANDLERS["stop_loss"].lower()
        assert order.signingScheme == SigningScheme.EIP1271

    def test_create_good_after_time_order(self, factory):
        """Test Good-After-Time order generation."""
        order = factory.create_good_after_time_order(
            sell_amount=1.0, delay_seconds=300, valid_duration=3600
        )

        # Verify order structure
        assert order.owner == factory.safe_wallet_address
        assert order.signingScheme == SigningScheme.EIP1271
        assert order.params.handler.lower() == MAINNET_HANDLERS["good_after_time"].lower()
        assert len(order.params.salt) == 66
        assert order.params.staticInput.startswith("0x")

    def test_create_good_after_time_order_with_random_parameters(self, factory):
        """Test Good-After-Time order generation with random parameters."""
        order = factory.create_good_after_time_order()

        # Should generate valid order
        assert order.params.handler.lower() == MAINNET_HANDLERS["good_after_time"].lower()
        assert order.signingScheme == SigningScheme.EIP1271

    def test_create_batch_conditional_orders(self, factory):
        """Test batch generation of mixed conditional orders."""
        orders = factory.create_batch_conditional_orders(
            count=10, order_types=["twap", "stop_loss"]
        )

        assert len(orders) == 10
        assert all(
            order.params.handler.lower()
            in [MAINNET_HANDLERS["twap"].lower(), MAINNET_HANDLERS["stop_loss"].lower()]
            for order in orders
        )

    def test_create_batch_conditional_orders_all_types(self, factory):
        """Test batch generation with all order types."""
        orders = factory.create_batch_conditional_orders(count=15)

        assert len(orders) == 15
        # Should include mix of all three types
        handler_types = {order.params.handler for order in orders}
        assert len(handler_types) >= 1  # At least one type present

    def test_create_batch_conditional_orders_invalid_count(self, factory):
        """Test batch generation with invalid count."""
        with pytest.raises(ValueError, match="Count must be positive"):
            factory.create_batch_conditional_orders(count=0)

    def test_create_batch_conditional_orders_invalid_type(self, factory):
        """Test batch generation with invalid order type."""
        with pytest.raises(ValueError, match="Invalid order type"):
            factory.create_batch_conditional_orders(count=5, order_types=["invalid_type"])

    def test_twap_order_with_specific_token_pair(self, factory, token_registry):
        """Test TWAP order generation with specific token pair."""
        # Get a specific token pair
        pairs = token_registry.get_all_pairs()
        specific_pair = pairs[0]

        order = factory.create_twap_order(token_pair=specific_pair, total_amount=10.0)

        # Decode and verify it uses the specified pair
        decoded = decode_twap_data(order.params.staticInput)
        assert decoded["sellToken"].lower() == specific_pair.sell_token.address.lower()
        assert decoded["buyToken"].lower() == specific_pair.buy_token.address.lower()

    def test_unique_salts_generated(self, factory):
        """Test that each order gets a unique salt."""
        orders = factory.create_batch_conditional_orders(count=10)

        salts = {order.params.salt for order in orders}
        assert len(salts) == 10  # All salts should be unique

    def test_oracle_registry_integration(self, factory):
        """Test that oracle registry is properly initialized."""
        assert factory.oracle_registry.chain_id == 1
        available_tokens = factory.oracle_registry.get_available_tokens()
        assert len(available_tokens) > 0
        assert "WETH" in available_tokens

    def test_calculate_buy_amount_with_slippage(self, factory, token_registry):
        """Test buy amount calculation with slippage."""
        pairs = token_registry.get_all_pairs()
        pair = pairs[0]

        sell_amount_wei = pair.sell_token.to_wei(1.0)
        buy_amount = factory._calculate_buy_amount_with_slippage(
            sell_amount_wei, pair, slippage_percent=10.0
        )

        # Buy amount should be positive
        assert buy_amount > 0

        # Buy amount should be less than 1:1 due to slippage
        expected_1_to_1 = factory._calculate_buy_amount(
            sell_amount_wei,
            pair.sell_token.decimals,
            pair.buy_token.decimals,
            price=None,
        )
        assert buy_amount < expected_1_to_1
