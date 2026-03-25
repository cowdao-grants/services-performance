# Expired Orders Database Update Investigation

**Date:** 2026-03-24
**Issue:** Orderbook doesn't update expired orders in the database
**Status:** Root cause identified, fix planned

---

## Executive Summary

**Root Cause:** The orderbook service **intentionally does NOT** update expired orders in the database. Order expiration is calculated **dynamically at query time** based on the `valid_to` timestamp field. No database field or event is ever set to mark an order as "expired".

**Impact:**
- Cannot track expiration metrics in real-time
- No historical data on when orders expired
- Performance dashboards show incomplete expiration data
- Analytics queries require complex time-based calculations

---

## Order Lifecycle and Database Flow

### 1. Order Creation Flow

**Location:** `modules/services/crates/orderbook/src/orderbook.rs:270-307`

```
User submits order
    ↓
OrderValidator validates order
    ↓
database.insert_order() → INSERT INTO orders (uid, owner, valid_to, ...)
    ↓
INSERT INTO order_events (order_uid, label='Created', timestamp)
    ↓
Order is now "Open" and available for trading
```

**Database Schema:**
```sql
CREATE TABLE orders (
    uid bytea PRIMARY KEY,
    owner bytea NOT NULL,
    creation_timestamp timestamptz NOT NULL,
    valid_to bigint NOT NULL,              -- ← Unix timestamp when order expires
    cancellation_timestamp timestamptz,     -- ← Only set when cancelled
    -- NOTE: No expiration_timestamp field exists!
    ...
);
```

### 2. Order Status Determination (Query Time)

**Location:** `modules/services/crates/orderbook/src/database/orders.rs:493-516`

```rust
fn calculate_status(order: &FullOrder) -> OrderStatus {
    // Check if filled
    match order.kind {
        DbOrderKind::Buy => {
            if is_buy_order_filled(&order.buy_amount, &order.sum_buy) {
                return OrderStatus::Fulfilled;
            }
        }
        DbOrderKind::Sell => {
            if is_sell_order_filled(&order.sell_amount, &order.sum_sell, &order.sum_fee) {
                return OrderStatus::Fulfilled;
            }
        }
    }

    // Check if cancelled
    if order.invalidated {
        return OrderStatus::Cancelled;
    }

    // ← EXPIRATION CHECK: Compare timestamp dynamically
    if order.valid_to() < Utc::now().timestamp() {
        return OrderStatus::Expired;  // Status computed, nothing written to DB
    }

    if order.presignature_pending {
        return OrderStatus::PresignaturePending;
    }

    OrderStatus::Open
}
```

**Key Finding:** Expiration is determined by comparing `valid_to < current_time`, but **no database update occurs**.

### 3. Order Cancellation Flow (For Comparison)

**Location:** `modules/services/crates/database/src/orders.rs:450-470`

```rust
pub async fn cancel_order(
    ex: &mut PgConnection,
    order_uid: &OrderUid,
    timestamp: DateTime<Utc>,
) -> Result<(), sqlx::Error> {
    // ← Cancelled orders ARE updated in the database
    const QUERY: &str = r#"
UPDATE orders
SET cancellation_timestamp = $1
WHERE uid = $2
AND cancellation_timestamp IS NULL
    "#;

    sqlx::query(QUERY)
        .bind(timestamp)
        .bind(order_uid.0.as_ref())
        .execute(ex)
        .await
        .map(|_| ())
}
```

**Contrast:** Cancelled orders get `cancellation_timestamp` updated; expired orders get nothing.

### 4. Auction Creation (How Expired Orders Are Filtered)

**Location:** `modules/services/crates/database/src/orders.rs:719-820`

```sql
WITH live_orders AS (
    SELECT o.*
    FROM   orders o
    LEFT   JOIN ethflow_orders e ON e.uid = o.uid
    WHERE  o.cancellation_timestamp IS NULL
      AND  o.valid_to >= $1  -- ← Filters out expired orders at query time
      AND (e.valid_to IS NULL OR e.valid_to >= $1)
      AND NOT EXISTS (SELECT 1 FROM invalidations i WHERE i.order_uid = o.uid)
      ...
)
SELECT * FROM live_orders
```

**Key Finding:** Expired orders are **excluded during queries** using `valid_to >= current_timestamp`, but the database record itself is never modified.

---

## Database Schema Analysis

### Orders Table

```sql
CREATE TABLE orders (
    uid bytea PRIMARY KEY,
    owner bytea NOT NULL,
    creation_timestamp timestamptz NOT NULL,
    sell_token bytea NOT NULL,
    buy_token bytea NOT NULL,
    valid_to bigint NOT NULL,              -- Unix timestamp
    cancellation_timestamp timestamptz,     -- NULL for expired orders
    ...
);
```

**Missing:** No `expiration_timestamp` field.

### Order Events Table

```sql
CREATE TYPE OrderEventLabel AS ENUM (
  'created',
  'ready',
  'filtered',
  'invalid',
  'executing',
  'considered',
  'traded',
  'cancelled'
  -- ⚠ NOTE: NO 'expired' event type exists!
);

CREATE TABLE order_events (
    order_uid bytea NOT NULL,
    timestamp timestamptz NOT NULL,
    label OrderEventLabel NOT NULL,
    ...
);
```

**Missing:** No `Expired` event label in the enum.

---

## Why This Design Was Chosen

The current architecture is **intentional** and has valid reasoning:

### Pros of Current Approach
1. **Performance:** Avoids writing to database for every expired order (could be millions)
2. **Efficiency:** Indexed `valid_to` field allows fast query-time filtering
3. **Simplicity:** No background jobs needed to update expired orders
4. **Storage:** Doesn't bloat database with unnecessary timestamps

### Cons of Current Approach
1. **No metrics:** Cannot track expiration rate in Prometheus
2. **No analytics:** Cannot query "how many orders expired in last hour"
3. **Incomplete audit:** No historical record of when orders expired
4. **Inconsistent:** Cancelled orders ARE tracked, but expired orders are not

---

## The Gap: What's Missing

The current design creates issues for:

1. **Performance Monitoring:**
   - Cannot track `orders_expired_total` metric in Prometheus
   - Dashboard shows incomplete order lifecycle data
   - No expiration rate tracking

2. **Analytics:**
   - Cannot answer: "What % of orders expire vs get filled?"
   - Cannot track expiration patterns over time
   - Cannot identify if `valid_to` times are too short/long

3. **Debugging:**
   - When investigating order issues, expiration timestamp would help
   - No clear audit trail of order lifecycle

4. **Reporting:**
   - Test reports show incomplete order status breakdown
   - Cannot generate "orders by final status" reports

---

## Proposed Fix: Implementation Plan

### Option 1: Add Expiration Timestamp (Recommended - Lightweight)

**Approach:** Add a new `expiration_timestamp` column that gets updated when order expires.

#### Step 1: Database Migration

**File:** `modules/services/database/sql/V0XX__add_expiration_timestamp.sql`

```sql
-- Add expiration_timestamp column
ALTER TABLE orders
ADD COLUMN expiration_timestamp timestamptz DEFAULT NULL;

-- Create index for efficient queries
CREATE INDEX idx_orders_expiration_timestamp
ON orders(expiration_timestamp)
WHERE expiration_timestamp IS NOT NULL;

-- Create index for finding unexpired orders efficiently
CREATE INDEX idx_orders_unexpired
ON orders(valid_to)
WHERE expiration_timestamp IS NULL
  AND cancellation_timestamp IS NULL;
```

#### Step 2: Background Expiration Task

**File:** `modules/services/crates/autopilot/src/expired_orders_updater.rs`

```rust
use crate::database::Postgres;
use anyhow::Result;
use chrono::Utc;
use std::time::Duration;

pub struct ExpiredOrdersUpdater {
    db: Postgres,
    update_interval: Duration,
}

impl ExpiredOrdersUpdater {
    pub fn new(db: Postgres) -> Self {
        Self {
            db,
            update_interval: Duration::from_secs(60), // Run every minute
        }
    }

    pub async fn run_forever(&self) -> ! {
        loop {
            if let Err(err) = self.update_expired_orders().await {
                tracing::error!(?err, "failed to update expired orders");
            }

            tokio::time::sleep(self.update_interval).await;
        }
    }

    async fn update_expired_orders(&self) -> Result<()> {
        let now = Utc::now().timestamp();

        let result = sqlx::query!(
            r#"
            UPDATE orders
            SET expiration_timestamp = NOW()
            WHERE valid_to < $1
              AND expiration_timestamp IS NULL
              AND cancellation_timestamp IS NULL
            "#,
            now
        )
        .execute(self.db.as_ref())
        .await?;

        let updated = result.rows_affected();
        if updated > 0 {
            tracing::info!(count = updated, "marked orders as expired");
        }

        Ok(())
    }
}
```

#### Step 3: Update Status Calculation

**File:** `modules/services/crates/orderbook/src/database/orders.rs`

```rust
fn calculate_status(order: &FullOrder) -> OrderStatus {
    // Check if filled
    if is_filled(order) {
        return OrderStatus::Fulfilled;
    }

    // Check if cancelled
    if order.invalidated || order.cancellation_timestamp.is_some() {
        return OrderStatus::Cancelled;
    }

    // ← NEW: Check expiration_timestamp first (if available)
    if let Some(_) = order.expiration_timestamp {
        return OrderStatus::Expired;
    }

    // ← FALLBACK: Check valid_to for backwards compatibility
    if order.valid_to() < Utc::now().timestamp() {
        return OrderStatus::Expired;
    }

    if order.presignature_pending {
        return OrderStatus::PresignaturePending;
    }

    OrderStatus::Open
}
```

#### Step 4: Register Task in Autopilot

**File:** `modules/services/crates/autopilot/src/main.rs`

```rust
// Add to main function
let expired_orders_updater = ExpiredOrdersUpdater::new(db.clone());
tokio::spawn(async move {
    expired_orders_updater.run_forever().await;
});
```

#### Step 5: Add Prometheus Metrics

**File:** `modules/services/crates/autopilot/src/expired_orders_updater.rs`

```rust
use prometheus::{IntCounter, Registry};

lazy_static! {
    static ref ORDERS_EXPIRED_TOTAL: IntCounter = IntCounter::new(
        "orders_expired_total",
        "Total number of orders marked as expired"
    ).unwrap();
}

pub fn register_metrics(registry: &Registry) -> Result<()> {
    registry.register(Box::new(ORDERS_EXPIRED_TOTAL.clone()))?;
    Ok(())
}

async fn update_expired_orders(&self) -> Result<()> {
    // ... existing code ...

    let updated = result.rows_affected();
    if updated > 0 {
        ORDERS_EXPIRED_TOTAL.inc_by(updated);  // ← Track in Prometheus
        tracing::info!(count = updated, "marked orders as expired");
    }

    Ok(())
}
```

---

### Option 2: Add Expired Event (More Complete)

**Approach:** Add `Expired` to `OrderEventLabel` enum and insert events.

#### Pros:
- Full audit trail in `order_events` table
- Consistent with existing event tracking
- Can track exact expiration time

#### Cons:
- Requires enum migration (more complex)
- More writes to database (one per expired order)
- `order_events` table grows faster

#### Implementation:

**Step 1:** Add enum variant
```sql
ALTER TYPE OrderEventLabel ADD VALUE 'expired';
```

**Step 2:** Insert expired events
```rust
for order_uid in expired_orders {
    insert_order_event(OrderEvent {
        order_uid,
        timestamp: Utc::now(),
        label: OrderEventLabel::Expired,
    }).await?;
}
```

---

### Option 3: Computed Column (PostgreSQL-Specific)

**Approach:** Use generated column that automatically computes expired status.

```sql
ALTER TABLE orders
ADD COLUMN is_expired BOOLEAN
GENERATED ALWAYS AS (
    valid_to < EXTRACT(EPOCH FROM NOW())
    AND cancellation_timestamp IS NULL
) STORED;

CREATE INDEX idx_orders_is_expired ON orders(is_expired);
```

#### Pros:
- No background task needed
- Always up-to-date
- Efficient querying

#### Cons:
- PostgreSQL-specific feature
- Cannot track "when" order expired (only current state)
- Generated columns have limitations

---

## ⚠️ CONSTRAINT: Cannot Modify CoW Protocol Services

**Critical Finding:** The code in `/modules/services` is from the CoW Protocol repository and **cannot be modified** by this performance testing suite.

**Implication:** We cannot add background tasks or modify the orderbook/autopilot services directly. The fix must be implemented **within the performance testing suite codebase**.

---

## Revised Recommendation: Track Expiration in Performance Testing Suite

Since we cannot modify the orderbook service, we need to **track order expiration ourselves** during performance tests.

### Approach: Order Lifecycle Tracker in Testing Suite

**Location:** `src/cow_performance/metrics/`

**Strategy:**
1. Track all submitted orders with their `valid_to` timestamps
2. Periodically check which orders have expired
3. Update our metrics/database when orders expire
4. Include expiration data in test reports

### Implementation Plan (Within Our Codebase)

#### Step 1: Extend OrderMetadata Model

**File:** `src/cow_performance/metrics/models.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class OrderMetadata:
    order_uid: str
    owner: str
    creation_time: float
    submission_time: Optional[float] = None
    acceptance_time: Optional[float] = None
    first_fill_time: Optional[float] = None
    completion_time: Optional[float] = None
    expiration_time: Optional[float] = None  # ← NEW: Track when we detected expiration
    valid_to: int  # ← NEW: Store order's expiration timestamp
    current_status: OrderStatus = OrderStatus.CREATED
```

#### Step 2: Create Expiration Checker Background Task

**File:** `src/cow_performance/metrics/expiration_checker.py`

```python
"""
Background task to check for expired orders and update metrics.

Since we cannot modify the orderbook service code, we track expiration
ourselves by periodically checking order valid_to timestamps.
"""

import asyncio
import time
from typing import Dict
from .models import OrderMetadata, OrderStatus
from .store import MetricsStore

class ExpirationChecker:
    """Periodically checks for expired orders and updates metrics."""

    def __init__(self, metrics_store: MetricsStore, check_interval: float = 5.0):
        """
        Args:
            metrics_store: Store containing all order metadata
            check_interval: How often to check for expirations (seconds)
        """
        self.metrics_store = metrics_store
        self.check_interval = check_interval
        self._running = False

    async def start(self):
        """Start background expiration checking."""
        self._running = True
        asyncio.create_task(self._check_loop())

    async def stop(self):
        """Stop background expiration checking."""
        self._running = False

    async def _check_loop(self):
        """Main loop that checks for expired orders."""
        while self._running:
            await self._check_expired_orders()
            await asyncio.sleep(self.check_interval)

    async def _check_expired_orders(self):
        """Check all orders and mark expired ones."""
        current_time = int(time.time())

        async with self.metrics_store.lock:
            for order_uid, metadata in self.metrics_store.orders.items():
                # Skip if already marked as expired
                if metadata.current_status == OrderStatus.EXPIRED:
                    continue

                # Skip if already in terminal state (filled/cancelled)
                if metadata.current_status in {OrderStatus.FILLED, OrderStatus.CANCELLED}:
                    continue

                # Check if order has expired
                if metadata.valid_to < current_time:
                    # Mark as expired
                    metadata.current_status = OrderStatus.EXPIRED
                    metadata.expiration_time = time.time()

                    # Log for debugging
                    print(f"Order {order_uid[:10]}... expired (valid_to={metadata.valid_to}, now={current_time})")
```

#### Step 3: Update OrderTracker to Store valid_to

**File:** `src/cow_performance/load_generation/order_tracker.py`

```python
async def submit_order(self, order_data: dict) -> Optional[str]:
    """Submit order and track in metrics."""

    # Extract valid_to from order data
    valid_to = order_data.get("validTo", 0)

    # Submit to API
    order_uid = await self.api_client.submit_order(order_data)

    # Track in metrics
    metadata = OrderMetadata(
        order_uid=order_uid,
        owner=order_data["signingScheme"]["owner"],
        creation_time=time.time(),
        valid_to=valid_to,  # ← Store expiration timestamp
        current_status=OrderStatus.CREATED,
    )

    async with self.metrics_store.lock:
        self.metrics_store.add_order(metadata)

    return order_uid
```

#### Step 4: Start Expiration Checker During Tests

**File:** `src/cow_performance/cli/run.py`

```python
async def run_performance_test(config: ScenarioConfig):
    """Run performance test with expiration tracking."""

    # Create metrics store
    metrics_store = MetricsStore()

    # ← NEW: Start expiration checker
    expiration_checker = ExpirationChecker(
        metrics_store=metrics_store,
        check_interval=5.0  # Check every 5 seconds
    )
    await expiration_checker.start()

    try:
        # Run test
        await run_load_generation(config, metrics_store)

    finally:
        # Stop expiration checker
        await expiration_checker.stop()
```

#### Step 5: Update Metrics Export

**File:** `src/cow_performance/metrics/aggregator.py`

```python
def aggregate_order_status_breakdown(self) -> Dict[str, int]:
    """Get count of orders by status including expired."""

    status_counts = {
        "created": 0,
        "submitted": 0,
        "accepted": 0,
        "filled": 0,
        "expired": 0,  # ← NEW: Track expired count
        "cancelled": 0,
        "failed": 0,
    }

    for order in self.store.get_all_orders():
        status_key = order.current_status.value.lower()
        if status_key in status_counts:
            status_counts[status_key] += 1

    return status_counts
```

#### Step 6: Add Prometheus Metric

**File:** `src/cow_performance/prometheus/metrics.py`

```python
from prometheus_client import Counter

# Add new metric
ORDERS_EXPIRED_TOTAL = Counter(
    'cow_perf_orders_expired_total',
    'Total number of orders that expired during test'
)

# Update in ExpirationChecker when order expires
if metadata.valid_to < current_time:
    metadata.current_status = OrderStatus.EXPIRED
    metadata.expiration_time = time.time()
    ORDERS_EXPIRED_TOTAL.inc()  # ← Increment Prometheus counter
```

### Advantages of This Approach

1. **No external code changes:** Works entirely within our testing suite
2. **Real-time tracking:** Detects expiration within 5 seconds
3. **Complete metrics:** Full expiration data in reports and Prometheus
4. **Lightweight:** Simple background task, minimal overhead
5. **Testable:** Easy to unit test expiration logic

### Limitations

1. **Not instant:** 5-second delay between expiration and detection
2. **Testing only:** Only tracks orders created by our tests
3. **Memory-based:** Expiration state not persisted to external database

### Recommendation

Implement the **Expiration Checker** approach as described above. This gives us complete visibility into order expiration **without requiring any changes to the CoW Protocol services**.

**Rollout:**
1. Implement `ExpirationChecker` class
2. Update `OrderMetadata` to include `valid_to` and `expiration_time`
3. Start checker in test runner
4. Add Prometheus metric
5. Update test reports to show expiration count
6. Test with scenario that has short `valid_to` times

---

## Testing Plan

### Unit Tests

```rust
#[tokio::test]
async fn test_expired_orders_updater() {
    let db = test_database().await;

    // Create order that expired 5 minutes ago
    let order_uid = create_test_order(&db, valid_to: now() - 300).await;

    // Run updater
    let updater = ExpiredOrdersUpdater::new(db.clone());
    updater.update_expired_orders().await.unwrap();

    // Verify expiration_timestamp is set
    let order = db.get_order(&order_uid).await.unwrap();
    assert!(order.expiration_timestamp.is_some());
}
```

### Integration Tests

1. Create orders with various `valid_to` timestamps
2. Wait for background task to run
3. Verify `expiration_timestamp` is set correctly
4. Verify Prometheus counter increments
5. Verify expired orders are excluded from auctions

### Performance Tests

1. Create 100,000 expired orders
2. Measure update query execution time
3. Verify database CPU/memory impact
4. Confirm index usage with `EXPLAIN ANALYZE`

---

## Rollback Plan

If issues arise:

1. **Stop autopilot** to halt background updates
2. **Keep column:** Don't drop `expiration_timestamp` (data is useful)
3. **Status calculation:** Falls back to `valid_to` check automatically
4. **Investigate:** Check logs for errors or performance issues

The migration is **safe** because:
- Column is nullable (no data migration needed)
- Status calculation has fallback logic
- Existing queries unaffected

---

## Metrics to Monitor

After deployment, monitor:

1. **Prometheus:**
   - `orders_expired_total` - Should increment steadily
   - Database query latency - Should remain stable

2. **Database:**
   - `SELECT COUNT(*) FROM orders WHERE expiration_timestamp IS NOT NULL`
   - Index usage: `pg_stat_user_indexes`

3. **Application:**
   - Autopilot task logs - Should show periodic updates
   - Error logs - Should be empty

---

## Future Enhancements

Once expiration tracking is implemented:

1. **Analytics Dashboard:**
   - Orders expired per hour
   - Average time until expiration
   - Expiration rate by token pair

2. **Alerting:**
   - Alert if >X% of orders expire without filling
   - Alert if expiration rate spikes

3. **Optimization:**
   - Adjust default `valid_to` based on expiration data
   - Identify token pairs with high expiration rates

---

## References

**Code Locations:**
- Order creation: `modules/services/crates/orderbook/src/orderbook.rs:270-307`
- Status calculation: `modules/services/crates/orderbook/src/database/orders.rs:493-516`
- Order cancellation: `modules/services/crates/database/src/orders.rs:450-470`
- Auction queries: `modules/services/crates/database/src/orders.rs:719-820`
- Database schema: `modules/services/database/sql/V001__create_orders.sql`

**Related:**
- Order events: `modules/services/crates/database/src/order_events.rs`
- Periodic cleanup: `modules/services/crates/autopilot/src/periodic_db_cleanup.rs`
