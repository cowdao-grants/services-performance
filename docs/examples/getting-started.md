# CoW Performance Testing Suite - Examples

This directory contains example scenarios demonstrating various features and use cases of the CoW Performance Testing Suite.

## Directory Structure

```
examples/
├── getting-started/   # Simple examples for beginners
├── load-testing/      # Various load testing patterns
├── advanced/          # Advanced features (inheritance, profiles)
├── ci-cd/            # CI/CD integration examples
└── comparison/        # Baseline comparison examples
```

## Quick Start

```bash
# Run your first test
cow-perf run --config examples/getting-started/01-minimal.yml

# Run a standard 5-minute test
cow-perf run --config examples/getting-started/03-standard-test.yml

# Create and use templates
cow-perf config-init --mode template
```

## Examples by Category

### Getting Started (3 examples)
**For:** First-time users, learning basics
- `01-minimal.yml` - Absolute minimum configuration (1 min)
- `02-quick-test.yml` - Quick 2-minute test (2 min)
- `03-standard-test.yml` - Standard 5-minute test (5 min)

### Load Testing (7 examples)
**For:** Testing system behavior under various load patterns
- `constant-load.yml` - Steady load (10 min)
- `quick-ramp-up-example.yml` - Gradual increase (5 min)
- `spike-test-example.yml` - Sudden traffic bursts
- `stress-test.yml` - Maximum load testing (5 min)
- `soak-test.yml` - Long-running stability (30 min)
- `sustained-load-example.yml` - Extended constant load
- `custom-ramp-up-example.yml` - Customized ramp pattern

### Advanced (3 examples)
**For:** Complex configurations and reuse
- `base-scenario.yml` - Base scenario for inheritance
- `inheritance-example.yml` - Extending scenarios
- `multi-profile-example.yml` - Multiple environments in one file

### CI/CD Integration (2 examples)
**For:** Automated testing pipelines
- `regression-test.yml` - Fast CI regression test (30 sec)
- `github-actions-workflow.yml` - Complete GitHub Actions workflow

### Comparison (2 examples)
**For:** Before/after testing and regression detection
- `simple-comparison.yml` - Basic baseline comparison
- `regression-detection.yml` - Automated regression detection

## Common Commands

```bash
# Run a scenario
cow-perf run --config examples/getting-started/01-minimal.yml

# Run a scenario and save as baseline
cow-perf run --config examples/advanced/multi-profile-example.yml \
  --save-baseline my-baseline

# Create and save baseline
cow-perf run --config examples/comparison/simple-comparison.yml \
  --save-baseline my-baseline

# Compare against baseline
cow-perf report generate my-new-baseline --compare my-baseline

# List all scenarios
cow-perf scenarios

# Validate a scenario
cow-perf scenarios --validate examples/getting-started/01-minimal.yml
```

## Learning Path

1. **Start here:** `getting-started/01-minimal.yml`
   - Verify your setup works
   - Understand basic structure

2. **Next:** `getting-started/02-quick-test.yml`
   - More realistic configuration
   - Multiple traders

3. **Then:** `getting-started/03-standard-test.yml`
   - Full-featured scenario
   - Success criteria
   - Metadata

4. **Explore:** `load-testing/` examples
   - Different load patterns
   - Find what fits your needs

5. **Advanced:** `advanced/` examples
   - Inheritance and composition
   - Profiles for multiple environments

6. **Automate:** `ci-cd/` and `comparison/` examples
   - Integrate into pipelines
   - Automated regression detection

## Need Help?

- **Creating scenarios:** See `docs/scenario-user-guide.md`
- **Configuration reference:** See `docs/configuration-reference.md`
- **Best practices:** See `docs/scenario-best-practices.md`
- **CLI commands:** Run `cow-perf --help`

## Contributing Examples

Have a useful scenario? Contributions welcome!

1. Create your scenario in the appropriate directory
2. Add extensive comments explaining what it does
3. Include expected outcomes
4. Test it thoroughly
5. Submit a pull request
