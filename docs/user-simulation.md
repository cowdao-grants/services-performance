# User Simulation Module

> Simulate multiple traders with Safe wallets and realistic behaviors.
>
> **See also**: [Order Generation](order-generation.md) | [Conditional Orders](conditional-orders.md)

## Quick Start

```python
from cow_performance.load_generation import (
    TraderPool,
    SafeWallet,
    submit_conditional_order,
    OrderSigner,
)
from web3 import Web3

# Connect to forked network
web3 = Web3(Web3.HTTPProvider("http://localhost:8545"))

# Create a pool of traders
trader_pool = TraderPool(num_traders=10)

# Get a trader
trader = trader_pool.get_random_trader()
print(f"Trader address: {trader.address}")
print(f"Orders submitted: {trader.orders_submitted}")

# Deploy Safe wallet for conditional orders
safe_wallet = SafeWallet.deploy(
    web3=web3,
    owner=trader.get_account(),
    chain_id=1
)
print(f"Safe wallet deployed at: {safe_wallet.address}")

# Attach Safe to trader
trader.safe_wallet = safe_wallet
```

---

## Trader Account Management

### TraderAccount

Individual trader with private key and metadata:

```python
from cow_performance.load_generation import TraderAccount

# Generate new trader
trader = TraderAccount.generate()

# From existing private key
trader = TraderAccount.from_private_key("0x...")

# Access trader info
print(f"Address: {trader.address}")
print(f"Nonce: {trader.nonce}")
print(f"Orders submitted: {trader.orders_submitted}")

# Get LocalAccount for signing
account = trader.get_account()

# Check Safe wallet integration
if trader.has_safe_wallet():
    safe_address = trader.get_safe_address()
    trading_address = trader.get_trading_address()  # Returns Safe or EOA
```

### TraderPool

Manage multiple traders for concurrent simulations:

```python
from cow_performance.load_generation import TraderPool

# Create pool of traders
pool = TraderPool(num_traders=20)

# Access traders
trader1 = pool.get_trader(0)              # By index
random_trader = pool.get_random_trader()  # Random selection
next_trader = pool.get_next_trader()      # Round-robin

# Pool statistics
pool_size = pool.get_pool_size()
total_orders = pool.get_total_orders_submitted()
all_traders = pool.get_all_traders()
```

---

## Safe Wallet Integration

### SafeWallet

Gnosis Safe deployment and management for EIP-1271 signatures:

```python
from cow_performance.load_generation import SafeWallet, deploy_safe_wallet
from web3 import Web3

web3 = Web3(Web3.HTTPProvider("http://localhost:8545"))
trader_account = trader.get_account()

# Deploy Safe wallet
safe_wallet = SafeWallet.deploy(
    web3=web3,
    owner=trader_account,
    chain_id=1
)

# Or use convenience function
safe_wallet = deploy_safe_wallet(web3, trader_account)

# Safe operations
nonce = safe_wallet.get_nonce()

# Execute transactions through Safe
tx_hash = safe_wallet.exec_transaction(
    to="0x...",
    value=0,
    data=b"...",
    operation=0  # 0=CALL, 1=DELEGATECALL
)

# Approve tokens for trading
safe_wallet.approve_token(
    token_address="0x...",
    spender="0x...",
    amount=1000 * 10**18
)

# Sign messages (EIP-1271)
signature = safe_wallet.sign_message(message_hash)
```

---

## Order Signing

### OrderSigner

EIP-712 signatures for EOAs:

```python
from cow_performance.load_generation import OrderSigner, OrderParameters

signer = OrderSigner(
    chain_id=1,
    settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41"
)

# Sign order with EOA
signed_order = signer.sign_order(order_params, trader.get_account())
```

### ConditionalOrderSigner

EIP-1271 signatures for Safe wallets:

```python
from cow_performance.load_generation import ConditionalOrderSigner

signer = ConditionalOrderSigner(
    safe_wallet=safe_wallet,
    composable_cow_address="0xfdaFc9d1902f4e0b84f65F49f244b32b31013b74"
)

# Create EIP-1271 signature for conditional order
signature = signer.create_signature(order_params)
```

---

## ComposableCow Submission

Submit conditional orders (TWAP, Stop-Loss) to the blockchain:

```python
from cow_performance.load_generation import (
    submit_conditional_order,
    get_tradeable_order,
    remove_conditional_order,
    ConditionalOrderFactory,
)

# Create conditional order
factory = ConditionalOrderFactory(
    token_pair_registry=token_registry,
    chain_id=1,
    safe_wallet_address=safe_wallet.address,
)

twap_order = factory.create_twap_order(
    total_amount=1000.0,
    num_parts=5,
    interval_seconds=300,
)

# Submit to ComposableCow contract
tx_hash = submit_conditional_order(
    web3=web3,
    composable_cow_address="0xfdaFc9d1902f4e0b84f65F49f244b32b31013b74",
    safe_wallet=safe_wallet,
    conditional_order=twap_order,
    dispatch=True,  # Immediately dispatch to watchtower
)

print(f"Conditional order submitted: {tx_hash.hex()}")

# Check if order is tradeable
tradeable = get_tradeable_order(
    web3=web3,
    composable_cow_address="0xfdaFc9d1902f4e0b84f65F49f244b32b31013b74",
    owner=safe_wallet.address,
    conditional_order_params={
        "handler": twap_order.params.handler,
        "salt": twap_order.params.salt,
        "staticInput": twap_order.params.staticInput,
    },
)

if tradeable:
    order, signature = tradeable
    print("Order is tradeable!")

# Remove conditional order
remove_conditional_order(
    web3=web3,
    composable_cow_address="0xfdaFc9d1902f4e0b84f65F49f244b32b31013b74",
    safe_wallet=safe_wallet,
    conditional_order_params={...},
)
```

---

## Hooks Orders

Create orders with custom pre-hooks and post-hooks that execute atomically with settlement:

```python
import json
from web3 import Web3
from cow_performance.load_generation import OrderParameters, OrderSigner

# Create hooks metadata
hooks_metadata = {
    "version": "0.9.0",
    "appCode": "CoW Swap",
    "hooks": {
        "version": "0.1.0",
        "pre": [
            {
                "target": "0x...",      # Contract to call
                "callData": "0x...",    # Encoded function call
                "gasLimit": 100000,     # Gas limit for hook
            }
        ],
        "post": [
            {
                "target": "0x...",
                "callData": "0x...",
                "gasLimit": 100000,
            }
        ],
    },
}

# Generate appData hash
app_data_json = json.dumps(hooks_metadata)
app_data_hash = Web3.keccak(text=app_data_json).hex()

# Upload appData to orderbook (required before order submission)
import requests
response = requests.put(
    f"http://localhost:8080/api/v1/app_data/{app_data_hash[2:]}",
    json={"fullAppData": app_data_json},
)

# Create order with hooks
order_params = OrderParameters(
    sellToken="0x...",
    buyToken="0x...",
    sellAmount="1000000000000000000",
    buyAmount="1000000000000000000",
    validTo=1234567890,
    appData=app_data_hash,  # Include hooks via appData
    feeAmount="0",
    kind="sell",
    partiallyFillable=False,
)

# Sign and submit
signer = OrderSigner(chain_id=1, settlement_contract="0x...")
signed_order = signer.sign_order(order_params, trader.get_account())

# Submit to orderbook
response = requests.post(
    "http://localhost:8080/api/v1/orders",
    json=signed_order.model_dump(by_alias=True),
)
```

**Common Hook Use Cases:**

- **Pre-hooks**: Permit signatures (gasless approvals), state checks, price validations
- **Post-hooks**: Token transfers, staking, LP deposits, reward claiming

---

## Trader Simulation & Orchestration

Simulate realistic trading behavior with configurable patterns:

```python
from cow_performance.load_generation import (
    TraderSimulator,
    TraderOrchestrator,
    OrchestrationConfig,
    TraderBehaviorConfig,
    TradingPattern,
)

# Configure trader behavior
behavior_config = TraderBehaviorConfig(
    think_time_range=(1.0, 5.0),           # Think time between actions (seconds)
    orders_per_session_range=(5, 20),      # Orders per trading session
    trading_pattern=TradingPattern.BURST,   # CONSTANT, BURST, or RAMP_UP
)

# Create simulator for a trader
simulator = TraderSimulator(
    trader_account=trader,
    order_factory=order_factory,
    behavior_config=behavior_config,
)

# Run simulation
await simulator.simulate_trading_session()

# Orchestrate multiple traders
orchestration_config = OrchestrationConfig(
    num_traders=10,
    orders_per_trader=100,
    duration_seconds=600,
    ramp_up_seconds=60,
)

orchestrator = TraderOrchestrator(
    trader_pool=trader_pool,
    order_factory=order_factory,
    config=orchestration_config,
)

# Run load test
metrics = await orchestrator.run_load_test()
print(f"Total orders submitted: {metrics.total_orders}")
print(f"Orders per second: {metrics.orders_per_second}")
```

---

## Order Tracking

Track order lifecycle and performance metrics:

```python
from cow_performance.load_generation import OrderTracker, OrderStatus

tracker = OrderTracker()

# Track order submission
tracker.track_submission(order_uid, order_data)

# Update order status
tracker.update_status(order_uid, OrderStatus.FULFILLED)

# Get metrics
metrics = tracker.get_metrics()
print(f"Success rate: {metrics.success_rate * 100}%")
print(f"Average latency: {metrics.average_latency}s")

# Get order history
history = tracker.get_order_history(order_uid)
```

---

## Architecture

```
User Simulation Module
│
├── Trader Management
│   ├── TraderAccount (EOA generation and management)
│   └── TraderPool (Multi-trader coordination)
│
├── Safe Wallet Layer
│   ├── SafeWallet (Deployment and management)
│   └── EIP-1271 signature generation
│
├── Order Creation
│   ├── OrderFactory (Regular orders)
│   ├── ConditionalOrderFactory (TWAP, Stop-Loss)
│   └── Hooks metadata generation
│
├── Order Signing
│   ├── OrderSigner (EIP-712 for EOAs)
│   └── ConditionalOrderSigner (EIP-1271 for Safe)
│
├── Order Submission
│   ├── Orderbook API submission (regular orders)
│   ├── ComposableCow submission (conditional orders)
│   └── AppData upload (hooks orders)
│
└── Simulation & Orchestration
    ├── TraderSimulator (Individual trader behavior)
    ├── TraderOrchestrator (Multi-trader coordination)
    └── OrderTracker (Metrics and monitoring)
```

---

## Technical Requirements

**For Regular Orders:**
- EOA with ETH for gas
- Token approvals to VaultRelayer

**For Conditional Orders:**
- Safe wallet deployment
- Safe funded with ETH for gas
- Token approvals from Safe to VaultRelayer
- ComposableCow contract access

**For Hooks Orders:**
- AppData document upload to orderbook
- HooksTrampoline contract deployed
- Token approvals for trading

---

## Features

- **Multi-Trader Simulation**: Concurrent trading with configurable pools
- **Safe Wallet Support**: Full Gnosis Safe integration for advanced orders
- **EIP-1271 Signatures**: Smart contract signature validation
- **Conditional Orders**: On-chain TWAP, Stop-Loss via ComposableCow
- **Hooks Integration**: Pre/post-settlement custom calls
- **Order Tracking**: Lifecycle monitoring and metrics collection
- **Realistic Behavior**: Configurable trading patterns and timing
- **Type Safe**: Full type hints and validation
- **Well Tested**: Comprehensive e2e test coverage

---

## Additional Resources

- [Safe Wallet Documentation](https://docs.safe.global/)
- [ComposableCow Documentation](https://docs.cow.fi/cow-protocol/reference/contracts/periphery/composable-cow)
- [CoW Protocol Hooks](https://docs.cow.fi/cow-protocol/reference/core/intents/hooks)
