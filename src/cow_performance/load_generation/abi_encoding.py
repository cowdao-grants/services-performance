"""
ABI encoding utilities for conditional orders.

This module provides functions to encode conditional order parameters
into the staticInput format required by ComposableCow handlers.
"""

from eth_abi import encode

from .conditional_order_schema import (
    GoodAfterTimeOrderParameters,
    StopLossOrderParameters,
    TWAPOrderParameters,
)


def encode_twap_data(params: TWAPOrderParameters) -> str:
    """
    Encode TWAP order parameters to staticInput format.

    Args:
        params: TWAP order parameters

    Returns:
        Hex-encoded staticInput string (with 0x prefix)
    """
    encoded = encode(
        [
            "address",  # sellToken
            "address",  # buyToken
            "address",  # receiver
            "uint256",  # partSellAmount
            "uint256",  # minPartLimit
            "uint256",  # t0
            "uint256",  # n
            "uint256",  # t
            "uint256",  # span
            "bytes32",  # appData
        ],
        [
            params.sellToken,
            params.buyToken,
            params.receiver,
            int(params.partSellAmount),
            int(params.minPartLimit),
            params.t0,
            params.n,
            params.t,
            params.span,
            bytes.fromhex(params.appData[2:]),  # Remove 0x prefix
        ],
    )
    return "0x" + encoded.hex()


def decode_twap_data(static_input: str) -> dict:
    """
    Decode TWAP staticInput back to parameters.

    Args:
        static_input: Hex-encoded staticInput string

    Returns:
        Dictionary with decoded TWAP parameters
    """
    from eth_abi import decode

    # Remove 0x prefix
    if static_input.startswith("0x"):
        static_input = static_input[2:]

    # pylint: disable=unsubscriptable-object
    decoded = decode(
        [
            "address",
            "address",
            "address",
            "uint256",
            "uint256",
            "uint256",
            "uint256",
            "uint256",
            "uint256",
            "bytes32",
        ],
        bytes.fromhex(static_input),
    )

    return {
        "sellToken": decoded[0],
        "buyToken": decoded[1],
        "receiver": decoded[2],
        "partSellAmount": decoded[3],
        "minPartLimit": decoded[4],
        "t0": decoded[5],
        "n": decoded[6],
        "t": decoded[7],
        "span": decoded[8],
        "appData": "0x" + decoded[9].hex(),  # pylint: disable=no-member
    }


def encode_stop_loss_data(params: StopLossOrderParameters) -> str:
    """
    Encode Stop-Loss order parameters to staticInput format.

    Args:
        params: Stop-Loss order parameters

    Returns:
        Hex-encoded staticInput string (with 0x prefix)
    """
    encoded = encode(
        [
            "address",  # sellToken
            "address",  # buyToken
            "uint256",  # sellAmount
            "uint256",  # buyAmount
            "bytes32",  # appData
            "address",  # receiver
            "bool",  # isSellOrder
            "bool",  # isPartiallyFillable
            "uint32",  # validTo
            "address",  # sellTokenPriceOracle
            "address",  # buyTokenPriceOracle
            "int256",  # strike
            "uint256",  # maxTimeSinceLastOracleUpdate
        ],
        [
            params.sellToken,
            params.buyToken,
            int(params.sellAmount),
            int(params.buyAmount),
            bytes.fromhex(params.appData[2:]),  # Remove 0x prefix
            params.receiver,
            params.isSellOrder,
            params.isPartiallyFillable,
            params.validTo,
            params.sellTokenPriceOracle,
            params.buyTokenPriceOracle,
            int(params.strike),
            params.maxTimeSinceLastOracleUpdate,
        ],
    )
    return "0x" + encoded.hex()


def decode_stop_loss_data(static_input: str) -> dict:
    """
    Decode Stop-Loss staticInput back to parameters.

    Args:
        static_input: Hex-encoded staticInput string

    Returns:
        Dictionary with decoded Stop-Loss parameters
    """
    from eth_abi import decode

    # Remove 0x prefix
    if static_input.startswith("0x"):
        static_input = static_input[2:]

    # pylint: disable=unsubscriptable-object
    decoded = decode(
        [
            "address",
            "address",
            "uint256",
            "uint256",
            "bytes32",
            "address",
            "bool",
            "bool",
            "uint32",
            "address",
            "address",
            "int256",
            "uint256",
        ],
        bytes.fromhex(static_input),
    )

    return {
        "sellToken": decoded[0],
        "buyToken": decoded[1],
        "sellAmount": decoded[2],
        "buyAmount": decoded[3],
        "appData": "0x" + decoded[4].hex(),  # pylint: disable=no-member
        "receiver": decoded[5],
        "isSellOrder": decoded[6],
        "isPartiallyFillable": decoded[7],
        "validTo": decoded[8],
        "sellTokenPriceOracle": decoded[9],
        "buyTokenPriceOracle": decoded[10],
        "strike": decoded[11],
        "maxTimeSinceLastOracleUpdate": decoded[12],
    }


def encode_good_after_time_data(params: GoodAfterTimeOrderParameters) -> str:
    """
    Encode Good-After-Time order parameters to staticInput format.

    Args:
        params: Good-After-Time order parameters

    Returns:
        Hex-encoded staticInput string (with 0x prefix)
    """
    encoded = encode(
        [
            "address",  # sellToken
            "address",  # buyToken
            "address",  # receiver
            "uint256",  # sellAmount
            "uint256",  # buyAmount
            "uint32",  # validTo
            "bytes32",  # appData
            "uint256",  # validFrom
            "string",  # buyTokenBalance
            "string",  # sellTokenBalance
            "bool",  # partiallyFillable
        ],
        [
            params.sellToken,
            params.buyToken,
            params.receiver,
            int(params.sellAmount),
            int(params.buyAmount),
            params.validTo,
            bytes.fromhex(params.appData[2:]),  # Remove 0x prefix
            params.validFrom,
            params.buyTokenBalance.value,
            params.sellTokenBalance.value,
            params.partiallyFillable,
        ],
    )
    return "0x" + encoded.hex()


def decode_good_after_time_data(static_input: str) -> dict:
    """
    Decode Good-After-Time staticInput back to parameters.

    Args:
        static_input: Hex-encoded staticInput string

    Returns:
        Dictionary with decoded Good-After-Time parameters
    """
    from eth_abi import decode

    # Remove 0x prefix
    if static_input.startswith("0x"):
        static_input = static_input[2:]

    # pylint: disable=unsubscriptable-object
    decoded = decode(
        [
            "address",
            "address",
            "address",
            "uint256",
            "uint256",
            "uint32",
            "bytes32",
            "uint256",
            "string",
            "string",
            "bool",
        ],
        bytes.fromhex(static_input),
    )

    return {
        "sellToken": decoded[0],
        "buyToken": decoded[1],
        "receiver": decoded[2],
        "sellAmount": decoded[3],
        "buyAmount": decoded[4],
        "validTo": decoded[5],
        "appData": "0x" + decoded[6].hex(),  # pylint: disable=no-member
        "validFrom": decoded[7],
        "buyTokenBalance": decoded[8],
        "sellTokenBalance": decoded[9],
        "partiallyFillable": decoded[10],
    }
