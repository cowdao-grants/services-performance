# Orderbook Event Sync Issue - Root Cause Analysis

**Date**: 2026-03-16
**Issue**: Orders not being filled during performance tests
**Status**: ROOT CAUSE IDENTIFIED

---

## Summary

Orders are being submitted successfully to the orderbook and solvers are computing valid solutions, but only 1 out of 14-20 orders actually gets filled. The remaining orders stay in "open" status indefinitely.

---

## Investigation Findings

### 1. End-to-End Flow Verification

**Wallets**: ✅ Successfully funded with ETH and tokens via Anvil fork
**Order Submission**: ✅ 14 orders created and submitted (100% API success rate)
**Order Acceptance**: ✅ All orders accepted by orderbook ([submitted → accepted])
**Order Filling**: ❌ Only 1/14 filled (7% fill rate)

### 2. Solver Activity Analysis

Checked driver logs for auction ID 13160:

```
driver-1  | INFO computed solutions solutions=[Solution { ... }]
driver-1  | INFO discarded solution: settlement encoding
           err=Simulation(Revert(RevertError {
             message: "execution reverted: GPv2: order filled"
           }))
driver-1  | DEBUG no solution found
```

**Key findings:**
- ✅ Solvers ARE generating valid solutions
- ✅ Solutions include proper liquidity from UniswapV2 pools
- ❌ When simulating on-chain, transaction reverts: **"GPv2: order filled"**
- ❌ Driver correctly discards solution and reports "no solution" to autopilot

### 3. Autopilot Auction Pattern

```
autopilot-1  | INFO solving auction_id=13160 auction_orders=33
autopilot-1  | INFO no solutions for auction

autopilot-1  | INFO solving auction_id=13161 auction_orders=33
autopilot-1  | INFO no solutions for auction

autopilot-1  | INFO solving auction_id=13162 auction_orders=33
autopilot-1  | INFO no solutions for auction
```

**Pattern:**
- Autopilot runs auctions every 5 seconds
- Each auction contains 33 orders
- Every auction results in "no solutions"
- Same 33 orders appear in multiple consecutive auctions

### 4. Root Cause: Event Sync Disabled

From `docker-compose.yml` autopilot configuration:

```yaml
environment:
  - SKIP_EVENT_SYNC=true  # ← This is the problem
```

**Impact:**
- Orderbook does not listen for on-chain settlement events
- When an order is filled on-chain, the orderbook database is NOT updated
- Filled orders remain in "open" status in the database
- These already-filled orders continue being included in new auctions
- Solvers compute solutions, but simulations fail with "order filled" error
- Driver discards all solutions
- Autopilot gets no valid solutions to settle

---

## Why Only 1 Order Fills

The first time an order appears in an auction:
1. Solver computes a valid solution
2. Simulation succeeds (order not yet filled)
3. Driver accepts the solution
4. Autopilot settles the transaction on-chain
5. Order is filled ✅

For subsequent auctions with the same order:
1. Order is still marked "open" in orderbook DB (no event sync)
2. Autopilot includes it in the auction again
3. Solver computes a solution
4. Simulation fails: "GPv2: order filled" (already filled on-chain)
5. Driver discards the solution
6. No valid solutions → no settlement

---

## Evidence Chain

1. **Test run created 14 orders** → `/tmp/cow-perf-orderbook-test.log`
2. **1 order filled on-chain** → Confirmed in test results: `"orders_filled": 1`
3. **Same 33 orders in every auction** → Autopilot logs show consistent count
4. **Solutions rejected due to "order filled"** → Driver logs show simulation errors
5. **Event sync is disabled** → `SKIP_EVENT_SYNC=true` in docker-compose.yml

---

## Solution

### Option 1: Enable Event Sync (Recommended)

Remove or set `SKIP_EVENT_SYNC=false` in autopilot configuration:

```yaml
autopilot:
  environment:
    # Remove this line or set to false:
    # - SKIP_EVENT_SYNC=true
```

This allows the orderbook to:
- Listen for `Trade` events from the settlement contract
- Update order status from "open" to "filled" in real-time
- Exclude filled orders from future auctions

### Option 2: Manual DB Cleanup (Workaround)

Run a script to manually update order statuses in the database:

```sql
UPDATE orders
SET status = 'filled'
WHERE uid IN (
  SELECT order_uid FROM trades WHERE block_number > 0
);
```

---

## Expected Behavior After Fix

With event sync enabled:

1. Order submitted → status: open
2. Order included in auction
3. Solver finds solution
4. Autopilot settles on-chain → order filled
5. **Settlement event emitted**
6. **Orderbook updates status: filled**
7. Order NO LONGER appears in future auctions
8. New orders can be solved without conflicts

Fill rate should improve from 7% to >>90% (accounting for legitimate unsolvable orders due to liquidity constraints).

---

## Related Files

- **Configuration**: `docker-compose.yml` (autopilot environment)
- **Test logs**: `/tmp/cow-perf-orderbook-test.log`
- **Driver logs**: Docker logs showing simulation rejections
- **Autopilot logs**: Docker logs showing auction patterns

---

## Next Steps

1. **Fix configuration**: Remove `SKIP_EVENT_SYNC=true` from docker-compose.yml
2. **Restart services**: `docker compose down && docker compose up -d`
3. **Clear old orders**: Optional - clean database of filled orders
4. **Re-run test**: Verify fill rate improves to >90%
5. **Update validation report**: Document resolution in M5 Issue 17

---

**Report Generated**: 2026-03-16
**Author**: Claude Sonnet 4.5
**Investigation Time**: ~30 minutes
**Validation**: M5 Issue 17 - End-to-End Order Fulfillment
