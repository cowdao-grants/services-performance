"""
Unit tests for order signing functionality.

Tests EIP-712 signing for standard orders.
"""

import pytest

from cow_performance.load_generation import (
    OrderFactory,
    OrderSigner,
    SigningScheme,
    TraderAccount,
    create_mainnet_token_registry,
)


class TestOrderSigner:
    """Tests for OrderSigner class."""

    @pytest.fixture
    def chain_id(self):
        """Test chain ID."""
        return 1

    @pytest.fixture
    def settlement_contract(self):
        """Test settlement contract address."""
        return "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"

    @pytest.fixture
    def order_signer(self, chain_id, settlement_contract):
        """Create order signer fixture."""
        return OrderSigner(chain_id, settlement_contract)

    @pytest.fixture
    def trader(self):
        """Create trader fixture."""
        return TraderAccount.generate()

    @pytest.fixture
    def order_factory(self, settlement_contract):
        """Create order factory fixture."""
        token_registry = create_mainnet_token_registry()
        return OrderFactory(
            token_pair_registry=token_registry,
            chain_id=1,
            settlement_contract=settlement_contract,
            valid_duration=3600,
        )

    @pytest.mark.asyncio
    async def test_sign_order_creates_valid_signature(self, order_signer, trader, order_factory):
        """Test that signing creates a valid signature."""
        order_params = await order_factory.create_market_order(trader.get_account())

        signed_order = order_signer.sign_order(
            order_params,
            trader.get_account(),
        )

        assert signed_order is not None
        assert signed_order.signature is not None
        assert signed_order.signature.startswith("0x")
        assert len(signed_order.signature) > 2  # Has actual signature data
        assert signed_order.from_ == trader.address
        assert signed_order.signingScheme == SigningScheme.EIP712

    @pytest.mark.asyncio
    async def test_signed_order_contains_all_parameters(self, order_signer, trader, order_factory):
        """Test that signed order contains all original parameters."""
        order_params = await order_factory.create_market_order(trader.get_account())

        signed_order = order_signer.sign_order(
            order_params,
            trader.get_account(),
        )

        assert signed_order.sellToken == order_params.sellToken
        assert signed_order.buyToken == order_params.buyToken
        assert signed_order.sellAmount == order_params.sellAmount
        assert signed_order.buyAmount == order_params.buyAmount
        assert signed_order.validTo == order_params.validTo
        assert signed_order.appData == order_params.appData
        assert signed_order.feeAmount == order_params.feeAmount
        assert signed_order.kind == order_params.kind
        assert signed_order.partiallyFillable == order_params.partiallyFillable

    @pytest.mark.asyncio
    async def test_verify_signature_succeeds_for_valid_signature(
        self, order_signer, trader, order_factory
    ):
        """Test that signature verification succeeds for valid signature."""
        order_params = await order_factory.create_market_order(trader.get_account())

        signed_order = order_signer.sign_order(
            order_params,
            trader.get_account(),
        )

        is_valid = order_signer.verify_signature(signed_order)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_signature_fails_for_wrong_signer(self, order_signer, order_factory):
        """Test that signature verification fails for wrong signer."""
        trader1 = TraderAccount.generate()
        trader2 = TraderAccount.generate()

        order_params = await order_factory.create_market_order(trader1.get_account())

        # Sign with trader1
        signed_order = order_signer.sign_order(
            order_params,
            trader1.get_account(),
        )

        # Change the owner to trader2
        signed_order.from_ = trader2.address

        # Verification should fail
        is_valid = order_signer.verify_signature(signed_order)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_different_traders_produce_different_signatures(
        self, order_signer, order_factory
    ):
        """Test that different traders produce different signatures for same order."""
        trader1 = TraderAccount.generate()
        trader2 = TraderAccount.generate()

        order_params = await order_factory.create_market_order(trader1.get_account())

        signed_order1 = order_signer.sign_order(
            order_params,
            trader1.get_account(),
        )

        signed_order2 = order_signer.sign_order(
            order_params,
            trader2.get_account(),
        )

        assert signed_order1.signature != signed_order2.signature
        assert signed_order1.from_ != signed_order2.from_

    @pytest.mark.asyncio
    async def test_same_trader_produces_same_signature_for_same_order(
        self, order_signer, trader, order_factory
    ):
        """Test that same trader produces same signature for identical order."""
        order_params = await order_factory.create_market_order(trader.get_account())

        signed_order1 = order_signer.sign_order(
            order_params,
            trader.get_account(),
        )

        signed_order2 = order_signer.sign_order(
            order_params,
            trader.get_account(),
        )

        # Same order + same trader = same signature
        assert signed_order1.signature == signed_order2.signature

    @pytest.mark.asyncio
    async def test_sign_limit_order(self, order_signer, trader, order_factory):
        """Test signing a limit order."""
        order_params = await order_factory.create_limit_order(trader.get_account())

        signed_order = order_signer.sign_order(
            order_params,
            trader.get_account(),
        )

        assert signed_order is not None
        assert signed_order.signature is not None
        is_valid = order_signer.verify_signature(signed_order)
        assert is_valid is True
