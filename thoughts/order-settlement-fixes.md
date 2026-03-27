# Order Settlement Fixes

## Issues Encountered and Fixed

### 1. Missing Order Priority Configuration
Added three order priority strategies to `configs/driver.toml`:
- `creation-timestamp`
- `external-price`
- `own-quotes`

Without these, the driver couldn't properly route orders through the auction system.

### 2. Solver Endpoint Naming Mismatch
Changed solver name in `configs/driver.toml` from `"solver-baseline-1"` to `"baseline"` to match the endpoint path `/baseline` expected by autopilot and orderbook services.

### 3. HTTP Timeout Issues
Reduced autopilot's `--solve-deadline` from 120s to 5s in `docker-compose.yml`. The autopilot has a hardcoded 10-second HTTP timeout, so the driver needs to complete within that window.

### 4. Exponential Gas Price Bug (Main Issue)
**Root Cause**: `SUBMISSION_DEADLINE=300` in autopilot configuration caused the driver to calculate gas prices using `current_gas_price * 1.13^300` ≈ 35 quadrillion multiplier.

**Fix**: Changed `SUBMISSION_DEADLINE=300` to `SUBMISSION_DEADLINE=5` (5 blocks ≈ 50 seconds).

**Result**: Gas prices became reasonable (`1.13^5` ≈ 1.84x), and orders successfully settled on-chain.

## Outcome
First order filled successfully in 24 seconds with realistic gas prices.
