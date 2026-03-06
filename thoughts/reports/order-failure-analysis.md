# Order Failure Analysis Report
**Date**: 2026-02-25
**Status**: Initial Analysis
**Purpose**: Determine root causes of order failures and classify as bugs vs. expected behavior

---

## Executive Summary

The performance testing suite generates orders that can fail for **multiple legitimate reasons**. Based on code analysis, most failures are **expected behavior** rather than bugs. However, there are **architectural limitations** that may increase failure rates beyond realistic scenarios.

**Key Findings**:
- ✅ **Expected**: Orders expire after short validity periods (2-5 minutes)
- ✅ **Expected**: Orders fail when market conditions are unfavorable (low liquidity, price movement)
- ✅ **Expected**: Rate limiting causes orders to be skipped
- ⚠️ **Limitation**: No retry logic for transient API failures
- ⚠️ **Limitation**: Short expiration times may not allow sufficient settlement time
- 🔴 **Bug/Incomplete**: Conditional orders (TWAP, Stop-Loss, Good-After-Time) are placeholder implementations

---

## Order Lifecycle and Terminal States

Orders can reach these terminal states:

| State | Meaning | Is This a Failure? |
|-------|---------|-------------------|
| `FILLED` | Order fully executed | ✅ Success |
| `PARTIALLY_FILLED` | Order partially executed | ⚠️ Partial success |
| `EXPIRED` | Validity period ended before settlement | ⚠️ Expected failure (time-based) |
| `CANCELLED` | User-initiated cancellation | ⚠️ Expected (test cleanup) |
| `FAILED` | Submission or processing error | 🔴 Unexpected failure |

**Source**: `src/cow_performance/metrics/models.py:24-35`

---

## Root Causes of Order Failures

### 1. **Order Expiration (EXPIRED) - Expected Behavior** ✅

**What happens**:
- Market orders: 120 seconds (2 minutes) validity
- Limit orders: 300 seconds (5 minutes) validity
- If not filled within validity period, order automatically expires

**Why this is expected**:
- Simulates realistic trading where users set expiration times
- Prevents stale orders from executing at outdated prices
- Tests the system's ability to handle expired orders

**Code reference**: `src/cow_performance/load_generation/order_factory.py:159-160` (market) and `line 219` (limit)

**When this becomes a bug**:
- If >50% of orders are expiring, validity periods may be too short
- If settlement times are consistently longer than validity periods
- If solver is slow to match orders due to performance issues

**Recommendation**: Monitor the `expired` vs `filled` ratio. A healthy system should have <20% expiration rate under normal load.

---

### 2. **Submission Failures (FAILED) - Mixed** ⚠️

**What causes submission failures**:

#### 2a. Network/API Errors (Expected in real-world scenarios)
- Connection timeouts (30-second timeout)
- DNS resolution failures
- Connection refused (service unavailable)
- HTTP 5xx server errors

**Code reference**: `src/cow_performance/api/orderbook_client.py:85-109`

#### 2b. Validation Errors (Expected - caught before submission)
Pre-submission validation catches these errors and prevents submission:
- Invalid Ethereum addresses (non-checksummed)
- Zero/negative amounts
- Same sell/buy tokens
- Invalid timestamps (validTo in past)
- Invalid appData format
- Negative fees

**Code reference**: `src/cow_performance/load_generation/order_validation.py:8-87`

#### 2c. API Rejection (HTTP 4xx errors)
- 400 Bad Request: Invalid order parameters
- 401/403: Authentication/permission errors
- 422 Unprocessable Entity: Server-side validation failure
- 409 Conflict: Order already exists (duplicate)

**Code reference**: `src/cow_performance/api/orderbook_client.py:85-109`

**Architectural Limitation** 🚨:
The suite has **NO retry logic for order submissions** - only for appData uploads. Any transient error (network glitch, temporary server overload) immediately marks the order as FAILED.

**Code reference**: `src/cow_performance/api/instrumented_client.py:119-139` (appData retry) vs. `src/cow_performance/load_generation/trader_simulator.py:353-425` (no order retry)

**Recommendation**:
- **Accept as-is** if testing worst-case scenarios (no retries)
- **Add retry logic** if simulating production client behavior (exponential backoff for transient errors)

---

### 3. **Rate Limiting - Expected Behavior** ✅

**What happens**:
- Token bucket algorithm limits order submission rate
- Per-trader limits: `max_orders_per_trader_per_second` or `per_minute`
- Global limits: `max_orders_global_per_second` or `per_minute`
- When rate-limited, the trader **skips** submission (no error, no retry)

**Code reference**: `src/cow_performance/load_generation/trader_orchestrator.py:280-320` and `src/cow_performance/load_generation/rate_limiter.py`

**Why this is expected**:
- Prevents overwhelming the orderbook API
- Simulates realistic client-side rate limiting
- Tests system behavior under sustained load

**How to detect**:
Check the rate limit metrics:
- `per_trader_hits`: Count of per-trader rate limit violations
- `global_hits`: Count of global rate limit violations

**Recommendation**: Rate limiting is **working as designed**. If you want to maximize order submission, adjust the rate limit configuration in your scenario file.

---

### 4. **Market Conditions - Expected Behavior** ✅

**Why orders may not fill**:
- Insufficient liquidity for the token pair
- Price movement between quote time and submission
- Sell amount too large for available liquidity
- Limit price too far from market price (limit orders)
- Solver unable to find profitable settlement path

**Code reference**: Order creation uses market quotes (`src/cow_performance/load_generation/order_factory.py:141-172`), but market conditions can change before settlement.

**Why this is expected**:
- Realistic simulation of market dynamics
- Tests solver's ability to handle unfillable orders
- Validates orderbook's handling of various market conditions

**When this becomes a bug**:
- If token pairs have zero liquidity (configuration issue)
- If all orders use unsupported token pairs
- If Anvil fork state doesn't have necessary token balances

**Recommendation**:
- Verify token pairs have sufficient liquidity on the forked block
- Check that test accounts have adequate token balances
- Monitor the `filled` vs `expired` ratio per token pair

---

### 5. **Trader Restart Logic - Fault Tolerance** ✅

**What happens**:
- Each trader can be restarted up to 3 times on failure
- 1-second delay between restarts
- Configurable: `restart_on_failure` and `max_restarts_per_trader`

**Code reference**: `src/cow_performance/load_generation/trader_orchestrator.py:383-490`

**Why this is expected**:
- Provides resilience to transient trader failures
- Prevents entire test from failing due to one trader error
- Simulates real-world retry behavior

**Recommendation**: This is **fault tolerance, not a bug**. Disable restarts (`restart_on_failure=False`) if you want to catch trader initialization errors immediately.

---

### 6. **Conditional Orders (TWAP, Stop-Loss, Good-After-Time) - INCOMPLETE** 🔴

**Critical Finding**: Conditional orders are **stub implementations** that do NOT actually submit to the blockchain.

**What the code does**:
- Generates conditional order structures
- Creates temporary UIDs with prefixes (`twap_pending_`, `stoploss_pending_`, `gat_pending_`)
- Marks them as ACCEPTED **without actual on-chain submission**
- No background monitoring (these aren't in the orderbook API)

**Code reference**: `src/cow_performance/load_generation/trader_simulator.py:426-538`

**TODO comments indicate**:
- Need to call `composable_cow.submit_conditional_order()`
- Need to extract order UID from transaction receipt
- Need to implement on-chain event monitoring
- Need to track TWAP part executions over time
- Need to monitor price oracles for Stop-Loss triggers
- Need to monitor block timestamps for Good-After-Time activation

**Impact**:
- Conditional orders will appear as ACCEPTED but never actually execute
- They won't fail, but they won't fill either
- Skews metrics if conditional orders are significant portion of test load

**Recommendation**:
- **Document this limitation** prominently
- **Disable conditional orders** in test scenarios until implementation is complete
- **File a bug** to complete the conditional order implementation

---

## Metrics to Monitor

The suite tracks comprehensive metrics to help you diagnose failures:

### Order Lifecycle Metrics
```python
orders_created: int           # Total orders generated
orders_submitted: int         # Successfully submitted to API
orders_accepted: int          # Accepted by orderbook
orders_filled: int            # Fully executed
orders_partially_filled: int  # Partially executed
orders_expired: int           # Expired before settlement
orders_cancelled: int         # User-cancelled
orders_failed: int            # Submission/processing errors

failure_rate: float           # orders_failed / orders_submitted
```

**Source**: `src/cow_performance/metrics/aggregator.py:74-88`

### API Metrics
- Endpoint, method, duration
- Status codes (201 = success, 4xx/5xx = failure)
- Payload and response sizes
- Error messages

**Source**: `src/cow_performance/api/instrumented_client.py:53-91`

### Rate Limit Metrics
- `per_trader_hits`: Per-trader rate limit violations
- `global_hits`: Global rate limit violations

**Source**: `src/cow_performance/load_generation/trader_orchestrator.py:133-153`

---

## Healthy vs. Unhealthy Failure Patterns

### ✅ Healthy Pattern (Expected)
```
Total Orders:      1000
Submitted:         950   (95% - some skipped by rate limiting)
Accepted:          940   (99% of submitted)
Filled:            750   (80% of accepted)
Expired:           180   (19% of accepted)
Failed:            10    (1% of submitted - transient network errors)

Failure Rate:      1.05%
```

**Interpretation**: System is working as designed. Most orders are filled, some expire naturally, minimal submission failures.

---

### ⚠️ Warning Pattern (Needs Investigation)
```
Total Orders:      1000
Submitted:         950
Accepted:          940
Filled:            300   (32% of accepted)
Expired:           600   (64% of accepted)
Failed:            40    (4.2% of submitted)

Failure Rate:      4.2%
```

**Interpretation**:
- High expiration rate suggests validity periods too short OR solver is slow
- Elevated failure rate suggests API issues or configuration problems
- Investigate: Are orders expiring before solver can match them?

---

### 🔴 Critical Pattern (Likely Bugs)
```
Total Orders:      1000
Submitted:         400   (40% - excessive rate limiting OR generation errors)
Accepted:          200   (50% of submitted - API rejecting orders)
Filled:            50    (25% of accepted)
Failed:            200   (50% of submitted)

Failure Rate:      50%
```

**Interpretation**:
- Very low submission rate: Check rate limits, trader generation, or order factory bugs
- High API rejection rate: Invalid orders passing validation, or API authentication issues
- Low fill rate: Market conditions, liquidity, or solver issues
- **This pattern indicates bugs or serious configuration problems**

---

## Alerting Thresholds (Prometheus)

The suite has built-in alerting rules for order failures:

**Critical**: `order_failure_rate > 0.10` (10%)
**Warning**: `order_failure_rate > 0.05` (5%)

**Source**: `thoughts/plans/2026-02-13-cow-598-alerting-rules.md:208`

These thresholds align with production reliability standards where >90% success rate is acceptable.

---

## Diagnostic Checklist

When investigating order failures, check:

### 1. Configuration
- [ ] Rate limits not too restrictive (`max_orders_per_trader_per_second`)
- [ ] Token pairs have liquidity on forked block
- [ ] Validity periods reasonable (not too short)
- [ ] Sufficient test traders for desired load

### 2. Environment
- [ ] Docker services running (`docker compose ps`)
- [ ] Orderbook API responding (`curl http://localhost:8080/api/v1/version`)
- [ ] Anvil fork healthy (check block number)
- [ ] Solver/Driver services operational

### 3. Logs
- [ ] Check CLI output for errors
- [ ] Check `docker compose logs orderbook` for API errors
- [ ] Check `docker compose logs driver` for solver errors
- [ ] Check Prometheus metrics at `http://localhost:9091/metrics`

### 4. Metrics Analysis
- [ ] Calculate `failure_rate = orders_failed / orders_submitted`
- [ ] Check `expired` vs `filled` ratio
- [ ] Identify token pairs with high failure rates
- [ ] Review API status code distribution

---

## Recommendations

### 1. **Accept as Expected** ✅
- Order expirations (if <30% of orders)
- Rate limiting (if intentionally configured)
- Market condition-based fill failures (if realistic scenarios)
- Occasional network errors (if <5% failure rate)

### 2. **Consider Bug Fixes** ⚠️
- **Add retry logic for transient errors**: Exponential backoff for HTTP 5xx errors, connection timeouts
- **Extend validity periods**: Increase from 2/5 minutes to 10/15 minutes for more realistic settlement windows
- **Improve error reporting**: Capture and categorize API rejection reasons (4xx errors)

### 3. **Must Fix** 🔴
- **Complete conditional order implementation**: Currently non-functional
- **Document limitations**: Clearly state that conditional orders are placeholders
- **Add better diagnostics**: Expose failure reasons in CLI output and reports

---

## Next Steps

1. **Run a test** with verbose logging enabled
2. **Capture metrics** using Prometheus or CLI JSON output
3. **Calculate failure rate**: `orders_failed / orders_submitted`
4. **Compare against thresholds**:
   - <5%: Acceptable
   - 5-10%: Warning (investigate)
   - >10%: Critical (likely bug or misconfiguration)
5. **Review this report** with your metrics to determine if failures are expected

---

## Key Files for Further Investigation

| File | Purpose |
|------|---------|
| `src/cow_performance/load_generation/trader_simulator.py:353-425` | Order submission and error handling |
| `src/cow_performance/load_generation/order_factory.py` | Order generation logic |
| `src/cow_performance/load_generation/order_validation.py` | Pre-submission validation |
| `src/cow_performance/api/orderbook_client.py` | API client with error handling |
| `src/cow_performance/load_generation/order_tracker.py` | Order lifecycle tracking |
| `src/cow_performance/metrics/aggregator.py:197` | Failure rate calculation |
| `src/cow_performance/reporting/recommendations.py:218` | Failure rate alerting thresholds |

---

## Conclusion

**Most order failures are expected behavior** based on:
- Natural order expirations
- Market conditions and liquidity constraints
- Intentional rate limiting
- Realistic network/API variability

**Potential bugs identified**:
1. No retry logic for transient API errors
2. Conditional orders are incomplete stubs
3. Possibly too-short validity periods for realistic settlement

**Recommended action**:
1. Run a performance test and capture metrics
2. Calculate your failure rate
3. If <10%, this is expected behavior
4. If >10%, investigate logs and consider fixes
5. Disable conditional orders until implementation is complete

---

**Report prepared by**: Claude Code Analysis
**Codebase version**: jefferson/cow-598-13-alerting-rules branch
**Last commit**: 721d397 (docs: add implementation plan and notes for COW-598 alerting rules)
