# Orderbook Submission Errors - Implementation Plan

**Date:** 2026-01-27
**Status:** Ready for Implementation
**Priority:** High
**Related Issue:** `issues/orderbook-submission-errors.md`

## Overview

Fix three critical bugs preventing sustained performance testing of the CoW Protocol orderbook:
1. **TooManyLimitOrders error** - Orderbook rejects orders after ~30-50 orders per wallet
2. **Market orders classified as limit** - Orders configured as "market" appear as "limit" in orderbook
3. **AppData validation error** - Custom appData hashes rejected due to missing pre-image upload

## Current State Analysis

### Bug #1: TooManyLimitOrders

**Root Cause:**
- Orderbook has hard limit of ~100-200 open orders per wallet
- Orders stay "open" indefinitely (no solvers in test environment, no automatic expiration)
- `validTo` timestamp set to 3600 seconds (1 hour) in future
- No order cancellation mechanism implemented

**Current Code:**
- `order_factory.py:40` - `valid_duration: int = 3600` (1 hour default)
- `order_factory.py:146-147` - `validTo` calculated as `int(time.time()) + self.valid_duration`
- `trader_simulator.py` - No order cancellation logic
- `orderbook_client.py` - No `cancel_order()` or `cancel_orders()` method

**Impact:** Blocks sustained performance testing after ~30-50 orders per wallet

### Bug #2: Market Orders Classified as Limit

**Root Cause:**
- CoW Protocol distinguishes order types based on **parameters**, not explicit classification
- Current implementation sets `buyAmount` to specific value (1:1 ratio)
- Both market and limit orders use identical parameters except price:
  - Market: `price=Decimal(1)` (fixed 1:1)
  - Limit: `price=Decimal(random.uniform(0.9, 1.1))` (±10% variation)
- `partiallyFillable=False` may force limit order classification

**Current Code:**
- `order_factory.py:187` - Market orders use `price=Decimal(1)`
- `order_factory.py:203,276` - Both types set `partiallyFillable=False`
- Orderbook API `/api/v1/orders/<uid>` returns `{"class": "limit"}` for all orders

**Hypothesis:** Orders need `buyAmount=1` (minimal) or `partiallyFillable=True` to be classified as "market"

**Impact:** Contributes to Bug #1 (all orders count as limit orders)

### Bug #3: AppData Validation Error

**Root Cause:**
- Only occurs in E2E test with hooks (`tests/e2e/test_hooks_orders.py`)
- Custom appData generated via `Web3.keccak(text=json.dumps(metadata)).hex()`
- Orderbook requires pre-image upload via `PUT /api/v1/app_data/<hash>` before order submission
- Test uploads appData but may have race condition or format issue

**Current Code:**
- `order_factory.py:41` - Default appData is zero hash (works fine)
- `conditional_order_factory.py:226,303,380` - All use zero hash (works fine)
- `test_hooks_orders.py:162-210` - Generates custom hash and uploads (sometimes fails)
- `orderbook_client.py:105-152` - `upload_app_data()` method exists

**Impact:** Only affects orders with custom appData (hooks). Production code uses zero hash.

### Key Discoveries

**From Codebase Research:**

1. **Order Submission Rate** (`trader_simulator.py:32-62`):
   - Default: 6 orders/minute per trader
   - 10 traders × 60 seconds = 60 orders total
   - TooManyLimitOrders error appears after ~30-50 orders

2. **No Cancellation Logic** (`trader_simulator.py`, `orderbook_client.py`):
   - No `cancel_order()` method in API client
   - No cleanup in trader lifecycle
   - Orders tracked but never cancelled

3. **API Supports Cancellation** (`modules/services/crates/orderbook/openapi.yml:87-115`):
   - `DELETE /api/v1/orders` - Batch cancellation (recommended)
   - `DELETE /api/v1/orders/{UID}` - Single cancellation (deprecated)
   - Requires EIP-712 signature of `OrderCancellations(bytes[] orderUids)`

4. **API Supports Account Orders** (`modules/services/crates/orderbook/openapi.yml:330-371`):
   - `GET /api/v1/account/{owner}/orders` - Query orders by owner
   - Pagination: `offset`, `limit` (max 1000)
   - Can determine current order count

## Desired End State

After implementation:

1. **Sustained Testing**: Performance tests run indefinitely without TooManyLimitOrders error
2. **Proper Order Classification**: Market orders correctly classified (if possible)
3. **AppData Reliability**: Custom appData orders always accepted
4. **Configurable Limits**: Users can configure max orders per wallet and cleanup behavior
5. **Monitoring**: Ability to query current order count per wallet

### Verification Checklist

**Automated Verification:**
- [x] All unit tests pass: `pytest tests/unit/` (178 tests passed)
- [ ] All integration tests pass: `pytest -m integration`
- [x] Type checking passes: `mypy src/`
- [x] Linting passes: `ruff check src/ tests/`
- [x] Formatting passes: `black --check src/ tests/`

**Manual Verification:**
- [ ] Can submit 100+ orders from single wallet without TooManyLimitOrders error
- [ ] Orders are correctly classified (if fix is possible)
- [ ] Long-running test (60+ seconds, 10 traders) completes without errors
- [ ] Order cancellation works correctly
- [ ] Query account orders returns expected results
- [ ] AppData upload/order submission sequence works reliably

## What We're NOT Doing

1. **Not solving market order classification** if it requires orderbook changes (accept as "known limitation")
2. **Not implementing solver simulation** (out of scope)
3. **Not modifying orderbook code** (only client-side changes)
4. **Not changing EIP-712 signature logic** (already correct)
5. **Not adding new order types** (only fixing existing ones)

## Implementation Approach

**Strategy:**
1. **Phase 1 (Bug #1)**: Implement order cleanup - highest priority, blocking testing
2. **Phase 2 (Bug #3)**: Fix appData reliability - medium priority, only affects hooks
3. **Phase 3 (Bug #2)**: Research and document market order classification - low priority if unfixable

**Rationale:**
- Bug #1 blocks all sustained testing → highest priority
- Bug #3 only affects E2E tests with hooks → medium priority
- Bug #2 may require orderbook changes → research first before implementation

---

## Phase 1: Implement Order Cleanup (Bug #1)

### Overview

Implement automatic order cancellation to prevent TooManyLimitOrders error. Use combination of:
- Shorter `validTo` periods (orders expire faster)
- Active order cancellation when approaching limit
- Configurable max orders per wallet

### Changes Required

#### 1. Add Orderbook API Methods

**File**: `src/cow_performance/api/orderbook_client.py`
**Changes**: Add order cancellation and account query methods

```python
async def cancel_orders(
    self,
    order_uids: list[str],
    signature: str,
    signing_scheme: str = "eip712",
) -> dict[str, Any]:
    """Cancel multiple orders in a single request (batch cancellation).

    Args:
        order_uids: List of order UIDs to cancel
        signature: EIP-712 signature of OrderCancellations message
        signing_scheme: Signing scheme (default: "eip712")

    Returns:
        Response from orderbook

    Raises:
        aiohttp.ClientResponseError: If cancellation fails
    """
    request_body = {
        "orderUids": order_uids,
        "signature": signature,
        "signingScheme": signing_scheme,
    }

    async with aiohttp.ClientSession(timeout=self.timeout) as session:
        async with session.delete(
            f"{self.base_url}/api/v1/orders",
            json=request_body,
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"Order cancellation failed: {error_text}",
                    headers=response.headers,
                )
            return await response.json()


async def get_account_orders(
    self,
    owner: str,
    offset: int = 0,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Get orders for an account with pagination.

    Args:
        owner: Ethereum address of order owner
        offset: Pagination offset (default: 0)
        limit: Max orders to return (default: 1000, max: 1000)

    Returns:
        List of orders for the account

    Raises:
        aiohttp.ClientResponseError: If request fails
    """
    async with aiohttp.ClientSession(timeout=self.timeout) as session:
        async with session.get(
            f"{self.base_url}/api/v1/account/{owner}/orders",
            params={"offset": offset, "limit": limit},
        ) as response:
            response.raise_for_status()
            return await response.json()


async def get_open_order_count(self, owner: str) -> int:
    """Get count of open orders for an account.

    Args:
        owner: Ethereum address of order owner

    Returns:
        Number of open orders
    """
    orders = await self.get_account_orders(owner, limit=1000)
    open_orders = [o for o in orders if o.get("status") == "open"]
    return len(open_orders)
```

**Location**: After `upload_app_data()` method (line 152)
**Lines to add**: ~80 lines

#### 2. Add Order Cancellation Signing

**File**: `src/cow_performance/load_generation/order_signer.py`
**Changes**: Add method to sign order cancellations

```python
def sign_order_cancellations(
    order_uids: list[str],
    trader_account: LocalAccount,
    chain_id: int,
    settlement_contract: str,
) -> str:
    """Sign order cancellations using EIP-712.

    Args:
        order_uids: List of order UIDs to cancel
        trader_account: Trader's account for signing
        chain_id: Network chain ID
        settlement_contract: Settlement contract address

    Returns:
        Signature as hex string (with 0x prefix)
    """
    # EIP-712 domain
    domain = {
        "name": "Gnosis Protocol",
        "version": "v2",
        "chainId": chain_id,
        "verifyingContract": settlement_contract,
    }

    # EIP-712 message types
    message_types = {
        "OrderCancellations": [
            {"name": "orderUids", "type": "bytes[]"},
        ]
    }

    # Convert order UIDs to bytes
    order_uid_bytes = [bytes.fromhex(uid[2:]) for uid in order_uids]

    # Message data
    message_data = {
        "orderUids": order_uid_bytes,
    }

    # Sign using EIP-712
    signable_message = encode_typed_data(
        domain_data=domain,
        message_types=message_types,
        message_data=message_data,
    )

    signed_message = Account.sign_message(
        signable_message,
        private_key=trader_account.key,
    )

    return "0x" + signed_message.signature.hex()
```

**Location**: After `sign_order()` function (line ~125)
**Lines to add**: ~50 lines

#### 3. Add Order Cleanup Configuration

**File**: `src/cow_performance/config/scenario_config.py`
**Changes**: Add cleanup configuration options

```python
@dataclass
class OrderCleanupConfig:
    """Configuration for order cleanup behavior."""

    enabled: bool = True
    """Enable automatic order cleanup/cancellation"""

    max_open_orders_per_wallet: int = 50
    """Maximum open orders per wallet before cleanup triggers"""

    cleanup_batch_size: int = 10
    """Number of orders to cancel in each cleanup batch"""

    cleanup_strategy: str = "oldest_first"
    """Cleanup strategy: 'oldest_first', 'random', or 'all'"""

    check_interval: float = 5.0
    """Interval (seconds) to check order count and trigger cleanup"""


# Add to ScenarioConfig
@dataclass
class ScenarioConfig:
    # ... existing fields ...

    order_cleanup: OrderCleanupConfig = field(default_factory=OrderCleanupConfig)
    """Order cleanup configuration"""
```

**Location**: After `OrchestrationConfig` (line ~180)
**Lines to add**: ~25 lines

#### 4. Reduce Default validTo Duration

**File**: `src/cow_performance/load_generation/order_factory.py`
**Changes**: Reduce default `valid_duration` from 3600s (1 hour) to 300s (5 minutes)

```python
def __init__(
    self,
    token_pair_registry: TokenPairRegistry,
    chain_id: int,
    settlement_contract: str,
    amount_range: tuple[float, float] | None = None,
    valid_duration: int = 300,  # Changed from 3600 (1 hour) to 300 (5 minutes)
    default_app_data: str = "0x0000000000000000000000000000000000000000000000000000000000000000",
    fee_percentage: float = 0.001,
) -> None:
```

**Location**: Line 40
**Lines to change**: 1 line

**Rationale**: Orders expire faster, freeing up quota automatically

#### 5. Implement Order Cleanup in Trader Simulator

**File**: `src/cow_performance/load_generation/trader_simulator.py`
**Changes**: Add background cleanup task

```python
def __init__(
    self,
    # ... existing params ...
    order_cleanup_config: OrderCleanupConfig | None = None,
):
    # ... existing initialization ...
    self.order_cleanup_config = order_cleanup_config or OrderCleanupConfig()
    self._cleanup_task: asyncio.Task | None = None


async def _cleanup_loop(self) -> None:
    """Background loop to check and cleanup old orders."""
    if not self.order_cleanup_config.enabled:
        return

    while self._running:
        try:
            # Check current order count
            open_count = await self.api_client.get_open_order_count(self.trader.address)

            if open_count >= self.order_cleanup_config.max_open_orders_per_wallet:
                print(
                    f"Trader {self.trader.address[:8]} has {open_count} open orders, "
                    f"triggering cleanup..."
                )
                await self._cleanup_orders()

        except Exception as e:
            print(f"Error in cleanup loop: {e}")

        await asyncio.sleep(self.order_cleanup_config.check_interval)


async def _cleanup_orders(self) -> None:
    """Cancel oldest orders to stay under limit."""
    config = self.order_cleanup_config

    # Get all orders for this wallet
    all_orders = await self.api_client.get_account_orders(
        self.trader.address,
        limit=1000,
    )

    # Filter to open orders only
    open_orders = [o for o in all_orders if o.get("status") == "open"]

    # Sort by creation time (oldest first)
    if config.cleanup_strategy == "oldest_first":
        open_orders.sort(key=lambda o: o.get("creationDate", ""))
    elif config.cleanup_strategy == "random":
        import random
        random.shuffle(open_orders)

    # Select orders to cancel
    orders_to_cancel = open_orders[:config.cleanup_batch_size]
    order_uids = [o["uid"] for o in orders_to_cancel]

    if not order_uids:
        return

    # Sign cancellation
    from .order_signer import sign_order_cancellations
    signature = sign_order_cancellations(
        order_uids=order_uids,
        trader_account=self.trader.get_account(),
        chain_id=self.order_factory.chain_id,
        settlement_contract=self.order_factory.settlement_contract,
    )

    # Cancel orders
    await self.api_client.cancel_orders(
        order_uids=order_uids,
        signature=signature,
        signing_scheme="eip712",
    )

    print(
        f"Trader {self.trader.address[:8]} cancelled {len(order_uids)} orders"
    )


async def start(self) -> None:
    """Start trader simulation with cleanup."""
    self._running = True

    # Start cleanup loop
    if self.order_cleanup_config.enabled and self.api_client:
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    # Start trading loop (existing code)
    # ...


async def stop(self) -> None:
    """Stop trader simulation and cleanup."""
    self._running = False

    # Cancel cleanup task
    if self._cleanup_task:
        self._cleanup_task.cancel()
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass

    # Existing stop logic
    # ...
```

**Location**: Add methods after `_apply_think_time()` (line ~190)
**Lines to add**: ~100 lines

#### 6. Pass Cleanup Config Through CLI

**File**: `src/cow_performance/cli/commands/run.py`
**Changes**: Pass cleanup config to traders

```python
# Around line 350-360, when creating TraderSimulator
trader_simulator = TraderSimulator(
    trader=trader,
    order_factory=order_factory,
    behavior_config=behavior_config,
    api_client=api_client if not config.dry_run else None,
    order_tracker=order_tracker,
    order_cleanup_config=config.order_cleanup,  # Add this line
)
```

**Location**: Line ~355
**Lines to change**: 1 line (add parameter)

#### 7. Update Scenario Config Files

**File**: `configs/scenarios/test-funded-scenario.yml`
**Changes**: Add order cleanup configuration

```yaml
# ... existing config ...

# Order cleanup configuration
order_cleanup:
  enabled: true
  max_open_orders_per_wallet: 50
  cleanup_batch_size: 10
  cleanup_strategy: "oldest_first"
  check_interval: 5.0
```

**Location**: End of file
**Lines to add**: 7 lines

### Success Criteria

#### Automated Verification:
- [ ] New unit tests pass for order cancellation signing
- [ ] New unit tests pass for orderbook client methods
- [ ] Integration test: Submit 100 orders without TooManyLimitOrders error
- [x] Type checking passes: `mypy src/cow_performance/api/orderbook_client.py src/cow_performance/load_generation/order_signer.py`
- [x] Linting passes: `ruff check src/ tests/`

#### Manual Verification:
- [ ] Run test with 10 traders for 120 seconds without TooManyLimitOrders error
- [ ] Verify orders are cancelled when approaching limit (check logs)
- [ ] Verify `get_account_orders()` returns expected results
- [ ] Verify `get_open_order_count()` accurately counts open orders
- [ ] Verify cancelled orders show status="cancelled" in orderbook API

---

## Phase 2: Fix AppData Reliability (Bug #3)

### Overview

Ensure appData upload/order submission sequence works reliably in E2E tests with hooks.

### Root Cause Analysis

**Current Issue:**
- `test_hooks_orders.py:162-210` uploads appData then submits order
- Sometimes fails with "Unknown pre-image for app data hash" error
- Possible race condition or formatting issue

**Investigation Needed:**
1. Check if appData upload returns 200 OK
2. Verify appData hash calculation matches orderbook expectation
3. Check if upload completes before order submission
4. Verify appData document format matches orderbook schema

### Changes Required

#### 1. Add Retry Logic to AppData Upload

**File**: `src/cow_performance/api/orderbook_client.py`
**Changes**: Implement retry logic for appData upload

```python
async def upload_app_data_with_retry(
    self,
    app_data_hash: str,
    app_data_doc: str | dict[str, Any],
    max_retries: int = 3,
) -> dict[str, Any]:
    """Upload appData with automatic retry on failure.

    Args:
        app_data_hash: 32-byte hash of appData document
        app_data_doc: Full appData JSON document
        max_retries: Maximum retry attempts

    Returns:
        Response from orderbook

    Raises:
        aiohttp.ClientResponseError: If all retries fail
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            return await self.upload_app_data(app_data_hash, app_data_doc)
        except aiohttp.ClientResponseError as e:
            last_error = e
            # Only retry on transient errors (5xx) or 409 Conflict
            if e.status not in (409, 500, 502, 503, 504):
                raise

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"AppData upload failed (attempt {attempt + 1}), retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

    raise last_error
```

**Location**: After `upload_app_data()` method (line ~152)
**Lines to add**: ~35 lines

#### 2. Verify AppData Upload Before Order Submission

**File**: `tests/e2e/test_hooks_orders.py`
**Changes**: Add verification step after upload

```python
# Upload appData document first
print("\nUploading appData document to orderbook...")
try:
    upload_response = orderbook_client.upload_app_data(order_params.appData, app_data_json)
    print(f"✓ AppData uploaded successfully: {upload_response}")

    # Verify upload by querying back (if API supports)
    # Wait briefly to ensure it's propagated
    await asyncio.sleep(0.5)

except Exception as e:
    print(f"⚠ AppData upload failed: {e}")
    # Check if it already exists (409 Conflict is OK)
    if "409" not in str(e):
        raise
```

**Location**: Line ~190 (replace existing upload logic)
**Lines to change**: ~10 lines

#### 3. Add AppData Validation Helper

**File**: `src/cow_performance/load_generation/order_validation.py`
**Changes**: Add helper to verify appData hash

```python
def validate_app_data_hash(app_data_doc: dict[str, Any], expected_hash: str) -> None:
    """Validate that appData document hashes to expected value.

    Args:
        app_data_doc: Full appData JSON document
        expected_hash: Expected keccak256 hash (with 0x prefix)

    Raises:
        OrderValidationError: If hash doesn't match
    """
    import json
    from web3 import Web3

    # Compute hash
    app_data_json = json.dumps(app_data_doc, separators=(',', ':'), sort_keys=True)
    computed_hash = Web3.keccak(text=app_data_json).hex()

    if computed_hash != expected_hash:
        raise OrderValidationError(
            f"AppData hash mismatch: expected {expected_hash}, got {computed_hash}"
        )
```

**Location**: After `validate_app_data()` function (line ~111)
**Lines to add**: ~25 lines

#### 4. Use Consistent JSON Serialization

**File**: `tests/e2e/test_hooks_orders.py`
**Changes**: Ensure consistent JSON serialization for hashing

```python
# Convert to JSON with consistent formatting
app_data_json = json.dumps(hooks_metadata, separators=(',', ':'), sort_keys=True)
app_data_hash = Web3.keccak(text=app_data_json).hex()

# Validate hash before upload
from cow_performance.load_generation.order_validation import validate_app_data_hash
validate_app_data_hash(hooks_metadata, app_data_hash)
```

**Location**: Line ~170
**Lines to change**: 3 lines

### Success Criteria

#### Automated Verification:
- [ ] E2E test `test_hooks_orders.py` passes consistently (run 10 times)
- [ ] New unit test for `validate_app_data_hash()` passes
- [ ] New unit test for `upload_app_data_with_retry()` passes
- [ ] Type checking passes

#### Manual Verification:
- [ ] AppData upload succeeds on first attempt (check logs)
- [ ] Orders with custom appData are accepted by orderbook
- [ ] Hash validation catches mismatches (test with wrong hash)
- [ ] Retry logic works on transient failures (simulate with network error)

---

## Phase 3: Research Market Order Classification (Bug #2)

### Overview

Research CoW Protocol's order classification logic to determine if market orders can be properly classified.

### Changes Required

#### 1. Add Research Documentation

**File**: `docs/research/market-order-classification.md` (NEW)
**Changes**: Document findings from CoW Protocol orderbook source code

```markdown
# Market Order Classification Research

## Objective
Understand how CoW Protocol classifies orders as "market" vs "limit" and whether our implementation can generate true market orders.

## CoW Protocol Source Investigation

### Orderbook Classification Logic

**File**: `modules/services/crates/orderbook/src/domain/order.rs`
**Location**: Order class determination

[Research findings to be filled in during implementation]

### Market Order Criteria

According to CoW Protocol:
- **Market orders**: ???
- **Limit orders**: ???

### Parameter Requirements

Parameters that affect classification:
1. `buyAmount`: ???
2. `partiallyFillable`: ???
3. Price ratio: ???

## Experiments

### Experiment 1: Minimal buyAmount
- Set `buyAmount=1` (minimal value)
- Result: ???

### Experiment 2: partiallyFillable=True
- Set `partiallyFillable=True`
- Result: ???

### Experiment 3: Extreme Price Ratio
- Set very low `buyAmount` (high slippage tolerance)
- Result: ???

## Conclusion

[To be filled in after research]

**Recommendation**: ???

**Action Items**:
- [ ] ???
```

**Lines to add**: ~50 lines (template)

#### 2. Add Experimental Order Methods

**File**: `src/cow_performance/load_generation/order_factory.py`
**Changes**: Add experimental market order variants

```python
def create_market_order_v2(
    self,
    trader_account: LocalAccount,
    token_pair: TokenPair | None = None,
    sell_amount: float | None = None,
    kind: OrderKind = OrderKind.SELL,
) -> SignedOrder:
    """Create market order with alternative parameters (experimental).

    This version tries different parameters to achieve proper market order classification:
    - buyAmount=1 (minimal, indicates "any price")
    - partiallyFillable=True (may affect classification)

    Returns:
        Signed market order
    """
    # ... (similar to create_market_order but with different params)

    params = OrderParameters(
        # ... other fields same ...
        buyAmount="1",  # Minimal buy amount
        partiallyFillable=True,  # Try with partial fills
        # ... other fields same ...
    )

    # Validate and sign
    assert_valid_order(params)
    return self._sign_order(params, trader_account)
```

**Location**: After `create_limit_order()` method (line ~286)
**Lines to add**: ~60 lines

#### 3. Add Classification Test

**File**: `tests/integration/test_order_classification.py` (NEW)
**Changes**: Test different order parameters and check classification

```python
"""Test order classification by orderbook API."""

import pytest
from cow_performance.load_generation.order_factory import OrderFactory
from cow_performance.api.orderbook_client import OrderbookClient


@pytest.mark.integration
async def test_market_order_classification(order_factory, trader_account, orderbook_client):
    """Test that market orders are classified as 'market' by orderbook."""
    # Create market order
    order = order_factory.create_market_order(trader_account)

    # Submit to orderbook
    response = await orderbook_client.submit_order(order.model_dump(by_alias=True))
    order_uid = response["uid"]

    # Query order
    order_data = await orderbook_client.get_order(order_uid)

    # Check classification
    assert order_data["class"] == "market", f"Expected 'market', got '{order_data['class']}'"


@pytest.mark.integration
async def test_market_order_v2_classification(order_factory, trader_account, orderbook_client):
    """Test alternative market order parameters."""
    # Create experimental market order
    order = order_factory.create_market_order_v2(trader_account)

    # Submit and check
    response = await orderbook_client.submit_order(order.model_dump(by_alias=True))
    order_uid = response["uid"]
    order_data = await orderbook_client.get_order(order_uid)

    # Document result
    print(f"Order class with v2 parameters: {order_data['class']}")
    print(f"Parameters: buyAmount=1, partiallyFillable=True")
```

**Lines to add**: ~40 lines

### Success Criteria

#### Automated Verification:
- [ ] Classification tests run without errors
- [ ] Results documented in research file

#### Manual Verification:
- [ ] Research document completed with findings
- [ ] Recommendation made (implement fix or accept limitation)
- [ ] If unfixable: Update documentation to clarify all orders are "limit" orders
- [ ] If fixable: Implement fix and verify classification

---

## Testing Strategy

### Unit Tests

**New Tests Required:**

1. **Test order cancellation signing** (`tests/unit/test_order_signer.py`):
   - `test_sign_order_cancellations()` - Verify EIP-712 signature format
   - `test_sign_multiple_cancellations()` - Batch cancellation signature
   - `test_cancellation_signature_matches_owner()` - Signature verification

2. **Test orderbook client methods** (`tests/unit/test_orderbook_client.py`):
   - `test_cancel_orders()` - Mock API call verification
   - `test_get_account_orders()` - Pagination handling
   - `test_get_open_order_count()` - Count calculation

3. **Test appData validation** (`tests/unit/test_order_validation.py`):
   - `test_validate_app_data_hash()` - Hash matching
   - `test_validate_app_data_hash_mismatch()` - Error on wrong hash

### Integration Tests

**New Tests Required:**

1. **Test order cleanup** (`tests/integration/test_order_cleanup.py`):
   - `test_cleanup_when_limit_reached()` - Automatic cleanup triggers
   - `test_cleanup_oldest_first()` - Strategy verification
   - `test_cleanup_maintains_limit()` - Order count stays under limit

2. **Test sustained load** (`tests/integration/test_sustained_load.py`):
   - `test_100_orders_single_wallet()` - No TooManyLimitOrders error
   - `test_long_running_test()` - 120 second test completes
   - `test_multiple_wallets()` - 10 wallets × 10 orders each

3. **Test appData reliability** (`tests/integration/test_app_data_upload.py`):
   - `test_app_data_upload_and_order()` - Complete flow
   - `test_app_data_retry_on_failure()` - Retry logic
   - `test_app_data_hash_validation()` - Pre-upload validation

### Manual Testing Steps

1. **Phase 1 Verification**:
   ```bash
   # Start environment
   docker-compose up -d

   # Run sustained load test
   cow-perf run --config configs/scenarios/test-funded-scenario.yml \
                --traders 10 \
                --duration 120

   # Check logs for:
   # - No TooManyLimitOrders errors
   # - Cleanup messages showing cancelled orders
   # - Order count staying under limit

   # Query orderbook to verify cancellations
   curl http://localhost:8080/api/v1/account/<WALLET_ADDRESS>/orders
   ```

2. **Phase 2 Verification**:
   ```bash
   # Run E2E hooks test multiple times
   for i in {1..10}; do
     pytest tests/e2e/test_hooks_orders.py -v
   done

   # All runs should pass without appData errors
   ```

3. **Phase 3 Verification**:
   ```bash
   # Run classification tests
   pytest tests/integration/test_order_classification.py -v

   # Check orderbook API manually
   ORDER_UID=<uid_from_test>
   curl http://localhost:8080/api/v1/orders/$ORDER_UID | jq '.class'
   ```

## Performance Considerations

**Order Cancellation Overhead:**
- Batch cancellation reduces API calls (cancel 10 orders in 1 request)
- EIP-712 signing is fast (~1ms per batch)
- Background cleanup runs every 5 seconds (configurable)
- Minimal impact on order submission rate

**API Query Overhead:**
- `get_account_orders()` query every 5 seconds per trader
- With 10 traders: 2 queries/second
- Orderbook API can handle this load
- Consider caching if needed

**Memory Usage:**
- Storing order UIDs for cleanup: ~64 bytes per order
- With 1000 orders: ~64 KB per trader
- Negligible memory impact

## Migration Notes

**Configuration Changes:**

Users must add `order_cleanup` section to scenario configs:

```yaml
order_cleanup:
  enabled: true
  max_open_orders_per_wallet: 50
  cleanup_batch_size: 10
  cleanup_strategy: "oldest_first"
  check_interval: 5.0
```

**Backward Compatibility:**

- `valid_duration` default changes from 3600s to 300s
- Existing configs with explicit `valid_duration` unaffected
- Cleanup disabled by default if not configured
- No breaking changes to API

## References

- **Bug Report**: `issues/orderbook-submission-errors.md`
- **OpenAPI Spec**: `modules/services/crates/orderbook/openapi.yml`
- **Order Factory**: `src/cow_performance/load_generation/order_factory.py`
- **Trader Simulator**: `src/cow_performance/load_generation/trader_simulator.py`
- **Orderbook Client**: `src/cow_performance/api/orderbook_client.py`
- **Order Signer**: `src/cow_performance/load_generation/order_signer.py`
- **EIP-712 Spec**: https://eips.ethereum.org/EIPS/eip-712

---

## Implementation Sequence

1. **Phase 1** (Days 1-2):
   - Add API methods (orderbook_client.py)
   - Add cancellation signing (order_signer.py)
   - Add configuration (scenario_config.py)
   - Reduce default validTo duration
   - Implement cleanup loop (trader_simulator.py)
   - Update scenario config files
   - Write unit tests
   - Write integration tests
   - Manual testing

2. **Phase 2** (Day 3):
   - Add retry logic (orderbook_client.py)
   - Fix E2E test (test_hooks_orders.py)
   - Add validation helper (order_validation.py)
   - Write tests
   - Manual testing

3. **Phase 3** (Day 4):
   - Research CoW Protocol source
   - Document findings
   - Run classification experiments
   - Make recommendation
   - Implement fix if possible, or document limitation

**Total Estimated Time**: 4 days

---

## Open Questions

None - all decisions made during planning phase.

## Success Metrics

- [ ] Can run 120-second test with 10 traders without TooManyLimitOrders error
- [ ] Orders correctly cancelled when approaching limit
- [ ] E2E hooks test passes 10 consecutive times
- [ ] All automated tests pass
- [ ] Documentation updated
- [ ] Configuration migration guide provided
