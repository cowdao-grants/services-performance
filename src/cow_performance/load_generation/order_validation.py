"""
Order validation utilities for CoW Protocol orders.

This module provides validation functions to ensure orders meet all requirements
before submission to the orderbook API.
"""

import time
from typing import Any

from web3 import Web3

from .order_schema import OrderParameters, SignedOrder


class OrderValidationError(Exception):
    """Raised when order validation fails."""

    pass


def validate_address(address: str, field_name: str = "address") -> None:
    """
    Validate an Ethereum address.

    Args:
        address: Address to validate
        field_name: Name of the field for error messages

    Raises:
        OrderValidationError: If address is invalid
    """
    if not address:
        raise OrderValidationError(f"{field_name} is required")
    if not Web3.is_address(address):
        raise OrderValidationError(f"{field_name} is not a valid Ethereum address: {address}")


def validate_amount(amount: str, field_name: str = "amount", allow_zero: bool = False) -> None:
    """
    Validate an amount is a positive integer string.

    Args:
        amount: Amount to validate
        field_name: Name of the field for error messages
        allow_zero: If True, allow zero values (default: False)

    Raises:
        OrderValidationError: If amount is invalid
    """
    if not amount:
        raise OrderValidationError(f"{field_name} is required")

    try:
        amount_int = int(amount)
    except ValueError as e:
        raise OrderValidationError(f"{field_name} must be a valid integer: {amount}") from e

    if allow_zero:
        if amount_int < 0:
            raise OrderValidationError(f"{field_name} must be non-negative: {amount}")
    else:
        if amount_int <= 0:
            raise OrderValidationError(f"{field_name} must be positive: {amount}")


def validate_timestamp(timestamp: int, field_name: str = "timestamp") -> None:
    """
    Validate a timestamp is in the future.

    Args:
        timestamp: Unix timestamp to validate
        field_name: Name of the field for error messages

    Raises:
        OrderValidationError: If timestamp is invalid or in the past
    """
    if timestamp <= 0:
        raise OrderValidationError(f"{field_name} must be positive: {timestamp}")

    current_time = int(time.time())
    if timestamp <= current_time:
        raise OrderValidationError(
            f"{field_name} must be in the future. Current: {current_time}, Given: {timestamp}"
        )


def validate_app_data(app_data: str) -> None:
    """
    Validate appData hash format.

    Args:
        app_data: AppData hash to validate

    Raises:
        OrderValidationError: If appData is invalid
    """
    if not app_data:
        raise OrderValidationError("appData is required")

    if not app_data.startswith("0x"):
        raise OrderValidationError("appData must start with 0x")

    if len(app_data) != 66:  # 0x + 64 hex chars = 32 bytes
        raise OrderValidationError(
            f"appData must be 32 bytes (66 characters with 0x prefix), got {len(app_data)}"
        )

    try:
        int(app_data, 16)
    except ValueError as e:
        raise OrderValidationError(f"appData must be valid hex: {app_data}") from e


def validate_app_data_hash(app_data_doc: dict[str, Any], expected_hash: str) -> None:
    """Validate that appData document hashes to expected value.

    Args:
        app_data_doc: Full appData JSON document
        expected_hash: Expected keccak256 hash (with 0x prefix)

    Raises:
        OrderValidationError: If hash doesn't match
    """
    import json

    from web3 import Web3

    # Compute hash with consistent serialization
    app_data_json = json.dumps(app_data_doc, separators=(",", ":"), sort_keys=True)
    computed_hash = Web3.keccak(text=app_data_json).hex()

    if computed_hash != expected_hash:
        raise OrderValidationError(
            f"AppData hash mismatch: expected {expected_hash}, got {computed_hash}"
        )


def validate_order_parameters(params: OrderParameters) -> list[str]:
    """
    Validate order parameters and return list of validation errors.

    Args:
        params: Order parameters to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors: list[str] = []

    # Validate addresses
    try:
        validate_address(params.sellToken, "sellToken")
    except OrderValidationError as e:
        errors.append(str(e))

    try:
        validate_address(params.buyToken, "buyToken")
    except OrderValidationError as e:
        errors.append(str(e))

    if params.receiver:
        try:
            validate_address(params.receiver, "receiver")
        except OrderValidationError as e:
            errors.append(str(e))

    # Validate tokens are different
    if params.sellToken and params.buyToken:
        try:
            sell_normalized = Web3.to_checksum_address(params.sellToken)
            buy_normalized = Web3.to_checksum_address(params.buyToken)
            if sell_normalized == buy_normalized:
                errors.append("sellToken and buyToken must be different")
        except Exception:
            pass  # Address validation will catch this

    # Validate amounts
    try:
        validate_amount(params.sellAmount, "sellAmount")
    except OrderValidationError as e:
        errors.append(str(e))

    try:
        validate_amount(params.buyAmount, "buyAmount")
    except OrderValidationError as e:
        errors.append(str(e))

    try:
        validate_amount(params.feeAmount, "feeAmount", allow_zero=True)
    except OrderValidationError as e:
        errors.append(str(e))

    # Validate timestamp
    try:
        validate_timestamp(params.validTo, "validTo")
    except OrderValidationError as e:
        errors.append(str(e))

    # Validate appData
    try:
        validate_app_data(params.appData)
    except OrderValidationError as e:
        errors.append(str(e))

    return errors


def validate_signed_order(order: SignedOrder) -> list[str]:
    """
    Validate a signed order and return list of validation errors.

    Args:
        order: Signed order to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors: list[str] = []

    # Validate addresses
    try:
        validate_address(order.sellToken, "sellToken")
    except OrderValidationError as e:
        errors.append(str(e))

    try:
        validate_address(order.buyToken, "buyToken")
    except OrderValidationError as e:
        errors.append(str(e))

    try:
        validate_address(order.from_, "from")
    except OrderValidationError as e:
        errors.append(str(e))

    if order.receiver:
        try:
            validate_address(order.receiver, "receiver")
        except OrderValidationError as e:
            errors.append(str(e))

    # Validate tokens are different
    if order.sellToken and order.buyToken:
        try:
            sell_normalized = Web3.to_checksum_address(order.sellToken)
            buy_normalized = Web3.to_checksum_address(order.buyToken)
            if sell_normalized == buy_normalized:
                errors.append("sellToken and buyToken must be different")
        except Exception:
            pass

    # Validate amounts
    try:
        validate_amount(order.sellAmount, "sellAmount")
    except OrderValidationError as e:
        errors.append(str(e))

    try:
        validate_amount(order.buyAmount, "buyAmount")
    except OrderValidationError as e:
        errors.append(str(e))

    try:
        validate_amount(order.feeAmount, "feeAmount", allow_zero=True)
    except OrderValidationError as e:
        errors.append(str(e))

    # Validate timestamp
    try:
        validate_timestamp(order.validTo, "validTo")
    except OrderValidationError as e:
        errors.append(str(e))

    # Validate appData
    try:
        validate_app_data(order.appData)
    except OrderValidationError as e:
        errors.append(str(e))

    # Validate signature
    if not order.signature:
        errors.append("signature is required")
    elif not order.signature.startswith("0x"):
        errors.append("signature must start with 0x")

    return errors


def is_valid_order(params: OrderParameters) -> bool:
    """
    Check if order parameters are valid.

    Args:
        params: Order parameters to validate

    Returns:
        True if order is valid, False otherwise
    """
    errors = validate_order_parameters(params)
    return len(errors) == 0


def is_valid_signed_order(order: SignedOrder) -> bool:
    """
    Check if signed order is valid.

    Args:
        order: Signed order to validate

    Returns:
        True if order is valid, False otherwise
    """
    errors = validate_signed_order(order)
    return len(errors) == 0


def assert_valid_order(params: OrderParameters) -> None:
    """
    Assert that order parameters are valid, raising exception if not.

    Args:
        params: Order parameters to validate

    Raises:
        OrderValidationError: If order is invalid
    """
    errors = validate_order_parameters(params)
    if errors:
        raise OrderValidationError(
            "Order validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )


def assert_valid_signed_order(order: SignedOrder) -> None:
    """
    Assert that signed order is valid, raising exception if not.

    Args:
        order: Signed order to validate

    Raises:
        OrderValidationError: If order is invalid
    """
    errors = validate_signed_order(order)
    if errors:
        raise OrderValidationError(
            "Signed order validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )
