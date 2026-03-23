# Conditional Orders

> TWAP, Stop-Loss, and Good-After-Time orders via ComposableCow.
>
> **See also**: [Order Generation](order-generation.md) | [User Simulation](user-simulation.md)

> **⚠️ Implementation Status**: Conditional order **generation** is fully implemented.
> On-chain submission via ComposableCow is **NOT yet implemented**. Orders can be created
> and signed, but will not be submitted to the blockchain or monitored for fills.
>
> Track implementation status: [trader_simulator.py:443-450](../src/cow_performance/load_generation/trader_simulator.py)

## Overview

The order generation module supports advanced CoW Protocol conditional orders through ComposableCow, enabling TWAP, Stop-Loss, and Good-After-Time orders for sophisticated trading strategies.

---

## Quick Start

```python
from cow_performance.load_generation import (
    ConditionalOrderFactory,
    create_mainnet_token_registry,
)

# Create conditional order factory
token_registry = create_mainnet_token_registry()
factory = ConditionalOrderFactory(
    token_pair_registry=token_registry,
    chain_id=1,
    safe_wallet_address="0x...",  # Your Safe wallet address
)

# Create TWAP order: 3000 USDC split into 3 parts over 12 minutes
twap_order = factory.create_twap_order(
    total_amount=3000.0,
    num_parts=3,
    interval_seconds=240,  # 4 minutes between parts
)

# Create stop-loss: Sell 1 WETH when price drops 10%
stop_loss_order = factory.create_stop_loss_order(
    sell_amount=1.0,
    strike_percentage=90.0,  # Trigger at 90% of current price
    valid_duration=3600,     # Valid for 1 hour
)

# Create good-after-time: Order activates after 5 minutes
delayed_order = factory.create_good_after_time_order(
    sell_amount=10.0,
    delay_seconds=300,
    valid_duration=3600,
)

# Generate mixed batch of conditional orders
batch = factory.create_batch_conditional_orders(
    count=50,
    order_types=["twap", "stop_loss", "good_after_time"]
)
```

**Important**: This example shows order creation only. The orders are not submitted to
ComposableCow or tracked on-chain. Integration with ComposableCow contract submission
is planned but not yet implemented.

---

## TWAP Orders

Time-Weighted Average Price orders split large trades into smaller parts executed over time to minimize market impact.

```python
twap = factory.create_twap_order(
    total_amount=1000.0,      # Total amount to trade
    num_parts=5,              # Split into 5 parts
    interval_seconds=600,     # 10 minutes between parts
    start_delay_seconds=10,   # Start after 10 seconds
)
```

**Use cases:**
- Large trades that would move the market
- Gradual position entry/exit
- Time-based trading strategies

---

## Stop-Loss Orders

Price-triggered orders using Chainlink oracles:

```python
stop_loss = factory.create_stop_loss_order(
    sell_amount=10.0,
    strike_percentage=85.0,   # Trigger when price drops to 85%
    valid_duration=14400,     # Valid for 4 hours
)
```

**Use cases:**
- Risk management and downside protection
- Automated liquidation strategies
- Price-based portfolio rebalancing

---

## Good-After-Time Orders

Orders that activate after a specified delay:

```python
delayed = factory.create_good_after_time_order(
    sell_amount=5.0,
    delay_seconds=1800,       # Activate after 30 minutes
    valid_duration=7200,      # Then valid for 2 hours
)
```

**Use cases:**
- Scheduled trades
- Post-event trading strategies
- Time-based DCA (Dollar Cost Averaging)

---

## Conditional Order Templates

Pre-configured templates for common conditional order patterns:

```python
from cow_performance.load_generation import (
    create_default_conditional_templates,
    ConditionalOrderTemplateRegistry,
)

# Load templates
templates = create_default_conditional_templates()
registry = ConditionalOrderTemplateRegistry(templates)

# Available TWAP templates
twap_small = registry.get_template("twap_small")        # 3 parts, 4 min intervals
twap_medium = registry.get_template("twap_medium")      # 5 parts, 5 min intervals
twap_large = registry.get_template("twap_large")        # 10 parts, 10 min intervals

# Available Stop-Loss templates
sl_conservative = registry.get_template("stop_loss_conservative")  # 5% drop
sl_moderate = registry.get_template("stop_loss_moderate")          # 10% drop
sl_aggressive = registry.get_template("stop_loss_aggressive")      # 20% drop

# Available Good-After-Time templates
delayed_short = registry.get_template("delayed_order_short")   # 5 min delay
delayed_medium = registry.get_template("delayed_order_medium") # 30 min delay
delayed_long = registry.get_template("delayed_order_long")     # 1 hour delay

# Use template to generate order
order = factory.create_twap_order(
    num_parts=twap_medium.num_parts,
    interval_seconds=twap_medium.interval_seconds,
)
```

---

## Handler and Oracle Registries

The module includes comprehensive registries for ComposableCow handlers and Chainlink oracles:

```python
from cow_performance.load_generation import (
    get_handler_address,
    get_composable_cow_address,
    OracleRegistry,
)

# Get handler addresses
twap_handler = get_handler_address("twap", chain_id=1)
stop_loss_handler = get_handler_address("stop_loss", chain_id=1)

# Get ComposableCow address
composable_cow = get_composable_cow_address(chain_id=1)

# Work with oracles
oracle_registry = OracleRegistry(chain_id=1)
weth_oracle = oracle_registry.get_oracle_for_token("WETH")
usdc_oracle = oracle_registry.get_oracle_for_token("USDC")

# List available tokens with oracles
available_tokens = oracle_registry.get_available_tokens()
print(f"Tokens with oracles: {available_tokens}")
```

---

## Network Support

Conditional orders are currently configured for Ethereum Mainnet:

```python
# Ethereum Mainnet
factory = ConditionalOrderFactory(
    token_pair_registry=token_registry,
    chain_id=1,
    safe_wallet_address="0x...",
)
```

The architecture is designed to be expandable to additional networks in the future by adding handler and oracle addresses to the respective registries.

---

## Features

- **TWAP Orders**: Split large trades over time
- **Stop-Loss Orders**: Oracle-triggered protective orders
- **Good-After-Time Orders**: Time-delayed execution
- **Template System**: Pre-configured order patterns
- **Mainnet Support**: Ethereum mainnet (expandable to other networks)
- **Oracle Integration**: Chainlink price feeds for 8 major tokens
- **Handler Registry**: Automatic handler address resolution
- **Type Safe**: Full Pydantic validation and type hints
- **Well Tested**: Comprehensive unit and integration tests

---

## Technical Requirements

Conditional orders use the ComposableCow framework and require:

- **Safe wallet** (EIP-1271 signatures)
- **ComposableCow deployment** on target network
- **Handler contracts** for each order type
- **Chainlink oracles** for stop-loss orders

Orders are encoded using ABI encoding and submitted to ComposableCow for conditional execution by the CoW Protocol watchtower service.

---

## Implementation Status

### ✅ Fully Implemented

- Order generation for all types (TWAP, Stop-Loss, Good-After-Time)
- Parameter validation and ABI encoding
- EIP-1271 signature generation for Safe wallets
- Order templates and factory methods
- Safe wallet deployment and management

**Files:**
- Schema: `src/cow_performance/load_generation/conditional_order_schema.py`
- Factory: `src/cow_performance/load_generation/conditional_order_factory.py`
- ABI Encoding: `src/cow_performance/load_generation/abi_encoding.py`
- Safe Integration: `src/cow_performance/load_generation/safe_integration.py`

### ❌ Not Implemented

- On-chain submission via ComposableCow contract
- Transaction sending and confirmation
- ConditionalOrderCreated event watching
- Order fill monitoring from on-chain events
- TWAP part execution tracking

**Workaround**: Conditional orders are generated with temporary UIDs and tracked locally, but do not affect on-chain state or settlement.

**TODO** (from source code):
```python
# TODO: Implement full conditional order lifecycle tracking:
# 1. Actually submit via composable_cow.submit_conditional_order()
# 2. Get order UID from transaction receipt or ConditionalOrderCreated event
# 3. Track token amounts from the generated ConditionalOrder
# 4. Implement on-chain event watching for order fills (not API polling)
# 5. For TWAP: track individual part executions over time
```

**Implementation Location**: `src/cow_performance/load_generation/trader_simulator.py:437-552`

---

## Related Documentation

- [Order Generation](order-generation.md) - Basic order creation
- [User Simulation](user-simulation.md) - Safe wallet integration and order submission
- [CLI Reference](cli.md) - Running tests with conditional orders
