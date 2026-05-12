# User Simulation Module

> Simulate multiple traders with Safe wallets and realistic behaviors.
>
> **See also**: [Order Generation](order-generation.md) | [Conditional Orders](conditional-orders.md)

## Quick Start

```python
from cow_performance.load_generation import (
    TraderPool,
    SafeWallet,
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

### EIP-1271 Signatures for Safe Wallets

Safe wallets sign messages using the `sign_message` method, which produces an EIP-1271-compatible signature:

```python
# Sign a message hash with the Safe wallet (EIP-1271)
signature = safe_wallet.sign_message(message_hash)
```

---

## ComposableCow Submission

Conditional orders (TWAP, Stop-Loss) are submitted to the ComposableCow contract by calling it through the Safe wallet's `exec_transaction` method. The Safe wallet executes the `create` function on the ComposableCow contract, encoding the conditional order parameters as call data.

See [Conditional Orders](conditional-orders.md) for full details on creating and submitting TWAP and Stop-Loss orders.

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
    OrderSigner,
    OrderTracker,
)

# Configure trader behavior
behavior_config = TraderBehaviorConfig(
    min_think_time=1.0,                    # Minimum think time before each order (seconds)
    max_think_time=5.0,                    # Maximum think time before each order (seconds)
    pattern=TradingPattern.BURST,          # Trading pattern (e.g., BURST, CONSTANT_RATE, RAMP_UP)
)

# Create simulator for a trader
simulator = TraderSimulator(
    trader=trader,
    order_factory=order_factory,
    order_signer=order_signer,
    order_tracker=order_tracker,
    behavior_config=behavior_config,
)

# Run simulation
await simulator.run(duration=600)

# Orchestrate multiple traders
orchestration_config = OrchestrationConfig(
    num_traders=10,
    duration=600,
    startup_interval=0.5,
)

orchestrator = TraderOrchestrator(
    trader_pool=trader_pool,
    order_factory=order_factory,
    order_signer=order_signer,
    order_tracker=order_tracker,
    default_behavior_config=behavior_config,
    orchestration_config=orchestration_config,
)

# Run load test
await orchestrator.run()
```

---

## Order Tracking

Track order lifecycle and performance metrics:

```python
from cow_performance.load_generation import OrderTracker, OrderStatus

tracker = OrderTracker()

# Track order submission
tracker.track_order(order_uid, owner=trader.address, order_type="market")

# Update order status
tracker.update_order_status(order_uid, OrderStatus.FILLED)

# Get metrics
metrics = tracker.get_metrics()
print(f"Total orders: {metrics.total_orders}")
print(f"Orders filled: {metrics.orders_filled}")
print(f"Average time to fill: {metrics.avg_time_to_fill}s")

# Get order metadata
metadata = tracker.get_order(order_uid)
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
│   └── Hooks metadata generation
│
├── Order Signing
│   ├── OrderSigner (EIP-712 for EOAs)
│   └── SafeWallet.sign_message (EIP-1271 for Safe)
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
