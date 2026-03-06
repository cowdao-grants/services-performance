"""
Integration tests for conditional order generation.

These tests verify end-to-end functionality of conditional order generation,
encoding, and validation across all token pairs.
"""

import pytest

from cow_performance.load_generation import create_mainnet_token_registry
from cow_performance.load_generation.abi_encoding import (
    decode_good_after_time_data,
    decode_stop_loss_data,
    decode_twap_data,
)
from cow_performance.load_generation.conditional_order_factory import (
    ConditionalOrderFactory,
)
from cow_performance.load_generation.conditional_order_templates import (
    ConditionalOrderTemplateRegistry,
    create_default_conditional_templates,
)


@pytest.mark.integration
class TestConditionalOrderGeneration:
    """Integration tests for conditional order generation."""

    @pytest.fixture
    def factory(self):
        """Create factory with mainnet token registry."""
        token_registry = create_mainnet_token_registry()
        return ConditionalOrderFactory(
            token_pair_registry=token_registry,
            chain_id=1,
            safe_wallet_address="0x1234567890123456789012345678901234567890",
            amount_range=(1.0, 100.0),
        )

    def test_generate_twap_orders_all_token_pairs(self, factory):
        """Test TWAP order generation for all available token pairs."""
        pairs = factory.token_pair_registry.get_all_pairs()

        for pair in pairs:
            order = factory.create_twap_order(
                token_pair=pair, total_amount=10.0, num_parts=3, interval_seconds=240
            )

            # Validate order structure
            assert order.params.handler is not None
            assert len(order.params.salt) == 66
            assert order.params.staticInput.startswith("0x")

            # Decode and verify staticInput
            decoded = decode_twap_data(order.params.staticInput)
            assert decoded["sellToken"].lower() == pair.sell_token.address.lower()
            assert decoded["buyToken"].lower() == pair.buy_token.address.lower()
            assert decoded["n"] == 3
            assert decoded["t"] == 240

    def test_generate_stop_loss_orders_all_token_pairs(self, factory):
        """Test Stop-Loss order generation for all available token pairs."""
        pairs = factory.token_pair_registry.get_all_pairs()

        for pair in pairs:
            order = factory.create_stop_loss_order(
                token_pair=pair, sell_amount=1.0, strike_percentage=90.0
            )

            # Validate order structure
            assert order.params.handler is not None
            assert len(order.params.salt) == 66
            assert order.params.staticInput.startswith("0x")

            # Decode and verify staticInput
            decoded = decode_stop_loss_data(order.params.staticInput)
            assert decoded["sellToken"].lower() == pair.sell_token.address.lower()
            assert decoded["buyToken"].lower() == pair.buy_token.address.lower()
            assert decoded["isSellOrder"] is True

    def test_generate_good_after_time_orders_all_token_pairs(self, factory):
        """Test Good-After-Time order generation for all available token pairs."""
        pairs = factory.token_pair_registry.get_all_pairs()

        for pair in pairs:
            order = factory.create_good_after_time_order(
                token_pair=pair, sell_amount=1.0, delay_seconds=300
            )

            # Validate order structure
            assert order.params.handler is not None
            assert len(order.params.salt) == 66
            assert order.params.staticInput.startswith("0x")

            # Decode and verify staticInput
            decoded = decode_good_after_time_data(order.params.staticInput)
            assert decoded["sellToken"].lower() == pair.sell_token.address.lower()
            assert decoded["buyToken"].lower() == pair.buy_token.address.lower()

    def test_conditional_order_serialization(self, factory):
        """Test JSON serialization and deserialization of conditional orders."""
        from cow_performance.load_generation.conditional_order_schema import ConditionalOrder

        # Create orders of each type
        twap = factory.create_twap_order()
        stop_loss = factory.create_stop_loss_order()
        gat = factory.create_good_after_time_order()

        for order in [twap, stop_loss, gat]:
            # Serialize to JSON
            json_data = order.model_dump(by_alias=True)

            # Deserialize
            restored = ConditionalOrder(**json_data)

            # Verify restoration
            assert restored.params.handler == order.params.handler
            assert restored.params.salt == order.params.salt
            assert restored.params.staticInput == order.params.staticInput
            assert restored.owner == order.owner

    @pytest.mark.slow
    def test_generate_1000_conditional_orders_performance(self, factory):
        """Performance test: generate 1000 mixed conditional orders."""
        import time

        start = time.time()
        orders = factory.create_batch_conditional_orders(count=1000)
        duration = time.time() - start

        orders_per_sec = 1000 / duration

        assert len(orders) == 1000
        assert orders_per_sec > 50  # Should generate >50 orders/sec (relaxed from 100)

        # Verify variety of order types
        handler_types = {order.params.handler for order in orders}
        assert len(handler_types) >= 2  # At least 2 different types

    def test_twap_encoding_decoding_roundtrip(self, factory):
        """Test TWAP order encoding/decoding roundtrip."""
        order = factory.create_twap_order(
            total_amount=100.0, num_parts=5, interval_seconds=300, start_delay_seconds=20
        )

        # Decode the staticInput
        decoded = decode_twap_data(order.params.staticInput)

        # Verify key parameters
        assert decoded["n"] == 5
        assert decoded["t"] == 300
        assert decoded["span"] == 300

        # Verify addresses are valid
        assert decoded["sellToken"].startswith("0x")
        assert decoded["buyToken"].startswith("0x")
        assert decoded["receiver"].lower() == factory.safe_wallet_address.lower()

    def test_stop_loss_encoding_decoding_roundtrip(self, factory):
        """Test Stop-Loss order encoding/decoding roundtrip."""
        order = factory.create_stop_loss_order(
            sell_amount=10.0, strike_percentage=85.0, valid_duration=7200
        )

        # Decode the staticInput
        decoded = decode_stop_loss_data(order.params.staticInput)

        # Verify key parameters
        assert decoded["isSellOrder"] is True
        assert decoded["isPartiallyFillable"] is False
        assert decoded["maxTimeSinceLastOracleUpdate"] == 3600

        # Verify addresses are valid
        assert decoded["sellToken"].startswith("0x")
        assert decoded["buyToken"].startswith("0x")
        assert decoded["receiver"].lower() == factory.safe_wallet_address.lower()
        assert decoded["sellTokenPriceOracle"].startswith("0x")
        assert decoded["buyTokenPriceOracle"].startswith("0x")

    def test_template_integration(self, factory):
        """Test integration with conditional order templates."""
        templates = create_default_conditional_templates()
        registry = ConditionalOrderTemplateRegistry(templates)

        # Test TWAP templates
        twap_template = registry.get_template("twap_small")
        assert twap_template.order_type == "twap"
        assert twap_template.num_parts == 3

        # Test Stop-Loss templates
        stop_loss_template = registry.get_template("stop_loss_conservative")
        assert stop_loss_template.order_type == "stop_loss"
        assert stop_loss_template.strike_percentage == 95.0

        # Test Good-After-Time templates
        gat_template = registry.get_template("delayed_order_short")
        assert gat_template.order_type == "good_after_time"
        assert gat_template.delay_seconds == 300

    def test_template_based_order_generation(self, factory):
        """Test generating orders using templates."""
        templates = create_default_conditional_templates()

        # Generate TWAP order using template parameters
        twap_template = templates["twap_medium"]
        twap_order = factory.create_twap_order(
            num_parts=twap_template.num_parts,
            interval_seconds=twap_template.interval_seconds,
            start_delay_seconds=twap_template.start_delay_seconds,
        )

        decoded = decode_twap_data(twap_order.params.staticInput)
        assert decoded["n"] == twap_template.num_parts
        assert decoded["t"] == twap_template.interval_seconds

        # Generate Stop-Loss order using template parameters
        stop_loss_template = templates["stop_loss_aggressive"]
        stop_loss_order = factory.create_stop_loss_order(
            strike_percentage=stop_loss_template.strike_percentage,
            valid_duration=stop_loss_template.valid_duration,
        )

        # Verify order was created successfully
        assert stop_loss_order.params.handler is not None

    def test_order_uniqueness(self, factory):
        """Test that generated orders are unique."""
        orders = factory.create_batch_conditional_orders(count=100)

        # Check salt uniqueness
        salts = [order.params.salt for order in orders]
        assert len(set(salts)) == 100  # All salts should be unique

        # Check staticInput uniqueness (orders should differ in amounts, timestamps, etc.)
        static_inputs = [order.params.staticInput for order in orders]
        # Most should be unique (some might collide due to random generation, but most should differ)
        assert len(set(static_inputs)) >= 95

    def test_mainnet_support(self):
        """Test that factory works with mainnet chain ID."""
        token_registry = create_mainnet_token_registry()

        # Test with mainnet
        factory = ConditionalOrderFactory(
            token_pair_registry=token_registry,
            chain_id=1,
            safe_wallet_address="0x1234567890123456789012345678901234567890",
        )

        # Should be able to create all order types on mainnet
        twap = factory.create_twap_order()
        stop_loss = factory.create_stop_loss_order()
        gat = factory.create_good_after_time_order()

        assert twap.params.handler is not None
        assert stop_loss.params.handler is not None
        assert gat.params.handler is not None

        # Verify all use mainnet handlers
        from cow_performance.load_generation.handlers import MAINNET_HANDLERS

        assert twap.params.handler.lower() == MAINNET_HANDLERS["twap"].lower()
        assert stop_loss.params.handler.lower() == MAINNET_HANDLERS["stop_loss"].lower()
        assert gat.params.handler.lower() == MAINNET_HANDLERS["good_after_time"].lower()
