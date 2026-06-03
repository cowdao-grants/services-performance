"""Unit tests for order validation."""

import time

import pytest

from cow_performance.load_generation.order_schema import OrderBalance, OrderKind, OrderParameters
from cow_performance.load_generation.order_validation import (
    OrderValidationError,
    assert_valid_order,
    is_valid_order,
    validate_address,
    validate_amount,
    validate_app_data,
    validate_order_parameters,
    validate_timestamp,
)


class TestValidateAddress:
    """Tests for address validation."""

    def test_valid_address(self) -> None:
        """Test validating a valid address."""
        # Should not raise
        validate_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")

    def test_invalid_address(self) -> None:
        """Test validating an invalid address."""
        with pytest.raises(OrderValidationError, match="not a valid Ethereum address"):
            validate_address("invalid")

    def test_empty_address(self) -> None:
        """Test validating an empty address."""
        with pytest.raises(OrderValidationError, match="is required"):
            validate_address("")


class TestValidateAmount:
    """Tests for amount validation."""

    def test_valid_amount(self) -> None:
        """Test validating a valid amount."""
        validate_amount("1000000000000000000")  # 1 ETH in wei
        validate_amount("1")

    def test_zero_amount(self) -> None:
        """Test validating zero amount fails."""
        with pytest.raises(OrderValidationError, match="must be positive"):
            validate_amount("0")

    def test_negative_amount(self) -> None:
        """Test validating negative amount fails."""
        with pytest.raises(OrderValidationError, match="must be positive"):
            validate_amount("-1")

    def test_invalid_amount(self) -> None:
        """Test validating non-integer amount fails."""
        with pytest.raises(OrderValidationError, match="must be a valid integer"):
            validate_amount("1.5")

        with pytest.raises(OrderValidationError, match="must be a valid integer"):
            validate_amount("abc")


class TestValidateTimestamp:
    """Tests for timestamp validation."""

    def test_future_timestamp(self) -> None:
        """Test validating future timestamp."""
        future = int(time.time()) + 3600
        validate_timestamp(future)

    def test_past_timestamp(self) -> None:
        """Test validating past timestamp fails."""
        past = int(time.time()) - 3600
        with pytest.raises(OrderValidationError, match="must be in the future"):
            validate_timestamp(past)

    def test_zero_timestamp(self) -> None:
        """Test validating zero timestamp fails."""
        with pytest.raises(OrderValidationError, match="must be positive"):
            validate_timestamp(0)


class TestValidateAppData:
    """Tests for appData validation."""

    def test_valid_app_data(self) -> None:
        """Test validating valid appData."""
        validate_app_data("0x" + "0" * 64)

    def test_invalid_prefix(self) -> None:
        """Test appData without 0x prefix fails."""
        with pytest.raises(OrderValidationError, match="must start with 0x"):
            validate_app_data("0" * 64)

    def test_invalid_length(self) -> None:
        """Test appData with wrong length fails."""
        with pytest.raises(OrderValidationError, match="must be 32 bytes"):
            validate_app_data("0x" + "0" * 32)  # Too short

    def test_invalid_hex(self) -> None:
        """Test appData with invalid hex fails."""
        with pytest.raises(OrderValidationError, match="must be valid hex"):
            validate_app_data("0x" + "z" * 64)


class TestValidateOrderParameters:
    """Tests for order parameters validation."""

    @pytest.fixture
    def valid_order_params(self) -> OrderParameters:
        """Create valid order parameters."""
        return OrderParameters(
            sellToken="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            buyToken="0x6B175474E89094C44Da98b954EedeAC495271d0F",
            sellAmount="1000000000000000000",
            buyAmount="1000000000000000000",
            validTo=int(time.time()) + 3600,
            appData="0x" + "0" * 64,
            feeAmount="1000000000000000",
            kind=OrderKind.SELL,
            partiallyFillable=False,
            sellTokenBalance=OrderBalance.ERC20,
            buyTokenBalance=OrderBalance.ERC20,
        )

    def test_valid_order(self, valid_order_params: OrderParameters) -> None:
        """Test validating valid order parameters."""
        errors = validate_order_parameters(valid_order_params)
        assert len(errors) == 0
        assert is_valid_order(valid_order_params)

    def test_invalid_sell_token(self, valid_order_params: OrderParameters) -> None:
        """Test order with invalid sell token."""
        valid_order_params.sellToken = "invalid"
        errors = validate_order_parameters(valid_order_params)
        assert len(errors) > 0
        assert any("sellToken" in e for e in errors)
        assert not is_valid_order(valid_order_params)

    def test_same_tokens(self, valid_order_params: OrderParameters) -> None:
        """Test order with same sell and buy token."""
        valid_order_params.buyToken = valid_order_params.sellToken
        errors = validate_order_parameters(valid_order_params)
        assert len(errors) > 0
        assert any("must be different" in e for e in errors)

    def test_invalid_sell_amount(self, valid_order_params: OrderParameters) -> None:
        """Test order with invalid sell amount."""
        valid_order_params.sellAmount = "0"
        errors = validate_order_parameters(valid_order_params)
        assert len(errors) > 0
        assert any("sellAmount" in e for e in errors)

    def test_invalid_timestamp(self, valid_order_params: OrderParameters) -> None:
        """Test order with past timestamp."""
        valid_order_params.validTo = int(time.time()) - 3600
        errors = validate_order_parameters(valid_order_params)
        assert len(errors) > 0
        assert any("validTo" in e for e in errors)

    def test_invalid_app_data(self, valid_order_params: OrderParameters) -> None:
        """Test order with invalid appData."""
        valid_order_params.appData = "0x123"
        errors = validate_order_parameters(valid_order_params)
        assert len(errors) > 0
        assert any("appData" in e for e in errors)

    def test_assert_valid_order(self, valid_order_params: OrderParameters) -> None:
        """Test assert_valid_order with valid order."""
        # Should not raise
        assert_valid_order(valid_order_params)

    def test_assert_valid_order_invalid(self, valid_order_params: OrderParameters) -> None:
        """Test assert_valid_order with invalid order."""
        valid_order_params.sellAmount = "0"
        with pytest.raises(OrderValidationError, match="Order validation failed"):
            assert_valid_order(valid_order_params)
