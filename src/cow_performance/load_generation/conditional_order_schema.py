"""
Conditional order schema models for CoW Protocol ComposableCow.

This module defines Pydantic models for advanced order types including TWAP,
Stop-Loss, and Good-After-Time orders that use the ComposableCow framework.
"""

from pydantic import BaseModel, Field, field_validator
from web3 import Web3

from .order_schema import OrderBalance, SigningScheme


class TWAPOrderParameters(BaseModel):
    """
    Parameters for a TWAP (Time-Weighted Average Price) order.

    TWAP orders split a large trade into multiple smaller parts executed over time
    to minimize market impact and achieve better average pricing.
    """

    sellToken: str = Field(..., description="Address of token to sell")
    buyToken: str = Field(..., description="Address of token to buy")
    receiver: str = Field(..., description="Address to receive bought tokens")
    partSellAmount: str = Field(..., description="Amount to sell per part (in wei)")
    minPartLimit: str = Field(..., description="Minimum buy amount per part (in wei)")
    t0: int = Field(..., description="Start timestamp (Unix epoch)")
    n: int = Field(..., description="Number of parts (must be >= 2)", ge=2)
    t: int = Field(..., description="Time interval between parts (seconds)", gt=0)
    span: int = Field(..., description="Duration each part is valid (seconds)", gt=0)
    appData: str = Field(
        default="0x0000000000000000000000000000000000000000000000000000000000000000",
        description="App data hash (32 bytes)",
    )

    @field_validator("sellToken", "buyToken", "receiver")
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate Ethereum addresses are properly checksummed."""
        if not Web3.is_address(v):
            raise ValueError(f"Invalid Ethereum address: {v}")
        return Web3.to_checksum_address(v)

    @field_validator("partSellAmount", "minPartLimit")
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


class StopLossOrderParameters(BaseModel):
    """
    Parameters for a Stop-Loss order.

    Stop-loss orders trigger when the price (from Chainlink oracles) crosses
    a specified strike price, protecting against adverse price movements.
    """

    sellToken: str = Field(..., description="Address of token to sell")
    buyToken: str = Field(..., description="Address of token to buy")
    sellAmount: str = Field(..., description="Amount to sell (in wei)")
    buyAmount: str = Field(..., description="Minimum buy amount (in wei)")
    appData: str = Field(..., description="App data hash (32 bytes)")
    receiver: str = Field(..., description="Address to receive bought tokens")
    isSellOrder: bool = Field(..., description="True for sell order, False for buy order")
    isPartiallyFillable: bool = Field(
        default=False, description="Whether order can be partially filled"
    )
    validTo: int = Field(..., description="Unix timestamp until order is valid")
    sellTokenPriceOracle: str = Field(..., description="Chainlink oracle address for sell token")
    buyTokenPriceOracle: str = Field(..., description="Chainlink oracle address for buy token")
    strike: str = Field(..., description="Strike price in 18 decimals (trigger threshold)")
    maxTimeSinceLastOracleUpdate: int = Field(
        ..., description="Maximum staleness of oracle data (seconds)", gt=0
    )

    @field_validator(
        "sellToken", "buyToken", "receiver", "sellTokenPriceOracle", "buyTokenPriceOracle"
    )
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate Ethereum addresses are properly checksummed."""
        if not Web3.is_address(v):
            raise ValueError(f"Invalid Ethereum address: {v}")
        return Web3.to_checksum_address(v)

    @field_validator("sellAmount", "buyAmount", "strike")
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

    @field_validator("appData")
    @classmethod
    def validate_app_data(cls, v: str) -> str:
        """Validate appData is a valid 32-byte hex string."""
        if not v.startswith("0x"):
            raise ValueError("appData must start with 0x")
        if len(v) != 66:
            raise ValueError("appData must be 32 bytes (66 characters with 0x prefix)")
        try:
            int(v, 16)
        except ValueError as e:
            raise ValueError(f"appData must be valid hex: {v}") from e
        return v.lower()


class GoodAfterTimeOrderParameters(BaseModel):
    """
    Parameters for a Good-After-Time order.

    Good-after-time orders become active only after a specified timestamp,
    useful for scheduling trades or implementing time-based strategies.
    """

    sellToken: str = Field(..., description="Address of token to sell")
    buyToken: str = Field(..., description="Address of token to buy")
    receiver: str = Field(..., description="Address to receive bought tokens")
    sellAmount: str = Field(..., description="Amount to sell (in wei)")
    buyAmount: str = Field(..., description="Minimum buy amount (in wei)")
    validTo: int = Field(..., description="Unix timestamp until order is valid")
    appData: str = Field(..., description="App data hash (32 bytes)")
    validFrom: int = Field(..., description="Unix timestamp when order becomes active")
    buyTokenBalance: OrderBalance = Field(
        default=OrderBalance.ERC20, description="Source for buy token balance"
    )
    sellTokenBalance: OrderBalance = Field(
        default=OrderBalance.ERC20, description="Source for sell token balance"
    )
    partiallyFillable: bool = Field(
        default=False, description="Whether order can be partially filled"
    )

    @field_validator("sellToken", "buyToken", "receiver")
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate Ethereum addresses are properly checksummed."""
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

    @field_validator("appData")
    @classmethod
    def validate_app_data(cls, v: str) -> str:
        """Validate appData is a valid 32-byte hex string."""
        if not v.startswith("0x"):
            raise ValueError("appData must start with 0x")
        if len(v) != 66:
            raise ValueError("appData must be 32 bytes (66 characters with 0x prefix)")
        try:
            int(v, 16)
        except ValueError as e:
            raise ValueError(f"appData must be valid hex: {v}") from e
        return v.lower()


class ConditionalOrderParams(BaseModel):
    """
    Parameters for a conditional order in ComposableCow.

    This structure is submitted to ComposableCow.create() to register
    a conditional order with a specific handler.
    """

    handler: str = Field(..., description="Handler contract address")
    salt: str = Field(..., description="Unique identifier (32 bytes hex)")
    staticInput: str = Field(..., description="ABI-encoded order-specific data")

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        """Validate handler address is properly checksummed."""
        if not Web3.is_address(v):
            raise ValueError(f"Invalid handler address: {v}")
        return Web3.to_checksum_address(v)

    @field_validator("salt")
    @classmethod
    def validate_salt(cls, v: str) -> str:
        """Validate salt is a valid 32-byte hex string."""
        if not v.startswith("0x"):
            raise ValueError("salt must start with 0x")
        if len(v) != 66:  # 0x + 64 hex chars = 32 bytes
            raise ValueError("salt must be 32 bytes (66 characters with 0x prefix)")
        try:
            int(v, 16)
        except ValueError as e:
            raise ValueError(f"salt must be valid hex: {v}") from e
        return v.lower()

    @field_validator("staticInput")
    @classmethod
    def validate_static_input(cls, v: str) -> str:
        """Validate staticInput is valid hex data."""
        if not v.startswith("0x"):
            raise ValueError("staticInput must start with 0x")
        if len(v) < 2:
            raise ValueError("staticInput must contain data")
        try:
            int(v, 16)
        except ValueError as e:
            raise ValueError(f"staticInput must be valid hex: {v}") from e
        return v.lower()


class ConditionalOrder(BaseModel):
    """
    A complete conditional order ready for submission to ComposableCow.

    Conditional orders use EIP-1271 signatures (Safe wallet) or PRESIGN.
    """

    params: ConditionalOrderParams = Field(..., description="Conditional order parameters")
    owner: str = Field(..., description="Safe wallet address (order owner)")
    signingScheme: SigningScheme = Field(
        default=SigningScheme.EIP1271,
        description="Signature scheme (typically EIP1271 for Safe wallets)",
    )

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, v: str) -> str:
        """Validate owner address is properly checksummed."""
        if not Web3.is_address(v):
            raise ValueError(f"Invalid owner address: {v}")
        return Web3.to_checksum_address(v)
