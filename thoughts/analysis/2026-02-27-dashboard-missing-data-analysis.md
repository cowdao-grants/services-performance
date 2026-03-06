# Dashboard Missing Data Analysis

**Date:** 2026-02-27
**Branch:** luizhatem/cow-699-dashboard-fixes
**Issue:** Multiple Grafana dashboard panels showing "No data"
**Status:** ✅ **FIX IMPLEMENTED**

## Executive Summary

The root cause is a **missing callback trigger** in the `OrderTracker.update_order_status()` method. When order statuses change (CREATED → SUBMITTED → FILLED), the MetricsStore is not notified, preventing the Prometheus exporter from incrementing counters and recording histograms.

## Affected Dashboard Panels

### 1. Performance Dashboard (`performance.json`)
- ❌ **Success Rate** - Query: `(orders_filled / orders_submitted) * 100`
- ❌ **Total Orders Submitted** - Query: `cow_perf_orders_submitted_total`
- ❌ **Total Orders Filled** - Query: `cow_perf_orders_filled_total`
- ❌ **Total Orders Failed** - Query: `cow_perf_orders_failed_total`
- ❌ **Submission Latency Distribution** - Query: `rate(cow_perf_submission_latency_seconds_bucket[...])`
- ❌ **Settlement Latency Distribution** - Query: `rate(cow_perf_settlement_latency_seconds_bucket[...])`
- ❌ **Submission Latency Percentiles** - Query: `histogram_quantile(..., cow_perf_submission_latency_seconds_bucket)`
- ✅ **Active Orders** - Works (gauge set directly)
- ✅ **Order Status Distribution** - Partially works (shows Active: 39)

### 2. Trader Activity Dashboard (`trader-activity.json`)
- ❌ **Avg Orders/Trader** - Query: `sum(cow_perf_trader_orders_submitted) / cow_perf_num_traders`
- ❌ **Fill Rate** - Query: `sum(cow_perf_trader_orders_filled) / sum(cow_perf_trader_orders_submitted) * 100`
- ❌ **Orders Submitted (Top N)** - Query: `topk($top_n, cow_perf_trader_orders_submitted)`
- ❌ **Orders Filled (Top N)** - Query: `topk($top_n, cow_perf_trader_orders_filled)`
- ✅ **Active Traders** - Works (3)
- ✅ **Total Traders** - Works (3)

### 3. Comparison Dashboard (`comparison.json`)
- ❌ **All baseline comparison metrics** - No baseline data being recorded
- ❌ **Baseline ID** - Query: `cow_perf_baseline_comparison_percent{baseline_id=~"$baseline_id"}`
- ❌ **Total Regressions** - Query: `sum(cow_perf_regressions_total)`
- ❌ **Submission/Settlement Latency Delta** - No data

### 4. API Performance Dashboard (`api-performance.json`)
- ✅ **Most panels work** - API metrics are recorded correctly
- ❌ **Error-related panels** - Likely no errors occurred

## Root Cause Analysis

### The Problem

In `src/cow_performance/load_generation/order_tracker.py`:

```python
def update_order_status(
    self,
    order_uid: str,
    new_status: OrderStatus,
    filled_amount: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update the status of a tracked order."""
    if order_uid not in self._orders:
        return

    metadata = self._orders[order_uid]
    metadata.update_status(new_status)  # ← Updates metadata locally

    if filled_amount is not None:
        metadata.filled_amount = filled_amount
    if error_message is not None:
        metadata.error_message = error_message

    # ❌ MISSING: No call to self._metrics_store.add_order(metadata)
    # This means the Prometheus exporter callback is never triggered!
```

### The Flow

1. **Order Created** (Status: CREATED)
   - `OrderTracker.track_order()` called
   - Calls `self._metrics_store.add_order(metadata)` ✅
   - Triggers Prometheus exporter callback
   - Increments `cow_perf_orders_created_total` ✅

2. **Order Submitted** (Status: SUBMITTED)
   - `OrderTracker.update_order_status()` called
   - Updates `metadata.current_status = SUBMITTED`
   - **DOES NOT** call `self._metrics_store.add_order(metadata)` ❌
   - **NO** callback to Prometheus exporter ❌
   - `cow_perf_orders_submitted_total` **NOT incremented** ❌
   - Submission latency **NOT recorded** ❌

3. **Order Filled** (Status: FILLED)
   - `OrderTracker.update_order_status()` called
   - Updates `metadata.current_status = FILLED`
   - **DOES NOT** call `self._metrics_store.add_order(metadata)` ❌
   - **NO** callback to Prometheus exporter ❌
   - `cow_perf_orders_filled_total` **NOT incremented** ❌
   - Settlement latency **NOT recorded** ❌

### Why Some Metrics Work

**Working metrics:**
- `cow_perf_orders_active` - Gauge set directly in exporter via `update_active_orders()`
- `cow_perf_traders_active` - Gauge set directly in exporter
- `cow_perf_num_traders` - Gauge set via `set_num_traders()`
- API metrics - Callbacks work correctly via `InstrumentedOrderbookClient`

**Not working metrics:**
- All Counter metrics that depend on status transitions (submitted, filled, failed, expired)
- All Histogram metrics that record latencies (submission, settlement, lifecycle)
- All derived metrics that use counters (success rate, fill rate, averages)

## The Fix

### Required Change

In `src/cow_performance/load_generation/order_tracker.py`, add the following after line 151:

```python
def update_order_status(
    self,
    order_uid: str,
    new_status: OrderStatus,
    filled_amount: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update the status of a tracked order."""
    if order_uid not in self._orders:
        return

    metadata = self._orders[order_uid]
    metadata.update_status(new_status)

    if filled_amount is not None:
        metadata.filled_amount = filled_amount
    if error_message is not None:
        metadata.error_message = error_message

    # ✅ FIX: Notify metrics store to trigger callbacks
    if self._metrics_store is not None:
        self._metrics_store.add_order(metadata)
```

### Why This Works

1. Each status transition will now call `self._metrics_store.add_order(metadata)`
2. This triggers the Prometheus exporter callback `_on_metric_update()`
3. The exporter checks `metadata.current_status` and increments the appropriate counter
4. Latencies are calculated and observed in histograms

### Impact

After this fix:
- ✅ `cow_perf_orders_submitted_total` will increment when orders are submitted
- ✅ `cow_perf_orders_filled_total` will increment when orders fill
- ✅ `cow_perf_orders_failed_total` will increment when orders fail
- ✅ Submission latency histograms will record data
- ✅ Settlement latency histograms will record data
- ✅ Success Rate, Fill Rate, and all derived metrics will work
- ✅ Per-trader metrics will populate
- ✅ Baseline comparison metrics will work (when baseline comparisons are run)

## Testing the Fix

1. Apply the fix to `order_tracker.py`
2. Run a performance test with Prometheus exporter enabled:
   ```bash
   poetry run cow-perf run --scenario baseline --prometheus-port 9091
   ```
3. Check Prometheus metrics endpoint:
   ```bash
   curl http://localhost:9091/metrics | grep cow_perf_orders
   ```
4. Verify Grafana dashboards show data for all panels

## Additional Notes

### Why This Bug Wasn't Caught Earlier

- The exporter was recently refactored to use callbacks (COW-591, COW-614, COW-616)
- The callback mechanism works correctly for API metrics and resource metrics
- The bug is specific to order status transitions not triggering callbacks
- Unit tests may not cover the end-to-end callback flow
- Integration tests might not verify Prometheus metric increments

### Related Files

- `src/cow_performance/load_generation/order_tracker.py` - **Needs fix**
- `src/cow_performance/prometheus/exporter.py` - Callback handler (working correctly)
- `src/cow_performance/metrics/store.py` - MetricsStore with callbacks (working correctly)
- `configs/dashboards/performance.json` - Dashboard queries (correct)
- `configs/dashboards/trader-activity.json` - Dashboard queries (correct)

### Recommendation

Add integration tests that verify:
1. Order status transitions trigger Prometheus counter increments
2. Latency histograms receive observations
3. Dashboard queries return non-zero values after test runs

## Implementation

**Date:** 2026-02-27
**Status:** ✅ Fixed

### Changes Made

Modified `src/cow_performance/load_generation/order_tracker.py:158-160`:

```python
# Notify metrics store to trigger Prometheus exporter callbacks
if self._metrics_store is not None:
    self._metrics_store.add_order(metadata)
```

This change was added to the `update_order_status()` method after updating the metadata fields. Now every status transition will:
1. Update the local metadata object
2. Notify the MetricsStore
3. Trigger the Prometheus exporter callback
4. Increment appropriate counters and observe histograms

### Expected Results

After this fix, all dashboard panels should populate with data:
- Order counters (submitted, filled, failed, expired)
- Success rates and fill rates
- Latency distributions and percentiles
- Per-trader metrics
- Baseline comparison metrics (when baseline runs are executed)

### Next Steps

1. Test the fix with a performance test run
2. Verify dashboard panels show data
3. Run linting and tests before committing
4. Consider adding integration tests to prevent regression
