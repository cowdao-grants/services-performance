# Issue: Event Sync Failure in Anvil Fork Mode Causes Inaccurate Fill Rate Metrics

**Status:** ✅ RESOLVED (Phase 1 & 2 Complete)
**Priority:** High
**Created:** 2026-03-16
**Updated:** 2026-03-16
**Resolved:** 2026-03-16
**Labels:** bug, metrics, anvil, event-sync, resolved

## Problem Statement

Settlements execute successfully on-chain in Anvil fork mode (75% fill rate), but the database shows 0% because event synchronization is broken. This creates a critical discrepancy between actual performance and measured performance.

## Root Causes

### 1. Anvil Lacks `debug_traceTransaction` Support
- **Issue:** Anvil (Foundry's local node) doesn't implement `debug_traceTransaction` RPC method
- **Impact:** Autopilot cannot post-process settlements to extract trade data
- **Evidence:** No trades appear in database despite successful on-chain settlements
- **Limitation:** This is a fundamental Anvil limitation, not a CoW Protocol bug

### 2. Autopilot Event Post-Processing Failure
- **Issue:** Autopilot relies on `debug_traceTransaction` to extract settlement events
- **Impact:** Successfully submitted settlements are never indexed
- **Evidence:** Autopilot logs show "settlement failed err=Timeout" even for successful txs
- **Current Behavior:** Autopilot submits tx → waits for confirmation → times out → never indexes

### 3. Orderbook Order Status Not Updated
- **Issue:** Orders remain marked as "open" in database despite being filled on-chain
- **Impact:**
  - Fill rate metrics show 0% instead of actual 75%
  - Stale "unfilled" orders pollute subsequent auctions
  - Causes "no solutions" errors as solvers attempt to fill already-filled orders
- **Evidence:** Database query shows 0 trades, on-chain query shows 6 Trade events

### 4. Metrics Collection Relies on Database State
- **Issue:** Performance metrics read from database, not from chain
- **Impact:** All fill rate, settlement rate, and order status metrics are inaccurate
- **Current State:**
  - Database: 0 trades, 8 open orders
  - On-chain: 6 trades, 2 unfilled orders
  - Discrepancy: 100%

## Evidence

### Database State
```sql
SELECT COUNT(*) FROM trades;
-- Result: 0

SELECT COUNT(*), signing_scheme FROM orders GROUP BY signing_scheme;
-- Result: 8 EIP-712 orders, all status=open
```

### On-Chain State
```bash
cast logs --from-block 24673430 --to-block 24673700 \
  "Trade(address indexed,address,address,uint256,uint256,uint256,bytes)" \
  --rpc-url http://localhost:8545 | grep -c "transactionHash"
# Result: 6
```

### Settlement Transactions (All Successful)
1. `0x371b829f5b04e489f241ee124ab7d1094ed5f2a288a6abc50d47a39643b93aa0` - status: success
2. `0x11fb4b797d2843e5145035463c7f75941300e6852437db47474552e5109f323f` - status: success
3. `0x53097c93200cfb6c4a90d11ea57406c2565d27d18e48db0473f631a3063abd64` - status: success
4. `0xdd5c5a0ca812555ebee05d8a5635d81a32987355ab83ae887b7e0610f6b22d56` - status: success
5. `0x9854e5a73d2566dcf3ef7b2118ba14bad2e3525c2b931e372c950206e561e590` - status: success
6. `0xb77fd4a1d29007ef2bdaa2118790f783be3324f83aef42a2637b90772bc5e8b9` - status: success

### Autopilot Logs (Misleading)
```
autopilot | settlement failed err=Timeout driver=solver-baseline-2
```
**Reality:** Settlement transaction was submitted, mined, and succeeded. Autopilot just couldn't detect it.

## Impact Assessment

### Critical Issues
1. **Inaccurate Metrics:** Cannot measure actual performance in fork mode testing
2. **False Negatives:** 75% fill rate appears as 0%
3. **Stale Order Pollution:** Filled orders remain "open", blocking subsequent auctions
4. **Development Velocity:** Cannot validate fixes without accurate metrics

### Business Impact
- Performance testing suite cannot fulfill its primary function in fork mode
- Regression detection impossible (can't distinguish 0% from 75%)
- Baseline establishment blocked

## Proposed Solutions

### Solution 1: Direct Chain Indexing (Recommended)
**Approach:** Implement a lightweight event indexer that polls the chain directly for Trade events

**Implementation:**
1. Add post-test chain scraping utility
2. Query settlement contract for Trade events in test block range
3. Match Trade events to submitted order UIDs
4. Update order and trade tables with on-chain data
5. Recalculate metrics from corrected database state

**Pros:**
- Works with Anvil's limitations
- Accurate metrics
- Can be run post-test or in real-time

**Cons:**
- Adds latency to metrics reporting
- Requires custom indexing code

**Effort:** Medium (1-2 days)

### Solution 2: Mempool Tracking + Receipt Polling
**Approach:** Track submitted settlements and poll for receipts, parsing events directly

**Implementation:**
1. When driver submits settlement, store tx hash + order UIDs
2. Poll for transaction receipt
3. Parse Trade events from receipt logs
4. Update database with trade data

**Pros:**
- Real-time event detection
- No reliance on `debug_traceTransaction`

**Cons:**
- Requires driver modifications
- More complex than solution 1

**Effort:** High (3-4 days)

### Solution 3: Alternative Node (Hardhat/Ganache)
**Approach:** Switch from Anvil to a node that supports `debug_traceTransaction`

**Pros:**
- No code changes needed
- Existing event sync works as-is

**Cons:**
- May have different fork behavior
- Performance differences
- Requires testing with different node

**Effort:** Low (configuration change) but risky

### Solution 4: Hybrid Approach (Recommended for MVP)
**Approach:** Add post-test reconciliation script that compares chain state to database

**Implementation:**
1. Test runs normally (metrics show 0%)
2. Post-test script queries chain for Trade events
3. Script outputs true fill rate and comparison
4. Database remains unchanged (services continue with existing behavior)

**Pros:**
- Minimal changes to existing code
- Quick to implement
- Validates metrics without breaking services
- Can be enhanced later to update database

**Cons:**
- Metrics not updated in real-time
- Two sources of truth (chain + database)

**Effort:** Low (4-6 hours)

## Recommended Action Plan

### Phase 1: Immediate Fix (Solution 4) - COMPLETE
1. ✅ Create `src/cow_performance/utils/chain_reconciliation.py`
2. ✅ Implement Trade event scraper
3. ✅ Add `--reconcile` flag to test runner
4. ✅ Output comparison report at end of test
5. ✅ Update documentation with known limitation
6. ✅ Update Prometheus metrics with accurate on-chain data

**Timeline:** 1 day (Completed: 2026-03-16)

**Implementation Details:**
- Chain reconciliation utility queries blockchain directly for Trade events
- Parses settlement contract logs to extract order UIDs and match with submitted orders
- Generates detailed reconciliation report comparing database vs on-chain state
- Updates Prometheus/Grafana metrics with accurate fill rates using `update_from_reconciliation()`
- Grafana dashboards now show correct metrics when `--reconcile` flag is used

### Phase 2: Database Updates (Solution 1) - COMPLETE
1. ✅ Added PostgreSQL connectivity via psycopg2
2. ✅ Implemented `update_database()` method in ChainReconciliator
3. ✅ Database connection via environment variables
4. ✅ Inserts trade records from on-chain events
5. ✅ Updates order statuses (orders with trades → FILLED)
6. ✅ Integrated into CLI `--reconcile` flow

**Timeline:** 1 day (Completed: 2026-03-16)

**Implementation Details:**
- Database updates are now part of the `--reconcile` process
- Trade records are inserted with (block_number, log_index, order_uid, amounts)
- Orders are marked as FILLED by the presence of trade records (CoW Protocol convention)
- Prevents stale order pollution in subsequent auctions
- Uses `ON CONFLICT DO NOTHING` to handle duplicate inserts gracefully
- Connection parameters from environment: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB

## Acceptance Criteria

### Phase 1 (COMPLETE)
- [x] Script can query chain for Trade events
- [x] Script matches events to order UIDs
- [x] Script outputs accurate fill rate (75% in test case)
- [x] Script runs automatically with `--reconcile` flag
- [x] Documentation explains discrepancy and workaround
- [x] Prometheus metrics updated with accurate on-chain data (Grafana shows correct fill rates)

### Phase 2 (COMPLETE)
- [x] Database trades table populated with on-chain data
- [x] Order statuses correctly reflect on-chain state (via trade records)
- [x] Metrics calculations use accurate data
- [x] No stale order pollution in subsequent auctions
- [ ] Integration tests validate event sync (deferred)

## Related Issues

- Fixed SUBMISSION_DEADLINE issue (was 5, now 30 blocks)
- Stale order pollution from previous sessions
- BlockOutOfRangeError with Anvil pruning

## Files to Modify

### Phase 1
- Create: `src/cow_performance/utils/chain_reconciliation.py`
- Modify: `src/cow_performance/cli/run.py` (add --reconcile flag)
- Update: `README.md` (document limitation)

### Phase 2
- Create: `src/cow_performance/indexer/event_indexer.py`
- Modify: `src/cow_performance/orchestrator.py` (integrate indexer)
- Modify: `src/cow_performance/metrics/collector.py` (use chain data)

## References

- Investigation document: `thoughts/fork-mode-fill-rate-investigation.md`
- Test logs: `/tmp/post-fixes-test.log`
- Anvil limitations: https://github.com/foundry-rs/foundry/issues
- CoW Protocol settlement contract: `0x9008D19f58AAbD9eD0D60971565AA8510560ab41`
