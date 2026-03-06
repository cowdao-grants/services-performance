"""
Order templates for generating configurable CoW Protocol orders.

This module provides a template system for creating orders with pre-configured
parameters that can be overridden for specific use cases.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from eth_account.signers.local import LocalAccount

from .order_factory import OrderFactory
from .order_schema import OrderBalance, OrderKind, SignedOrder
from .token_pair import TokenPair


@dataclass
class OrderTemplate:
    """
    Template for generating orders with pre-configured parameters.

    Templates allow defining default parameters that can be overridden
    when creating specific orders.
    """

    name: str
    description: str
    order_type: str  # "market" or "limit"
    kind: OrderKind = OrderKind.SELL
    sell_amount_range: tuple[float, float] = (0.1, 10.0)
    limit_price: Decimal | None = None
    partially_fillable: bool = False
    sell_token_balance: OrderBalance = OrderBalance.ERC20
    buy_token_balance: OrderBalance = OrderBalance.ERC20
    valid_duration: int = 3600
    fee_percentage: float = 0.001
    token_pair_filter: str | None = None  # e.g., "WETH/*" or "*/USDC"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate template after initialization."""
        if self.order_type not in ("market", "limit"):
            raise ValueError(f"Invalid order type: {self.order_type}")
        if self.sell_amount_range[0] <= 0:
            raise ValueError("Minimum sell amount must be positive")
        if self.sell_amount_range[0] >= self.sell_amount_range[1]:
            raise ValueError("Maximum sell amount must be greater than minimum")
        if self.valid_duration <= 0:
            raise ValueError("Valid duration must be positive")
        if self.fee_percentage < 0 or self.fee_percentage > 1:
            raise ValueError("Fee percentage must be between 0 and 1")

    def matches_token_pair(self, pair: TokenPair) -> bool:
        """
        Check if token pair matches the template filter.

        Args:
            pair: Token pair to check

        Returns:
            True if pair matches filter or no filter is set
        """
        if self.token_pair_filter is None:
            return True

        sell_filter, buy_filter = self.token_pair_filter.split("/")

        if sell_filter != "*" and sell_filter != pair.sell_token.symbol:
            return False

        if buy_filter != "*" and buy_filter != pair.buy_token.symbol:
            return False

        return True


class OrderTemplateRegistry:
    """Registry for managing and applying order templates."""

    def __init__(self) -> None:
        """Initialize the template registry."""
        self._templates: dict[str, OrderTemplate] = {}

    def register(self, template: OrderTemplate) -> None:
        """
        Register a new template.

        Args:
            template: Template to register
        """
        self._templates[template.name] = template

    def get(self, name: str) -> OrderTemplate | None:
        """
        Get a template by name.

        Args:
            name: Template name

        Returns:
            Template if found, None otherwise
        """
        return self._templates.get(name)

    def list_templates(self) -> list[str]:
        """
        List all registered template names.

        Returns:
            List of template names
        """
        return list(self._templates.keys())

    async def create_order_from_template(
        self,
        template_name: str,
        factory: OrderFactory,
        trader_account: LocalAccount,
        token_pair: TokenPair | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> SignedOrder:
        """
        Create an order from a template with optional overrides.

        Args:
            template_name: Name of template to use
            factory: OrderFactory instance
            trader_account: Account to sign the order
            token_pair: Token pair (if None, factory will select)
            overrides: Dictionary of parameters to override

        Returns:
            Signed order

        Raises:
            ValueError: If template not found
        """
        template = self.get(template_name)
        if template is None:
            raise ValueError(f"Template not found: {template_name}")

        overrides = overrides or {}

        # Get parameters from template with overrides
        kind = overrides.get("kind", template.kind)
        sell_amount = overrides.get("sell_amount")

        # Select token pair
        if token_pair is None:
            # Try to select matching pair from registry
            all_pairs = factory.token_pair_registry.get_all_pairs()
            matching_pairs = [p for p in all_pairs if template.matches_token_pair(p)]
            if not matching_pairs:
                raise ValueError(
                    f"No token pairs match template filter: {template.token_pair_filter}"
                )
            token_pair = factory.token_pair_registry.select_weighted_random()

        # Create order based on template type
        if template.order_type == "market":
            return await factory.create_market_order(
                trader_account=trader_account,
                token_pair=token_pair,
                sell_amount=sell_amount,
                kind=kind,
            )
        else:  # limit
            limit_price = overrides.get("limit_price", template.limit_price)
            return await factory.create_limit_order(
                trader_account=trader_account,
                token_pair=token_pair,
                limit_price=limit_price,
                sell_amount=sell_amount,
                kind=kind,
            )


def create_default_templates() -> OrderTemplateRegistry:
    """
    Create a registry with default order templates.

    Returns:
        OrderTemplateRegistry with pre-configured templates
    """
    registry = OrderTemplateRegistry()

    # Small market order template
    registry.register(
        OrderTemplate(
            name="small_market",
            description="Small market order (0.1-1.0 tokens)",
            order_type="market",
            kind=OrderKind.SELL,
            sell_amount_range=(0.1, 1.0),
            valid_duration=1800,  # 30 minutes
        )
    )

    # Medium market order template
    registry.register(
        OrderTemplate(
            name="medium_market",
            description="Medium market order (1.0-10.0 tokens)",
            order_type="market",
            kind=OrderKind.SELL,
            sell_amount_range=(1.0, 10.0),
            valid_duration=3600,  # 1 hour
        )
    )

    # Large market order template
    registry.register(
        OrderTemplate(
            name="large_market",
            description="Large market order (10.0-100.0 tokens)",
            order_type="market",
            kind=OrderKind.SELL,
            sell_amount_range=(10.0, 100.0),
            valid_duration=7200,  # 2 hours
        )
    )

    # Conservative limit order template
    registry.register(
        OrderTemplate(
            name="conservative_limit",
            description="Conservative limit order with tight spread",
            order_type="limit",
            kind=OrderKind.SELL,
            sell_amount_range=(1.0, 10.0),
            limit_price=Decimal("0.99"),  # 1% below market
            valid_duration=7200,  # 2 hours
        )
    )

    # Aggressive limit order template
    registry.register(
        OrderTemplate(
            name="aggressive_limit",
            description="Aggressive limit order with wide spread",
            order_type="limit",
            kind=OrderKind.SELL,
            sell_amount_range=(1.0, 10.0),
            limit_price=Decimal("0.95"),  # 5% below market
            valid_duration=86400,  # 24 hours
        )
    )

    # WETH buy template
    registry.register(
        OrderTemplate(
            name="weth_buy",
            description="Buy WETH with any token",
            order_type="market",
            kind=OrderKind.BUY,
            sell_amount_range=(100.0, 1000.0),  # Stablecoin amounts
            token_pair_filter="*/WETH",
            valid_duration=1800,
        )
    )

    # Stablecoin swap template
    registry.register(
        OrderTemplate(
            name="stablecoin_swap",
            description="Swap between stablecoins",
            order_type="market",
            kind=OrderKind.SELL,
            sell_amount_range=(100.0, 10000.0),
            token_pair_filter="DAI/USDC",  # Example, can be expanded
            valid_duration=1800,
            fee_percentage=0.0001,  # Lower fee for stablecoin swaps
        )
    )

    # Partially fillable order template
    registry.register(
        OrderTemplate(
            name="partially_fillable",
            description="Large order that can be partially filled",
            order_type="limit",
            kind=OrderKind.SELL,
            sell_amount_range=(10.0, 100.0),
            limit_price=Decimal("0.98"),
            partially_fillable=True,
            valid_duration=86400,  # 24 hours
        )
    )

    return registry
