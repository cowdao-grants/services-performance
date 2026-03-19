# M5 Issue 17: Action Items for Critical Fixes

**Created**: 2026-03-16
**Status**: READY FOR IMPLEMENTATION
**Related Ticket**: `thoughts/tickets/m5-issue-17-e2e-validation.md`
**Validation Report**: `thoughts/validation/m5-issue-17-comprehensive-validation.md`

---

## Overview

This document outlines actionable fixes for issues discovered during M5 Issue 17 validation. Issues are prioritized by severity and impact on production readiness.

**Total Estimated Effort**:
- Critical fixes (production blockers): 4-6 hours
- High priority (reliability): 9-13 hours
- Medium priority (quality): 4-6 days

---

## Critical Fixes (Production Blockers)

### Action Item 1: Fix Scenario Schema Mismatch
**Priority**: 🚨 CRITICAL
**Estimated Effort**: 1-2 hours
**Assignee**: TBD
**Blocks**: Production deployment, scenario validation, baseline creation

#### Problem
All 9 predefined scenarios in `configs/scenarios/predefined/` fail validation:
- Missing required `name` field
- Using extended `trading_pattern` values not recognized by validator

#### Affected Files
```
configs/scenarios/predefined/quick-test.yml
configs/scenarios/predefined/light-load.yml
configs/scenarios/predefined/medium-load.yml
configs/scenarios/predefined/heavy-load.yml
configs/scenarios/predefined/spike-stress-test.yml
configs/scenarios/predefined/ramp-up-load-test.yml
configs/scenarios/predefined/ramp-down-cooldown.yml
configs/scenarios/predefined/exponential-ramp-stress.yml
configs/scenarios/predefined/poisson-realistic-traffic.yml
```

#### Current Error
```bash
$ cow-perf scenarios --validate configs/scenarios/predefined/quick-test.yml
ERROR: 1 validation error for ScenarioConfig
name
  Field required [type=missing, input_value={...}, input_type=dict]
```

#### Implementation Steps

1. **Add `name` field to all predefined scenarios** (30 minutes)

   For each file in `configs/scenarios/predefined/*.yml`:
   ```yaml
   # Add at the top of each scenario file
   name: "Quick Test Scenario"  # or appropriate name
   ```

   Recommended names:
   - `quick-test.yml` → `"Quick Test Scenario"`
   - `light-load.yml` → `"Light Load Test"`
   - `medium-load.yml` → `"Medium Load Test"`
   - `heavy-load.yml` → `"Heavy Load Test"`
   - `spike-stress-test.yml` → `"Spike Stress Test"`
   - `ramp-up-load-test.yml` → `"Ramp-Up Load Test"`
   - `ramp-down-cooldown.yml` → `"Ramp-Down Cooldown"`
   - `exponential-ramp-stress.yml` → `"Exponential Ramp Stress Test"`
   - `poisson-realistic-traffic.yml` → `"Poisson Realistic Traffic"`

2. **Update `ScenarioConfig` validator** (30 minutes)

   File: `src/cow_performance/scenarios/schema.py` (or wherever `ScenarioConfig` is defined)

   Find the `trading_pattern` field validator and update allowed values:
   ```python
   # Current (assumed):
   allowed_patterns = ["constant_rate", "burst", "random_interval"]

   # Update to:
   allowed_patterns = [
       "constant_rate",
       "burst",
       "random_interval",
       "poisson",
       "spike",
       "ramp_up",
       "ramp_down",
       "exponential_ramp"
   ]
   ```

3. **Validate all predefined scenarios** (15 minutes)

   Test each scenario individually:
   ```bash
   for scenario in configs/scenarios/predefined/*.yml; do
       echo "Validating: $scenario"
       cow-perf scenarios --validate "$scenario" || echo "FAILED: $scenario"
   done
   ```

   Expected: All scenarios pass validation

4. **Add regression test** (15 minutes)

   File: `tests/integration/test_scenarios.py` (or create if doesn't exist)

   ```python
   import pytest
   from pathlib import Path

   @pytest.mark.parametrize("scenario_file", [
       "quick-test.yml",
       "light-load.yml",
       "medium-load.yml",
       "heavy-load.yml",
       "spike-stress-test.yml",
       "ramp-up-load-test.yml",
       "ramp-down-cooldown.yml",
       "exponential-ramp-stress.yml",
       "poisson-realistic-traffic.yml",
   ])
   def test_predefined_scenario_validation(scenario_file):
       """All predefined scenarios should pass validation."""
       from cow_performance.scenarios.schema import ScenarioConfig
       import yaml

       scenario_path = Path("configs/scenarios/predefined") / scenario_file
       with open(scenario_path) as f:
           scenario_data = yaml.safe_load(f)

       # Should not raise ValidationError
       config = ScenarioConfig(**scenario_data)
       assert config.name  # Ensure name is present
       assert config.trading_pattern in [
           "constant_rate", "burst", "random_interval",
           "poisson", "spike", "ramp_up", "ramp_down", "exponential_ramp"
       ]
   ```

5. **Run tests** (10 minutes)
   ```bash
   poetry run pytest tests/integration/test_scenarios.py -v
   poetry run pytest  # Full suite
   ```

#### Verification Checklist
- [ ] All 9 predefined scenarios have `name` field
- [ ] Validator accepts all trading pattern values used in predefined scenarios
- [ ] `cow-perf scenarios --validate` passes for all predefined scenarios
- [ ] Regression test added and passing
- [ ] Full test suite passes
- [ ] Documentation updated (if needed)

#### Success Criteria
- All predefined scenarios pass validation
- Users can use `cow-perf run` with predefined scenarios
- No validation errors when listing scenarios

---

### Action Item 2: Fix Prometheus Solver Scrape Configuration
**Priority**: 🚨 CRITICAL
**Estimated Effort**: 15 minutes
**Assignee**: TBD
**Blocks**: Solver metrics collection, performance validation

#### Problem
Prometheus configured to scrape non-existent target `baseline:80`, but actual solver services are `solver-baseline-1:80`, `solver-baseline-2:80`, `solver-baseline-3:80`. Result: Solver metrics not being collected.

#### Current Configuration
File: `configs/prometheus.yml`

```yaml
scrape_configs:
  - job_name: 'baseline'
    static_configs:
      - targets: ['baseline:80']  # ❌ This service doesn't exist
```

#### Implementation Steps

1. **Update Prometheus configuration** (5 minutes)

   File: `configs/prometheus.yml`

   Find and replace the solver scrape config:
   ```yaml
   scrape_configs:
     # ... other jobs ...

     - job_name: 'solvers'
       static_configs:
         - targets:
           - 'solver-baseline-1:80'
           - 'solver-baseline-2:80'
           - 'solver-baseline-3:80'
       scrape_interval: 15s
       scrape_timeout: 10s
   ```

2. **Restart Prometheus** (2 minutes)
   ```bash
   docker compose restart prometheus
   ```

3. **Verify scrape targets** (3 minutes)

   Open browser: http://localhost:9090/targets

   Expected:
   - All 3 solver targets show as "UP"
   - Last scrape successful
   - No errors

4. **Validate metrics are collected** (5 minutes)

   Open Prometheus: http://localhost:9090/graph

   Query: `up{job="solvers"}`

   Expected: 3 results (one per solver)

   Query solver-specific metrics (examples):
   - `solver_request_duration_seconds`
   - `solver_orders_processed_total`
   - `solver_errors_total`

   Expected: Metrics appear with solver labels

#### Verification Checklist
- [ ] Prometheus config updated with correct solver targets
- [ ] Prometheus restarted successfully
- [ ] All 3 solver targets show as "UP" in Prometheus UI
- [ ] Solver metrics queryable in Prometheus
- [ ] Grafana dashboards display solver metrics (if applicable)

#### Success Criteria
- Solver metrics visible in Prometheus
- No scrape errors for solver targets
- Solver performance can be monitored and validated

---

### Action Item 3: Fix E2E Test Isolation Issue
**Priority**: 🚨 CRITICAL
**Estimated Effort**: 2-4 hours
**Assignee**: TBD
**Blocks**: CI/CD reliability, test suite stability

#### Problem
`tests/e2e/test_cli_run.py::TestCLIRun::test_cli_run_with_results_save` fails when run in full E2E suite but passes when run individually. Root cause: Test isolation issue (shared state or improper cleanup).

#### Current Behavior
```bash
# Fails in full suite
$ poetry run pytest tests/e2e/
FAILED tests/e2e/test_cli_run.py::TestCLIRun::test_cli_run_with_results_save

# Passes individually
$ poetry run pytest tests/e2e/test_cli_run.py::TestCLIRun::test_cli_run_with_results_save
PASSED
```

#### Investigation Steps (1 hour)

1. **Identify shared resources**

   Review test file: `tests/e2e/test_cli_run.py`

   Look for:
   - Temporary file paths (check for hardcoded names)
   - Shared fixtures without proper scope
   - Global state modifications
   - Background processes not cleaned up
   - File system state pollution

2. **Check for resource leaks**

   Add debugging to test:
   ```python
   import pytest
   import os
   import tempfile

   @pytest.fixture(autouse=True, scope="function")
   def debug_test_isolation(request):
       """Debug fixture to identify isolation issues."""
       test_name = request.node.name
       print(f"\n=== Starting test: {test_name} ===")
       print(f"Temp dir: {tempfile.gettempdir()}")
       print(f"Files in temp: {os.listdir(tempfile.gettempdir())}")

       yield

       print(f"\n=== Ending test: {test_name} ===")
       print(f"Files in temp: {os.listdir(tempfile.gettempdir())}")
   ```

   Run tests and compare output.

3. **Run tests with different orderings**
   ```bash
   # Test with random order
   poetry run pytest tests/e2e/ --random-order

   # Test in reverse order
   poetry run pytest tests/e2e/ --reverse
   ```

   Identify which tests cause the failure when run before the failing test.

#### Implementation Steps (1-3 hours)

**Option A: If issue is temporary file collisions**

1. Add unique identifiers to temp files:
   ```python
   import uuid
   import tempfile
   from pathlib import Path

   def test_cli_run_with_results_save(self, tmp_path):
       """Use pytest's tmp_path fixture for unique temp directories."""
       test_id = uuid.uuid4().hex[:8]
       results_file = tmp_path / f"results_{test_id}.json"

       # Use results_file instead of hardcoded path
       # ...
   ```

2. Ensure cleanup:
   ```python
   @pytest.fixture
   def cleanup_results():
       yield
       # Clean up any leftover files
       for f in Path(tempfile.gettempdir()).glob("results_*.json"):
           f.unlink()
   ```

**Option B: If issue is shared fixtures**

1. Review fixture scopes:
   ```python
   # Change from:
   @pytest.fixture(scope="module")
   def shared_fixture():
       # ...

   # To:
   @pytest.fixture(scope="function")
   def shared_fixture():
       # ...
   ```

2. Add proper cleanup to fixtures:
   ```python
   @pytest.fixture
   def resource():
       r = create_resource()
       yield r
       r.cleanup()  # Ensure cleanup happens
   ```

**Option C: If issue is background processes**

1. Track all spawned processes:
   ```python
   import subprocess

   @pytest.fixture
   def process_tracker():
       processes = []

       def spawn(cmd):
           p = subprocess.Popen(cmd)
           processes.append(p)
           return p

       yield spawn

       # Cleanup
       for p in processes:
           p.terminate()
           p.wait(timeout=5)
   ```

#### Verification Steps (30 minutes)

1. **Run failing test individually**
   ```bash
   poetry run pytest tests/e2e/test_cli_run.py::TestCLIRun::test_cli_run_with_results_save -v
   ```
   Expected: PASS

2. **Run full E2E suite**
   ```bash
   poetry run pytest tests/e2e/ -v
   ```
   Expected: All tests PASS (including previously failing test)

3. **Run suite multiple times**
   ```bash
   for i in {1..5}; do
       echo "Run $i"
       poetry run pytest tests/e2e/ -v || echo "FAILED on run $i"
   done
   ```
   Expected: All runs pass

4. **Run with random ordering**
   ```bash
   poetry run pytest tests/e2e/ --random-order --random-order-bucket=global -v
   ```
   Expected: PASS (proves order independence)

5. **Run in parallel** (if applicable)
   ```bash
   poetry run pytest tests/e2e/ -n auto -v
   ```
   Expected: PASS (proves true isolation)

#### Verification Checklist
- [ ] Root cause identified
- [ ] Fix implemented
- [ ] Test passes individually
- [ ] Test passes in full suite
- [ ] Test passes with random order
- [ ] Test passes when run 5 times consecutively
- [ ] No resource leaks detected
- [ ] Cleanup verified

#### Success Criteria
- Test passes reliably in full suite
- No order dependencies
- CI/CD can run tests without flakiness
- Resource cleanup verified

---

## High Priority Fixes (Reliability)

### Action Item 4: Add Service Healthchecks
**Priority**: ⚠️ HIGH
**Estimated Effort**: 2-3 hours
**Assignee**: TBD
**Impact**: Service failure detection, operational reliability

#### Problem
8 services missing healthchecks in Docker Compose configuration. Docker cannot detect service failures automatically.

#### Services Needing Healthchecks
1. `autopilot` (port 9589)
2. `driver` (port 9000)
3. `solver-baseline-1` (port 9001)
4. `solver-baseline-2` (port 9002)
5. `solver-baseline-3` (port 9003)
6. `watch-tower` (no HTTP port - needs different approach)
7. `prometheus` (port 9090)
8. `grafana` (port 3000)

#### Implementation Steps

File: `docker/docker-compose.yml`

1. **Add healthcheck for autopilot** (15 minutes)
   ```yaml
   autopilot:
     # ... existing config ...
     healthcheck:
       test: ["CMD", "curl", "-f", "http://localhost:9589/health"]
       interval: 30s
       timeout: 10s
       retries: 3
       start_period: 40s
   ```

   If `/health` endpoint doesn't exist, use metrics endpoint:
   ```yaml
   test: ["CMD", "curl", "-f", "http://localhost:9589/metrics"]
   ```

2. **Add healthcheck for driver** (15 minutes)
   ```yaml
   driver:
     # ... existing config ...
     healthcheck:
       test: ["CMD", "curl", "-f", "http://localhost:9000/health"]
       interval: 30s
       timeout: 10s
       retries: 3
       start_period: 40s
   ```

3. **Add healthchecks for solvers** (20 minutes)
   ```yaml
   solver-baseline-1:
     # ... existing config ...
     healthcheck:
       test: ["CMD", "curl", "-f", "http://localhost:9001/health"]
       interval: 30s
       timeout: 10s
       retries: 3
       start_period: 40s

   solver-baseline-2:
     # ... existing config ...
     healthcheck:
       test: ["CMD", "curl", "-f", "http://localhost:9002/health"]
       interval: 30s
       timeout: 10s
       retries: 3
       start_period: 40s

   solver-baseline-3:
     # ... existing config ...
     healthcheck:
       test: ["CMD", "curl", "-f", "http://localhost:9003/health"]
       interval: 30s
       timeout: 10s
       retries: 3
       start_period: 40s
   ```

4. **Add healthcheck for Prometheus** (10 minutes)
   ```yaml
   prometheus:
     # ... existing config ...
     healthcheck:
       test: ["CMD", "wget", "--spider", "-q", "http://localhost:9090/-/healthy"]
       interval: 30s
       timeout: 10s
       retries: 3
       start_period: 30s
   ```

5. **Add healthcheck for Grafana** (10 minutes)
   ```yaml
   grafana:
     # ... existing config ...
     healthcheck:
       test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
       interval: 30s
       timeout: 10s
       retries: 3
       start_period: 30s
   ```

6. **Add healthcheck for watch-tower** (20 minutes)

   Watch-tower doesn't expose HTTP port, so use process check:
   ```yaml
   watch-tower:
     # ... existing config ...
     healthcheck:
       test: ["CMD", "pgrep", "-f", "watch-tower"]
       interval: 30s
       timeout: 10s
       retries: 3
       start_period: 60s
   ```

   Or if it has a health endpoint internally:
   ```yaml
   healthcheck:
     test: ["CMD", "curl", "-f", "http://localhost:INTERNAL_PORT/health"]
     # ...
   ```

7. **Restart services and verify** (30 minutes)
   ```bash
   docker compose down
   docker compose up -d
   docker compose ps
   ```

   Expected: All services show "healthy" status after start_period

8. **Test failure detection** (30 minutes)

   For each service, intentionally crash it and verify Docker detects failure:
   ```bash
   # Example: crash autopilot
   docker compose exec autopilot killall -9 autopilot

   # Wait 30-60s, then check status
   docker compose ps autopilot
   ```

   Expected: Status changes to "unhealthy"

#### Verification Checklist
- [ ] All 8 services have healthcheck directives
- [ ] Services restart and show "healthy" status
- [ ] Healthcheck intervals appropriate (30s)
- [ ] Retries configured (3)
- [ ] Start period allows service startup
- [ ] Failure detection tested for each service
- [ ] Documentation updated

#### Success Criteria
- `docker compose ps` shows all services as "healthy"
- Service failures detected within 90s (interval + timeout * retries)
- No false positives (healthy services marked unhealthy)

---

### Action Item 5: Implement Anvil Stability Monitoring
**Priority**: ⚠️ MEDIUM
**Estimated Effort**: 3-4 hours
**Assignee**: TBD
**Impact**: Operational stability, reduced manual intervention

#### Problem
Anvil service became stuck after 3 days uptime, requiring manual restart. Need monitoring and recovery procedures.

#### Implementation Steps

1. **Add Prometheus metric for Anvil block height** (1 hour)

   File: `src/cow_performance/monitoring/chain_monitor.py` (create if doesn't exist)

   ```python
   import asyncio
   from web3 import Web3
   from prometheus_client import Gauge

   # Metric
   anvil_block_height = Gauge(
       'anvil_block_height',
       'Current block height of Anvil chain'
   )
   anvil_last_block_timestamp = Gauge(
       'anvil_last_block_timestamp',
       'Timestamp of last block on Anvil chain'
   )

   class ChainMonitor:
       def __init__(self, rpc_url: str = "http://localhost:8545"):
           self.web3 = Web3(Web3.HTTPProvider(rpc_url))

       async def monitor_loop(self, interval: int = 15):
           """Monitor Anvil chain health."""
           while True:
               try:
                   block = self.web3.eth.get_block('latest')
                   anvil_block_height.set(block['number'])
                   anvil_last_block_timestamp.set(block['timestamp'])
               except Exception as e:
                   print(f"Chain monitoring error: {e}")

               await asyncio.sleep(interval)
   ```

   Register in Prometheus exporter.

2. **Add Prometheus alert rule for stalled chain** (30 minutes)

   File: `configs/prometheus/alerts/chain.yml` (create if doesn't exist)

   ```yaml
   groups:
     - name: chain_health
       interval: 30s
       rules:
         - alert: AnvilChainStalled
           expr: increase(anvil_block_height[5m]) == 0
           for: 5m
           labels:
             severity: critical
           annotations:
             summary: "Anvil chain has not progressed in 5 minutes"
             description: "Block height {{ $value }} has not changed for 5 minutes"

         - alert: AnvilChainUnreachable
           expr: up{job="anvil"} == 0
           for: 1m
           labels:
             severity: critical
           annotations:
             summary: "Anvil chain is unreachable"
             description: "Cannot connect to Anvil RPC endpoint"
   ```

   Update `configs/prometheus.yml` to include alert file:
   ```yaml
   rule_files:
     - "alerts/*.yml"
   ```

3. **Document manual recovery procedure** (1 hour)

   File: `docs/troubleshooting.md` (create section)

   ```markdown
   ## Anvil Chain Recovery

   ### Symptoms
   - Chain stops producing blocks
   - RPC requests timeout
   - Services report connection errors

   ### Detection
   - Prometheus alert: `AnvilChainStalled`
   - Manual check: `docker compose logs chain | tail -20`
   - Block height not increasing: http://localhost:9090/graph?g0.expr=anvil_block_height

   ### Recovery Steps
   1. Restart Anvil service:
      ```bash
      docker compose restart chain
      ```

   2. Verify recovery:
      ```bash
      # Check block progression
      curl -X POST -H "Content-Type: application/json" \
        --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
        http://localhost:8545

      # Check dependent services auto-recovered
      docker compose ps
      ```

   3. If restart fails, full reset:
      ```bash
      docker compose down
      docker compose up -d
      ```

   ### Prevention
   - Monitor `anvil_block_height` metric
   - Set up alerts for stalled chain
   - Consider scheduled restarts every 24h (optional)
   ```

4. **Optional: Add scheduled restart script** (1 hour)

   File: `hack/restart-anvil-daily.sh`

   ```bash
   #!/bin/bash
   # Restart Anvil every 24 hours to prevent stability issues

   set -e

   echo "Restarting Anvil chain (scheduled maintenance)..."
   docker compose restart chain

   echo "Waiting for chain to recover..."
   sleep 30

   # Verify chain is responding
   BLOCK=$(curl -s -X POST -H "Content-Type: application/json" \
     --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
     http://localhost:8545 | jq -r '.result')

   if [ -z "$BLOCK" ]; then
       echo "ERROR: Chain not responding after restart"
       exit 1
   fi

   echo "Chain recovered, current block: $BLOCK"
   ```

   Add to crontab:
   ```bash
   # Restart Anvil daily at 3 AM
   0 3 * * * /path/to/services-performance/hack/restart-anvil-daily.sh >> /var/log/anvil-restart.log 2>&1
   ```

#### Verification Checklist
- [ ] Chain monitor implemented
- [ ] Prometheus metrics exported
- [ ] Alert rules configured
- [ ] Manual recovery procedure documented
- [ ] Recovery procedure tested
- [ ] Optional scheduled restart implemented (if desired)

#### Success Criteria
- Alert fires when chain stalls
- Manual recovery procedure works reliably
- Downtime minimized (detected within 5 minutes)
- Documented for operational team

---

### Action Item 6: Add Config Generator Tests
**Priority**: ⚠️ MEDIUM
**Estimated Effort**: 4-6 hours
**Assignee**: TBD
**Impact**: Code quality, regression protection for user-facing feature

#### Problem
`src/cow_performance/scenarios/generator.py` has 0% test coverage. Interactive wizard (`cow-perf config-init`) not tested.

#### Implementation Steps

File: `tests/integration/test_generator.py` (create)

1. **Set up test infrastructure** (1 hour)

   ```python
   import pytest
   from unittest.mock import patch, MagicMock
   from pathlib import Path
   from cow_performance.scenarios.generator import ConfigGenerator

   @pytest.fixture
   def mock_prompts():
       """Mock questionary prompts for automated testing."""
       with patch('questionary.select') as mock_select, \
            patch('questionary.text') as mock_text, \
            patch('questionary.confirm') as mock_confirm:
           yield {
               'select': mock_select,
               'text': mock_text,
               'confirm': mock_confirm
           }

   @pytest.fixture
   def generator(tmp_path):
       """ConfigGenerator instance with temp output directory."""
       return ConfigGenerator(output_dir=tmp_path)
   ```

2. **Test template selection** (1 hour)

   ```python
   def test_select_template_minimal(mock_prompts, generator):
       """Test selecting minimal template."""
       mock_prompts['select'].return_value.ask.return_value = "minimal"

       template = generator.select_template()

       assert template == "minimal"
       mock_prompts['select'].assert_called_once()

   def test_select_template_all_options(mock_prompts, generator):
       """Test all template options are available."""
       # Mock to return list of available templates
       mock_prompts['select'].return_value.ask.side_effect = [
           "minimal", "base", "advanced"
       ]

       for expected in ["minimal", "base", "advanced"]:
           template = generator.select_template()
           assert template == expected
   ```

3. **Test scenario configuration prompts** (1.5 hours)

   ```python
   def test_configure_scenario_minimal(mock_prompts, generator):
       """Test minimal scenario configuration."""
       mock_prompts['text'].return_value.ask.side_effect = [
           "test-scenario",  # name
           "60",            # duration
           "5",             # order_rate
       ]
       mock_prompts['select'].return_value.ask.return_value = "constant_rate"

       config = generator.configure_scenario()

       assert config['name'] == "test-scenario"
       assert config['duration'] == 60
       assert config['trading_pattern'] == "constant_rate"

   def test_configure_scenario_validation(mock_prompts, generator):
       """Test input validation for invalid values."""
       mock_prompts['text'].return_value.ask.side_effect = [
           "",              # empty name - should retry
           "valid-name",
           "-10",           # negative duration - should retry
           "60",
       ]

       # Should handle validation and retry
       config = generator.configure_scenario()
       assert config['name'] == "valid-name"
       assert config['duration'] == 60
   ```

4. **Test file writing** (1 hour)

   ```python
   def test_write_scenario_file(mock_prompts, generator, tmp_path):
       """Test writing scenario to file."""
       scenario_config = {
           'name': 'test-scenario',
           'duration': 60,
           'trading_pattern': 'constant_rate',
       }

       output_file = generator.write_scenario(scenario_config)

       assert output_file.exists()
       assert output_file.suffix == '.yml'

       # Validate written YAML
       import yaml
       with open(output_file) as f:
           data = yaml.safe_load(f)

       assert data['name'] == 'test-scenario'

   def test_write_scenario_file_collision(mock_prompts, generator, tmp_path):
       """Test handling of existing file."""
       scenario_config = {'name': 'test-scenario', 'duration': 60}

       # Write first time
       file1 = generator.write_scenario(scenario_config)

       # Mock user chooses to overwrite
       mock_prompts['confirm'].return_value.ask.return_value = True

       # Write again
       file2 = generator.write_scenario(scenario_config)

       assert file1 == file2
       mock_prompts['confirm'].assert_called_once()
   ```

5. **Test end-to-end wizard flow** (1.5 hours)

   ```python
   def test_wizard_full_flow_minimal(mock_prompts, generator, tmp_path):
       """Test complete wizard flow for minimal scenario."""
       mock_prompts['select'].return_value.ask.side_effect = [
           "minimal",           # template
           "constant_rate",     # trading pattern
       ]
       mock_prompts['text'].return_value.ask.side_effect = [
           "test-scenario",
           "60",
           "5",
       ]
       mock_prompts['confirm'].return_value.ask.return_value = True

       output_file = generator.run_wizard()

       assert output_file.exists()

       # Validate scenario can be loaded
       from cow_performance.scenarios.schema import ScenarioConfig
       import yaml

       with open(output_file) as f:
           config = ScenarioConfig(**yaml.safe_load(f))

       assert config.name == "test-scenario"

   def test_wizard_user_cancels(mock_prompts, generator):
       """Test wizard when user cancels."""
       mock_prompts['confirm'].return_value.ask.return_value = False

       output_file = generator.run_wizard()

       assert output_file is None
   ```

6. **Run tests and verify coverage** (30 minutes)

   ```bash
   poetry run pytest tests/integration/test_generator.py -v
   poetry run pytest tests/integration/test_generator.py --cov=src/cow_performance/scenarios/generator --cov-report=term-missing
   ```

   Target: 70%+ coverage

#### Verification Checklist
- [ ] Test infrastructure set up (mocked prompts)
- [ ] Template selection tested
- [ ] Scenario configuration tested
- [ ] Input validation tested
- [ ] File writing tested
- [ ] File collision handling tested
- [ ] End-to-end wizard flow tested
- [ ] User cancellation tested
- [ ] Coverage ≥70%
- [ ] All tests passing

#### Success Criteria
- Config generator has ≥70% test coverage
- User-facing wizard has regression protection
- All test scenarios pass

---

## Summary

### Critical Path (Production Blockers)
**Total Time**: 4-6 hours

1. ✅ Fix scenario schema mismatch (1-2 hours)
2. ✅ Fix Prometheus solver scrape (15 min)
3. ✅ Fix E2E test isolation (2-4 hours)

**After these fixes, the suite is production-ready.**

---

### High Priority (Reliability)
**Total Time**: 9-13 hours

4. ⚠️ Add service healthchecks (2-3 hours)
5. ⚠️ Add config generator tests (4-6 hours)
6. ⚠️ Implement Anvil monitoring (3-4 hours)

**These improve operational reliability and code quality.**

---

### Progress Tracking

Use this checklist to track overall progress:

#### Critical Fixes
- [ ] Action Item 1: Scenario schema mismatch
- [ ] Action Item 2: Prometheus solver scrape
- [ ] Action Item 3: E2E test isolation

#### High Priority
- [ ] Action Item 4: Service healthchecks
- [ ] Action Item 5: Anvil stability monitoring
- [ ] Action Item 6: Config generator tests

#### Documentation
- [ ] Update README with any new procedures
- [ ] Update troubleshooting guide
- [ ] Update monitoring documentation

#### Final Validation
- [ ] Re-run full test suite
- [ ] Validate all predefined scenarios
- [ ] Verify Prometheus metrics
- [ ] Verify service health
- [ ] Sign off on production readiness

---

**Created**: 2026-03-16
**Last Updated**: 2026-03-16
**Status**: Ready for implementation
