# Implementation Plan: Order Submission Strategies

**Issue**: M1 Issue 06 - Order Submission Strategies
**Date**: 2026-01-27
**Status**: Draft

## Overview

This plan covers the implementation of additional order submission strategies and rate limiting capabilities for the CoW Performance Testing Suite. The goal is to expand the existing `trader_simulator.py` to support more realistic trading patterns and add configurable rate limiting at the orchestrator level.

## Current State Analysis

### What Exists

**Trading Patterns** (in `trader_simulator.py`):
- `CONSTANT_RATE`: Fixed interval between orders
- `RANDOM_INTERVAL`: Random intervals within a range
- `BURST`: Bursts of activity followed by quiet periods
- `TIME_BASED`: More active during certain periods

**Architecture**:
- Enum-based pattern selection (`TradingPattern` enum)
- Pattern-specific loop methods (`_constant_rate_loop`, `_burst_pattern_loop`, etc.)
- Configuration via `TraderBehaviorConfig` dataclass with validation in `__post_init__`
- Order cleanup loop for managing open orders per wallet
- Multi-trader coordination via `TraderOrchestrator` with staggered startup

**Configuration Parameters**:
- `base_rate`: Orders per minute
- Pattern-specific params: `min_interval`, `max_interval`, `burst_size`, `quiet_period`, `active_hours`, etc.
- Order type distribution: market, limit, TWAP, stop-loss, good-after-time ratios

### What's Missing

**Trading Patterns**:
- `RAMP_UP`: Gradually increase order rate from start to target
- `RAMP_DOWN`: Gradually decrease order rate from start to target
- `SPIKE`: Sudden burst of activity with configurable spike parameters
- `POISSON`: Poisson distribution for realistic random intervals

**Rate Limiting**:
- No global rate limiter across all traders
- No per-trader rate limiter configuration
- No backpressure handling from API responses
- No circuit breaker pattern for API failures

**Strategy Features**:
- No strategy composition or switching
- No per-trader strategy assignment (all traders use same pattern)

## Desired End State

### New Trading Patterns

1. **RAMP_UP**: Linearly or exponentially increase submission rate
   - Start rate, target rate, ramp duration
   - Support linear and exponential curves
   - Useful for gradual load increase testing

2. **RAMP_DOWN**: Linearly or exponentially decrease submission rate
   - Start rate, target rate, ramp duration
   - Mirror of RAMP_UP for cooldown scenarios

3. **SPIKE**: Sudden burst with recovery
   - Normal rate, spike rate, spike duration, recovery time
   - Simulates sudden market activity events

4. **POISSON**: Statistically realistic random intervals
   - Lambda parameter (events per time unit)
   - More realistic than uniform random intervals

### Rate Limiting

1. **Per-Trader Rate Limiter**:
   - Configurable max orders per second/minute per trader
   - Prevents individual trader from exceeding limits
   - Helps avoid `tooManyLimitOrders` API errors

2. **Global Rate Limiter**:
   - Configurable max orders per second/minute across all traders
   - Controls total system load
   - Implemented at orchestrator level

3. **Configuration**:
   - Enable/disable per-trader and global limiters independently
   - Configure limits in config file
   - Token bucket or leaky bucket algorithm

### Enhanced Configuration

- Extend `TraderBehaviorConfig` with new pattern parameters
- Add `RateLimitConfig` for rate limiting settings
- Support per-trader pattern assignment (optional enhancement)

## What We're NOT Doing

1. **NOT creating abstract strategy base class**: Keeping the enum-based dispatch pattern for simplicity
2. **NOT implementing strategy composition**: Single pattern per trader (can be future enhancement)
3. **NOT implementing strategy switching**: Pattern set at trader creation time
4. **NOT implementing backpressure handling**: Will be addressed in separate ticket if needed
5. **NOT implementing circuit breaker**: Out of scope for this issue
6. **NOT breaking backwards compatibility**: All existing patterns remain functional

## Implementation Approach

### Design Decisions (based on user input)

1. **Expand existing `trader_simulator.py`**: Don't create new abstraction layers
2. **Rate limiting at orchestrator level**: Orchestrator manages both per-trader and global limits
3. **Configuration-driven**: All new features configurable via dataclasses
4. **Keep validation pattern**: Use `__post_init__` for parameter validation

### Key Files to Modify

1. `src/cow_performance/load_generation/trader_simulator.py`:
   - Add new patterns to `TradingPattern` enum
   - Extend `TraderBehaviorConfig` with new parameters
   - Add pattern-specific loop methods

2. `src/cow_performance/load_generation/trader_orchestrator.py`:
   - Add `RateLimitConfig` dataclass
   - Implement `RateLimiter` class (token bucket algorithm)
   - Integrate rate limiting into order submission flow

3. `tests/unit/test_trader_simulator.py`: Add unit tests for new patterns
4. `tests/unit/test_rate_limiter.py`: New file for rate limiter tests
5. `tests/integration/test_user_simulation.py`: Integration tests for rate limiting

### Code Structure Patterns

**Pattern-specific loop method signature**:
```python
async def _<pattern_name>_loop(self, duration: float) -> None:
    """Run trading loop with <pattern> pattern."""
    end_time = time.time() + duration
    config = self.behavior_config

    # Pattern-specific implementation
    while self._running and time.time() < end_time:
        # Generate and submit orders based on pattern
        pass
```

**Configuration validation**:
```python
@dataclass
class TraderBehaviorConfig:
    # ... existing fields ...

    # New pattern parameters
    ramp_start_rate: float | None = None
    ramp_target_rate: float | None = None
    ramp_duration: float | None = None
    ramp_curve: str = "linear"  # "linear" or "exponential"

    spike_normal_rate: float | None = None
    spike_burst_rate: float | None = None
    spike_duration: float | None = None

    poisson_lambda: float | None = None

    def __post_init__(self) -> None:
        # ... existing validation ...

        # Validate ramp parameters
        if self.pattern in (TradingPattern.RAMP_UP, TradingPattern.RAMP_DOWN):
            if self.ramp_start_rate is None or self.ramp_target_rate is None:
                raise ValueError(f"{self.pattern} requires ramp_start_rate and ramp_target_rate")
            # ... more validation ...
```

## Implementation Phases

### Phase 1: Add RAMP_UP and RAMP_DOWN Patterns

**Estimated Duration**: 4 hours

**Changes**:

1. **Add to TradingPattern enum** (`trader_simulator.py:22-28`):
   ```python
   class TradingPattern(str, Enum):
       # ... existing patterns ...
       RAMP_UP = "ramp_up"
       RAMP_DOWN = "ramp_down"
   ```

2. **Extend TraderBehaviorConfig** (`trader_simulator.py:32-86`):
   ```python
   @dataclass
   class TraderBehaviorConfig:
       # ... existing fields ...

       # Ramp parameters
       ramp_start_rate: float | None = None  # Orders per minute
       ramp_target_rate: float | None = None  # Orders per minute
       ramp_duration: float = 300.0  # Duration in seconds (default 5 minutes)
       ramp_curve: str = "linear"  # "linear" or "exponential"
   ```

3. **Add validation in __post_init__**:
   ```python
   # Validate ramp parameters
   if self.pattern in (TradingPattern.RAMP_UP, TradingPattern.RAMP_DOWN):
       if self.ramp_start_rate is None:
           raise ValueError(f"{self.pattern} requires ramp_start_rate")
       if self.ramp_target_rate is None:
           raise ValueError(f"{self.pattern} requires ramp_target_rate")
       if self.ramp_start_rate <= 0 or self.ramp_target_rate <= 0:
           raise ValueError("Ramp rates must be positive")
       if self.ramp_duration <= 0:
           raise ValueError("Ramp duration must be positive")
       if self.ramp_curve not in ("linear", "exponential"):
           raise ValueError("ramp_curve must be 'linear' or 'exponential'")
   ```

4. **Implement _ramp_up_loop method** (after line 464):
   ```python
   async def _ramp_up_loop(self, duration: float) -> None:
       """Run trading loop with ramp-up pattern."""
       end_time = time.time() + duration
       config = self.behavior_config
       start_time = time.time()
       ramp_end_time = start_time + config.ramp_duration

       while self._running and time.time() < end_time:
           current_time = time.time()

           # Calculate current rate based on progress
           if current_time < ramp_end_time:
               progress = (current_time - start_time) / config.ramp_duration

               if config.ramp_curve == "linear":
                   # Linear interpolation
                   current_rate = (
                       config.ramp_start_rate +
                       (config.ramp_target_rate - config.ramp_start_rate) * progress
                   )
               else:  # exponential
                   # Exponential curve
                   current_rate = config.ramp_start_rate * (
                       (config.ramp_target_rate / config.ramp_start_rate) ** progress
                   )
           else:
               # After ramp completes, use target rate
               current_rate = config.ramp_target_rate

           await self._generate_and_submit_order()

           # Calculate interval from rate (orders per minute)
           interval = 60.0 / current_rate
           await asyncio.sleep(interval)
   ```

5. **Implement _ramp_down_loop method** (similar to ramp_up but reversed):
   ```python
   async def _ramp_down_loop(self, duration: float) -> None:
       """Run trading loop with ramp-down pattern."""
       # Similar to ramp_up but with start and target swapped
       end_time = time.time() + duration
       config = self.behavior_config
       start_time = time.time()
       ramp_end_time = start_time + config.ramp_duration

       while self._running and time.time() < end_time:
           current_time = time.time()

           if current_time < ramp_end_time:
               progress = (current_time - start_time) / config.ramp_duration

               if config.ramp_curve == "linear":
                   # Start high, end low
                   current_rate = (
                       config.ramp_start_rate -
                       (config.ramp_start_rate - config.ramp_target_rate) * progress
                   )
               else:  # exponential
                   current_rate = config.ramp_start_rate * (
                       (config.ramp_target_rate / config.ramp_start_rate) ** progress
                   )
           else:
               current_rate = config.ramp_target_rate

           await self._generate_and_submit_order()

           interval = 60.0 / current_rate
           await asyncio.sleep(interval)
   ```

6. **Add to run() dispatch** (`trader_simulator.py:466-497`):
   ```python
   elif self.behavior_config.pattern == TradingPattern.RAMP_UP:
       await self._ramp_up_loop(duration)
   elif self.behavior_config.pattern == TradingPattern.RAMP_DOWN:
       await self._ramp_down_loop(duration)
   ```

**Testing**:
- Unit test: Verify rate increases/decreases over time
- Unit test: Verify linear vs exponential curves produce different rates
- Unit test: Verify validation catches invalid parameters
- Integration test: Run short ramp-up simulation and verify order distribution

**Success Criteria**:
- [x] RAMP_UP and RAMP_DOWN added to TradingPattern enum
- [x] Configuration parameters added and validated
- [x] Loop methods implemented with linear and exponential curves
- [ ] Unit tests pass with >90% coverage
- [ ] Manual test: Run 5-minute ramp-up from 6 to 30 orders/min successfully

### Phase 2: Add SPIKE Pattern

**Estimated Duration**: 3 hours

**Changes**:

1. **Add to TradingPattern enum**:
   ```python
   SPIKE = "spike"
   ```

2. **Extend TraderBehaviorConfig**:
   ```python
   # Spike parameters
   spike_normal_rate: float | None = None  # Normal orders per minute
   spike_burst_rate: float | None = None  # Burst orders per minute
   spike_duration: float = 30.0  # Duration of spike in seconds
   spike_recovery_time: float = 60.0  # Time between spikes
   ```

3. **Add validation**:
   ```python
   if self.pattern == TradingPattern.SPIKE:
       if self.spike_normal_rate is None or self.spike_burst_rate is None:
           raise ValueError("SPIKE pattern requires spike_normal_rate and spike_burst_rate")
       if self.spike_normal_rate <= 0 or self.spike_burst_rate <= 0:
           raise ValueError("Spike rates must be positive")
       if self.spike_burst_rate <= self.spike_normal_rate:
           raise ValueError("spike_burst_rate must be greater than spike_normal_rate")
       if self.spike_duration <= 0:
           raise ValueError("spike_duration must be positive")
   ```

4. **Implement _spike_loop method**:
   ```python
   async def _spike_loop(self, duration: float) -> None:
       """Run trading loop with spike pattern."""
       end_time = time.time() + duration
       config = self.behavior_config

       while self._running and time.time() < end_time:
           # Normal rate period
           spike_start = time.time() + config.spike_recovery_time

           while self._running and time.time() < min(spike_start, end_time):
               await self._generate_and_submit_order()
               interval = 60.0 / config.spike_normal_rate
               await asyncio.sleep(interval)

           if time.time() >= end_time:
               break

           # Spike period
           spike_end = time.time() + config.spike_duration

           while self._running and time.time() < min(spike_end, end_time):
               await self._generate_and_submit_order()
               interval = 60.0 / config.spike_burst_rate
               await asyncio.sleep(interval)
   ```

5. **Add to run() dispatch**:
   ```python
   elif self.behavior_config.pattern == TradingPattern.SPIKE:
       await self._spike_loop(duration)
   ```

**Testing**:
- Unit test: Verify alternating normal/spike rates
- Unit test: Verify spike rate higher than normal rate
- Integration test: Monitor order timestamps match spike pattern

**Success Criteria**:
- [x] SPIKE pattern added and functional
- [x] Validation ensures spike rate > normal rate
- [ ] Unit tests pass
- [ ] Manual test: Run spike pattern and observe rate changes in logs

### Phase 3: Add POISSON Pattern

**Estimated Duration**: 3 hours

**Changes**:

1. **Add to TradingPattern enum**:
   ```python
   POISSON = "poisson"
   ```

2. **Extend TraderBehaviorConfig**:
   ```python
   # Poisson parameters
   poisson_lambda: float | None = None  # Events per minute (rate parameter)
   ```

3. **Add validation**:
   ```python
   if self.pattern == TradingPattern.POISSON:
       if self.poisson_lambda is None:
           raise ValueError("POISSON pattern requires poisson_lambda")
       if self.poisson_lambda <= 0:
           raise ValueError("poisson_lambda must be positive")
   ```

4. **Implement _poisson_loop method**:
   ```python
   async def _poisson_loop(self, duration: float) -> None:
       """Run trading loop with Poisson distribution for intervals."""
       import numpy as np

       end_time = time.time() + duration
       config = self.behavior_config

       # Convert lambda from events per minute to events per second
       lambda_per_second = config.poisson_lambda / 60.0

       while self._running and time.time() < end_time:
           await self._generate_and_submit_order()

           # Generate Poisson-distributed interval
           # Inter-arrival times follow exponential distribution
           interval = np.random.exponential(1.0 / lambda_per_second)

           await asyncio.sleep(interval)
   ```

5. **Add to run() dispatch**:
   ```python
   elif self.behavior_config.pattern == TradingPattern.POISSON:
       await self._poisson_loop(duration)
   ```

6. **Update dependencies** (`pyproject.toml`):
   ```toml
   dependencies = [
       # ... existing dependencies ...
       "numpy>=1.26.0",
   ]
   ```

**Testing**:
- Unit test: Verify intervals follow exponential distribution
- Unit test: Verify mean rate matches lambda parameter
- Statistical test: Run for 1000 orders, verify distribution properties

**Success Criteria**:
- [x] POISSON pattern added
- [x] numpy dependency added (already present in pyproject.toml)
- [ ] Unit tests verify statistical properties
- [ ] Manual test: Run Poisson pattern, verify intervals are variable but average rate correct

### Phase 4: Implement Rate Limiting Infrastructure

**Estimated Duration**: 5 hours

**Changes**:

1. **Create RateLimitConfig dataclass** (in `trader_orchestrator.py` before `TraderOrchestrator`):
   ```python
   @dataclass
   class RateLimitConfig:
       """Configuration for rate limiting."""

       # Per-trader rate limiting
       enable_per_trader_limit: bool = False
       max_orders_per_trader_per_second: float | None = None
       max_orders_per_trader_per_minute: float | None = None

       # Global rate limiting
       enable_global_limit: bool = False
       max_orders_global_per_second: float | None = None
       max_orders_global_per_minute: float | None = None

       # Algorithm settings
       algorithm: str = "token_bucket"  # "token_bucket" or "leaky_bucket"
       burst_allowance: float = 1.5  # Allow burst up to 1.5x the rate

       def __post_init__(self) -> None:
           """Validate configuration."""
           if self.enable_per_trader_limit:
               if (self.max_orders_per_trader_per_second is None and
                   self.max_orders_per_trader_per_minute is None):
                   raise ValueError(
                       "Per-trader rate limit enabled but no limit specified"
                   )

           if self.enable_global_limit:
               if (self.max_orders_global_per_second is None and
                   self.max_orders_global_per_minute is None):
                   raise ValueError(
                       "Global rate limit enabled but no limit specified"
                   )

           if self.algorithm not in ("token_bucket", "leaky_bucket"):
               raise ValueError(
                   f"Unknown rate limit algorithm: {self.algorithm}"
               )
   ```

2. **Implement RateLimiter class** (in `trader_orchestrator.py`):
   ```python
   class RateLimiter:
       """Token bucket rate limiter."""

       def __init__(
           self,
           rate_per_second: float,
           burst_allowance: float = 1.5,
       ):
           """
           Initialize rate limiter.

           Args:
               rate_per_second: Maximum sustained rate (operations per second)
               burst_allowance: Multiplier for burst capacity (e.g., 1.5 = 50% burst)
           """
           self.rate_per_second = rate_per_second
           self.capacity = rate_per_second * burst_allowance
           self.tokens = self.capacity
           self.last_update = time.time()
           self._lock = asyncio.Lock()

       async def acquire(self, tokens: int = 1) -> bool:
           """
           Try to acquire tokens from the bucket.

           Args:
               tokens: Number of tokens to acquire

           Returns:
               True if tokens acquired, False if rate limit exceeded
           """
           async with self._lock:
               now = time.time()
               elapsed = now - self.last_update

               # Refill tokens based on elapsed time
               self.tokens = min(
                   self.capacity,
                   self.tokens + elapsed * self.rate_per_second
               )
               self.last_update = now

               # Try to acquire
               if self.tokens >= tokens:
                   self.tokens -= tokens
                   return True
               else:
                   return False

       async def wait_for_token(self, tokens: int = 1) -> None:
           """
           Wait until tokens are available.

           Args:
               tokens: Number of tokens to acquire
           """
           while True:
               if await self.acquire(tokens):
                   return

               # Calculate wait time
               wait_time = tokens / self.rate_per_second
               await asyncio.sleep(wait_time)
   ```

3. **Add rate_limit_config to TraderOrchestrator** (`trader_orchestrator.py`):
   ```python
   class TraderOrchestrator:
       def __init__(
           self,
           # ... existing parameters ...
           rate_limit_config: RateLimitConfig | None = None,
       ):
           # ... existing initialization ...
           self.rate_limit_config = rate_limit_config or RateLimitConfig()

           # Initialize rate limiters
           self._global_limiter: RateLimiter | None = None
           self._per_trader_limiters: dict[str, RateLimiter] = {}

           if self.rate_limit_config.enable_global_limit:
               rate = self._calculate_rate_per_second(
                   self.rate_limit_config.max_orders_global_per_second,
                   self.rate_limit_config.max_orders_global_per_minute,
               )
               self._global_limiter = RateLimiter(
                   rate_per_second=rate,
                   burst_allowance=self.rate_limit_config.burst_allowance,
               )

       def _calculate_rate_per_second(
           self,
           per_second: float | None,
           per_minute: float | None,
       ) -> float:
           """Calculate rate per second from config."""
           if per_second is not None:
               return per_second
           elif per_minute is not None:
               return per_minute / 60.0
           else:
               raise ValueError("No rate specified")
   ```

4. **Create per-trader limiters when needed**:
   ```python
   def _get_or_create_trader_limiter(self, trader_address: str) -> RateLimiter | None:
       """Get or create rate limiter for trader."""
       if not self.rate_limit_config.enable_per_trader_limit:
           return None

       if trader_address not in self._per_trader_limiters:
           rate = self._calculate_rate_per_second(
               self.rate_limit_config.max_orders_per_trader_per_second,
               self.rate_limit_config.max_orders_per_trader_per_minute,
           )
           self._per_trader_limiters[trader_address] = RateLimiter(
               rate_per_second=rate,
               burst_allowance=self.rate_limit_config.burst_allowance,
           )

       return self._per_trader_limiters[trader_address]
   ```

5. **Integrate rate limiting into order submission**: This will be done by wrapping the trader's order submission. We'll need to modify how the orchestrator coordinates with traders. Instead of traders directly submitting, they'll request permission from orchestrator.

   Add method to orchestrator:
   ```python
   async def request_submission_permission(self, trader_address: str) -> bool:
       """
       Request permission to submit an order.

       Checks both global and per-trader rate limits.

       Args:
           trader_address: Address of the trader requesting permission

       Returns:
           True if submission allowed, False if rate limited
       """
       # Check per-trader limit first
       if self.rate_limit_config.enable_per_trader_limit:
           trader_limiter = self._get_or_create_trader_limiter(trader_address)
           if trader_limiter and not await trader_limiter.acquire():
               return False

       # Check global limit
       if self.rate_limit_config.enable_global_limit and self._global_limiter:
           if not await self._global_limiter.acquire():
               return False

       return True
   ```

**Testing**:
- Unit test: RateLimiter token bucket algorithm
- Unit test: Rate limiting configuration validation
- Unit test: Per-trader limiter creation
- Integration test: Verify rate limiting enforces limits

**Success Criteria**:
- [x] RateLimitConfig and RateLimiter classes implemented
- [x] Token bucket algorithm correctly limits rate
- [x] Configuration validation works
- [ ] Unit tests pass

### Phase 5: Integrate Rate Limiting with TraderSimulator

**Estimated Duration**: 4 hours

**Changes**:

1. **Add orchestrator reference to TraderSimulator** (`trader_simulator.py`):
   ```python
   class TraderSimulator:
       def __init__(
           self,
           # ... existing parameters ...
           orchestrator: Any | None = None,  # Type hint as Any to avoid circular import
       ):
           # ... existing initialization ...
           self.orchestrator = orchestrator
   ```

2. **Modify _generate_and_submit_order to check rate limits** (`trader_simulator.py:266`):
   ```python
   async def _generate_and_submit_order(self) -> None:
       """Generate and submit a single order with rate limiting."""
       try:
           # Check rate limits if orchestrator available
           if self.orchestrator is not None:
               allowed = await self.orchestrator.request_submission_permission(
                   self.trader.address
               )
               if not allowed:
                   # Rate limited, wait a bit and try again
                   await asyncio.sleep(0.1)
                   return

           # ... existing order generation code ...
       except Exception as e:
           # ... existing error handling ...
   ```

3. **Update TraderOrchestrator to pass self reference** (`trader_orchestrator.py`):
   ```python
   async def run_simulation(self, duration: float) -> SimulationMetrics:
       """Run the simulation."""
       # ... existing code ...

       # Create simulators with orchestrator reference
       simulators = []
       for trader in self.traders:
           simulator = TraderSimulator(
               trader=trader,
               factory=self.factory,
               behavior_config=self.behavior_config,
               api_client=self.api_client,
               order_cleanup_config=self.order_cleanup_config,
               orchestrator=self,  # Pass self reference
           )
           simulators.append(simulator)

       # ... rest of existing code ...
   ```

4. **Add rate limit metrics to SimulationMetrics** (`trader_orchestrator.py`):
   ```python
   @dataclass
   class SimulationMetrics:
       # ... existing fields ...

       # Rate limiting metrics
       total_rate_limit_hits: int = 0
       per_trader_rate_limit_hits: int = 0
       global_rate_limit_hits: int = 0
   ```

5. **Track rate limit hits in orchestrator**:
   ```python
   def __init__(self, ...):
       # ... existing initialization ...
       self._rate_limit_hits = {
           "per_trader": 0,
           "global": 0,
       }

   async def request_submission_permission(self, trader_address: str) -> bool:
       """Request permission with tracking."""
       # Check per-trader limit
       if self.rate_limit_config.enable_per_trader_limit:
           trader_limiter = self._get_or_create_trader_limiter(trader_address)
           if trader_limiter and not await trader_limiter.acquire():
               self._rate_limit_hits["per_trader"] += 1
               return False

       # Check global limit
       if self.rate_limit_config.enable_global_limit and self._global_limiter:
           if not await self._global_limiter.acquire():
               self._rate_limit_hits["global"] += 1
               return False

       return True
   ```

**Testing**:
- Integration test: Run simulation with per-trader limits, verify limit enforced
- Integration test: Run simulation with global limits, verify limit enforced
- Integration test: Run with both limits, verify both work together
- Integration test: Verify rate limit hit metrics tracked correctly

**Success Criteria**:
- [x] TraderSimulator integrates with orchestrator for rate limiting
- [x] Rate limits correctly prevent excessive submissions
- [x] Rate limit metrics tracked and reported
- [ ] Integration tests pass

### Phase 6: Comprehensive Testing and Documentation

**Estimated Duration**: 4 hours

**Changes**:

1. **Create comprehensive test file** (`tests/unit/test_trading_patterns.py`):
   ```python
   """Unit tests for all trading patterns."""

   import pytest
   from cow_performance.load_generation import (
       TraderSimulator,
       TraderBehaviorConfig,
       TradingPattern,
   )

   class TestRampUpPattern:
       """Tests for RAMP_UP pattern."""

       @pytest.fixture
       def ramp_up_config(self):
           return TraderBehaviorConfig(
               pattern=TradingPattern.RAMP_UP,
               ramp_start_rate=6.0,
               ramp_target_rate=30.0,
               ramp_duration=60.0,
               ramp_curve="linear",
           )

       @pytest.mark.asyncio
       async def test_ramp_up_increases_rate(self, ramp_up_config):
           """Test that rate increases over time."""
           # ... test implementation ...
   ```

2. **Create integration test** (`tests/integration/test_rate_limiting.py`):
   ```python
   """Integration tests for rate limiting."""

   import pytest
   from cow_performance.load_generation import (
       TraderOrchestrator,
       RateLimitConfig,
   )

   class TestRateLimiting:
       """Tests for rate limiting integration."""

       @pytest.mark.asyncio
       async def test_global_rate_limit_enforced(self):
           """Test that global rate limit is enforced."""
           # ... test implementation ...
   ```

3. **Add usage examples to README** (`README.md`):
   ```markdown
   ## Order Submission Strategies

   ### Available Patterns

   #### Ramp-Up
   Gradually increase submission rate over time:

   ```python
   config = TraderBehaviorConfig(
       pattern=TradingPattern.RAMP_UP,
       ramp_start_rate=6.0,  # Start at 6 orders/minute
       ramp_target_rate=30.0,  # Ramp up to 30 orders/minute
       ramp_duration=300.0,  # Over 5 minutes
       ramp_curve="linear",  # Linear increase
   )
   ```

   #### Rate Limiting
   Control submission rate with global and per-trader limits:

   ```python
   rate_config = RateLimitConfig(
       enable_global_limit=True,
       max_orders_global_per_second=10.0,
       enable_per_trader_limit=True,
       max_orders_per_trader_per_minute=100.0,
   )
   ```
   ```

4. **Update CHANGELOG**:
   ```markdown
   ## [Unreleased]

   ### Added
   - RAMP_UP and RAMP_DOWN trading patterns with linear/exponential curves
   - SPIKE trading pattern for simulating sudden bursts
   - POISSON trading pattern for realistic random intervals
   - Global rate limiting across all traders
   - Per-trader rate limiting
   - Rate limit metrics in simulation results
   ```

**Testing**:
- Run full test suite: `pytest tests/`
- Verify all new tests pass
- Check code coverage: `pytest --cov=src/cow_performance`
- Manual testing with example configurations

**Success Criteria**:
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Code coverage >85% for new code
- [ ] Documentation updated
- [ ] Manual testing successful

## Testing Strategy

### Unit Tests

**test_trading_patterns.py**:
- Test each new pattern independently
- Verify configuration validation
- Test rate calculations (linear, exponential)
- Test edge cases (zero duration, negative rates, etc.)

**test_rate_limiter.py**:
- Test token bucket algorithm
- Test burst allowance
- Test concurrent access
- Test wait_for_token method

**test_rate_limit_config.py**:
- Test configuration validation
- Test invalid configurations

### Integration Tests

**test_user_simulation.py** (extend existing):
- Test simulation with RAMP_UP pattern
- Test simulation with SPIKE pattern
- Test simulation with POISSON pattern
- Test simulation with rate limiting enabled
- Test combined patterns and rate limiting

**test_rate_limiting.py** (new):
- Test global rate limiting across multiple traders
- Test per-trader rate limiting
- Test rate limit hit metrics
- Test rate limiting doesn't break normal operation

### Manual Testing

1. **Ramp-Up Pattern**:
   - Run 10-minute simulation with ramp from 6 to 60 orders/min
   - Verify rate increases smoothly in logs
   - Compare linear vs exponential curves

2. **Spike Pattern**:
   - Run simulation with spike pattern
   - Verify rate changes visible in logs
   - Check order timestamps match expected pattern

3. **Poisson Pattern**:
   - Run simulation with Poisson distribution
   - Export order timestamps
   - Verify distribution properties with statistical analysis

4. **Rate Limiting**:
   - Run high-rate simulation with global limit
   - Verify submission rate capped at limit
   - Check rate limit hit metrics
   - Run with per-trader limit
   - Verify individual traders limited

## Success Criteria

### Automated Tests
- [x] All existing tests continue to pass
- [ ] Unit tests for RAMP_UP pattern pass (to be written)
- [ ] Unit tests for RAMP_DOWN pattern pass (to be written)
- [ ] Unit tests for SPIKE pattern pass (to be written)
- [ ] Unit tests for POISSON pattern pass (to be written)
- [ ] Unit tests for RateLimiter class pass (to be written)
- [ ] Unit tests for RateLimitConfig pass (to be written)
- [ ] Integration tests for rate limiting pass (to be written)
- [ ] Code coverage >85% for new code (pending test implementation)
- [x] No new type errors from mypy (only pre-existing errors remain)
- [x] No linting errors from ruff

### Manual Validation
- [ ] RAMP_UP: 5-minute ramp from 6 to 30 orders/min completes successfully
- [ ] RAMP_DOWN: 5-minute ramp from 30 to 6 orders/min completes successfully
- [ ] SPIKE: Spike pattern produces visible rate changes in logs
- [ ] POISSON: Order intervals are variable but average rate matches lambda
- [ ] Global rate limit: 10 traders with 60 orders/min each limited to global max
- [ ] Per-trader rate limit: Single trader cannot exceed configured limit
- [ ] Combined limits: Both limits work together without conflicts
- [ ] Metrics: Rate limit hit counts reported correctly
- [ ] Configuration: All new config parameters work as documented
- [ ] Backwards compatibility: All existing patterns still work

### Documentation
- [ ] README updated with new pattern examples
- [ ] README updated with rate limiting examples
- [ ] CHANGELOG updated
- [ ] Docstrings added for all new classes and methods
- [ ] Type hints correct for all new code

## Risk Mitigation

### Potential Issues

1. **Rate limiting too restrictive**:
   - Risk: Rate limits might prevent legitimate submissions
   - Mitigation: Make burst_allowance configurable, provide clear error messages

2. **Poisson pattern requires numpy**:
   - Risk: New dependency might conflict
   - Mitigation: Use widely-compatible numpy version, document requirement

3. **Circular import with orchestrator reference**:
   - Risk: Adding orchestrator to TraderSimulator might cause import issues
   - Mitigation: Use `TYPE_CHECKING` and type hints as strings if needed

4. **Performance overhead of rate limiting**:
   - Risk: Checking rate limits on every submission might slow down
   - Mitigation: Use asyncio.Lock efficiently, measure performance

5. **Backwards compatibility**:
   - Risk: New parameters might break existing configs
   - Mitigation: All new parameters have defaults, existing patterns unchanged

## Timeline Estimate

- Phase 1 (RAMP_UP/DOWN): 4 hours
- Phase 2 (SPIKE): 3 hours
- Phase 3 (POISSON): 3 hours
- Phase 4 (Rate Limiting Infrastructure): 5 hours
- Phase 5 (Integration): 4 hours
- Phase 6 (Testing & Docs): 4 hours

**Total Estimated Time**: 23 hours (~3 working days)

## Implementation Notes

1. **Start with Phase 1**: Get ramp patterns working first as they're most straightforward
2. **Test incrementally**: Run tests after each phase
3. **Manual verification**: Test each pattern manually before moving to next
4. **Rate limiting last**: Implement rate limiting after all patterns work
5. **Documentation concurrent**: Update docs as each phase completes

## Future Enhancements (Out of Scope)

- Strategy composition (e.g., ramp-up then spike)
- Dynamic strategy switching during simulation
- Backpressure handling from API responses
- Circuit breaker pattern for API failures
- Per-trader pattern assignment (different patterns for different traders)
- Machine learning-based patterns
- Historical market replay patterns

## References

- Ticket: `/issues/description/m1-issue-06-order-submission-strategies.md`
- Existing Implementation: `src/cow_performance/load_generation/trader_simulator.py`
- Orchestrator: `src/cow_performance/load_generation/trader_orchestrator.py`
- Test Examples: `tests/unit/test_order_factory.py`, `tests/unit/test_trader_account.py`
