# Integration Validation Report - M5 Issue 17

## Executive Summary

**Date:** 2026-03-16  
**Environment:** Ethereum Mainnet Fork (Chain ID: 1)  
**Status:** PASS WITH RECOMMENDATIONS

All critical services are operational and integrated correctly after chain service recovery. Core end-to-end flow validated, metrics collection working, Prometheus/Grafana monitoring active.

---

## 1. Docker Services Health

### Service Status

| Service | Status | Health | Port(s) | Notes |
|---------|--------|--------|---------|-------|
| chain (Anvil) | Running | Healthy | 8545 | Recovered after restart |
| db (PostgreSQL) | Running | Healthy | 5432 | No issues |
| orderbook | Running | Healthy | 8080, 9586 | /api/v1/version responding |
| autopilot | Running | No HC | 9589 | Metrics available |
| driver | Running | No HC | 9000 | Metrics available |
| solver-baseline-1 | Running | No HC | 9001 | Metrics available |
| solver-baseline-2 | Running | No HC | 9002 | Metrics available |
| solver-baseline-3 | Running | No HC | 9003 | Metrics available |
| watch-tower | Running | No HC | — | Processing conditional orders |
| prometheus | Running | No HC | 9090 | /-/healthy responding |
| grafana | Running | No HC | 3000 | /api/health responding |

**Issues Found:**
1. **CRITICAL (RESOLVED):** Chain service was unhealthy due to stuck Anvil RPC (timeout after 3 days uptime). Required restart to recover.
2. **WARNING:** No healthchecks configured for autopilot, driver, solvers, watch-tower, prometheus, grafana.

### Healthcheck Configuration

**Services WITH healthchecks:**
- `chain`: `cast block-number` + authenticator contract patch
- `db`: `pg_isready`
- `orderbook`: `curl http://localhost:80/api/v1/version`

**Services WITHOUT healthchecks:**
- autopilot, driver, solver-baseline-{1,2,3}, watch-tower, prometheus, grafana

---

## 2. Prometheus Integration

### Scrape Targets Status

| Job Name | Target | Health | Error |
|----------|--------|--------|-------|
| prometheus | prometheus:9090 | UP | — |
| orderbook | orderbook:9586 | UP | — |
| autopilot | autopilot:9589 | UP | — |
| driver | driver:80 | UP | — |
| baseline | baseline:80 | DOWN | DNS lookup failed |
| cow-performance-test | host.docker.internal:9091 | DOWN | Expected (not running) |

**Issues Found:**
1. **CRITICAL:** Baseline solver target misconfigured - targets "baseline:80" which doesn't exist. Should target "solver-baseline-1:80", "solver-baseline-2:80", "solver-baseline-3:80".
2. **INFO:** cow-performance-test exporter not running (expected - only active during tests).

### Metrics Collection

**Total CoW Protocol metrics scraped:** 155 metrics across:
- `driver_*` (30+ metrics)
- `gp_v2_api_*` (orderbook metrics)
- `gp_v2_autopilot_*` (autopilot metrics)
- `solver_engine_*` (solver metrics - accessible via direct endpoint check)

**Sample Metrics Verified:**
```
gp_v2_api_alloy_rpc_requests_complete{method="eth_call"} - Working
gp_v2_autopilot_alloy_rpc_requests_complete{method="eth_call"} - Working
driver_liquidity_enabled - Working
driver_auction_overhead_count - Working
```

### Alert Rules

**Status:** 7 alert rules loaded in 1 group (cow_performance_testing)

**Alert types:**
- Latency alerts (submission latency warning/critical)
- Error rate alerts
- Throughput alerts
- Resource usage alerts (CPU, memory)
- Test stalled detection

---

## 3. Order Flow End-to-End

### Orderbook API

- **Version endpoint:** ✓ Responding
- **Auction endpoint:** ✓ Responding (currently 0 orders, prices available)
- **Orders endpoint:** ✓ Available (HTTP method validation working)

### Current Auction State

```json
{
  "id": 12255,
  "block": 24671623,
  "orders": [],
  "prices": {
    "USDC": "432138331697646574023737344",
    "WETH": "1000000000000000000"
  },
  "surplusCapturingJitOrderOwners": []
}
```

### Watch-Tower (Conditional Orders)

**Status:** ✓ Operational

- Processing 491 conditional orders across 24 owners
- TWAP order validation working
- Stop-loss order detection working
- Expired order cleanup working

**Sample activity:**
```
Processing order 492/492 with ID 0x41be1b75...
Check result: DONT_TRY_AGAIN - TWAP has expired
Stop Watching conditional order 0x41be1b75...
```

### Settlement Flow

**Not tested in this validation** - No orders were submitted during validation. Integration tests cover order submission/tracking logic (87 tests passed).

---

## 4. External Service Integrations

### Blockchain (Anvil Fork)

- **RPC URL:** http://eth.rpc.ts.bleu.builders
- **Anvil endpoint:** http://localhost:8545
- **Chain ID:** 1 (Mainnet)
- **Current block:** 24671623
- **Fork mode:** Latest block (no ETH_BLOCKNUMBER specified)
- **Status:** ✓ Working after restart

**Upstream RPC test:**
```bash
curl http://eth.rpc.ts.bleu.builders -> Block: 0x178756a (Working)
```

### Database (PostgreSQL)

- **Host:** localhost:5432
- **Health:** ✓ `pg_isready` passing
- **Migrations:** ✓ Completed successfully

### Monitoring Stack

#### Prometheus
- **Endpoint:** http://localhost:9090
- **Health:** ✓ Healthy
- **Scrape interval:** 5s
- **Data retention:** 7 days / 1GB
- **Alert evaluation:** 5s

#### Grafana
- **Endpoint:** http://localhost:3000
- **Health:** ✓ Healthy (version 12.4.1)
- **Datasource:** Prometheus configured (proxy, POST method, 5s interval)
- **Default dashboard:** /etc/grafana/dashboards/performance.json
- **Anonymous access:** Enabled (Admin role)

---

## 5. Fork Mode Behavior

### Anvil Configuration

```bash
anvil \
  --fork-url http://eth.rpc.ts.bleu.builders \
  --host 0.0.0.0 \
  --port 8545 \
  --chain-id 1 \
  --block-time 1 \
  --gas-limit 30000000 \
  --code-size-limit 50000 \
  --accounts 10 \
  --balance 10000 \
  --prune-history \
  --silent
```

**Key features:**
- Forking from latest mainnet block (no fixed block number)
- 1 second block time
- 30M gas limit
- Prune history (no disk accumulation)
- 10 pre-funded accounts with 10000 ETH each

### Healthcheck Behavior

**Chain healthcheck includes:**
1. Block number check: `cast block-number`
2. Authenticator contract patch: `anvil_setCode 0x2c4c28DDBdAc9C5E7055b4C863b72eA0149D8aFE 0x600160005260206000F3`

This ensures solver authentication is bypassed in test mode.

---

## 6. Integration Gaps Identified

### Missing Health Checks

**High Priority:**
- autopilot (no healthcheck - should check metrics endpoint)
- driver (no healthcheck - should check metrics endpoint or /quote endpoint)
- prometheus (no healthcheck - should check /-/healthy)
- grafana (no healthcheck - should check /api/health)

**Medium Priority:**
- solver-baseline-{1,2,3} (no healthcheck - could check /metrics or solve endpoint)
- watch-tower (no healthcheck - could check metrics or registry state)

### Missing Metrics

**Prometheus config issues:**
- Baseline solver target points to non-existent "baseline:80" service
- Should have separate targets for each solver instance with proper labels

**Recommended scrape config:**
```yaml
- job_name: "solver-baseline"
  metrics_path: /metrics
  static_configs:
    - targets:
        - "solver-baseline-1:80"
        - "solver-baseline-2:80"
        - "solver-baseline-3:80"
      labels:
        service: "solver"
        component: "baseline"
```

### Order Submission Gap

**No E2E order submission tested** in this validation:
- Orderbook API is healthy
- Auction endpoint working
- But no actual orders submitted/fulfilled
- Integration tests cover this logic (all 87 passed)

**Recommendation:** Run E2E test scenario to verify:
1. Order submission to orderbook
2. Auction creation by autopilot
3. Solution generation by solvers
4. Settlement transaction submission

---

## 7. Error Recovery Mechanisms

### Chain Service Recovery

**Issue:** Anvil RPC became unresponsive after 3 days uptime  
**Symptom:** Connection timeout on all RPC calls  
**Recovery:** `docker compose restart chain` - successful  
**Time to recovery:** ~10 seconds  

**Services dependent on chain:**
- orderbook (crashed until chain recovered)
- autopilot (continued running, logged timeouts)
- driver (continued running, logged timeouts)

**Restart cascade behavior:**
```
chain restart → orderbook auto-recovered (depends_on: chain)
              → autopilot auto-recovered (depends_on: chain)
              → driver auto-recovered (depends_on: chain)
```

### Service Restart Policies

All services configured with `restart: always` (except db-migrations: `restart: on-failure`)

### Dependency Graph Validation

```
db ─┬─→ db-migrations (completed successfully)
    └─→ orderbook ─→ autopilot
                  └─→ watch-tower

chain ─┬─→ orderbook ─→ autopilot
       ├─→ autopilot
       ├─→ driver
       ├─→ solver-baseline-{1,2,3}
       └─→ watch-tower
```

**All dependencies validated:** ✓

---

## 8. Integration Test Results

**Test suite:** `tests/integration/`  
**Total tests:** 87  
**Passed:** 87  
**Failed:** 0  
**Coverage:** 69% (src/cow_performance/)

**Key test categories:**
- CLI integration (14 tests) ✓
- Comparison engine (4 tests) ✓
- Conditional orders (11 tests) ✓
- Metrics collection (7 tests) ✓
- Order generation (12 tests) ✓
- Prometheus integration (4 tests) ✓
- Reporting (12 tests) ✓
- User simulation (9 tests) ✓
- Wallet funding (7 tests) ✓

---

## 9. Recommendations

### High Priority

1. **Fix Prometheus solver scrape config** - Replace "baseline:80" with individual solver targets
2. **Add healthchecks for critical services:**
   - autopilot: `curl -f http://localhost:9589/metrics`
   - driver: `curl -f http://localhost:80/metrics`
   - prometheus: `curl -f http://localhost:9090/-/healthy`
   - grafana: `curl -f http://localhost:3000/api/health`

3. **Implement Anvil restart monitoring** - Chain service showed instability after 3 days uptime. Consider:
   - Scheduled restarts every 24h
   - Memory usage monitoring (was at 3.2GB before failure)
   - RPC timeout detection in healthcheck

### Medium Priority

4. **Add solver healthchecks** - Check `/metrics` endpoint availability
5. **Add watch-tower healthcheck** - Verify registry processing
6. **Add E2E validation test** - Automated test that:
   - Funds a wallet
   - Submits an order
   - Verifies order appears in auction
   - Checks solver solutions
   - Validates settlement (or timeout)

7. **Configure Prometheus recording rules** - Pre-compute common queries for dashboard performance
8. **Add alerting for service health** - Alert when Prometheus targets go down

### Low Priority

9. **Document recovery procedures** - Formalize "what to do when X fails"
10. **Add Grafana dashboard screenshots** to docs
11. **Implement automated smoke tests** on `docker compose up`

---

## 10. Verdict

**PASS WITH RECOMMENDATIONS**

### What's Working

✓ All Docker services operational (after chain recovery)  
✓ Prometheus scraping 4/6 targets successfully  
✓ Grafana connected to Prometheus  
✓ Alert rules loaded (7 rules)  
✓ Orderbook API responding  
✓ Watch-tower processing conditional orders  
✓ All integration tests passing (87/87)  
✓ Metrics collection functioning  
✓ Chain fork mode operational  

### What Needs Attention

⚠ Prometheus solver target misconfigured (1 target)  
⚠ 6 services missing healthchecks  
⚠ Chain service required restart after 3 days  
⚠ No E2E order settlement validated  

### Next Steps

1. Fix Prometheus config for solver targets
2. Add missing healthchecks
3. Run E2E scenario test to validate full order flow
4. Monitor Anvil stability over longer periods
5. Document recovery procedures

---

## Appendix: Validation Commands

### Service Health
```bash
docker compose ps
curl http://localhost:8545 -X POST -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
curl http://localhost:8080/api/v1/version
curl http://localhost:9090/-/healthy
curl http://localhost:3000/api/health
```

### Metrics Verification
```bash
curl http://localhost:9586/metrics | grep gp_v2_api
curl http://localhost:9589/metrics | grep gp_v2_autopilot
curl http://localhost:9000/metrics | grep driver_
curl http://localhost:9001/metrics | grep solver_
```

### Prometheus Targets
```bash
curl http://localhost:9090/api/v1/targets
curl 'http://localhost:9090/api/v1/query?query=up'
curl 'http://localhost:9090/api/v1/label/__name__/values'
```

### Integration Tests
```bash
.venv/bin/pytest tests/integration/ -v
```
