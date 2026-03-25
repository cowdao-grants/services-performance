# Fix active_orders Count: UID Swap Not Propagated to PrometheusExporter

## Overview

The `orders_active` Prometheus gauge never decrements for orders that go through the full lifecycle (created → submitted → accepted → expired/filled/failed). The root cause is that `MetricsStore.update_order_uid()` swaps the internal dictionary key but never fires any callback, leaving `PrometheusExporter._active_orders` with a stale `temp_uid` forever. All terminal-state callbacks arrive with `real_uid`, which is not in the set, so every `discard(real_uid)` is a silent no-op.

## Current State Analysis

### The Bug: UID Swap Path

**`MetricsStore.update_order_uid()`** — `src/cow_performance/metrics/store.py:149-160`

```python
def update_order_uid(self, old_uid: str, new_uid: str) -> None:
    if old_uid in self._orders:
        order = self._orders.pop(old_uid)
        order.order_uid = new_uid        # mutates metadata object
        self._orders[new_uid] = order
    # ← NO callback fired here
```

**`PrometheusExporter._active_orders`** — `src/cow_performance/prometheus/exporter.py:63`

- Populated at `CREATED` status with `temp_uid` (line 140).
- All terminal state handlers call `_active_orders.discard(order.order_uid)` (lines 166, 184, 190, 196).
- After the UID swap, `order.order_uid` is already `real_uid`, so every discard is a no-op.

### Lifecycle Data Flow (Broken)

```
1. track_order(temp_uid)  → CREATED callback → _active_orders.add(temp_uid)   ✓
2. update_order_uid(temp_uid, real_uid)                                         ✗ no callback
   → _active_orders still has temp_uid, not real_uid
3. update_order_status(real_uid, ACCEPTED) → ACCEPTED callback (no discard)    benign
4. [ExpirationChecker] → EXPIRED callback with real_uid
   → _active_orders.discard(real_uid)  → no-op (real_uid was never added)      ✗
   → temp_uid leaks in set forever → active count stays inflated
```

### What's Already Working Correctly

- `ExpirationChecker` (`src/cow_performance/metrics/expiration_checker.py`): correctly detects expired orders, calls `metadata.update_status(EXPIRED)` and `metrics_store.add_order(metadata)`.
- `PrometheusExporter._update_order_metrics()`: correctly handles all terminal states with `discard()`.
- Unit tests for `ExpirationChecker` exist and pass (`tests/unit/test_expiration_checker.py`).

### Key Discoveries

- `MetricsStore.update_order_uid()` (store.py:149): no callback fired — this is the single root cause.
- `_notify_callbacks()` (store.py:292): already supports arbitrary `(metric_type, metric_object)` pairs — we can add a new type.
- `PrometheusExporter._orders_by_trader` (exporter.py:68) has the same bug: it stores `temp_uid` per trader and never renames on UID swap.
- `_active_traders` tracking (exporter.py:67) is also affected since `_remove_order_from_trader` uses the wrong UID.

## Desired End State

After this fix:
- `orders_active` gauge in Grafana decrements by 1 for each expired, filled, failed, or cancelled order.
- `orders_active` never accumulates stale counts from the `temp_uid → real_uid` swap.
- The existing `ExpirationChecker` correctly drives the Prometheus `EXPIRED` path.
- Per-trader tracking (`_orders_by_trader`, `traders_active`) also stays consistent after UID swap.

### Verification

Run the performance suite, submit orders, wait for them to expire (60s with current `valid_duration=60`), and observe `orders_active{scenario=...}` in Grafana declining toward 0 as orders expire. The gauge must equal `orders_created - orders_filled - orders_expired - orders_failed - orders_cancelled` at all times.

## What We're NOT Doing

- Not changing the `ExpirationChecker` logic — it is correct.
- Not changing the `OrderTracker.update_order_uid()` — it already delegates to `MetricsStore`.
- Not refactoring the callback architecture beyond the minimal addition needed.
- Not changing the Grafana dashboard JSON.
- Not touching the `OrderFactory` or `TraderSimulator` submission flow.

## Implementation Approach

Add a `"uid_rename"` event type to `MetricsStore.update_order_uid()`. `PrometheusExporter` handles this by swapping `temp_uid → real_uid` in `_active_orders` and `_orders_by_trader`. This is the minimal, targeted fix that preserves all existing behavior.

---

## Phase 1: Fire UID-rename callback from MetricsStore

### Overview

`MetricsStore.update_order_uid()` will fire `_notify_callbacks("uid_rename", (old_uid, new_uid))` after swapping the key. This lets any registered listener keep its internal UID-based data structures consistent.

### Changes Required

#### 1. `MetricsStore.update_order_uid()`

**File**: `src/cow_performance/metrics/store.py`
**Change**: Add callback notification after the UID swap.

```python
def update_order_uid(self, old_uid: str, new_uid: str) -> None:
    if old_uid in self._orders:
        order = self._orders.pop(old_uid)
        order.order_uid = new_uid
        self._orders[new_uid] = order
        # Notify listeners so they can rename UID in their own state
        self._notify_callbacks("uid_rename", (old_uid, new_uid))
```

### Success Criteria

#### Automated Verification

- [ ] `poetry run pytest tests/unit/test_metrics_store.py` — existing store tests pass
- [ ] `poetry run ruff check src/` — no lint errors
- [ ] `poetry run mypy src/` — no type errors

---

## Phase 2: Handle `uid_rename` in PrometheusExporter

### Overview

`PrometheusExporter._on_metric_update()` will dispatch a new `"uid_rename"` event to a new `_rename_order_uid()` method that swaps `temp_uid → real_uid` in `_active_orders` and `_orders_by_trader`.

### Changes Required

#### 1. `PrometheusExporter._on_metric_update()`

**File**: `src/cow_performance/prometheus/exporter.py:113-127`
**Change**: Add `elif metric_type == "uid_rename"` dispatch.

```python
def _on_metric_update(self, metric_type: str, metric: object) -> None:
    try:
        if metric_type == "order" and isinstance(metric, OrderMetadata):
            self._update_order_metrics(metric)
        elif metric_type == "api" and isinstance(metric, APIMetrics):
            self._update_api_metrics(metric)
        elif metric_type == "resource":
            self._update_resource_metrics(metric)
        elif metric_type == "uid_rename" and isinstance(metric, tuple) and len(metric) == 2:
            old_uid, new_uid = metric
            self._rename_order_uid(str(old_uid), str(new_uid))
    except Exception as e:
        logger.warning("Error updating Prometheus metric: %s", e)
```

#### 2. New `PrometheusExporter._rename_order_uid()` method

**File**: `src/cow_performance/prometheus/exporter.py`
**Change**: Add private method after `_update_order_metrics`.

```python
def _rename_order_uid(self, old_uid: str, new_uid: str) -> None:
    """Update internal UID references after a temp→real UID swap."""
    if old_uid in self._active_orders:
        self._active_orders.discard(old_uid)
        self._active_orders.add(new_uid)

    # Update per-trader order tracking
    for trader_index, order_set in self._orders_by_trader.items():
        if old_uid in order_set:
            order_set.discard(old_uid)
            order_set.add(new_uid)
            break  # UIDs are unique across traders
```

### Success Criteria

#### Automated Verification

- [ ] `poetry run pytest tests/unit/` — all unit tests pass
- [ ] `poetry run ruff check src/ tests/` — no lint errors
- [ ] `poetry run mypy src/` — no type errors
- [ ] `poetry run black --check src/ tests/` — formatting passes

---

## Phase 3: Unit Tests for the Fix

### Overview

Add a unit test that verifies `_active_orders` is correctly decremented after a `temp_uid → real_uid` swap followed by a terminal state update.

### Changes Required

#### 1. New test file (or extend existing)

**File**: `tests/unit/test_exporter_uid_rename.py`
**Change**: Test the full lifecycle with UID swap.

```python
"""Test that active_orders is decremented correctly after UID swap."""

import pytest
from unittest.mock import MagicMock
from cow_performance.prometheus.exporter import PrometheusExporter
from cow_performance.metrics.models import OrderMetadata, OrderStatus
import time

class TestExporterUidRename:
    @pytest.fixture
    def exporter(self):
        return PrometheusExporter(scenario="test")

    def _make_order(self, uid: str, status: OrderStatus) -> OrderMetadata:
        order = OrderMetadata(
            order_uid=uid,
            owner="0xabc",
            creation_time=time.time(),
            valid_to=int(time.time()) - 1,
        )
        order.update_status(status)
        return order

    def test_active_count_decrements_after_uid_swap_and_expire(self, exporter):
        """Active count must reach 0 after temp→real UID swap and EXPIRED status."""
        temp_uid = "0xtemp"
        real_uid = "0xreal"

        # 1. CREATED with temp_uid
        order = self._make_order(temp_uid, OrderStatus.CREATED)
        exporter._on_metric_update("order", order)
        assert len(exporter._active_orders) == 1
        assert temp_uid in exporter._active_orders

        # 2. UID swap notification
        exporter._on_metric_update("uid_rename", (temp_uid, real_uid))
        assert real_uid in exporter._active_orders
        assert temp_uid not in exporter._active_orders

        # 3. EXPIRED with real_uid
        order.order_uid = real_uid
        order.update_status(OrderStatus.EXPIRED)
        exporter._on_metric_update("order", order)
        assert len(exporter._active_orders) == 0

    def test_active_count_decrements_after_uid_swap_and_fill(self, exporter):
        """Active count must reach 0 after temp→real UID swap and FILLED status."""
        temp_uid = "0xtemp2"
        real_uid = "0xreal2"

        order = self._make_order(temp_uid, OrderStatus.CREATED)
        exporter._on_metric_update("order", order)
        exporter._on_metric_update("uid_rename", (temp_uid, real_uid))
        order.order_uid = real_uid
        order.update_status(OrderStatus.FILLED)
        exporter._on_metric_update("order", order)
        assert len(exporter._active_orders) == 0

    def test_active_count_decrements_after_uid_swap_and_failed(self, exporter):
        """Active count must reach 0 after temp→real UID swap and FAILED status."""
        temp_uid = "0xtemp3"
        real_uid = "0xreal3"

        order = self._make_order(temp_uid, OrderStatus.CREATED)
        exporter._on_metric_update("order", order)
        exporter._on_metric_update("uid_rename", (temp_uid, real_uid))
        order.order_uid = real_uid
        order.update_status(OrderStatus.FAILED)
        exporter._on_metric_update("order", order)
        assert len(exporter._active_orders) == 0

    def test_uid_not_in_active_orders_is_safe(self, exporter):
        """Renaming a UID not in active_orders should not raise."""
        exporter._on_metric_update("uid_rename", ("0xghost", "0xreal"))
        assert len(exporter._active_orders) == 0

    def test_per_trader_orders_renamed_correctly(self, exporter):
        """_orders_by_trader must reflect the new UID after swap."""
        temp_uid = "0xtemp_trader"
        real_uid = "0xreal_trader"

        order = self._make_order(temp_uid, OrderStatus.CREATED)
        exporter._on_metric_update("order", order)

        exporter._on_metric_update("uid_rename", (temp_uid, real_uid))

        # Check that the real_uid is now in the trader's order set
        for order_set in exporter._orders_by_trader.values():
            assert temp_uid not in order_set
            assert real_uid in order_set
```

### Success Criteria

#### Automated Verification

- [ ] `poetry run pytest tests/unit/test_exporter_uid_rename.py -v` — all 5 tests pass
- [ ] `poetry run pytest` — full test suite passes
- [ ] `poetry run ruff check src/ tests/` — no lint errors
- [ ] `poetry run mypy src/` — no type errors

---

## Phase 4: Manual Grafana Verification

### Overview

Run the performance suite and confirm in Grafana that `orders_active` decrements correctly as orders expire.

### Manual Testing Steps

1. Start services: `docker compose up -d`
2. Run a short test (orders expire after 60s):
   ```bash
   poetry run cow-perf run --duration 120 --traders 2 --scenario test
   ```
3. Open Grafana dashboard → "Orders Active" panel.
4. Observe:
   - `orders_active` rises as orders are submitted.
   - After ~60s, `orders_active` starts declining (ExpirationChecker fires).
   - By end of test, `orders_active` should equal `orders_created - orders_expired - orders_filled - orders_failed`.
5. Check logs for the `EXPIRED:` debug prints (exporter.py:188-191) showing `was_in_active=True` after the fix (currently shows `False`).

### Success Criteria

#### Manual Verification

- [ ] `orders_active` panel in Grafana shows declining count after orders expire (not flat/growing)
- [ ] Log output shows `EXPIRED: was_in_active=True` for all expired orders
- [ ] `orders_active` converges toward `orders_created - orders_expired - orders_filled - orders_failed - orders_cancelled` by end of test
- [ ] No stale positive value remains in `orders_active` after all orders reach terminal state

---

## Testing Strategy

### Unit Tests

- `test_exporter_uid_rename.py` (new): covers all terminal states after UID swap, edge cases (ghost UID, per-trader tracking).
- `tests/unit/test_expiration_checker.py` (existing): ensures `ExpirationChecker` still correctly marks orders expired — no changes needed.

### Integration / Manual Tests

- Short 2-minute run with 2 traders and 60s order expiry.
- Grafana observation of `orders_active` metric.

## References

- Root cause: `src/cow_performance/metrics/store.py:149-160` — `update_order_uid` fires no callback
- Active set: `src/cow_performance/prometheus/exporter.py:63` — `_active_orders: set[str]`
- EXPIRED debug prints: `src/cow_performance/prometheus/exporter.py:188-191`
- ExpirationChecker: `src/cow_performance/metrics/expiration_checker.py:77-128`
- Existing tests: `tests/unit/test_expiration_checker.py`
