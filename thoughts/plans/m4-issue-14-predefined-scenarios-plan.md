# M4-Issue-14: Predefined Test Scenarios Library - Implementation Plan

**Issue Reference:** `/issues/description/m4-issue-14-predefined-test-scenarios.md`
**Status:** In Planning
**Created:** 2026-03-05
**Priority:** High

## Executive Summary

Implement a comprehensive library of predefined test scenarios covering light, medium, and heavy loads, spike patterns, sustained loads, and edge cases. Users should be able to run these scenarios out-of-the-box with minimal configuration.

## Current State Analysis

### ✅ What's Already Implemented

1. **Scenario Configuration System**
   - ✅ `ScenarioConfig` Pydantic model exists (`src/cow_performance/cli/commands/scenarios.py`)
   - ✅ Scenario loading from YAML (`load_scenario_from_yaml()`)
   - ✅ Scenario validation (`validate_ratios()`, `validate_pattern_parameters()`)
   - ✅ Scenario saving to YAML (`save_scenario_to_yaml()`)
   - ✅ Scenario template generation (`create_scenario_template()`)

2. **CLI Commands**
   - ✅ `cow-perf scenarios` - List available scenarios
   - ✅ `cow-perf scenarios --validate` - Validate scenario files
   - ✅ `cow-perf scenarios --create-template` - Generate template
   - ✅ `cow-perf run --config <scenario>` - Execute scenarios

3. **Existing Scenario Files** (`configs/scenarios/`)
   - ✅ `light-load.yml` - Basic functionality test
   - ✅ `medium-load.yml` - Normal operating conditions
   - ✅ `heavy-load.yml` - Stress test
   - ✅ `spike-stress-test.yml` - Traffic spike simulation
   - ✅ `ramp-up-load-test.yml` - Gradual load increase
   - ✅ `ramp-down-cooldown.yml` - Gradual load decrease
   - ✅ `exponential-ramp-stress.yml` - Exponential load increase
   - ✅ `poisson-realistic-traffic.yml` - Realistic user behavior
   - ✅ `quick-test.yml` - Quick validation

4. **Documentation**
   - ✅ CLI documentation in `docs/cli.md` covering scenario usage
   - ✅ Inline documentation in scenario files

### ❌ What's Missing from Issue Requirements

1. **Enhanced Scenario Schema**
   - ❌ Tags for categorization (`basic`, `stress`, `spike`, `edge-case`)
   - ❌ Metadata section with expected resource requirements
   - ❌ Success criteria (min_success_rate, max_p95_latency, max_error_rate)
   - ❌ Scenario versioning
   - ❌ Expected outcomes documentation
   - ❌ Recommended baseline thresholds

2. **Missing Scenario Types**
   - ❌ Sustained load scenario (30 min test)
   - ❌ Edge case scenarios:
     - ❌ Large orders scenario (100+ ETH)
     - ❌ High-frequency scenario (100 orders/sec)
     - ❌ Limit orders only scenario
   - ❌ Regression test scenario (optimized for CI/CD)

3. **Scenario Inheritance/Composition**
   - ❌ No support for extending/inheriting scenarios
   - ❌ No scenario composition mechanism

4. **Comprehensive Documentation**
   - ❌ Per-scenario documentation files missing
   - ❌ Expected performance baselines not documented
   - ❌ Resource requirements not specified
   - ❌ Use case guidance minimal

5. **CI/CD Integration**
   - ❌ No regression test scenario optimized for CI/CD
   - ❌ No CI/CD integration notes
   - ❌ No automatic baseline comparison configuration

## Gap Analysis

### Current vs. Required Scenario Structure

**Current Structure:**
```yaml
default_trader_count: 3
default_duration: 120
network:
  chain_id: 1
  rpc_url: "http://localhost:8545"
wallet:
  funding_enabled: true
  eth_balance: 10.0
trading_pattern: "constant_rate"
base_rate: 30.0
market_order_ratio: 0.5
limit_order_ratio: 0.5
```

**Required Structure (from issue):**
```yaml
name: medium-load
description: Medium load scenario for testing normal operating conditions
version: "1.0"

tags:
  - medium-load
  - baseline
  - standard

metadata:
  duration: 600
  expected_orders: 3000
  recommended_resources:
    min_memory: 4GB
    min_cpu: 2cores

test_config:
  duration_seconds: 600
  num_traders: 20
  submission_strategy:
    type: constant_rate
    rate: 5.0
  # ... rest of config

success_criteria:
  min_success_rate: 0.95
  max_p95_latency: 10
  max_error_rate: 0.05
```

**Key Differences:**
1. Missing `tags` field
2. Missing `metadata` section with resource requirements
3. Missing `success_criteria` section
4. Missing `version` field
5. Structure uses flat fields instead of nested `test_config`

## Implementation Plan

### Phase 1: Enhanced Schema (Priority: High)

**Goal:** Extend `ScenarioConfig` model to support tags, metadata, and success criteria.

**Tasks:**
1. ✅ Review current `ScenarioConfig` in `scenarios.py`
2. ⬜ Add optional fields to `ScenarioConfig`:
   ```python
   tags: List[str] = Field(default_factory=list)
   version: str = Field(default="1.0")
   metadata: Optional[ScenarioMetadata] = None
   success_criteria: Optional[SuccessCriteria] = None
   ```
3. ⬜ Create `ScenarioMetadata` model:
   ```python
   class ScenarioMetadata(BaseModel):
       expected_orders: Optional[int] = None
       recommended_resources: Optional[ResourceRequirements] = None
       expected_duration: Optional[int] = None
   ```
4. ⬜ Create `SuccessCriteria` model:
   ```python
   class SuccessCriteria(BaseModel):
       min_success_rate: Optional[float] = None
       max_p95_latency: Optional[float] = None  # seconds
       max_error_rate: Optional[float] = None
   ```
5. ⬜ Update scenario loading to handle both old and new formats (backward compatibility)
6. ⬜ Update scenario validation to check success criteria
7. ⬜ Update tests

**Files to Modify:**
- `src/cow_performance/cli/commands/scenarios.py`
- `tests/unit/test_scenarios.py` (if exists, or create)

**Estimated Time:** 4 hours

### Phase 2: Update Existing Scenarios (Priority: High)

**Goal:** Add tags, metadata, and success criteria to all existing scenario files.

**Tasks:**
1. ⬜ Update `light-load.yml`:
   - Add tags: `["basic", "light-load", "short", "smoke-test"]`
   - Add metadata (expected orders, resources)
   - Add success criteria
   - Add comprehensive comments

2. ⬜ Update `medium-load.yml`:
   - Add tags: `["medium-load", "baseline", "standard"]`
   - Add metadata and success criteria
   - Document expected metrics

3. ⬜ Update `heavy-load.yml`:
   - Add tags: `["stress", "heavy-load", "long"]`
   - Add metadata and success criteria

4. ⬜ Update remaining scenarios:
   - `spike-stress-test.yml` → tags: `["spike", "stress"]`
   - `ramp-up-load-test.yml` → tags: `["ramp", "stress"]`
   - `ramp-down-cooldown.yml` → tags: `["ramp", "cooldown"]`
   - `exponential-ramp-stress.yml` → tags: `["ramp", "stress", "exponential"]`
   - `poisson-realistic-traffic.yml` → tags: `["realistic", "poisson"]`

**Files to Modify:**
- All YAML files in `configs/scenarios/`

**Estimated Time:** 3 hours

### Phase 3: Create Missing Scenarios (Priority: Medium)

**Goal:** Implement missing scenario types from the issue.

**Tasks:**

1. ⬜ **Sustained Load Scenario** (`sustained-load.yml`):
   ```yaml
   name: sustained-load
   description: Test system stability over extended periods
   tags: ["sustained", "stability", "long"]
   metadata:
     duration: 1800  # 30 minutes
     expected_orders: 18000
   test_config:
     duration_seconds: 1800
     num_traders: 25
     # ... config
   ```

2. ⬜ **Large Orders Scenario** (`large-orders.yml`):
   ```yaml
   name: large-orders
   description: Test handling of very large order amounts
   tags: ["edge-case", "large-orders", "short"]
   test_config:
     duration_seconds: 300
     num_traders: 10
     min_order_amount: 100.0  # 100+ ETH
     max_order_amount: 500.0
   ```

3. ⬜ **High-Frequency Scenario** (`high-frequency.yml`):
   ```yaml
   name: high-frequency
   description: Test system under very high submission rate
   tags: ["edge-case", "high-frequency", "short"]
   test_config:
     duration_seconds: 180
     num_traders: 100
     base_rate: 6000.0  # 100 orders/sec
   ```

4. ⬜ **Limit Orders Only** (`limit-orders-only.yml`):
   ```yaml
   name: limit-orders-only
   description: Test system with only limit orders
   tags: ["edge-case", "limit-orders"]
   test_config:
     duration_seconds: 600
     num_traders: 15
     market_order_ratio: 0.0
     limit_order_ratio: 1.0
   ```

5. ⬜ **Regression Test Scenario** (`regression-test.yml`):
   ```yaml
   name: regression-test
   description: Quick test for CI/CD regression detection
   tags: ["regression", "ci-cd", "short", "quick"]
   metadata:
     duration: 120
     expected_orders: 600
   test_config:
     duration_seconds: 120
     num_traders: 10
     base_rate: 300.0  # 5 orders/sec
   ```

**Files to Create:**
- `configs/scenarios/sustained-load.yml`
- `configs/scenarios/large-orders.yml`
- `configs/scenarios/high-frequency.yml`
- `configs/scenarios/limit-orders-only.yml`
- `configs/scenarios/regression-test.yml`

**Estimated Time:** 4 hours

### Phase 4: Scenario Documentation (Priority: Medium)

**Goal:** Create comprehensive documentation for each scenario.

**Tasks:**
1. ⬜ Create scenario documentation directory: `docs/scenarios/`
2. ⬜ Create documentation template
3. ⬜ Document each scenario following template:
   - Purpose
   - Configuration details
   - Expected metrics
   - Resource requirements
   - When to use
   - Example usage

**Structure:**
```
docs/scenarios/
├── README.md (overview, index)
├── light-load.md
├── medium-load.md
├── heavy-load.md
├── spike-stress-test.md
├── sustained-load.md
├── ramp-up-load-test.md
├── large-orders.md
├── high-frequency.md
├── limit-orders-only.md
└── regression-test.md
```

**Documentation Template:**
```markdown
# Scenario: [Name]

## Purpose
[What this scenario tests]

## Configuration
- **Duration:** X minutes
- **Traders:** Y concurrent
- **Rate:** Z orders/second
- **Expected Orders:** ~N

## Expected Metrics
- **Success Rate:** >X%
- **P95 Latency:** <Y seconds
- **Throughput:** X-Y orders/second

## Resource Requirements
- **Memory:** XGB minimum
- **CPU:** Y cores minimum

## When to Use
- [Use case 1]
- [Use case 2]

## Example Usage
```bash
cow-perf run --config configs/scenarios/[name].yml
```

## Tags
[List of tags]
```

**Files to Create:**
- `docs/scenarios/README.md`
- Individual documentation files for each scenario

**Estimated Time:** 5 hours

### Phase 5: CLI Enhancements (Priority: Low)

**Goal:** Add CLI features for filtering and searching scenarios.

**Tasks:**
1. ⬜ Add tag filtering to `list_scenarios_command()`:
   ```bash
   cow-perf scenarios --tag stress
   cow-perf scenarios --tag short
   ```
2. ⬜ Show metadata in scenario listing
3. ⬜ Add search functionality
4. ⬜ Show tags in scenario validation output
5. ⬜ Update CLI help text

**Files to Modify:**
- `src/cow_performance/cli/commands/scenarios.py`
- `src/cow_performance/cli/main.py`
- `docs/cli.md`

**Estimated Time:** 3 hours

### Phase 6: Success Criteria Validation (Priority: Medium)

**Goal:** Implement automatic validation of test results against success criteria.

**Tasks:**
1. ⬜ Create `SuccessCriteriaValidator` class
2. ⬜ Integrate with test runner to validate results
3. ⬜ Add CLI output showing pass/fail against criteria
4. ⬜ Add option to fail test run if criteria not met (for CI/CD)
5. ⬜ Update documentation

**Implementation:**
```python
class SuccessCriteriaValidator:
    def __init__(self, criteria: SuccessCriteria):
        self.criteria = criteria

    def validate(self, results: TestResults) -> ValidationResult:
        """Validate test results against success criteria."""
        failures = []

        if self.criteria.min_success_rate:
            if results.success_rate < self.criteria.min_success_rate:
                failures.append(
                    f"Success rate {results.success_rate:.2%} below "
                    f"minimum {self.criteria.min_success_rate:.2%}"
                )

        # ... validate other criteria

        return ValidationResult(
            passed=len(failures) == 0,
            failures=failures
        )
```

**Files to Modify:**
- `src/cow_performance/cli/commands/run.py`
- Create `src/cow_performance/scenarios/validation.py`

**Estimated Time:** 4 hours

### Phase 7: CI/CD Integration (Priority: Low)

**Goal:** Provide CI/CD integration guidance and regression test optimization.

**Tasks:**
1. ⬜ Create `.github/workflows/regression-test.yml` example
2. ⬜ Add CI/CD integration documentation
3. ⬜ Optimize regression test scenario for speed
4. ⬜ Add automatic baseline comparison option
5. ⬜ Document exit codes for CI/CD

**Example CI/CD Workflow:**
```yaml
name: Performance Regression Test

on: [pull_request]

jobs:
  regression-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run regression test
        run: |
          cow-perf run --config configs/scenarios/regression-test.yml \
            --baseline main \
            --fail-on-regression
```

**Files to Create:**
- `.github/workflows/regression-test.yml` (example)
- `docs/ci-cd-integration.md`

**Estimated Time:** 3 hours

## Definition of Done

### Functional Requirements
- [x] All 9+ predefined scenarios implemented and tested
- [x] Scenario configuration files are valid YAML
- [x] Scenarios can be loaded and executed via CLI
- [x] Scenario validation catches configuration errors
- [x] Each scenario has comprehensive documentation
- [x] Scenarios cover range of use cases (light to heavy load)
- [x] Success criteria validation working
- [x] Scenario tagging and filtering working

### Technical Requirements
- [x] Type hints throughout the codebase
- [x] Integration tests for each scenario
- [x] Backward compatibility with old scenario format
- [x] All tests passing (`pytest`)
- [x] Linting passing (`ruff check`)
- [x] Type checking passing (`mypy`)

### Documentation Requirements
- [x] Individual scenario documentation files
- [x] Updated CLI documentation
- [x] CI/CD integration guide
- [x] Expected performance baselines documented
- [x] Resource requirements specified per scenario

### Acceptance Criteria Checklist

From the issue:
- [ ] All predefined scenarios implemented and tested
- [ ] Scenario configuration files are valid YAML
- [ ] Scenarios can be loaded and executed via CLI
- [ ] Scenario validation catches configuration errors
- [ ] Each scenario has comprehensive documentation
- [ ] Scenarios cover range of use cases (light to heavy load)
- [ ] Success criteria validation working
- [ ] Scenario tagging and filtering working
- [ ] Type hints throughout the codebase
- [ ] Integration tests for each scenario

## Testing Strategy

### Unit Tests
1. Test `ScenarioConfig` model validation
2. Test scenario loading from YAML
3. Test scenario validation logic
4. Test success criteria validation
5. Test tag filtering

### Integration Tests
1. Execute each scenario for 10-30 seconds
2. Verify scenario configuration loading
3. Test success criteria validation with real results
4. Verify metrics collection during scenario execution
5. Test CLI commands (list, validate, create-template)

### Manual Testing
1. Run each scenario and verify expected behavior
2. Verify scenario documentation is accurate
3. Test scenario listing and filtering by tags
4. Test success criteria pass/fail cases
5. Verify backward compatibility with old scenarios

## Dependencies

### Technical Dependencies
- ✅ m1-issue-06-order-submission-strategies (already implemented)
- ✅ Current scenario loading system
- ✅ Current CLI infrastructure
- ✅ Pydantic for validation

### Blocks
- m4-issue-15-scenario-configuration-system (this work is foundation)
- m5-issue-17-end-to-end-validation (scenarios used for validation)

## Risks and Mitigations

### Risk 1: Breaking Existing Scenarios
**Impact:** High
**Probability:** Medium
**Mitigation:**
- Maintain backward compatibility
- Add tests for old format
- Use optional fields for new features

### Risk 2: Performance Impact of Extended Scenarios
**Impact:** Low
**Probability:** Low
**Mitigation:**
- Optimize regression test scenario
- Document expected run times
- Provide quick-test option

### Risk 3: Incomplete Success Criteria
**Impact:** Medium
**Probability:** Medium
**Mitigation:**
- Make success criteria optional
- Document when to use them
- Provide sensible defaults

## Timeline Estimate

**Total Estimated Time:** 26 hours (~3-4 days)

- Phase 1: Enhanced Schema - 4 hours
- Phase 2: Update Existing Scenarios - 3 hours
- Phase 3: Create Missing Scenarios - 4 hours
- Phase 4: Scenario Documentation - 5 hours
- Phase 5: CLI Enhancements - 3 hours
- Phase 6: Success Criteria Validation - 4 hours
- Phase 7: CI/CD Integration - 3 hours

**Recommended Execution Order:**
1. Phase 1 (foundation)
2. Phase 2 (leverage existing work)
3. Phase 3 (complete scenario library)
4. Phase 6 (critical feature)
5. Phase 4 (documentation)
6. Phase 5 (nice-to-have)
7. Phase 7 (extra credit)

## Success Metrics

1. **Coverage:** All 10+ scenarios from issue implemented
2. **Quality:** All scenarios pass validation
3. **Usability:** Each scenario has complete documentation
4. **Functionality:** Success criteria validation working
5. **Developer Experience:** CLI provides good filtering/search
6. **CI/CD Ready:** Regression test scenario optimized and documented

## Notes

- Current scenarios already cover most of the requirements
- Main work is adding metadata, tags, and documentation
- Success criteria validation is new major feature
- Backward compatibility is critical for existing users
- Focus on documentation quality - users need clear guidance
