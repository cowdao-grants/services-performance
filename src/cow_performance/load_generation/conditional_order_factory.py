"""
Factory for generating conditional orders for CoW Protocol ComposableCow.

This module provides the ConditionalOrderFactory class which generates
TWAP, Stop-Loss, and Good-After-Time orders with configurable parameters.
"""

import random
import secrets
import time
from decimal import Decimal

from .abi_encoding import (
    encode_good_after_time_data,
    encode_stop_loss_data,
    encode_twap_data,
)
from .conditional_order_schema import (
    ConditionalOrder,
    ConditionalOrderParams,
    GoodAfterTimeOrderParameters,
    SigningScheme,
    StopLossOrderParameters,
    TWAPOrderParameters,
)
from .handlers import get_composable_cow_address, get_handler_address
from .oracles import OracleRegistry
from .order_schema import OrderBalance
from .token_pair import TokenPair, TokenPairRegistry


class ConditionalOrderFactory:
    """
    Factory for creating CoW Protocol conditional orders.

    This class provides methods to create TWAP, Stop-Loss, and Good-After-Time
    orders with realistic parameters for load testing scenarios.
    """

    def __init__(
        self,
        token_pair_registry: TokenPairRegistry,
        chain_id: int,
        safe_wallet_address: str,
        amount_range: tuple[float, float] | None = None,
    ) -> None:
        """
        Initialize the conditional order factory.

        Args:
            token_pair_registry: Registry of available token pairs
            chain_id: Chain ID (1 for mainnet, etc.)
            safe_wallet_address: Address of Safe wallet (order owner)
            amount_range: Min and max amounts in token units (default: 1.0 to 100.0)
        """
        self.token_pair_registry = token_pair_registry
        self.chain_id = chain_id
        self.safe_wallet_address = safe_wallet_address
        self.amount_range = amount_range or (1.0, 100.0)

        # Initialize oracle registry
        self.oracle_registry = OracleRegistry(chain_id)

        # Get ComposableCow address
        self.composable_cow_address = get_composable_cow_address(chain_id)

        # Validate configuration
        if self.amount_range[0] <= 0:
            raise ValueError("Minimum amount must be positive")
        if self.amount_range[0] >= self.amount_range[1]:
            raise ValueError("Maximum amount must be greater than minimum amount")

    def _generate_random_amount(self, min_amount: float, max_amount: float) -> float:
        """
        Generate a random amount within the specified range.

        Args:
            min_amount: Minimum amount
            max_amount: Maximum amount

        Returns:
            Random amount in the range
        """
        # Use log scale for more realistic distribution
        log_min = Decimal(str(min_amount)).ln()
        log_max = Decimal(str(max_amount)).ln()
        log_amount = float(log_min) + random.random() * float(log_max - log_min)
        return float(Decimal(str(log_amount)).exp())

    def _calculate_buy_amount(
        self,
        sell_amount_wei: int,
        sell_token_decimals: int,
        buy_token_decimals: int,
        price: Decimal | None = None,
    ) -> int:
        """
        Calculate buy amount based on sell amount and price.

        Args:
            sell_amount_wei: Sell amount in wei
            sell_token_decimals: Decimals of sell token
            buy_token_decimals: Decimals of buy token
            price: Price of sell token in buy token (if None, use 1:1)

        Returns:
            Buy amount in wei
        """
        # Convert to decimal
        sell_amount_decimal = Decimal(sell_amount_wei) / Decimal(10**sell_token_decimals)

        # Apply price (default to 1:1 ratio)
        if price is None:
            price = Decimal(1)

        buy_amount_decimal = sell_amount_decimal * price

        # Convert to wei
        buy_amount_wei = int(buy_amount_decimal * Decimal(10**buy_token_decimals))

        return max(1, buy_amount_wei)  # Ensure at least 1 wei

    def _calculate_buy_amount_with_slippage(
        self,
        sell_amount_wei: int,
        token_pair: TokenPair,
        slippage_percent: float = 5.0,
    ) -> int:
        """
        Calculate buy amount with slippage applied.

        Args:
            sell_amount_wei: Sell amount in wei
            token_pair: Token pair
            slippage_percent: Slippage percentage (default 5%)

        Returns:
            Buy amount in wei with slippage
        """
        # Calculate at 1:1 price
        buy_amount_wei = self._calculate_buy_amount(
            sell_amount_wei,
            token_pair.sell_token.decimals,
            token_pair.buy_token.decimals,
            price=Decimal(1),
        )

        # Apply slippage (reduce buy amount to allow for price impact)
        slippage_factor = Decimal(1) - Decimal(slippage_percent) / Decimal(100)
        buy_amount_with_slippage = int(Decimal(buy_amount_wei) * slippage_factor)

        return max(1, buy_amount_with_slippage)

    def _get_oracle_for_token(self, token_symbol: str) -> str:
        """
        Get oracle address for a token symbol.

        Args:
            token_symbol: Token symbol (e.g., "WETH", "USDC")

        Returns:
            Oracle address (or zero address if not found)
        """
        try:
            return self.oracle_registry.get_oracle_for_token(token_symbol)
        except ValueError:
            # Return zero address as fallback for tokens without oracles
            return "0x0000000000000000000000000000000000000000"

    def create_twap_order(
        self,
        token_pair: TokenPair | None = None,
        total_amount: float | None = None,
        num_parts: int = 3,
        interval_seconds: int = 240,
        start_delay_seconds: int = 10,
    ) -> ConditionalOrder:
        """
        Create a TWAP order that splits a large trade into multiple parts.

        Args:
            token_pair: Token pair to trade (random if None)
            total_amount: Total amount to sell (random if None)
            num_parts: Number of parts to split into (>= 2)
            interval_seconds: Time between parts (default 240s = 4 minutes)
            start_delay_seconds: Delay before first part (default 10s)

        Returns:
            ConditionalOrder ready for submission
        """
        # Validate num_parts
        if num_parts < 2:
            raise ValueError("TWAP order must have at least 2 parts")

        # Select token pair
        if token_pair is None:
            token_pair = self.token_pair_registry.select_weighted_random()

        # Generate total amount
        if total_amount is None:
            total_amount = self._generate_random_amount(*self.amount_range)

        # Calculate per-part amounts
        part_amount = total_amount / num_parts
        part_amount_wei = token_pair.sell_token.to_wei(part_amount)

        # Calculate minimum buy amount per part (with slippage)
        min_buy_amount_wei = self._calculate_buy_amount_with_slippage(
            part_amount_wei, token_pair, slippage_percent=5.0
        )

        # Get current timestamp
        current_time = int(time.time())

        # Create TWAP parameters
        twap_params = TWAPOrderParameters(
            sellToken=token_pair.sell_token.address,
            buyToken=token_pair.buy_token.address,
            receiver=self.safe_wallet_address,
            partSellAmount=str(part_amount_wei),
            minPartLimit=str(min_buy_amount_wei),
            t0=current_time + start_delay_seconds,
            n=num_parts,
            t=interval_seconds,
            span=interval_seconds,  # Each part valid for interval duration
            appData="0x0000000000000000000000000000000000000000000000000000000000000000",
        )

        # Encode to staticInput
        static_input = encode_twap_data(twap_params)

        # Generate unique salt
        salt = "0x" + secrets.token_hex(32)

        # Get handler address
        handler = get_handler_address("twap", self.chain_id)

        return ConditionalOrder(
            params=ConditionalOrderParams(
                handler=handler,
                salt=salt,
                staticInput=static_input,
            ),
            owner=self.safe_wallet_address,
            signingScheme=SigningScheme.EIP1271,
        )

    def create_stop_loss_order(
        self,
        token_pair: TokenPair | None = None,
        sell_amount: float | None = None,
        strike_percentage: float = 90.0,
        valid_duration: int = 3600,
    ) -> ConditionalOrder:
        """
        Create a stop-loss order that triggers when price drops below strike.

        Args:
            token_pair: Token pair to trade (random if None)
            sell_amount: Amount to sell (random if None)
            strike_percentage: Strike as percentage of current price (default 90% = 10% drop)
            valid_duration: Order validity in seconds (default 1 hour)

        Returns:
            ConditionalOrder ready for submission
        """
        # Select token pair
        if token_pair is None:
            token_pair = self.token_pair_registry.select_weighted_random()

        # Generate sell amount
        if sell_amount is None:
            sell_amount = self._generate_random_amount(*self.amount_range)

        sell_amount_wei = token_pair.sell_token.to_wei(sell_amount)

        # Get oracle addresses
        sell_oracle = self._get_oracle_for_token(token_pair.sell_token.symbol)
        buy_oracle = self._get_oracle_for_token(token_pair.buy_token.symbol)

        # Calculate strike price (as percentage of "current" price)
        # Assuming 1:1 base price for simplicity in testing
        current_price = Decimal(1)
        strike_price = current_price * Decimal(strike_percentage) / Decimal(100)

        # Calculate minimum buy amount at strike price
        buy_amount_wei = self._calculate_buy_amount(
            sell_amount_wei,
            token_pair.sell_token.decimals,
            token_pair.buy_token.decimals,
            price=strike_price,
        )

        # Get current timestamp
        current_time = int(time.time())

        # Create stop-loss parameters
        stop_loss_params = StopLossOrderParameters(
            sellToken=token_pair.sell_token.address,
            buyToken=token_pair.buy_token.address,
            sellAmount=str(sell_amount_wei),
            buyAmount=str(buy_amount_wei),
            appData="0x0000000000000000000000000000000000000000000000000000000000000000",
            receiver=self.safe_wallet_address,
            isSellOrder=True,
            isPartiallyFillable=False,
            validTo=current_time + valid_duration,
            sellTokenPriceOracle=sell_oracle,
            buyTokenPriceOracle=buy_oracle,
            strike=str(int(strike_price * Decimal(10**18))),  # Convert to 18 decimals
            maxTimeSinceLastOracleUpdate=3600,  # 1 hour max staleness
        )

        # Encode to staticInput
        static_input = encode_stop_loss_data(stop_loss_params)

        # Generate unique salt
        salt = "0x" + secrets.token_hex(32)

        # Get handler address
        handler = get_handler_address("stop_loss", self.chain_id)

        return ConditionalOrder(
            params=ConditionalOrderParams(
                handler=handler,
                salt=salt,
                staticInput=static_input,
            ),
            owner=self.safe_wallet_address,
            signingScheme=SigningScheme.EIP1271,
        )

    def create_good_after_time_order(
        self,
        token_pair: TokenPair | None = None,
        sell_amount: float | None = None,
        delay_seconds: int = 300,
        valid_duration: int = 3600,
    ) -> ConditionalOrder:
        """
        Create a good-after-time order that becomes active after a delay.

        Args:
            token_pair: Token pair to trade (random if None)
            sell_amount: Amount to sell (random if None)
            delay_seconds: Delay before order activates (default 5 minutes)
            valid_duration: Order validity after activation (default 1 hour)

        Returns:
            ConditionalOrder ready for submission
        """
        # Select token pair
        if token_pair is None:
            token_pair = self.token_pair_registry.select_weighted_random()

        # Generate sell amount
        if sell_amount is None:
            sell_amount = self._generate_random_amount(*self.amount_range)

        sell_amount_wei = token_pair.sell_token.to_wei(sell_amount)

        # Calculate buy amount (1:1 with slippage)
        buy_amount_wei = self._calculate_buy_amount_with_slippage(
            sell_amount_wei, token_pair, slippage_percent=5.0
        )

        # Get current timestamp
        current_time = int(time.time())
        valid_from = current_time + delay_seconds
        valid_to = valid_from + valid_duration

        # Create good-after-time parameters
        gat_params = GoodAfterTimeOrderParameters(
            sellToken=token_pair.sell_token.address,
            buyToken=token_pair.buy_token.address,
            receiver=self.safe_wallet_address,
            sellAmount=str(sell_amount_wei),
            buyAmount=str(buy_amount_wei),
            validTo=valid_to,
            appData="0x0000000000000000000000000000000000000000000000000000000000000000",
            validFrom=valid_from,
            buyTokenBalance=OrderBalance.ERC20,
            sellTokenBalance=OrderBalance.ERC20,
            partiallyFillable=False,
        )

        # Encode to staticInput
        static_input = encode_good_after_time_data(gat_params)

        # Generate unique salt
        salt = "0x" + secrets.token_hex(32)

        # Get handler address
        handler = get_handler_address("good_after_time", self.chain_id)

        return ConditionalOrder(
            params=ConditionalOrderParams(
                handler=handler,
                salt=salt,
                staticInput=static_input,
            ),
            owner=self.safe_wallet_address,
            signingScheme=SigningScheme.EIP1271,
        )

    def create_batch_conditional_orders(
        self,
        count: int,
        order_types: list[str] | None = None,
    ) -> list[ConditionalOrder]:
        """
        Generate batch of mixed conditional orders.

        Args:
            count: Number of orders to generate
            order_types: List of types ["twap", "stop_loss", "good_after_time"]
                        (random mix if None)

        Returns:
            List of ConditionalOrder instances
        """
        if count <= 0:
            raise ValueError("Count must be positive")

        if order_types is None:
            order_types = ["twap", "stop_loss", "good_after_time"]

        # Validate order types
        valid_types = {"twap", "stop_loss", "good_after_time"}
        for order_type in order_types:
            if order_type not in valid_types:
                raise ValueError(
                    f"Invalid order type: {order_type}. " f"Valid types: {valid_types}"
                )

        orders = []
        for _ in range(count):
            order_type = random.choice(order_types)

            if order_type == "twap":
                order = self.create_twap_order()
            elif order_type == "stop_loss":
                order = self.create_stop_loss_order()
            else:  # good_after_time
                order = self.create_good_after_time_order()

            orders.append(order)

        return orders
