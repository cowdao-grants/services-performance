# COW-598: 13 - Alerting Rules

**Linear URL**: https://linear.app/bleu-builders/issue/COW-598/13-alerting-rules
**Status**: Todo
**Priority**: High
**Estimate**: 2 Points
**Milestone**: M3 — Metrics & Visualization
**Git Branch**: `jefferson/cow-598-13-alerting-rules`

## Summary

Implement Prometheus alerting rules and Grafana alerts that notify developers when performance degrades, error rates spike, or resource utilization exceeds thresholds during performance testing.

## Background

Automated alerting helps catch performance issues immediately during testing, especially for long-running tests. Alerts can notify developers of regressions, resource exhaustion, or unexpected errors without constant dashboard monitoring.

## Deliverables

### 1. Prometheus Alerting Rules

**Subtasks:**

- [ ] Create Prometheus alert rule configuration file
- [ ] Define alert severity levels (critical, warning, info)
- [ ] Implement alert grouping and routing
- [ ] Configure alert evaluation intervals
- [ ] Document alert conditions

### 2. Performance Degradation Alerts

**Subtasks:**

- [ ] **High Latency Alert:**
  * Trigger: P95 submission latency > threshold (e.g., 5 seconds)
  * Severity: Warning
  * Duration: 2 minutes
- [ ] **Very High Latency Alert:**
  * Trigger: P95 submission latency > critical threshold (e.g., 10 seconds)
  * Severity: Critical
  * Duration: 1 minute
- [ ] **Settlement Latency Alert:**
  * Trigger: P95 settlement latency > threshold (e.g., 60 seconds)
  * Severity: Warning
- [ ] **Low Throughput Alert:**
  * Trigger: Actual throughput < 80% of target rate
  * Severity: Warning
  * Duration: 2 minutes

### 3. Error Rate Alerts

**Subtasks:**

- [ ] **High Error Rate Alert:**
  * Trigger: Error rate > 5%
  * Severity: Critical
  * Duration: 1 minute
- [ ] **Elevated Error Rate Alert:**
  * Trigger: Error rate > 1%
  * Severity: Warning
  * Duration: 2 minutes
- [ ] **API Error Spike:**
  * Trigger: API error rate increases by >50% in 5 minutes
  * Severity: Warning

### 4. Resource Alerts

**Subtasks:**

- [ ] **High CPU Usage:**
  * Trigger: Container CPU > 80%
  * Severity: Warning
  * Duration: 5 minutes
- [ ] **Critical CPU Usage:**
  * Trigger: Container CPU > 95%
  * Severity: Critical
  * Duration: 2 minutes
- [ ] **High Memory Usage:**
  * Trigger: Container memory > 80% of limit
  * Severity: Warning
- [ ] **Memory Exhaustion:**
  * Trigger: Container memory > 95% of limit
  * Severity: Critical

### 5. Test Execution Alerts

**Subtasks:**

- [ ] **Test Stalled:**
  * Trigger: No orders submitted in 60 seconds during active test
  * Severity: Critical
- [ ] **Test Completed:**
  * Trigger: Test duration reached
  * Severity: Info
- [ ] **Test Failed:**
  * Trigger: Test process exit with error
  * Severity: Critical

### 6. Regression Alerts

**Subtasks:**

- [ ] **Performance Regression Detected:**
  * Trigger: Regression severity = critical
  * Severity: Critical
- [ ] **Major Regression Detected:**
  * Trigger: Regression severity = major
  * Severity: Warning

### 7. Alert Manager Configuration

**Subtasks:**

- [ ] Configure Alertmanager (if using)
- [ ] Define alert routing rules
- [ ] Configure notification channels:
  - Slack (optional)
  - Email (optional)
  - Webhook (optional)
- [ ] Implement alert deduplication
- [ ] Configure alert silencing

### 8. Grafana Alerts

**Subtasks:**

- [ ] Create Grafana alert rules (alternative to Prometheus alerts)
- [ ] Configure Grafana notification channels
- [ ] Set up alert dashboards
- [ ] Implement alert annotations on dashboards

### 9. Alert Testing

**Subtasks:**

- [ ] Test each alert condition manually
- [ ] Verify alert notifications delivered
- [ ] Test alert resolution notifications
- [ ] Validate alert grouping

### 10. Alert Documentation

**Subtasks:**

- [ ] Document each alert with:
  - Condition
  - Severity
  - Expected action
  - Troubleshooting steps
- [ ] Create runbook for common alerts
- [ ] Document alert configuration

## Implementation Details

### Prometheus Alert Rules

```yaml
# prometheus/alerts/performance-testing.yml
groups:
  - name: performance_testing
    interval: 10s
    rules:
      # High Latency Alerts
      - alert: HighSubmissionLatency
        expr: |
          histogram_quantile(0.95,
            rate(cow_perf_submission_latency_seconds_bucket[1m])
          ) > 5
        for: 2m
        labels:
          severity: warning
          component: performance-testing
        annotations:
          summary: "High submission latency detected"
          description: "P95 submission latency is {{ $value }}s (threshold: 5s) for scenario {{ $labels.scenario }}"
          runbook_url: "https://docs.cow.fi/performance-testing/runbooks/high-latency"

      - alert: CriticalSubmissionLatency
        expr: |
          histogram_quantile(0.95,
            rate(cow_perf_submission_latency_seconds_bucket[1m])
          ) > 10
        for: 1m
        labels:
          severity: critical
          component: performance-testing
        annotations:
          summary: "Critical submission latency detected"
          description: "P95 submission latency is {{ $value }}s (threshold: 10s)"

      # Error Rate Alerts
      - alert: HighErrorRate
        expr: |
          sum(rate(cow_perf_orders_failed_total[5m]))
          /
          sum(rate(cow_perf_orders_submitted_total[5m]))
          > 0.05
        for: 1m
        labels:
          severity: critical
          component: performance-testing
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 5%)"

      # Throughput Alerts
      - alert: LowThroughput
        expr: |
          cow_perf_actual_rate / cow_perf_target_rate < 0.8
        for: 2m
        labels:
          severity: warning
          component: performance-testing
        annotations:
          summary: "Low throughput detected"
          description: "Actual throughput is {{ $value | humanizePercentage }} of target"

      # Resource Alerts
      - alert: HighCPUUsage
        expr: |
          cow_perf_container_cpu_percent > 80
        for: 5m
        labels:
          severity: warning
          component: performance-testing
        annotations:
          summary: "High CPU usage on {{ $labels.container }}"
          description: "CPU usage is {{ $value }}% (threshold: 80%)"

      - alert: CriticalMemoryUsage
        expr: |
          (cow_perf_container_memory_bytes / cow_perf_container_memory_limit_bytes) > 0.95
        for: 2m
        labels:
          severity: critical
          component: performance-testing
        annotations:
          summary: "Critical memory usage on {{ $labels.container }}"
          description: "Memory usage is {{ $value | humanizePercentage }} of limit"

      # Test Execution Alerts
      - alert: TestStalled
        expr: |
          rate(cow_perf_orders_submitted_total[1m]) == 0
          and
          cow_perf_test_progress_percent < 100
        for: 1m
        labels:
          severity: critical
          component: performance-testing
        annotations:
          summary: "Performance test appears to be stalled"
          description: "No orders submitted in the last minute"

      # Regression Alerts
      - alert: PerformanceRegression
        expr: |
          cow_perf_regression_detected{severity="critical"} > 0
        labels:
          severity: critical
          component: performance-testing
        annotations:
          summary: "Performance regression detected"
          description: "Critical performance regression in {{ $labels.metric }}"
```

### Alertmanager Configuration

```yaml
# alertmanager/alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'component']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
      continue: true

    - match:
        severity: warning
      receiver: 'warning-alerts'

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://localhost:9093/webhook'

  - name: 'critical-alerts'
    # Configure critical notification channels
    # slack_configs:
    #   - api_url: 'YOUR_SLACK_WEBHOOK_URL'
    #     channel: '#performance-alerts'
    #     title: "Critical Alert: {{ .CommonAnnotations.summary }}"

  - name: 'warning-alerts'
    # Configure warning notification channels

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'component']
```

### Alert Testing Script

```python
class AlertTester:
    """Test alert conditions"""

    def __init__(self, prometheus_url: str):
        self.prometheus_url = prometheus_url

    async def trigger_high_latency_alert(self):
        """Artificially create high latency condition"""
        # Submit orders with intentional delays
        logger.info("Triggering high latency alert...")

    async def trigger_error_rate_alert(self):
        """Artificially create high error rate"""
        # Submit invalid orders
        logger.info("Triggering error rate alert...")

    async def verify_alert_fired(self, alert_name: str, timeout: int = 60):
        """Verify alert was triggered"""
        # Query Prometheus /api/v1/alerts
        # Check if alert is in "firing" state
```

### Grafana Alert Configuration

```json
{
  "alert": {
    "name": "High Submission Latency",
    "conditions": [
      {
        "type": "query",
        "query": {
          "datasource": "Prometheus",
          "expr": "histogram_quantile(0.95, rate(cow_perf_submission_latency_seconds_bucket[1m]))"
        },
        "reducer": {
          "type": "last"
        },
        "evaluator": {
          "type": "gt",
          "params": [5]
        }
      }
    ],
    "frequency": "1m",
    "for": "2m",
    "notifications": [
      {
        "uid": "slack-notification"
      }
    ]
  }
}
```

## Acceptance Criteria

- [ ] All alert rules defined and validated
- [ ] Alerts trigger correctly for each condition
- [ ] Alert notifications delivered successfully
- [ ] Alert annotations include actionable information
- [ ] Alert routing and grouping working correctly
- [ ] Alert documentation complete
- [ ] False positive rate is acceptably low
- [ ] Alerts resolve automatically when conditions clear
- [ ] Integration with existing monitoring stack
- [ ] Alert testing framework implemented

## Testing Requirements

### Manual Testing

* Trigger each alert condition manually
* Verify alert notifications
* Test alert resolution
* Verify alert routing

### Automated Testing

* Script to trigger alert conditions
* Verify alerts fire via Prometheus API
* Test notification delivery (if applicable)

## Technical Notes

* Use appropriate alert evaluation intervals
* Set reasonable `for` durations to avoid flapping
* Use alert grouping to reduce notification spam
* Implement alert inhibition rules to suppress related alerts
* Consider time-of-day for alert routing (if tests run on schedule)
* Test alerts in isolation before enabling all
* Document expected alert frequency
* Provide clear next steps in alert descriptions

## Alert Runbook Template

```markdown
# Alert: HighSubmissionLatency

## Severity: Warning

## Description
P95 submission latency has exceeded 5 seconds for more than 2 minutes.

## Impact
Orders are taking longer than expected to be accepted by the API.

## Possible Causes
- API overload
- Network latency issues
- Database performance issues
- Insufficient API capacity

## Investigation Steps
1. Check API logs for errors
2. Verify API container CPU/memory usage
3. Check database query performance
4. Review recent code changes
5. Check network connectivity

## Resolution
- Scale API service if CPU/memory is high
- Optimize database queries if needed
- Reduce test load if environment is undersized

## Prevention
- Monitor API capacity planning
- Implement rate limiting
- Add API caching where appropriate
```

## Related Issues

* Depends on: m3-issue-11-prometheus-exporters, m3-issue-12-grafana-dashboards
* Related: m5-issue-19-comprehensive-documentation (alert documentation)

---

## Planning Notes (M3 Planning — 2026-02-05)

> **STATUS: DEFERRED** — This ticket is out of scope for the current M3 planning cycle.
> COW-598 will be refined and implemented after COW-591 (Prometheus Exporters) and COW-593 (Grafana Dashboards) are complete.

### Deferral Rationale

COW-598 (Alerting Rules) feels out of context compared to COW-591 and COW-593 and the work done so far. The manager/user has requested that this ticket be set aside for now and refined in a later planning step.

**What this means**:
- No implementation work on COW-598 during the current M3 phase
- COW-591 and COW-593 take priority
- After COW-591 and COW-593 are complete, return to COW-598 for detailed planning

### Preserved Analysis (For Future Reference)

The following analysis was conducted during initial M3 planning and is preserved for when COW-598 is revisited:

#### Current State

1. **Prometheus config** (`configs/prometheus.yml`):
   - Rule file loading is NOT configured (no `rule_files:` section)
   - Alertmanager is NOT configured (no `alerting:` section)
   - Only scrape configs for CoW services

2. **No alerting infrastructure** - Will be built from scratch.

3. **Docker Compose** - No Alertmanager service defined.

#### Future Implementation Considerations

1. **Alertmanager is optional**: For a local performance testing tool:
   - **Option A**: Prometheus alerting rules + Grafana alert visualization (simpler)
   - **Option B**: Full Alertmanager with notification channels (more complex)
   - **Recommendation**: Start with Option A.

2. **Core alerts to prioritize** (when implementing):

| Alert | Severity | Condition |
|-------|----------|-----------|
| HighSubmissionLatency | Warning | P95 > 5s for 2m |
| CriticalSubmissionLatency | Critical | P95 > 10s for 1m |
| HighErrorRate | Critical | Error rate > 5% for 1m |
| LowThroughput | Warning | Actual < 80% target for 2m |
| TestStalled | Critical | No orders for 1m during active test |

3. **Dependencies** (will be satisfied before COW-598 starts):
   - Requires COW-591 complete: Alerts depend on Prometheus metrics
   - Requires COW-593 dashboards: Alerts can be visualized in dashboards

### Next Steps

When COW-591 and COW-593 are complete:
1. Revisit this ticket's Planning Notes
2. Refine alert thresholds based on actual metric behavior observed during COW-591/COW-593 testing
3. Determine if full scope (15+ alerts) or reduced scope (5-7 alerts) is appropriate
4. Update validation and grant-alignment documents accordingly

---

## Implementation Notes (2026-02-13)

### Implemented Scope

**Approach**: Option A (Prometheus alerting rules + Grafana visualization)
**Alert Count**: 7 core alerts (reduced from 15+ in original scope)

### Alerts Implemented

| Alert | Severity | Condition | Duration |
|-------|----------|-----------|----------|
| HighSubmissionLatency | Warning | P95 > 5s | 2m |
| CriticalSubmissionLatency | Critical | P95 > 10s | 1m |
| HighErrorRate | Critical | Error rate > 5% | 1m |
| LowThroughput | Warning | Actual < 80% target | 2m |
| TestStalled | Critical | No orders for 1m during active test | 1m |
| HighCPUUsage | Warning | CPU > 80% | 5m |
| CriticalMemoryUsage | Critical | Memory > 95% | 2m |

### What Was NOT Implemented

- Alertmanager (no Slack/email/webhook notifications)
- Settlement latency alerts
- API error spike alerts
- Regression alerts
- Alert testing framework
- Configurable thresholds (see COW-617)

### Threshold Configuration

All thresholds are hardcoded in `configs/prometheus/alerts/performance-testing.yml`.
Parameters are documented at the top of the file for easy modification.

**TODO(COW-617)**: Move thresholds to configurable TOML/env variables.

### Files Created/Modified

- `configs/prometheus/alerts/performance-testing.yml` (NEW)
- `configs/prometheus.yml` (modified: enabled rule_files)
- `docker-compose.yml` (modified: added alerts volume mount)
- `configs/dashboards/performance.json` (modified: added alert annotations)
- `src/cow_performance/prometheus/metrics.py` (modified: added memory_percent gauge)
- `src/cow_performance/prometheus/exporter.py` (modified: export memory_percent metric)
