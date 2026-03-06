"""
Template system for conditional order generation.

This module provides templates for generating conditional orders with
predefined parameters for common use cases.
"""

# mypy: disable-error-code=call-arg

from typing import Any

from pydantic import BaseModel, Field


class ConditionalOrderTemplate(BaseModel):
    """
    Template for conditional order generation.

    Templates define predefined parameters for generating conditional orders
    with consistent characteristics for load testing scenarios.
    """

    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    order_type: str = Field(..., description="Order type (twap, stop_loss, good_after_time)")

    # TWAP-specific parameters
    num_parts: int | None = Field(None, description="Number of TWAP parts", ge=2)
    interval_seconds: int | None = Field(
        None, description="Interval between TWAP parts (seconds)", gt=0
    )
    start_delay_seconds: int | None = Field(
        None, description="Delay before first TWAP part (seconds)", ge=0
    )

    # Stop-Loss-specific parameters
    strike_percentage: float | None = Field(
        None, description="Strike as % of current price (e.g., 90.0 = 10% drop)", gt=0, le=100
    )

    # Good-After-Time-specific parameters
    delay_seconds: int | None = Field(
        None, description="Delay before order activates (seconds)", gt=0
    )

    # Common parameters
    amount_range: tuple[float, float] = Field(
        default=(1.0, 10.0), description="Min and max amounts in token units"
    )
    token_pair_filter: str | None = Field(
        None, description="Filter for specific token pairs (e.g., 'WETH-USDC')"
    )
    valid_duration: int = Field(
        default=3600, description="Order validity duration in seconds", gt=0
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


def create_default_conditional_templates() -> dict[str, ConditionalOrderTemplate]:
    """
    Create default conditional order templates for common use cases.

    Returns:
        Dictionary mapping template names to ConditionalOrderTemplate instances
    """
    return {
        # TWAP Templates
        "twap_small": ConditionalOrderTemplate(
            name="twap_small",
            description="Small TWAP order (3 parts, 4 min intervals)",
            order_type="twap",
            num_parts=3,
            interval_seconds=240,
            start_delay_seconds=10,
            amount_range=(10.0, 50.0),
            valid_duration=3600,
            metadata={"category": "twap", "size": "small"},
        ),
        "twap_medium": ConditionalOrderTemplate(
            name="twap_medium",
            description="Medium TWAP order (5 parts, 5 min intervals)",
            order_type="twap",
            num_parts=5,
            interval_seconds=300,
            start_delay_seconds=10,
            amount_range=(50.0, 200.0),
            valid_duration=7200,
            metadata={"category": "twap", "size": "medium"},
        ),
        "twap_large": ConditionalOrderTemplate(
            name="twap_large",
            description="Large TWAP order (10 parts, 10 min intervals)",
            order_type="twap",
            num_parts=10,
            interval_seconds=600,
            start_delay_seconds=10,
            amount_range=(100.0, 1000.0),
            valid_duration=14400,
            metadata={"category": "twap", "size": "large"},
        ),
        "twap_rapid": ConditionalOrderTemplate(
            name="twap_rapid",
            description="Rapid TWAP order (5 parts, 1 min intervals)",
            order_type="twap",
            num_parts=5,
            interval_seconds=60,
            start_delay_seconds=5,
            amount_range=(10.0, 100.0),
            valid_duration=1800,
            metadata={"category": "twap", "size": "rapid"},
        ),
        # Stop-Loss Templates
        "stop_loss_conservative": ConditionalOrderTemplate(
            name="stop_loss_conservative",
            description="Conservative stop-loss (5% below current)",
            order_type="stop_loss",
            strike_percentage=95.0,  # 5% drop triggers
            amount_range=(1.0, 10.0),
            valid_duration=3600,
            metadata={"category": "stop_loss", "risk": "conservative"},
        ),
        "stop_loss_moderate": ConditionalOrderTemplate(
            name="stop_loss_moderate",
            description="Moderate stop-loss (10% below current)",
            order_type="stop_loss",
            strike_percentage=90.0,  # 10% drop triggers
            amount_range=(1.0, 50.0),
            valid_duration=7200,
            metadata={"category": "stop_loss", "risk": "moderate"},
        ),
        "stop_loss_aggressive": ConditionalOrderTemplate(
            name="stop_loss_aggressive",
            description="Aggressive stop-loss (20% below current)",
            order_type="stop_loss",
            strike_percentage=80.0,  # 20% drop triggers
            amount_range=(1.0, 100.0),
            valid_duration=14400,
            metadata={"category": "stop_loss", "risk": "aggressive"},
        ),
        # Good-After-Time Templates
        "delayed_order_short": ConditionalOrderTemplate(
            name="delayed_order_short",
            description="Order active after 5 minutes",
            order_type="good_after_time",
            delay_seconds=300,
            amount_range=(1.0, 10.0),
            valid_duration=3600,
            metadata={"category": "good_after_time", "delay": "short"},
        ),
        "delayed_order_medium": ConditionalOrderTemplate(
            name="delayed_order_medium",
            description="Order active after 30 minutes",
            order_type="good_after_time",
            delay_seconds=1800,
            amount_range=(1.0, 50.0),
            valid_duration=7200,
            metadata={"category": "good_after_time", "delay": "medium"},
        ),
        "delayed_order_long": ConditionalOrderTemplate(
            name="delayed_order_long",
            description="Order active after 1 hour",
            order_type="good_after_time",
            delay_seconds=3600,
            amount_range=(1.0, 100.0),
            valid_duration=14400,
            metadata={"category": "good_after_time", "delay": "long"},
        ),
    }


class ConditionalOrderTemplateRegistry:
    """
    Registry for managing conditional order templates.

    This class provides methods to register, retrieve, and list templates
    for generating conditional orders.
    """

    def __init__(self, templates: dict[str, ConditionalOrderTemplate] | None = None):
        """
        Initialize the template registry.

        Args:
            templates: Initial templates (uses defaults if None)
        """
        if templates is None:
            templates = create_default_conditional_templates()
        self.templates = templates

    def register_template(self, template: ConditionalOrderTemplate) -> None:
        """
        Register a new template.

        Args:
            template: Template to register

        Raises:
            ValueError: If template name already exists
        """
        if template.name in self.templates:
            raise ValueError(f"Template '{template.name}' already exists")
        self.templates[template.name] = template

    def get_template(self, name: str) -> ConditionalOrderTemplate:
        """
        Get a template by name.

        Args:
            name: Template name

        Returns:
            ConditionalOrderTemplate instance

        Raises:
            KeyError: If template not found
        """
        if name not in self.templates:
            raise KeyError(
                f"Template '{name}' not found. "
                f"Available templates: {list(self.templates.keys())}"
            )
        return self.templates[name]

    def list_templates(self) -> list[str]:
        """
        List all registered template names.

        Returns:
            List of template names
        """
        return list(self.templates.keys())

    def list_templates_by_type(self, order_type: str) -> list[str]:
        """
        List templates filtered by order type.

        Args:
            order_type: Order type to filter by ("twap", "stop_loss", "good_after_time")

        Returns:
            List of template names matching the order type
        """
        return [
            name for name, template in self.templates.items() if template.order_type == order_type
        ]

    def get_all_templates(self) -> dict[str, ConditionalOrderTemplate]:
        """
        Get all registered templates.

        Returns:
            Dictionary mapping template names to templates
        """
        return self.templates.copy()

    def remove_template(self, name: str) -> None:
        """
        Remove a template from the registry.

        Args:
            name: Template name

        Raises:
            KeyError: If template not found
        """
        if name not in self.templates:
            raise KeyError(f"Template '{name}' not found")
        del self.templates[name]
