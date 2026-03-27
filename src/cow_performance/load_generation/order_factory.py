"""
Order factory for generating CoW Protocol orders.

This module provides the OrderFactory class which generates realistic market and limit
orders with configurable parameters, token pairs, and amounts.
"""

import random
import time
from decimal import Decimal
from typing import Any

from eth_account import Account
from eth_account.signers.local import LocalAccount

from .app_data import create_app_data
from .order_schema import (
    OrderBalance,
    OrderClass,
    OrderKind,
    OrderParameters,
    SignedOrder,
    SigningScheme,
)
from .order_validation import assert_valid_order
from .token_pair import TokenPair, TokenPairRegistry


class OrderFactory:
    """
    Factory for generating CoW Protocol orders with realistic parameters.

    This class provides methods to create market and limit orders with configurable
    parameters including token pairs, amounts, and validity duration.
    """

    def __init__(
        self,
        token_pair_registry: TokenPairRegistry,
        chain_id: int,
        settlement_contract: str,
        amount_range: tuple[float, float] | None = None,
        valid_duration: int = 120,
        default_app_data: str = "0x0000000000000000000000000000000000000000000000000000000000000000",
        fee_percentage: float = 0.001,
        api_client: Any | None = None,
    ) -> None:
        """
        Initialize the order factory.

        Args:
            token_pair_registry: Registry of available token pairs
            chain_id: Chain ID (1 for mainnet, etc.)
            settlement_contract: Address of CoW Protocol settlement contract
            amount_range: Min and max amounts in token units (default: 0.1 to 10.0)
            valid_duration: Order validity duration in seconds (default: 120 = 2 minutes)
            default_app_data: Default appData hash (default: zero hash)
            fee_percentage: Fee as percentage of sell amount (default: 0.1%)
            api_client: Optional API client for getting quotes (enables realistic pricing)
        """
        self.token_pair_registry = token_pair_registry
        self.chain_id = chain_id
        self.settlement_contract = settlement_contract
        self.amount_range = amount_range or (0.1, 10.0)
        self.valid_duration = valid_duration
        self.default_app_data = default_app_data
        self.fee_percentage = fee_percentage
        self.api_client = api_client

        # Validate configuration
        if self.amount_range[0] <= 0:
            raise ValueError("Minimum amount must be positive")
        if self.amount_range[0] >= self.amount_range[1]:
            raise ValueError("Maximum amount must be greater than minimum amount")
        if self.valid_duration <= 0:
            raise ValueError("Valid duration must be positive")
        if self.fee_percentage < 0 or self.fee_percentage > 1:
            raise ValueError("Fee percentage must be between 0 and 1")

        # Generate appData with orderClass metadata
        self.market_app_data_hash, self.market_app_data_doc = create_app_data(OrderClass.MARKET)
        self.limit_app_data_hash, self.limit_app_data_doc = create_app_data(OrderClass.LIMIT)

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

    def _get_market_rate_fallback(self, sell_token_symbol: str, buy_token_symbol: str) -> Decimal:
        """
        Get approximate market rate for common token pairs as fallback.

        This provides realistic pricing when quote API fails, ensuring orders
        are economically viable for solvers.

        Args:
            sell_token_symbol: Symbol of token being sold
            buy_token_symbol: Symbol of token being bought

        Returns:
            Approximate exchange rate (sell token → buy token)
        """
        # Approximate USD values for common tokens (mainnet fork)
        usd_values = {
            "WETH": Decimal(3000),  # ~$3000
            "DAI": Decimal(1),  # $1
            "USDC": Decimal(1),  # $1
            "USDT": Decimal(1),  # $1
        }

        # Get USD values for both tokens
        sell_usd = usd_values.get(sell_token_symbol, Decimal(1))
        buy_usd = usd_values.get(buy_token_symbol, Decimal(1))

        # Calculate exchange rate with 15% surplus for solver profitability
        # Surplus makes the order more favorable to buyers (solvers)
        market_rate = sell_usd / buy_usd
        surplus_factor = Decimal("0.85")  # Give 15% better price to solver

        return market_rate * surplus_factor

    def _calculate_fee_amount(self, sell_amount_wei: int) -> int:
        """
        Calculate fee amount based on sell amount.

        Args:
            sell_amount_wei: Sell amount in wei

        Returns:
            Fee amount in wei
        """
        fee = int(sell_amount_wei * self.fee_percentage)
        # Allow zero fees when fee_percentage is 0 (required for some test environments)
        if self.fee_percentage == 0:
            return 0
        return max(1, fee)  # Ensure at least 1 wei for non-zero fees

    def _get_valid_to_timestamp(self) -> int:
        """
        Get validTo timestamp based on current time and valid_duration.

        Returns:
            Unix timestamp for order expiry
        """
        return int(time.time()) + self.valid_duration

    async def create_market_order(
        self,
        trader_account: LocalAccount,
        token_pair: TokenPair | None = None,
        sell_amount: float | None = None,
        kind: OrderKind = OrderKind.SELL,
    ) -> SignedOrder:
        """
        Generate a realistic market order.

        Market orders in CoW Protocol are limit orders with shorter expiration times
        (typically 2 minutes) and fill-or-kill semantics (partiallyFillable=False).
        The price is approximated as 1:1 for testing scenarios.

        Args:
            trader_account: Account to sign the order
            token_pair: Token pair to trade (if None, random selection)
            sell_amount: Sell amount in token units (if None, random)
            kind: Order kind (buy or sell)

        Returns:
            Signed market order ready for submission
        """
        # Select token pair
        if token_pair is None:
            token_pair = self.token_pair_registry.select_weighted_random()

        # Generate sell amount
        if sell_amount is None:
            sell_amount = self._generate_random_amount(*self.amount_range)

        # Convert to wei
        sell_amount_wei = token_pair.sell_token.to_wei(sell_amount)

        # Get realistic quote with surplus if API client available
        quote_id = None
        if self.api_client is not None:
            # Quote is required - if it fails, let the exception propagate
            # The caller should retry with different parameters (amount, token pair, etc.)
            quote = await self.api_client.get_quote(
                sell_token=token_pair.sell_token.address,
                buy_token=token_pair.buy_token.address,
                sell_amount=str(sell_amount_wei),
                from_address=trader_account.address,
                kind=kind.value,
                app_data=self.market_app_data_hash,  # Include appData for accurate quote
                validity_seconds=self.valid_duration,  # Market orders: short validity (e.g., 120s)
            )
            # Use values from quote (matches CoW Swap frontend behavior)
            # The quote's sellAmount is AFTER fees are deducted
            # Fee is implicit in the sellAmount, so feeAmount field must be 0
            sell_amount_wei = int(quote["quote"]["sellAmount"])
            # Apply 15% slippage to buy amount to ensure solver profitability
            # This gives the solver room to profit after gas costs (~$5-10)
            buy_amount_wei = int(int(quote["quote"]["buyAmount"]) * 0.85)
            fee_amount_wei = 0  # Fee is implicit (sellAmountBeforeFee = sellAmount + fee)
            market_valid_to = int(quote["quote"]["validTo"])
            quote_id = quote["id"]  # Extract quote ID for market order classification
        else:
            # No API client - use approximate market rates (dry-run mode)
            fallback_rate = self._get_market_rate_fallback(
                token_pair.sell_token.symbol,
                token_pair.buy_token.symbol,
            )
            buy_amount_wei = self._calculate_buy_amount(
                sell_amount_wei,
                token_pair.sell_token.decimals,
                token_pair.buy_token.decimals,
                price=fallback_rate,
            )
            fee_amount_wei = 0  # Use zero fee in dry-run mode
            # Market orders have shorter expiration (2 minutes) for immediate execution
            market_valid_to = int(time.time()) + self.valid_duration

        # Create order parameters with market orderClass metadata
        params = OrderParameters(
            sellToken=token_pair.sell_token.address,
            buyToken=token_pair.buy_token.address,
            sellAmount=str(sell_amount_wei),
            buyAmount=str(buy_amount_wei),
            validTo=market_valid_to,
            appData=self.market_app_data_hash,  # Use market-specific appData
            feeAmount=str(fee_amount_wei),
            kind=kind,
            partiallyFillable=False,  # Market orders: fill-or-kill semantics
            sellTokenBalance=OrderBalance.ERC20,
            buyTokenBalance=OrderBalance.ERC20,
            receiver=None,
        )

        # Validate order
        assert_valid_order(params)

        # Sign order (include quote_id for market orders)
        return self._sign_order(params, trader_account, quote_id=quote_id)

    async def create_limit_order(
        self,
        trader_account: LocalAccount,
        token_pair: TokenPair | None = None,
        limit_price: Decimal | None = None,
        sell_amount: float | None = None,
        kind: OrderKind = OrderKind.SELL,
    ) -> SignedOrder:
        """
        Generate a realistic limit order.

        Limit orders in CoW Protocol specify an exact price and typically have longer
        expiration times (hours to days). They allow partial fills so the order can
        be gradually filled as liquidity becomes available.

        Args:
            trader_account: Account to sign the order
            token_pair: Token pair to trade (if None, random selection)
            limit_price: Limit price (sell token / buy token ratio)
            sell_amount: Sell amount in token units (if None, random)
            kind: Order kind (buy or sell)

        Returns:
            Signed limit order ready for submission
        """
        # Select token pair
        if token_pair is None:
            token_pair = self.token_pair_registry.select_weighted_random()

        # Generate sell amount
        if sell_amount is None:
            sell_amount = self._generate_random_amount(*self.amount_range)

        # Convert to wei
        sell_amount_wei = token_pair.sell_token.to_wei(sell_amount)

        # Get realistic quote with surplus if API client available
        quote_id = None
        if self.api_client is not None:
            # Quote is required - if it fails, let the exception propagate
            # The caller should retry with different parameters (amount, token pair, etc.)
            quote = await self.api_client.get_quote(
                sell_token=token_pair.sell_token.address,
                buy_token=token_pair.buy_token.address,
                sell_amount=str(sell_amount_wei),
                from_address=trader_account.address,
                kind=kind.value,
                app_data=self.limit_app_data_hash,  # Include appData for accurate quote
            )
            # Use values from quote (matches CoW Swap frontend behavior)
            # The quote's sellAmount is AFTER fees are deducted
            # Fee is implicit in the sellAmount, so feeAmount field must be 0
            sell_amount_wei = int(quote["quote"]["sellAmount"])
            # Apply 15% slippage to buy amount to ensure solver profitability
            # This gives the solver room to profit after gas costs (~$5-10)
            buy_amount_wei = int(int(quote["quote"]["buyAmount"]) * 0.85)
            fee_amount_wei = 0  # Fee is implicit (sellAmountBeforeFee = sellAmount + fee)
<<<<<<< HEAD
            # Override API's valid_to with our configured valid_duration for testing
            valid_to = self._get_valid_to_timestamp()
=======
            valid_to = int(quote["quote"]["validTo"])
>>>>>>> 401ffd3a52dae443146c8441ae8805cc196d2ac9
            quote_id = quote["id"]  # Extract quote ID
        else:
            # No API client - use approximate market rates (dry-run mode)
            if limit_price is None:
                # Use market rate with ±10% variation for limit orders
                market_rate = self._get_market_rate_fallback(
                    token_pair.sell_token.symbol,
                    token_pair.buy_token.symbol,
                )
                price_variation = Decimal(str(random.uniform(0.9, 1.1)))
                limit_price = market_rate * price_variation
            buy_amount_wei = self._calculate_buy_amount(
                sell_amount_wei,
                token_pair.sell_token.decimals,
                token_pair.buy_token.decimals,
                price=limit_price,
            )
            fee_amount_wei = 0  # Use zero fee in dry-run mode
            # Limit orders use configured valid_duration (default 300s = 5 minutes)
            # In production, this would typically be hours to days
            valid_to = self._get_valid_to_timestamp()

        # Create order parameters with limit orderClass metadata
        params = OrderParameters(
            sellToken=token_pair.sell_token.address,
            buyToken=token_pair.buy_token.address,
            sellAmount=str(sell_amount_wei),
            buyAmount=str(buy_amount_wei),
            validTo=valid_to,
            appData=self.limit_app_data_hash,  # Use limit-specific appData
            feeAmount=str(fee_amount_wei),
            kind=kind,
            partiallyFillable=False,  # Fill-or-kill (orderbook doesn't support partial fills)
            sellTokenBalance=OrderBalance.ERC20,
            buyTokenBalance=OrderBalance.ERC20,
            receiver=None,
        )

        # Validate order
        assert_valid_order(params)

        # Sign order (include quote_id if available)
        return self._sign_order(params, trader_account, quote_id=quote_id)

    def _sign_order(
        self,
        params: OrderParameters,
        trader_account: LocalAccount,
        quote_id: int | None = None,
    ) -> SignedOrder:
        """
        Sign an order using EIP-712.

        Args:
            params: Order parameters to sign
            trader_account: Account to sign with
            quote_id: Optional quote ID for market orders (enables proper classification)

        Returns:
            Signed order
        """
        # Prepare EIP-712 typed data
        domain_data = {
            "name": "Gnosis Protocol",
            "version": "v2",
            "chainId": self.chain_id,
            "verifyingContract": self.settlement_contract,
        }

        message_types = {
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

        message_data = {
            "sellToken": params.sellToken,
            "buyToken": params.buyToken,
            "receiver": params.receiver or "0x0000000000000000000000000000000000000000",
            "sellAmount": int(params.sellAmount),
            "buyAmount": int(params.buyAmount),
            "validTo": params.validTo,
            "appData": params.appData,
            "feeAmount": int(params.feeAmount),
            "kind": params.kind.value,
            "partiallyFillable": params.partiallyFillable,
            "sellTokenBalance": params.sellTokenBalance.value,
            "buyTokenBalance": params.buyTokenBalance.value,
        }

        # Sign using EIP-712 (Account.sign_typed_data is a class method)
        signed_message = Account.sign_typed_data(
            private_key=trader_account.key,
            domain_data=domain_data,
            message_types=message_types,
            message_data=message_data,
        )

        # Create signed order
        signed_order = SignedOrder(  # type: ignore[call-arg]
            sellToken=params.sellToken,
            buyToken=params.buyToken,
            sellAmount=params.sellAmount,
            buyAmount=params.buyAmount,
            validTo=params.validTo,
            appData=params.appData,
            feeAmount=params.feeAmount,
            kind=params.kind,
            partiallyFillable=params.partiallyFillable,
            sellTokenBalance=params.sellTokenBalance,
            buyTokenBalance=params.buyTokenBalance,
            receiver=params.receiver,
            from_=trader_account.address,
            signingScheme=SigningScheme.EIP712,
            signature="0x" + signed_message.signature.hex(),
            quoteId=quote_id,  # Include quote ID for market order classification
        )

        return signed_order

    async def create_batch_orders(
        self,
        trader_account: LocalAccount,
        count: int,
        market_order_ratio: float = 0.5,
    ) -> list[SignedOrder]:
        """
        Generate a batch of mixed market and limit orders.

        Args:
            trader_account: Account to sign orders
            count: Number of orders to generate
            market_order_ratio: Ratio of market orders (0.0 to 1.0, default 0.5)

        Returns:
            List of signed orders
        """
        if count <= 0:
            raise ValueError("Count must be positive")
        if market_order_ratio < 0 or market_order_ratio > 1:
            raise ValueError("Market order ratio must be between 0 and 1")

        orders = []
        for _ in range(count):
            # Randomly decide order type based on ratio
            if random.random() < market_order_ratio:
                order = await self.create_market_order(trader_account)
            else:
                order = await self.create_limit_order(trader_account)
            orders.append(order)

        return orders
