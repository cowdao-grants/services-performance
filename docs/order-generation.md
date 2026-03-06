# Order Generation Module

> Programmatic order creation for CoW Protocol testing.
>
> **See also**: [CLI Reference](cli.md) | [Conditional Orders](conditional-orders.md) | [User Simulation](user-simulation.md)

## Quick Start

```python
from eth_account import Account
from cow_performance.load_generation import (
    OrderFactory,
    create_mainnet_token_registry,
)

# Create token registry and factory
token_registry = create_mainnet_token_registry()
factory = OrderFactory(
    token_pair_registry=token_registry,
    chain_id=1,
    settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
)

# Create trader and generate orders
trader = Account.create()
market_order = factory.create_market_order(trader)
limit_order = factory.create_limit_order(trader, limit_price=0.99)
batch_orders = factory.create_batch_orders(trader, count=100)
```

---

## Components

### Order Schema

Pydantic models matching CoW Protocol specifications:

- `OrderKind` (buy/sell), `OrderBalance`, `SigningScheme` enums
- `OrderParameters` - Core order parameters with validation
- `SignedOrder` - Complete order with EIP-712 signature
- Full EIP-712 domain and type definitions

### Token Pair Management

- `Token` - Token metadata (address, symbol, decimals)
- `TokenPair` - Trading pairs with selection weights
- `TokenPairRegistry` - Multiple selection strategies:
  - Random selection
  - Weighted random (realistic distributions)
  - Sequential (round-robin)
- Pre-configured registries for Ethereum mainnet and Polygon

### Order Factory

Generate orders with realistic parameters:

- `create_market_order()` - Market orders at current price
- `create_limit_order()` - Limit orders with custom price
- `create_batch_orders()` - Bulk order generation
- Configurable amounts, fees, validity periods
- Log-scale amount distribution for realism

### Order Templates

Pre-configured templates for common scenarios:

- Small/medium/large market orders
- Conservative/aggressive limit orders
- WETH buy orders
- Stablecoin swaps
- Partially fillable orders

```python
from cow_performance.load_generation import create_default_templates

template_registry = create_default_templates()
order = template_registry.create_order_from_template(
    template_name="small_market",
    factory=factory,
    trader_account=trader,
)
```

### Order Validation

Comprehensive validation utilities:

```python
from cow_performance.load_generation import validate_order_parameters

errors = validate_order_parameters(order_params)
if errors:
    print("Validation errors:", errors)
```

---

## Features

- **CoW Protocol Compatible**: Orders validated against real orderbook API
- **EIP-712 Signatures**: Cryptographically signed with proper domain separation
- **Multi-Network**: Supports Ethereum mainnet and Polygon
- **Realistic Parameters**: Log-scale amounts, weighted token pair selection
- **High Performance**: Fast order generation rate
- **Type Safe**: Full type hints and Pydantic validation
- **Well Tested**: Comprehensive unit and integration test coverage

---

## Integration with CoW Protocol

Orders can be submitted directly to the orderbook API:

```python
import aiohttp

async def submit_order(order: SignedOrder):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8080/api/v1/orders",
            json=order.model_dump(by_alias=True),
        ) as response:
            return await response.json()
```

---

## Related Documentation

- [Conditional Orders](conditional-orders.md) - TWAP, Stop-Loss, Good-After-Time orders
- [User Simulation](user-simulation.md) - Multi-trader simulation and orchestration
- [CLI Reference](cli.md) - Running performance tests from command line
