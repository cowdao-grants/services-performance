# Troubleshooting Guide

Comprehensive error reference and diagnostic procedures for the CoW Performance Testing Suite.

## Quick Diagnostic Checklist

Before diving into specific errors:

```bash
# 1. Check CLI version
cow-perf version

# 2. Verify Docker services running
docker compose ps

# 3. Check Anvil chain
cast block-number --rpc-url http://localhost:8545

# 4. Test orderbook API
curl http://localhost:8080/api/v1/version

# 5. Check database connectivity
docker exec $(docker ps -qf "name=db") pg_isready -U postgres
```

---

## Error Reference by Category

### Configuration Errors

#### BaselineValidationError

**Error:** `"Missing required fields: id, name"`
- **Cause:** Baseline file is missing required metadata fields
- **Solution:** Ensure baseline was saved correctly with `--save-baseline` flag
- **Example:**
  ```bash
  cow-perf run --config scenario.yml --save-baseline "v1.0"
  ```

**Error:** `"Baseline schema version {version} is newer than supported"`
- **Cause:** Baseline created with newer version of cow-perf
- **Solution:** Upgrade cow-perf: `pip install --upgrade cow-performance`

**Error:** `"Invalid 'created_at' field"`
- **Cause:** Baseline file corrupted or manually edited incorrectly
- **Solution:** Re-create baseline from a fresh test run

**Error:** `"Invalid 'tags' field: expected list"`
- **Cause:** Tags must be a list, not a string
- **Solution:** Use `--baseline-tags "tag1,tag2"` or in YAML: `tags: [tag1, tag2]`

#### InheritanceError

**Error:** `"Parent scenario not found: {parent}"`
- **Cause:** Scenario uses `extends:` but parent file doesn't exist
- **Solution:**
  ```yaml
  # Verify parent path is correct
  extends: "./parent-scenario.yml"  # Relative to current file
  # OR
  extends: "configs/scenarios/base.yml"  # Absolute from project root
  ```

**Error:** `"Parent scenario must be a dictionary"`
- **Cause:** Parent YAML file is malformed or empty
- **Solution:** Validate parent YAML syntax: `yamllint parent-scenario.yml`

#### CircularDependencyError

**Error:** `"Circular dependency detected"`
- **Cause:** Scenario inheritance creates a loop (A extends B extends A)
- **Solution:** Review inheritance chain and remove circular reference
- **Example of circular dependency:**
  ```yaml
  # scenario-a.yml extends scenario-b.yml
  # scenario-b.yml extends scenario-a.yml ❌
  ```

#### ProfileError

**Error:** `"Profile '{name}' not found"`
- **Cause:** Using `--profile` flag but profile not defined in config
- **Solution:** Add profile to scenario or config file:
  ```yaml
  profiles:
    staging:
      num_traders: 5
      duration: 60
    production:
      num_traders: 20
      duration: 300
  ```
- **List available profiles:** Check YAML file for `profiles:` section

**Error:** `"No profiles defined in configuration"`
- **Cause:** Using `--profile` flag but no `profiles:` section exists
- **Solution:** Remove `--profile` flag or add profiles section

#### TemplateError

**Error:** `"Template '{name}' not found"`
- **Cause:** Template doesn't exist in template directories
- **Solution:** List available templates: `cow-perf scenarios --list-templates`
- **Template locations:** `configs/scenarios/templates/`

**Error:** `"Required parameter '${param}' not provided"`
- **Cause:** Template requires parameter without default value
- **Solution:** Provide parameter in scenario file:
  ```yaml
  template: sustained-load
  parameters:
    test_name: "My Test"  # Required parameter
    duration: 600         # Required parameter
  ```

**Error:** `"Failed to parse template"`
- **Cause:** Template YAML file has syntax errors
- **Solution:** Validate template YAML: `yamllint templates/template-name.yml`

#### DefaultsError

**Error:** `"Project defaults must be a dictionary"`
- **Cause:** `.cow-perf-defaults.yml` file is malformed
- **Solution:** Validate YAML syntax or delete file to use built-in defaults

---

### Order Validation Errors

#### OrderValidationError - Address Validation

**Error:** `"owner is not a valid Ethereum address"`
- **Cause:** Owner field doesn't match Ethereum address format
- **Solution:** Addresses must be 42-character hex strings starting with `0x`
- **Example:** `0x1234567890123456789012345678901234567890`

**Error:** `"sellToken is required"`
- **Cause:** Required field is missing or empty
- **Solution:** Ensure all required fields are provided

#### OrderValidationError - Amount Validation

**Error:** `"sellAmount must be positive"`
- **Cause:** Amount is zero or negative
- **Solution:** Use positive integers for token amounts (in wei/smallest unit)
- **Example:** `sellAmount: "1000000000000000000"` (1 ETH in wei)

#### OrderValidationError - Timestamp Validation

**Error:** `"validTo must be in the future"`
- **Cause:** Order expiry timestamp is in the past
- **Solution:** Use future timestamps or relative times
- **Example:** `validTo: ${now + 3600}` (expires in 1 hour)

#### OrderValidationError - AppData Validation

**Error:** `"appData must be 32 bytes (66 characters with 0x prefix)"`
- **Cause:** appData has incorrect length
- **Solution:** appData must be exactly 32 bytes as hex: `0x` + 64 hex characters
- **Example:** `0x0000000000000000000000000000000000000000000000000000000000000001`

**Error:** `"AppData hash mismatch"`
- **Cause:** Computed hash doesn't match provided appData
- **Solution:** Regenerate appData or verify JSON content matches

---

### Runtime Errors

#### Docker Service Issues

**Error:** Services not starting
- **Check logs:** `docker compose logs -f orderbook`
- **Common causes:**
  - Port conflicts (8080, 8545 already in use)
  - Insufficient memory
  - Previous containers not cleaned up
- **Solution:**
  ```bash
  # Stop and remove old containers
  docker compose down

  # Start fresh
  docker compose up -d

  # Check status
  docker compose ps
  ```

**Error:** "unhealthy" status on orderbook
- **Cause:** Rust compilation in progress (first startup)
- **Solution:** Wait 5-10 minutes, check logs for compilation progress
- **Command:** `docker compose logs -f orderbook | grep -i compiling`

#### Chain Connection Issues

**Error:** `"Wallet funding failed: connection refused"`
- **Cause:** Anvil (chain container) not running
- **Solution:**
  ```bash
  # Check chain status
  docker compose ps chain

  # Restart chain
  docker compose restart chain

  # Test RPC
  cast block-number --rpc-url http://localhost:8545
  ```

**Error:** Orders not filling (0% fill rate)
- **Cause:** Normal in Anvil fork mode (events don't sync)
- **Solution:** Chain reconciliation runs automatically after tests
- **Verify:** Check test output for "Chain reconciliation complete" message
- **See:** [Known Limitations](../README.md#known-limitations)

#### API Connection Issues

**Error:** `"Connection refused to http://localhost:8080"`
- **Cause:** Orderbook API not ready
- **Solution:**
  ```bash
  # Check orderbook status
  curl http://localhost:8080/api/v1/version

  # Check logs
  docker compose logs orderbook

  # Restart if unhealthy
  docker compose restart orderbook
  ```

**Error:** `"API timeout after 30 seconds"`
- **Cause:** Orderbook overloaded or database slow
- **Solution:**
  - Reduce test load (fewer traders or lower rate)
  - Check database performance: `docker stats`
  - Increase timeout: Configure in orderbook service

---

### Test Failures

#### Low Success Rate

**Symptom:** Success rate < 80%
- **Possible causes:**
  1. Load too high for environment
  2. Token balances insufficient
  3. Solver not finding solutions
  4. Rate limiting active
- **Diagnostic steps:**
  ```bash
  # Check resource usage
  docker stats

  # Check solver logs
  docker compose logs solver-baseline-1

  # Check for rate limiting
  docker compose logs orderbook | grep -i "rate limit"
  ```
- **Solutions:**
  - Reduce num_traders or base_rate
  - Increase wallet token balances
  - Check solver configuration in driver.toml

#### High Latency

**Symptom:** P95 latency > 30 seconds
- **Possible causes:**
  1. Underpowered hardware
  2. Solver performance issues
  3. Database bottleneck
  4. Network issues
- **Diagnostic steps:**
  ```bash
  # Monitor resource usage
  docker stats

  # Check for CPU/memory constraints
  # CPU should be < 80%, Memory < 90%
  ```
- **Solutions:**
  - Allocate more Docker resources
  - Use simpler order types (market only)
  - Reduce concurrent load

---

## Diagnostic Procedures

### Test Run Diagnostics

**Before running a test:**
```bash
# 1. Verify all services healthy
docker compose ps
# All should show "healthy" or "running"

# 2. Check available resources
docker system df
# Ensure sufficient disk space

# 3. Verify scenario file
cow-perf scenarios --validate my-scenario.yml
```

**During a test:**
```bash
# Monitor in real-time
docker stats

# Check for errors
docker compose logs -f --tail=50

# Monitor Prometheus metrics
open http://localhost:9091/metrics
```

**After a failed test:**
```bash
# Check logs for errors
docker compose logs orderbook | grep -i error
docker compose logs autopilot | grep -i error
docker compose logs driver | grep -i error

# Check database state
docker exec -it $(docker ps -qf "name=db") psql -U postgres -d database -c "SELECT COUNT(*) FROM orders;"

# Review test results
cat ~/.cow-perf/results/latest-result.json | jq .
```

### Recovery Procedures

**Reset to clean state:**
```bash
# Stop all services
docker compose down

# Remove volumes (deletes all data)
docker compose down -v

# Clean Docker system
docker system prune -f

# Restart fresh
docker compose up -d

# Wait for services to be healthy
watch -n 2 'docker compose ps'
```

**Clear stuck orders:**
```bash
# Connect to database
docker exec -it $(docker ps -qf "name=db") psql -U postgres -d database

# Clear orders table
DELETE FROM orders;

# Restart services
docker compose restart orderbook autopilot
```

**Reset Anvil chain state:**
```bash
# Restart chain (creates new fork)
docker compose restart chain

# Wait for sync
sleep 10

# Verify block number reset
cast block-number --rpc-url http://localhost:8545
```

---

## Performance Tuning

### Insufficient Resources

**Symptoms:**
- High CPU/memory usage
- Container OOM kills
- Slow response times

**Solutions:**
```bash
# Check Docker resource limits
docker info | grep -i memory
docker info | grep -i cpu

# Increase Docker Desktop resources:
# Settings → Resources → Adjust CPU/Memory

# For Docker Engine, edit daemon.json
```

### Database Performance

**Symptoms:**
- Slow API responses
- Query timeouts
- Growing memory usage

**Solutions:**
```bash
# Monitor database performance
docker stats | grep db

# Check connection count
docker exec $(docker ps -qf "name=db") psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Restart database if needed
docker compose restart db
```

---

## Common Questions

**Q: Why do I see 0% fill rate during tests?**
A: This is expected in Anvil fork mode. Chain reconciliation runs automatically after tests to show actual on-chain fill rate. See [Known Limitations](../README.md#known-limitations).

**Q: How do I know if my test succeeded?**
A: Check the test report verdict:
- SUCCESS: All success criteria met
- WARNING: Some issues but not critical
- FAILURE: Critical issues detected

**Q: What resources do I need?**
A: Minimum: 4 GB RAM, 2 CPU cores, 10 GB disk
   Recommended: 8 GB RAM, 4 CPU cores, 20 GB disk

**Q: How long should tests run?**
A: Minimum 2 minutes for valid statistics, 5-10 minutes for reliable benchmarks, 30+ minutes for stability testing.

---

## Getting Help

**Check documentation:**
- [CLI Reference](cli.md)
- [Scenario User Guide](scenario-user-guide.md)
- [Configuration Reference](configuration-reference.md)

**Enable debug logging:**
```bash
cow-perf --verbose run --config scenario.yml
```

**Report issues:**
- GitHub Issues: https://github.com/cowprotocol/cow-performance-testing-suite/issues
- Include: error message, logs, scenario file, system info

---

## See Also

- [Operations Guide](operations.md) - Disk management and maintenance
- [Wallet Funding](wallet-funding.md) - Wallet funding troubleshooting
- [Known Limitations](../README.md#known-limitations) - Anvil event sync issue
