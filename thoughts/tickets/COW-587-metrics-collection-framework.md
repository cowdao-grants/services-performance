# 07: Metrics Collection Framework

## Summary

Implement a comprehensive metrics collection framework that tracks order lifecycle timing, settlement latency, API response times, and resource utilization throughout the performance testing process.

## Background

Accurate performance measurement requires tracking multiple metrics across the entire order lifecycle. This is one of the most complex parts of the benchmarking system, requiring careful instrumentation and timing precision.

## Deliverables

### 1\. Metrics Data Models

**Subtasks:**

- [x] Define `OrderLifecycleMetrics` model (implemented as `OrderMetadata` in `metrics/models.py`):
  - Order creation timestamp
  - Submission timestamp
  - API acceptance timestamp
  - First seen in orderbook timestamp
  - Settlement start timestamp
  - Settlement completion timestamp
  - Calculated durations (submission latency, time to settlement, etc.)
- [x] Define `APIMetrics` model (`metrics/models.py`):
  - Endpoint URL
  - HTTP method
  - Response time
  - Status code
  - Payload size
- [x] Define `ResourceMetrics` model (`metrics/models.py`):
  - CPU usage percentage
  - Memory usage (RSS, VMS)
  - Network I/O
  - Disk I/O
- [x] Define `TestRunMetrics` model (aggregate metrics for entire test)

### 2\. Order Lifecycle Tracking

This is a complex requirement - track orders from creation through settlement.

**Subtasks:**

- [x] Implement `OrderLifecycleTracker` class (implemented as `OrderTracker` in `load_generation/order_tracker.py`)
- [x] Hook into order creation to capture initial timestamp
- [x] Hook into order submission to capture submission timestamp
- [x] Poll orderbook API to detect when order appears
- [x] Monitor for order status changes (open, filled, expired, cancelled)
- [ ] Detect settlement transactions on-chain (or via API) - *partial: API-based detection only*
- [x] Calculate lifecycle durations:
  - Submission latency (creation → accepted by API)
  - Orderbook latency (accepted → visible in orderbook)
  - Time to fill (orderbook → filled)
  - Total lifecycle (creation → settled)
- [x] Handle edge cases:
  - Orders that never get accepted
  - Orders that expire
  - Orders that get cancelled
  - Partially filled orders

> **Note**: Standard orders (market/limit) have full lifecycle tracking. Conditional orders (TWAP, stop-loss, good-after-time) currently have limited tracking since they use on-chain submission via ComposableCow and don't exist in the orderbook API.

### 3\. API Response Time Monitoring

**Subtasks:**

- [x] Implement HTTP client wrapper with timing instrumentation (`api/instrumented_client.py`)
- [x] Track request/response times for:
  - Order submission endpoint
  - Order status endpoint
  - Orderbook query endpoint
  - Autopilot endpoints (if applicable)
- [x] Calculate statistics (`metrics/aggregator.py`):
  - Min, max, mean, median response times
  - P50, P90, P95, P99 percentiles
  - Request rate (requests per second)
  - Success rate (2xx responses / total requests)
  - Error rate by status code
- [x] Support per-endpoint metrics (`aggregate_api_metrics_by_endpoint()`)
- [ ] Implement connection pooling metrics

### 4\. Resource Utilization Monitoring

Extract metrics from Docker container stats and system resources.

**Subtasks:**

- [x] Implement `ResourceMonitor` class (`monitoring/resource_monitor.py`)
- [x] Monitor target containers:
  - Orderbook API
  - Autopilot
  - Driver
  - Solver
  - Anvil (or node)
- [x] Collect metrics via Docker API:
  - CPU usage percentage
  - Memory usage (current, max, limit)
  - Network I/O (bytes sent/received)
  - Block I/O (read/write)
- [x] Sample metrics at configurable intervals (e.g., every 5 seconds)
- [x] Store time-series data for trend analysis
- [x] Calculate aggregate statistics (avg, max, min) with percentiles

### 5\. Metrics Storage

**Subtasks:**

- [x] Implement in-memory metrics store using appropriate data structures (`metrics/store.py`)
- [x] Use `collections.deque` for time-series data with size limits
- [x] Implement efficient lookups by order UID
- [x] Support concurrent writes from multiple traders
- [x] Implement thread-safe operations (`asyncio.Lock`)
- [x] Add metrics export functionality (JSON, CSV) (`metrics/export.py`)

### 6\. Metrics Aggregation

**Subtasks:**

- [x] Implement `MetricsAggregator` class (`metrics/aggregator.py`)
- [x] Calculate summary statistics across all orders:
  - Total orders created, submitted, filled
  - Success/failure rates
  - Average/median/percentile latencies (p50, p90, p95, p99)
  - Throughput (orders per second)
- [x] Group metrics by:
  - Time windows (per second, per minute) - `aggregate_orders_by_time_window()`
  - Order type (market, limit) - via token pair grouping
  - Token pair - `aggregate_orders_by_token_pair()`
  - Trader - `aggregate_orders_by_owner()`
- [x] Calculate performance indicators:
  - Orders per second (actual throughput) - `calculate_throughput()`
  - Average settlement time
  - API success rate
  - Error rate

### 7\. Real-time Metrics Updates

**Subtasks:**

- [x] Implement metrics streaming for live monitoring (`metrics/streaming.py`)
  - `MetricsEventStream` - async event stream for real-time monitoring
  - `RollingMetricsSummary` - rolling window summary for live dashboards
- [x] Support callbacks for metrics updates (`MetricsStore.register_callback()`)
- [x] Integrate with CLI progress display (`cli/live_display.py`)
  - `LiveMetricsDisplay` - Rich Live display for real-time visualization
  - `create_performance_metrics_dict()` - CLI output with percentiles
- [x] Emit metrics events for external consumers (via callback system)

## Implementation Details

### Order Lifecycle Tracking Architecture

```python
@dataclass
class OrderLifecycleMetrics:
    order_uid: str
    trader_address: str

    # Timestamps
    created_at: float
    submitted_at: Optional[float] = None
    accepted_at: Optional[float] = None
    first_seen_at: Optional[float] = None
    filled_at: Optional[float] = None
    settled_at: Optional[float] = None

    # Status
    final_status: Optional[str] = None
    error_message: Optional[str] = None

    # Calculated durations (in seconds)
    @property
    def submission_latency(self) -> Optional[float]:
        if self.submitted_at and self.accepted_at:
            return self.accepted_at - self.submitted_at
        return None

    @property
    def time_to_fill(self) -> Optional[float]:
        if self.first_seen_at and self.filled_at:
            return self.filled_at - self.first_seen_at
        return None

    @property
    def total_lifecycle(self) -> Optional[float]:
        if self.created_at and self.settled_at:
            return self.settled_at - self.created_at
        return None

class OrderLifecycleTracker:
    def __init__(self):
        self.orders: Dict[str, OrderLifecycleMetrics] = {}
        self._lock = asyncio.Lock()

    async def track_order_creation(self, order_uid: str, trader: str):
        """Record order creation"""
        async with self._lock:
            self.orders[order_uid] = OrderLifecycleMetrics(
                order_uid=order_uid,
                trader_address=trader,
                created_at=time.time(),
            )

    async def track_order_submission(self, order_uid: str, response_time: float):
        """Record order submission to API"""
        async with self._lock:
            if order_uid in self.orders:
                self.orders[order_uid].submitted_at = time.time()
                if response_time > 0:  # Successful submission
                    self.orders[order_uid].accepted_at = time.time()

    async def poll_order_status(self, order_uid: str):
        """Poll orderbook for order status - complex operation"""
        # Query orderbook API
        # Update first_seen_at, filled_at based on response
        # Detect settlement events
```

### API Metrics Collection

```python
class InstrumentedHTTPClient:
    def __init__(self, base_url: str, metrics_collector: MetricsCollector):
        self.base_url = base_url
        self.metrics = metrics_collector
        self.session = aiohttp.ClientSession()

    async def post(self, endpoint: str, data: dict) -> tuple[Response, float]:
        """POST request with timing"""
        start = time.perf_counter()
        try:
            response = await self.session.post(
                f"{self.base_url}{endpoint}",
                json=data
            )
            duration = time.perf_counter() - start

            self.metrics.record_api_call(
                endpoint=endpoint,
                method="POST",
                status_code=response.status,
                duration=duration,
                payload_size=len(json.dumps(data)),
            )

            return response, duration
        except Exception as e:
            duration = time.perf_counter() - start
            self.metrics.record_api_error(endpoint, "POST", str(e), duration)
            raise
```

### Resource Monitoring

```python
class ResourceMonitor:
    def __init__(self, container_names: List[str], sample_interval: int = 5):
        self.container_names = container_names
        self.sample_interval = sample_interval
        self.docker_client = docker.from_env()
        self.metrics: Dict[str, List[ResourceSample]] = defaultdict(list)

    async def start_monitoring(self):
        """Start background monitoring task"""
        while self.running:
            await self._collect_metrics()
            await asyncio.sleep(self.sample_interval)

    async def _collect_metrics(self):
        """Collect metrics from all containers"""
        for container_name in self.container_names:
            try:
                container = self.docker_client.containers.get(container_name)
                stats = container.stats(stream=False)

                sample = ResourceSample(
                    timestamp=time.time(),
                    cpu_percent=self._calculate_cpu_percent(stats),
                    memory_usage=stats['memory_stats']['usage'],
                    memory_limit=stats['memory_stats']['limit'],
                    network_rx_bytes=stats['networks']['eth0']['rx_bytes'],
                    network_tx_bytes=stats['networks']['eth0']['tx_bytes'],
                )

                self.metrics[container_name].append(sample)
            except Exception as e:
                logger.error(f"Failed to collect metrics for {container_name}: {e}")
```

## Acceptance Criteria

- [x] Order lifecycle tracked from creation to settlement
- [x] API response times captured with percentile calculations
- [x] Resource metrics collected from all relevant containers
- [x] Metrics stored efficiently in memory
- [x] Concurrent access to metrics is thread-safe
- [x] Metrics can be exported to JSON and CSV
- [x] Real-time metrics updates available
- [x] Comprehensive error handling for metrics collection failures
- [x] Type hints throughout the codebase
- [x] Unit tests for all metrics calculations
- [x] Integration tests with realistic order flows

## Testing Requirements

### Unit Tests

- Test metrics data model validation
- Test lifecycle duration calculations
- Test percentile calculations
- Test metrics aggregation logic
- Mock Docker API for resource monitoring tests

### Integration Tests

- Submit 100 orders and verify all lifecycle stages tracked
- Verify API metrics captured for all endpoints
- Verify resource metrics collected successfully
- Test metrics export in all formats
- Verify thread-safety with concurrent order submissions

## Technical Notes

- Use `time.perf_counter()` for high-precision timing
- Use `asyncio.Lock` for thread-safe metrics updates
- Consider using `numpy` for efficient percentile calculations
- Use `docker` Python library for container monitoring
- Implement circular buffers for time-series data to limit memory usage
- Log warning if order tracking detects anomalies (e.g., order never accepted)
- Consider using `dataclasses` or `pydantic` for metrics models

## Performance Considerations

- Metrics collection should add minimal overhead (<5%)
- Use efficient data structures (e.g., `collections.deque`)
- Implement lazy calculation of derived metrics
- Consider batching metrics writes
- Use connection pooling for Docker API

## Related Issues

- Depends on: m1-issue-03-order-generation-engine, m1-issue-04-user-simulation-module
- Blocks: m2-issue-08-baseline-snapshot-system, m2-issue-09-comparison-engine-regression-detection
- Related: m3-issue-11-prometheus-exporters (metrics will be exported to Prometheus)

## Metadata

- URL: [https://linear.app/bleu-builders/issue/COW-587/07-metrics-collection-framework](https://linear.app/bleu-builders/issue/COW-587/07-metrics-collection-framework)
- Identifier: COW-587
- Status: Done
- Priority: High
- Assignee: jefferson@bleu.studio
- Project: [cow-performance-testing-suite](https://linear.app/bleu-builders/project/cow-performance-testing-suite-76a5f7d55e4d).
- Project milestone: M2 — Performance Benchmarking
- Created: 2026-01-13T14:15:32.744Z
- Updated: 2026-01-29T19:30:00.000Z
