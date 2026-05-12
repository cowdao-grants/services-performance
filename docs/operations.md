# Operations Guide

Operational procedures for managing the CoW Performance Testing Suite, including disk management, troubleshooting, and maintenance.

## Disk Management

The Docker environment is optimized to prevent excessive disk usage, but monitoring and periodic cleanup are still recommended.

### Built-in Protections

The system includes several mechanisms to prevent disk accumulation:

- **Chain container (Anvil)**: Uses `--prune-history` flag to keep state in process memory only (no disk accumulation)
- **Container logs**: Limited to 10MB per file, max 3 files (30MB total per service)
- **Prometheus data**: Retention limited to 7 days and 1GB
- **Rust build artifacts**: Stored in Docker volumes (not on host disk)

### Monitoring Disk Usage

Check Docker disk usage regularly:

```bash
# Overall Docker disk usage summary
docker system df

# Detailed breakdown
docker system df -v

# Monitor specific container disk usage
docker stats --no-stream

# Check Docker volumes
docker volume ls
docker volume inspect services-performance_postgres-data
```

**Interpreting `docker system df` output:**
- **Images**: Docker images for CoW services (~2-5 GB)
- **Containers**: Running/stopped containers (usually minimal)
- **Local Volumes**: Persistent data (database, build caches)
- **Build Cache**: Intermediate build layers

### Cleanup Options

#### Quick Cleanup (Recommended)

For regular maintenance without data loss:

```bash
# Stop containers (preserves images and volumes)
docker compose down

# Remove stopped containers and dangling images
docker system prune -f

# Remove unused images (be careful with -a flag)
docker image prune -f
```

**What this removes:**
- Stopped containers
- Dangling images (untagged)
- Unused networks
- Build cache (dangling layers)

**What this preserves:**
- Running containers
- Tagged images
- Volumes (persistent data)

#### Deep Cleanup (Data Loss Warning)

**⚠️ WARNING:** This removes all data including databases and baselines!

Use when disk space is critical:

```bash
# Use the automated cleanup script (recommended)
./hack/cleanup-docker.sh

# Or manual deep cleanup
docker compose down -v
docker system prune -a -f --volumes
```

**What this removes:**
- All containers (running and stopped)
- All images (tagged and untagged)
- All volumes (⚠️ **INCLUDING DATABASE**)
- All networks
- All build cache

#### Selective Cleanup

Remove specific components:

```bash
# Remove specific container
docker compose rm -f orderbook

# Remove specific volume
docker volume rm services-performance_postgres-data

# Remove unused volumes only
docker volume prune -f

# Remove build cache only
docker builder prune -f
```

### After Cleanup

Restart services after cleanup:

```bash
docker compose up -d
```

> **Note**: First startup after cleanup may be slower due to:
> - Image rebuilding (5-10 minutes for orderbook compilation)
> - Database migrations
> - Chain fork synchronization

### Preventing Disk Issues

**Best practices:**

1. **Stop services when not testing:**
   ```bash
   docker compose down
   ```

2. **Run cleanup weekly:**
   ```bash
   docker system prune -f
   ```

3. **Monitor disk usage:**
   ```bash
   # Add to cron for daily monitoring
   docker system df
   ```

4. **Use dedicated test machine** with at least:
   - 50 GB free disk space
   - 16 GB RAM
   - 4 CPU cores

---

## Troubleshooting

### Services Failing to Start

**Symptoms:**
- Containers restart repeatedly
- "Unhealthy" status in `docker compose ps`
- Connection errors when running tests

**Diagnosis:**
```bash
# Check service status
docker compose ps

# View logs for specific service
docker compose logs orderbook
docker compose logs autopilot
docker compose logs driver

# Follow logs in real-time
docker compose logs -f orderbook
```

**Common issues:**

1. **Orderbook compilation timeout**
   - First startup takes 5-10 minutes
   - Check logs: `docker compose logs -f orderbook`
   - Look for "Server listening on" message

2. **Database connection failure**
   ```bash
   # Check database status
   docker compose ps db
   docker compose logs db

   # Verify database is accessible
   docker exec $(docker ps -qf "name=db") pg_isready -U postgres
   ```

3. **Anvil fork issues**
   - Verify ETH_RPC_URL in `.env`
   - Check RPC URL has sufficient rate limits
   - Test RPC connection:
     ```bash
     cast block-number --rpc-url $ETH_RPC_URL
     ```

**Solutions:**
```bash
# Restart specific service
docker compose restart orderbook

# Rebuild and restart
docker compose up -d --build orderbook

# Full reset
docker compose down
docker compose up -d
```

### Memory Issues

**Symptoms:**
- OOM (Out of Memory) errors
- Container crashes
- Slow performance

**Solutions:**

1. **Increase Docker memory limit:**
   - Docker Desktop → Settings → Resources → Memory
   - Recommended: 8 GB minimum, 16 GB preferred

2. **Reduce test load:**
   ```yaml
   # In scenario config
   num_traders: 5  # Reduce from 10
   duration: 60    # Shorter tests
   ```

3. **Stop unused containers:**
   ```bash
   # Stop monitoring stack if not needed
   docker compose stop prometheus grafana
   ```

### Network Issues

**Symptoms:**
- "Connection refused" errors
- API timeout errors
- Services can't communicate

**Diagnosis:**
```bash
# Check network exists
docker network ls | grep cow-perf-test

# Inspect network
docker network inspect cow-perf-test

# Test service connectivity (from inside container)
docker exec $(docker ps -qf "name=orderbook") curl http://autopilot:8080/health
```

**Solutions:**
```bash
# Recreate network
docker compose down
docker network prune -f
docker compose up -d
```

### Port Conflicts

**Symptoms:**
- "Port already in use" errors
- Services won't start

**Diagnosis:**
```bash
# Check what's using port 8080 (orderbook)
lsof -i :8080
netstat -an | grep 8080

# Check all CoW ports
lsof -i :8545  # Anvil
lsof -i :8080  # Orderbook
lsof -i :9000  # Driver
lsof -i :5432  # PostgreSQL
```

**Solutions:**
```bash
# Kill process using port
kill -9 <PID>

# Or change port in docker-compose.yml
```

---

## Service Health Checks

### Verifying the Environment

Check all services are running correctly:

```bash
# Check all service status
docker compose ps

# Verify Anvil is running
cast block-number --rpc-url http://localhost:8545

# Check orderbook API
curl http://localhost:8080/api/v1/version

# Check database connection
docker exec $(docker ps -qf "name=db") pg_isready -U postgres

# Check Prometheus (if monitoring enabled)
curl http://localhost:9090/-/healthy

# Check Grafana (if monitoring enabled)
curl http://localhost:3000/api/health
```

### Expected Responses

**Anvil (Chain):**
```bash
$ cast block-number --rpc-url http://localhost:8545
19000000  # Should return current mainnet block number
```

**Orderbook API:**
```bash
$ curl http://localhost:8080/api/v1/version
{"version":"2.x.x"}
```

**Database:**
```bash
$ docker exec $(docker ps -qf "name=db") pg_isready -U postgres
/var/run/postgresql:5432 - accepting connections
```

---

## Performance Tuning

### Docker Resource Allocation

Optimize Docker resource allocation for better performance:

**Recommended settings (Docker Desktop):**
- **Memory**: 16 GB
- **CPUs**: 4-8 cores
- **Swap**: 2 GB
- **Disk image size**: 100 GB

### Database Optimization

For high-volume tests, optimize PostgreSQL:

```yaml
# In docker-compose.yml, add to db service:
environment:
  - POSTGRES_SHARED_BUFFERS=256MB
  - POSTGRES_EFFECTIVE_CACHE_SIZE=1GB
  - POSTGRES_MAX_CONNECTIONS=200
```

### Chain Fork Optimization

Anvil fork performance tips:

1. **Use archive node RPC** for better performance
2. **Pin to specific block** to avoid state changes:
   ```yaml
   # In docker-compose.yml
   command: [..., "--fork-block-number", "19000000"]
   ```
3. **Use local Erigon node** if running many tests

---

## Backup and Restore

### Backup Baselines

Baselines are stored in `.cow-perf/baselines/`:

```bash
# Backup baselines directory
tar -czf baselines-backup-$(date +%Y%m%d).tar.gz .cow-perf/baselines/

# Copy to safe location
mv baselines-backup-*.tar.gz ~/backups/
```

### Restore Baselines

```bash
# Extract backup
tar -xzf baselines-backup-20241231.tar.gz

# Verify baselines
cow-perf baselines --list
```

### Backup Database (Optional)

Backup PostgreSQL database if needed:

```bash
# Export database
docker exec $(docker ps -qf "name=db") pg_dump -U postgres orderbook > orderbook-backup.sql

# Restore database
cat orderbook-backup.sql | docker exec -i $(docker ps -qf "name=db") psql -U postgres orderbook
```

---

## Monitoring and Alerts

### Log Monitoring

Monitor logs for issues:

```bash
# Monitor all services
docker compose logs -f

# Monitor specific service
docker compose logs -f orderbook

# Search logs for errors
docker compose logs | grep -i error
docker compose logs | grep -i exception
```

### Resource Monitoring

Monitor resource usage during tests:

```bash
# Real-time resource usage
docker stats

# Watch specific containers
watch docker stats --no-stream
```

### Setting Up Alerts

Example with Grafana alerting:

1. Enable monitoring stack:
   ```bash
   docker compose up -d prometheus grafana
   ```

2. Access Grafana: http://localhost:3000

3. Configure alert rules for:
   - High CPU usage (>80% for 5 minutes)
   - High memory usage (>90%)
   - Low order fill rate (<50%)
   - High API error rate (>10%)

---

## Maintenance Schedule

### Daily

- Check disk usage: `docker system df`
- Review test logs for errors
- Verify services are healthy

### Weekly

- Run cleanup: `docker system prune -f`
- Review baseline accumulation
- Check for Docker updates

### Monthly

- Deep cleanup (if disk space low)
- Review and archive old baselines
- Update Docker images:
  ```bash
  docker compose pull
  docker compose up -d
  ```

---

## Emergency Procedures

### Complete Reset

If everything is broken, perform a complete reset:

```bash
# 1. Stop all services
docker compose down -v

# 2. Clean Docker system
docker system prune -a -f --volumes

# 3. Remove project volumes
docker volume ls | grep cow-performance | awk '{print $2}' | xargs docker volume rm

# 4. Rebuild from scratch
docker compose up -d --build

# 5. Wait for orderbook to compile (5-10 minutes)
docker compose logs -f orderbook

# 6. Verify installation
cow-perf version
```

### Rollback Docker Compose Version

If update causes issues:

```bash
# Check current version
docker compose version

# Install specific version (example)
# See: https://docs.docker.com/compose/install/
```

---

## See Also

- [Development Guide](development.md) - Development setup and contribution guidelines
- [CLI Reference](cli.md) - Command-line interface documentation
- [Reports Guide](reports.md) - Baseline management and reporting
- [Architecture](architecture.md) - System architecture and design
