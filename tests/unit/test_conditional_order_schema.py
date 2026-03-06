"""
Unit tests for conditional order schema models.
"""

import pytest
from pydantic import ValidationError

from cow_performance.load_generation.conditional_order_schema import (
    ConditionalOrder,
    ConditionalOrderParams,
    GoodAfterTimeOrderParameters,
    StopLossOrderParameters,
    TWAPOrderParameters,
)
from cow_performance.load_generation.order_schema import OrderBalance, SigningScheme


class TestTWAPOrderParameters:
    """Tests for TWAP order parameters model."""

    def test_valid_twap_parameters(self) -> None:
        """Test creating valid TWAP parameters."""
        params = TWAPOrderParameters(
            sellToken="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
            buyToken="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
            receiver="0x1234567890123456789012345678901234567890",
            partSellAmount="1000000000000000000",  # 1 WETH
            minPartLimit="3000000000",  # 3000 USDC (6 decimals)
            t0=1700000000,
            n=5,
            t=240,
            span=240,
            appData="0x0000000000000000000000000000000000000000000000000000000000000000",
        )

        assert params.sellToken == "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
        assert params.n == 5
        assert params.t == 240

    def test_twap_num_parts_validation(self) -> None:
        """Test that n must be >= 2."""
        with pytest.raises(ValidationError):
            TWAPOrderParameters(
                sellToken="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                buyToken="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                receiver="0x1234567890123456789012345678901234567890",
                partSellAmount="1000000000000000000",
                minPartLimit="3000000000",
                t0=1700000000,
                n=1,  # Invalid: must be >= 2
                t=240,
                span=240,
            )

    def test_twap_invalid_address(self) -> None:
        """Test validation of invalid Ethereum address."""
        with pytest.raises(ValidationError):
            TWAPOrderParameters(
                sellToken="0xinvalid",
                buyToken="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                receiver="0x1234567890123456789012345678901234567890",
                partSellAmount="1000000000000000000",
                minPartLimit="3000000000",
                t0=1700000000,
                n=3,
                t=240,
                span=240,
            )

    def test_twap_app_data_validation(self) -> None:
        """Test validation of appData format."""
        with pytest.raises(ValidationError):
            TWAPOrderParameters(
                sellToken="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                buyToken="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                receiver="0x1234567890123456789012345678901234567890",
                partSellAmount="1000000000000000000",
                minPartLimit="3000000000",
                t0=1700000000,
                n=3,
                t=240,
                span=240,
                appData="0x123",  # Invalid: must be 32 bytes
            )


class TestStopLossOrderParameters:
    """Tests for Stop-Loss order parameters model."""

    def test_valid_stop_loss_parameters(self) -> None:
        """Test creating valid Stop-Loss parameters."""
        params = StopLossOrderParameters(
            sellToken="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            buyToken="0xdAC17F958D2ee523a2206206994597C13D831ec7",
            sellAmount="1000000000000000000",
            buyAmount="3000000000",
            appData="0x0000000000000000000000000000000000000000000000000000000000000000",
            receiver="0x1234567890123456789012345678901234567890",
            isSellOrder=True,
            isPartiallyFillable=False,
            validTo=1700000000,
            sellTokenPriceOracle="0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
            buyTokenPriceOracle="0x3E7d1eAB13ad0104d2750B8863b489D65364e32D",
            strike="3500000000000000000000",
            maxTimeSinceLastOracleUpdate=3600,
        )

        assert params.isSellOrder is True
        assert params.maxTimeSinceLastOracleUpdate == 3600

    def test_stop_loss_invalid_oracle_address(self) -> None:
        """Test validation of oracle addresses."""
        with pytest.raises(ValidationError):
            StopLossOrderParameters(
                sellToken="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                buyToken="0xdAC17F958D2ee523a2206206994597C13D831ec7",
                sellAmount="1000000000000000000",
                buyAmount="3000000000",
                appData="0x0000000000000000000000000000000000000000000000000000000000000000",
                receiver="0x1234567890123456789012345678901234567890",
                isSellOrder=True,
                isPartiallyFillable=False,
                validTo=1700000000,
                sellTokenPriceOracle="invalid",
                buyTokenPriceOracle="0x3E7d1eAB13ad0104d2750B8863b489D65364e32D",
                strike="3500000000000000000000",
                maxTimeSinceLastOracleUpdate=3600,
            )


class TestGoodAfterTimeOrderParameters:
    """Tests for Good-After-Time order parameters model."""

    def test_valid_good_after_time_parameters(self) -> None:
        """Test creating valid Good-After-Time parameters."""
        params = GoodAfterTimeOrderParameters(
            sellToken="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            buyToken="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            receiver="0x1234567890123456789012345678901234567890",
            sellAmount="1000000000000000000",
            buyAmount="3000000000",
            validTo=1700003600,
            appData="0x0000000000000000000000000000000000000000000000000000000000000000",
            validFrom=1700000000,
            buyTokenBalance=OrderBalance.ERC20,
            sellTokenBalance=OrderBalance.ERC20,
            partiallyFillable=False,
        )

        assert params.validFrom == 1700000000
        assert params.validTo == 1700003600
        assert params.partiallyFillable is False


class TestConditionalOrderParams:
    """Tests for ConditionalOrderParams model."""

    def test_valid_conditional_order_params(self) -> None:
        """Test creating valid conditional order params."""
        params = ConditionalOrderParams(
            handler="0x6cF1e9cA41f7611dEf408122793c358a3d11E5a5",
            salt="0x1234567890123456789012345678901234567890123456789012345678901234",
            staticInput="0xabcdef",
        )

        assert params.handler == "0x6cF1e9cA41f7611dEf408122793c358a3d11E5a5"
        assert len(params.salt) == 66  # 0x + 64 hex chars

    def test_invalid_salt_length(self) -> None:
        """Test validation of salt length."""
        with pytest.raises(ValidationError):
            ConditionalOrderParams(
                handler="0x6cF1e9cA41f7611dEf408122793c358a3d11E5a5",
                salt="0x1234",  # Invalid: must be 32 bytes
                staticInput="0xabcdef",
            )


class TestConditionalOrder:
    """Tests for ConditionalOrder model."""

    def test_valid_conditional_order(self) -> None:
        """Test creating valid conditional order."""
        order = ConditionalOrder(
            params=ConditionalOrderParams(
                handler="0x6cF1e9cA41f7611dEf408122793c358a3d11E5a5",
                salt="0x1234567890123456789012345678901234567890123456789012345678901234",
                staticInput="0xabcdef",
            ),
            owner="0x1234567890123456789012345678901234567890",
            signingScheme=SigningScheme.EIP1271,
        )

        assert order.signingScheme == SigningScheme.EIP1271
        assert order.owner == "0x1234567890123456789012345678901234567890"

    def test_conditional_order_serialization(self) -> None:
        """Test JSON serialization of conditional order."""
        order = ConditionalOrder(
            params=ConditionalOrderParams(
                handler="0x6cF1e9cA41f7611dEf408122793c358a3d11E5a5",
                salt="0x1234567890123456789012345678901234567890123456789012345678901234",
                staticInput="0xabcdef",
            ),
            owner="0x1234567890123456789012345678901234567890",
            signingScheme=SigningScheme.EIP1271,
        )

        # Serialize to dict
        order_dict = order.model_dump()
        assert "params" in order_dict
        assert "owner" in order_dict
        assert "signingScheme" in order_dict

        # Deserialize
        restored = ConditionalOrder(**order_dict)
        assert restored.params.handler == order.params.handler
        assert restored.owner == order.owner
