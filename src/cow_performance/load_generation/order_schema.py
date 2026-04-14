"""
Order schema models for CoW Protocol.

This module defines Pydantic models that match CoW Protocol order specifications,
including order kinds, classes, parameters, and signed orders with EIP-712 support.
"""

from enum import StrEnum

from eth_account.messages import encode_typed_data
from pydantic import BaseModel, ConfigDict, Field, field_validator
from web3 import Web3


class OrderKind(StrEnum):
    """Order kind indicating buy or sell side."""

    SELL = "sell"
    BUY = "buy"


class OrderClass(StrEnum):
    """Order class indicating market or limit order."""

    MARKET = "market"
    LIMIT = "limit"


class OrderBalance(StrEnum):
    """Token balance source for orders."""

    ERC20 = "erc20"
    EXTERNAL = "external"
    INTERNAL = "internal"


class SigningScheme(StrEnum):
    """Signature scheme for orders."""

    EIP712 = "eip712"
    ETHSIGN = "ethsign"
    EIP1271 = "eip1271"
    PRESIGN = "presign"


class OrderParameters(BaseModel):
    """
    Core parameters for a CoW Protocol order.

    This model represents all required fields for creating a valid CoW Protocol order,
    matching the specification at https://docs.cow.fi/cow-protocol/reference/core/intents/order-schema
    """

    sellToken: str = Field(..., description="Address of token to sell")
    buyToken: str = Field(..., description="Address of token to buy")
    sellAmount: str = Field(..., description="Amount of sellToken to sell (in wei)")
    buyAmount: str = Field(..., description="Amount of buyToken to buy (in wei)")
    validTo: int = Field(..., description="Unix timestamp until order is valid")
    appData: str = Field(..., description="App data hash (32 bytes)")
    feeAmount: str = Field(..., description="Fee amount in sellToken (in wei)")
    kind: OrderKind = Field(..., description="Order kind (buy or sell)")
    partiallyFillable: bool = Field(
        default=False, description="Whether order can be partially filled"
    )
    sellTokenBalance: OrderBalance = Field(
        default=OrderBalance.ERC20, description="Source of sell token balance"
    )
    buyTokenBalance: OrderBalance = Field(
        default=OrderBalance.ERC20, description="Destination for buy token"
    )
    receiver: str | None = Field(
        default=None, description="Receiver address (defaults to owner if None)"
    )

    @field_validator("sellToken", "buyToken", "receiver")
    @classmethod
    def validate_address(cls, v: str | None) -> str | None:
        """Validate Ethereum addresses are properly checksummed."""
        if v is None:
            return v
        if not Web3.is_address(v):
            raise ValueError(f"Invalid Ethereum address: {v}")
        return Web3.to_checksum_address(v)

    @field_validator("sellAmount", "buyAmount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        """Validate amounts are positive integers."""
        try:
            amount = int(v)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError as e:
            raise ValueError(f"Invalid amount: {v}") from e
        return v

    @field_validator("feeAmount")
    @classmethod
    def validate_fee_amount(cls, v: str) -> str:
        """Validate fee amount is non-negative integer (can be zero)."""
        try:
            amount = int(v)
            if amount < 0:
                raise ValueError("Fee amount must be non-negative")
        except ValueError as e:
            raise ValueError(f"Invalid fee amount: {v}") from e
        return v

    @field_validator("appData")
    @classmethod
    def validate_app_data(cls, v: str) -> str:
        """Validate appData is a valid 32-byte hex string."""
        if not v.startswith("0x"):
            raise ValueError("appData must start with 0x")
        if len(v) != 66:  # 0x + 64 hex chars = 32 bytes
            raise ValueError("appData must be 32 bytes (66 characters with 0x prefix)")
        try:
            int(v, 16)
        except ValueError as e:
            raise ValueError(f"appData must be valid hex: {v}") from e
        return v.lower()


class SignedOrder(BaseModel):
    """
    A complete CoW Protocol order with signature.

    This model includes all order parameters plus the required fields for
    submitting the order to the orderbook API.
    """

    sellToken: str
    buyToken: str
    sellAmount: str
    buyAmount: str
    validTo: int
    appData: str
    feeAmount: str
    kind: OrderKind
    partiallyFillable: bool
    sellTokenBalance: OrderBalance = OrderBalance.ERC20
    buyTokenBalance: OrderBalance = OrderBalance.ERC20
    receiver: str | None = None

    # Order metadata
    from_: str = Field(..., alias="from", description="Order owner address")
    signingScheme: SigningScheme = Field(
        default=SigningScheme.EIP712, description="Signature scheme used"
    )
    signature: str = Field(..., description="Order signature")
    quoteId: int | None = Field(
        default=None, description="Quote ID for market orders (enables proper classification)"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
    )


class EIP712Domain(BaseModel):
    """EIP-712 domain separator for CoW Protocol orders."""

    name: str = "Gnosis Protocol"
    version: str = "v2"
    chainId: int
    verifyingContract: str

    @field_validator("verifyingContract")
    @classmethod
    def validate_contract(cls, v: str) -> str:
        """Validate contract address is properly checksummed."""
        if not Web3.is_address(v):
            raise ValueError(f"Invalid contract address: {v}")
        return Web3.to_checksum_address(v)


def get_order_domain(chain_id: int, settlement_contract: str) -> dict:
    """
    Get the EIP-712 domain for CoW Protocol orders.

    Args:
        chain_id: The chain ID (1 for mainnet, 5 for Goerli, etc.)
        settlement_contract: Address of the settlement contract

    Returns:
        EIP-712 domain dictionary
    """
    domain = EIP712Domain(
        chainId=chain_id,
        verifyingContract=settlement_contract,
    )
    return domain.model_dump()


def get_order_types() -> dict:
    """
    Get the EIP-712 types for CoW Protocol orders.

    Returns:
        EIP-712 types dictionary
    """
    return {
        "Order": [
            {"name": "sellToken", "type": "address"},
            {"name": "buyToken", "type": "address"},
            {"name": "receiver", "type": "address"},
            {"name": "sellAmount", "type": "uint256"},
            {"name": "buyAmount", "type": "uint256"},
            {"name": "validTo", "type": "uint32"},
            {"name": "appData", "type": "bytes32"},
            {"name": "feeAmount", "type": "uint256"},
            {"name": "kind", "type": "string"},
            {"name": "partiallyFillable", "type": "bool"},
            {"name": "sellTokenBalance", "type": "string"},
            {"name": "buyTokenBalance", "type": "string"},
        ]
    }


def create_order_hash(
    order_params: OrderParameters,
    chain_id: int,
    settlement_contract: str,
) -> bytes:
    """
    Create EIP-712 hash for an order.

    Args:
        order_params: Order parameters to hash
        chain_id: Chain ID
        settlement_contract: Settlement contract address

    Returns:
        Order hash as bytes
    """
    domain = get_order_domain(chain_id, settlement_contract)
    types = get_order_types()

    # Prepare message data
    message = {
        "sellToken": order_params.sellToken,
        "buyToken": order_params.buyToken,
        "receiver": order_params.receiver or "0x0000000000000000000000000000000000000000",
        "sellAmount": int(order_params.sellAmount),
        "buyAmount": int(order_params.buyAmount),
        "validTo": order_params.validTo,
        "appData": order_params.appData,
        "feeAmount": int(order_params.feeAmount),
        "kind": order_params.kind.value,
        "partiallyFillable": order_params.partiallyFillable,
        "sellTokenBalance": order_params.sellTokenBalance.value,
        "buyTokenBalance": order_params.buyTokenBalance.value,
    }

    # Create typed data structure
    typed_data = {
        "types": {
            **types,
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
        },
        "primaryType": "Order",
        "domain": domain,
        "message": message,
    }

    # Encode and hash
    encoded = encode_typed_data(full_message=typed_data)
    return encoded.body
