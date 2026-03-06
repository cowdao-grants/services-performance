# COW-587.1: Foundation - Data Models & Storage

## Summary

Implement the foundational data models and storage infrastructure for the metrics collection framework.

## Deliverables

### 1. Metrics Data Models

- [ ] Define `OrderLifecycleMetrics` model with timestamps and calculated durations
- [ ] Define `APIMetrics` model (endpoint, method, response time, status, payload size)
- [ ] Define `ResourceMetrics` model (CPU, memory, network I/O, disk I/O)
- [ ] Define `TestRunMetrics` model (aggregate metrics for entire test)

### 2. Metrics Storage

- [ ] Implement in-memory metrics store using appropriate data structures
- [ ] Use `collections.deque` for time-series data with size limits
- [ ] Implement efficient lookups by order UID
- [ ] Support concurrent writes from multiple traders
- [ ] Implement thread-safe operations using `asyncio.Lock`
- [ ] Add metrics export functionality (JSON, CSV)

## Technical Notes

* Use Pydantic for data validation
* Use `dataclasses` or Pydantic models
* Consider circular buffers for memory efficiency

## Parent Issue

Part of COW-587: Metrics Collection Framework

## Metadata

- URL: https://linear.app/bleu-builders/issue/COW-609/cow-5871-foundation-data-models-and-storage
- Identifier: COW-609
- Status: In Progress
- Priority: Not set
- Estimate: 3 Points
- Assignee: jefferson@bleu.studio
- Project: cow-performance-testing-suite
- Project milestone: M2 — Performance Benchmarking
- Git Branch: jefferson/cow-609-cow-5871-foundation-data-models-storage
- Created: 2026-01-27T20:10:24.763Z
- Updated: 2026-01-27T23:39:19.967Z
