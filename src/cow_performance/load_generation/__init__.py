"""
Load generation module for CoW Protocol performance testing.

This module provides order generation, token pair management, validation,
template-based order creation, and user simulation for load testing CoW Protocol.
"""

# Re-export order metrics models from the metrics module for backward compatibility
from cow_performance.metrics import OrderMetadata, OrderMetrics, OrderStatus

from .app_data import compute_app_data_hash, create_app_data, create_app_data_doc
from .oracles import (
    MAINNET_ORACLES,
    OracleRegistry,
    get_oracle_address,
    get_supported_oracle_chains,
)
from .order_factory import OrderFactory
from .order_schema import (
    EIP712Domain,
    OrderBalance,
    OrderClass,
    OrderKind,
    OrderParameters,
    SignedOrder,
    SigningScheme,
    create_order_hash,
    get_order_domain,
    get_order_types,
)
from .order_signer import OrderSigner
from .order_templates import (
    OrderTemplate,
    OrderTemplateRegistry,
    create_default_templates,
)
from .order_tracker import OrderTracker
from .order_validation import (
    OrderValidationError,
    assert_valid_order,
    assert_valid_signed_order,
    is_valid_order,
    is_valid_signed_order,
    validate_order_parameters,
    validate_signed_order,
)
from .safe_wallet import SafeWallet, deploy_safe_wallet
from .status_mapping import (
    COW_API_STATUS_MAPPING,
    is_api_status_terminal,
    map_api_status_to_order_status,
)
from .token_pair import (
    Token,
    TokenPair,
    TokenPairRegistry,
    create_mainnet_token_registry,
    create_polygon_token_registry,
)
from .trader_account import TraderAccount, TraderPool
from .trader_orchestrator import (
    OrchestrationConfig,
    RateLimitConfig,
    RateLimiter,
    TraderOrchestrator,
    run_load_test,
)
from .trader_simulator import TraderBehaviorConfig, TraderSimulator, TradingPattern

__all__ = [
    # Order schema
    "OrderKind",
    "OrderClass",
    "OrderBalance",
    "SigningScheme",
    "OrderParameters",
    "SignedOrder",
    "EIP712Domain",
    "create_order_hash",
    "get_order_domain",
    "get_order_types",
    # AppData
    "create_app_data",
    "create_app_data_doc",
    "compute_app_data_hash",
    # Token pairs
    "Token",
    "TokenPair",
    "TokenPairRegistry",
    "create_mainnet_token_registry",
    "create_polygon_token_registry",
    # Order factory
    "OrderFactory",
    # Templates
    "OrderTemplate",
    "OrderTemplateRegistry",
    "create_default_templates",
    # Validation
    "OrderValidationError",
    "validate_order_parameters",
    "validate_signed_order",
    "is_valid_order",
    "is_valid_signed_order",
    "assert_valid_order",
    "assert_valid_signed_order",
    # Oracles
    "OracleRegistry",
    "get_oracle_address",
    "get_supported_oracle_chains",
    "MAINNET_ORACLES",
    # User simulation
    "TraderAccount",
    "TraderPool",
    "SafeWallet",
    "deploy_safe_wallet",
    "OrderSigner",
    "OrderStatus",
    "OrderMetadata",
    "OrderMetrics",
    "OrderTracker",
    "COW_API_STATUS_MAPPING",
    "is_api_status_terminal",
    "map_api_status_to_order_status",
    "TradingPattern",
    "TraderBehaviorConfig",
    "TraderSimulator",
    "OrchestrationConfig",
    "RateLimitConfig",
    "RateLimiter",
    "TraderOrchestrator",
    "run_load_test",
]
