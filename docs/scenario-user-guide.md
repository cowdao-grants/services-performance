# Scenario Configuration User Guide

> A step-by-step guide to creating and using performance test scenarios

**For:** Users who want to create and run performance tests
**Time:** 5-10 minutes to get started

---

## Table of Contents

- [What Are Scenarios?](#what-are-scenarios)
- [Quick Start: Create Your First Scenario](#quick-start-create-your-first-scenario)
- [Creating Scenarios (4 Ways)](#creating-scenarios-4-ways)
- [Working with Scenarios](#working-with-scenarios)
- [Running Tests](#running-tests)
- [Common Workflows](#common-workflows)
- [Tips and Tricks](#tips-and-tricks)
- [Troubleshooting](#troubleshooting)

---

## What Are Scenarios?

**Scenarios** are YAML configuration files that define performance tests. Think of them as "test recipes" that specify:

- How many traders to simulate
- How long to run the test
- What types of orders to submit
- What success looks like (pass/fail criteria)
- Resource requirements and metadata

**Why use scenarios?**
- ✅ **Reusable** - Create once, run many times
- ✅ **Shareable** - Give scenarios to teammates
- ✅ **Organized** - Tag and search your test library
- ✅ **Consistent** - Same parameters every time
- ✅ **Documented** - Built-in metadata explains what the test does

---

## Quick Start: Create Your First Scenario

The fastest way to get started is with the interactive wizard:

### Step 1: Run the Wizard

```bash
cow-perf config-init
```

### Step 2: Choose "Quick Start"

You'll see this menu:

```
🎯 Create New Performance Test Scenario

Choose a starting point:
  1. Quick start (minimal config)
  2. From template (ramp-up, spike, sustained)
  3. From existing scenario (customize a predefined one)
  4. Advanced (full configuration)

Your choice [1/2/3/4] (1):
```

**Press 1** and hit Enter.

### Step 3: Answer a Few Questions

```
⚡ Quick Start Mode
Answer a few questions to create a basic load test.

Scenario name: My First Load Test
Description (optional): Testing order submission
Number of concurrent traders [10]: 5
Test duration (seconds) [60]: 120
Target orders per minute (per trader) [60.0]: 30
```

### Step 4: Done!

```
✓ Configuration saved: scenario.yml

Next Steps:
  • Review: cat scenario.yml
  • Validate: cow-perf scenarios --validate scenario.yml
  • Run: cow-perf run --config scenario.yml
```

**That's it!** You've created your first scenario in under a minute.

---

## Creating Scenarios (4 Ways)

### Method 1: Quick Start (Recommended for Beginners)

**Best for:** First-time users, simple tests, rapid iteration

```bash
# Interactive (choose output file)
cow-perf config-init --mode quick

# Direct (specify output file)
cow-perf config-init --mode quick --output my-test.yml
```

**What you get:**
- Minimal configuration (6 questions)
- Constant-rate trading pattern
- Balanced order distribution (60% market, 40% limit)
- Quick setup (~1 minute)

**Example output:**
```yaml
name: My Test
num_traders: 5
duration: 120
base_rate: 30.0
market_order_ratio: 0.6
limit_order_ratio: 0.4
# ... other fields
```

---

### Method 2: From Template (Recommended for Common Patterns)

**Best for:** Standard test patterns (ramp-up, spike, sustained load)

```bash
cow-perf config-init --mode template --output spike-test.yml
```

**Available templates:**

| Template | Use Case | Characteristics |
|----------|----------|----------------|
| **ramp-up** | Find breaking points | Gradually increase load |
| **spike** | Test resilience | Sudden load burst |
| **sustained-load** | Stability testing | Constant load over time |

**Example: Creating a Spike Test**

```bash
$ cow-perf config-init --mode template

📋 Template Mode

Available Templates:
  1. ramp-up - Gradually increase load...
  2. spike - Sudden load burst...
  3. sustained-load - Constant load...

Select template [1/2/3]: 2

⚙️ Template Parameters: spike

Test Name [Spike Stress Test]: Production Spike Test
Num Traders: 20
Duration: 180
Normal Rate: 10.0
Spike Rate: 200.0

✓ Configuration saved
```

**What you get:**
- Pre-configured for the test pattern
- Recommended settings (success criteria, resources)
- Appropriate tags for organization
- Production-ready defaults

---

### Method 3: Copy from Existing (Recommended for Variations)

**Best for:** Modifying existing scenarios, creating test variants

```bash
cow-perf config-init --mode existing --output my-custom-test.yml
```

**Workflow:**

1. **Select** a predefined scenario to copy
2. **Customize** the name
3. **Modify** parameters (optional)
4. **Save** as a new scenario

**Example:**

```bash
$ cow-perf config-init --mode existing

📂 Copy From Existing Scenario

Available Scenarios:
  1. light-load.yml
  2. spike-stress-test.yml
  3. heavy-load.yml
  ...

Select scenario to copy: 1

New scenario name: My Custom Light Load

Modify test parameters? [y/n]: y
Number of traders [10]: 15
Duration [60]: 300
Base rate [30.0]: 45.0

✓ Configuration saved
```

**What you get:**
- All settings from the source scenario
- Your custom modifications applied
- Consistent with existing test patterns

---

### Method 4: Advanced (For Power Users)

**Best for:** Production tests, complex requirements, full control

```bash
cow-perf config-init --mode advanced --output production-test.yml
```

**What you configure:**
- Basic parameters (like quick start)
- Success criteria (min success rate, max latency)
- Resource metadata (memory, CPU requirements)
- All customizable fields

**When to use:**
- Creating baseline tests for CI/CD
- Production readiness validation
- Custom pass/fail requirements
- Resource planning needed

---

## Working with Scenarios

### List All Scenarios

See all scenarios in a directory:

```bash
# Default directory (.cow-perf/scenarios/)
cow-perf scenarios

# Custom directory
cow-perf scenarios --dir ./my-scenarios

# Simple view (no metadata)
cow-perf scenarios --simple
```

**Output:**
```
Available Scenarios
┌──────────────────┬──────────────┬──────────┬──────────┐
│ Name             │ Tags         │ Duration │ Memory   │
├──────────────────┼──────────────┼──────────┼──────────┤
│ My First Test    │ test, quick  │ 120s     │ -        │
│ Spike Test       │ spike, load  │ 180s     │ 8.0GB    │
│ Production Test  │ production   │ 300s     │ 16.0GB   │
└──────────────────┴──────────────┴──────────┴──────────┘
```

---

### Search Scenarios

Find scenarios by name or description:

```bash
# Search by keyword
cow-perf scenarios --search "spike"

# Search in custom directory
cow-perf scenarios --dir ./tests --search "production"
```

---

### Filter by Tags

Use tags to organize and filter:

```bash
# Single tag
cow-perf scenarios --tag regression

# Multiple tags (must match all)
cow-perf scenarios --tag regression --tag short

# Combine with search
cow-perf scenarios --tag stress --search "high"
```

**Common tags:**
- `regression` - CI/CD tests
- `smoke` - Quick validation
- `stress` - High-load tests
- `production` - Production simulation
- `short`, `medium`, `long` - Duration categories

---

### Validate a Scenario

Check if your scenario is valid:

```bash
# Validate single file
cow-perf scenarios --validate my-scenario.yml
```

**What gets validated:**
- ✅ Required fields present
- ✅ Order ratios sum to 1.0
- ✅ Trading pattern is valid
- ✅ Pattern-specific parameters provided
- ✅ Success criteria in valid ranges

**Example validation output:**
```
✓ Scenario is valid!

┌─────────────────┬─────────────────────┐
│ Property        │ Value               │
├─────────────────┼─────────────────────┤
│ Name            │ My Test             │
│ Traders         │ 10                  │
│ Duration        │ 120s                │
│ Trading Pattern │ constant_rate       │
└─────────────────┴─────────────────────┘
```

---

### View Scenario Details

See what's in a scenario without running it:

```bash
# View file contents
cat my-scenario.yml

# Validate (shows detailed info)
cow-perf scenarios --validate my-scenario.yml

# List with metadata
cow-perf scenarios
```

---

## Running Tests

### Running with a Scenario File

Pass a scenario YAML file directly to `cow-perf run` using `--config`:

```bash
cow-perf run --config my-scenario.yml
```

You can also pass a predefined scenario:

```bash
cow-perf run --config configs/scenarios/predefined/light-load.yml
```

### Overriding Parameters at Run Time

CLI flags override values from the scenario file:

```bash
# Use scenario file but override trader count and duration
cow-perf run --config my-scenario.yml --traders 10 --duration 120
```

### Saving Results

```bash
cow-perf run --config my-scenario.yml \
  --save-baseline my-baseline \
  --baseline-description "Before feature X"
```

---

## Common Workflows

### Workflow 1: Quick Validation Test

**Goal:** Validate a new feature quickly

```bash
# 1. Create quick scenario
cow-perf config-init --mode quick --output validate.yml
# Answer: 5 traders, 60s, 30 orders/min

# 2. Validate it
cow-perf scenarios --validate validate.yml

# 3. Run using parameters
cow-perf run --traders 5 --duration 60
```

---

### Workflow 2: Baseline Testing

**Goal:** Create reproducible baseline for comparisons

```bash
# 1. Create baseline scenario from template
cow-perf config-init --mode template --output baseline-v1.yml
# Choose: sustained-load, 10 traders, 600s, 60 orders/min

# 2. Validate
cow-perf scenarios --validate baseline-v1.yml

# 3. Run and save baseline
cow-perf run --traders 10 --duration 600 \
  --save-baseline baseline-v1 \
  --baseline-description "Initial baseline before feature X"

# 4. Later: Compare new test against baseline
cow-perf run --traders 10 --duration 600 \
  --save-baseline baseline-v2

cow-perf report compare baseline-v1 baseline-v2
```

---

### Workflow 3: Stress Testing

**Goal:** Find system breaking points

```bash
# 1. Create spike test
cow-perf config-init --mode template --output stress-test.yml
# Choose: spike, 50 traders, 300s, 10 normal / 200 spike

# 2. Tag it appropriately
# Edit stress-test.yml and add tags: [stress, spike, capacity]

# 3. Run series with increasing load
cow-perf run --traders 20 --duration 300  # 40% capacity
cow-perf run --traders 35 --duration 300  # 70% capacity
cow-perf run --traders 50 --duration 300  # 100% capacity

# 4. Find all stress tests later
cow-perf scenarios --tag stress
```

---

### Workflow 4: CI/CD Regression Tests

**Goal:** Fast regression tests in CI pipeline

```bash
# 1. Create regression scenario
cow-perf config-init --mode quick --output regression.yml
# Answer: 5 traders, 120s, 60 orders/min

# 2. Edit and add tags and success criteria
# Edit regression.yml:
tags: [regression, ci, short]
success_criteria:
  min_success_rate: 0.95
  max_p95_latency_seconds: 10.0

# 3. Add to CI pipeline (.github/workflows/test.yml):
- name: Run regression test
  run: |
    cow-perf run --traders 5 --duration 120 \
      --save-baseline regression-${{ github.sha }}

# 4. Find all regression tests
cow-perf scenarios --tag regression
```

---

### Workflow 5: Production Simulation

**Goal:** Test with production-like load

```bash
# 1. Copy production scenario
cow-perf config-init --mode existing --output prod-sim.yml
# Select: production-load template
# Customize: 100 traders, 1800s (30 min)

# 2. Add strict success criteria
# Edit prod-sim.yml:
success_criteria:
  min_success_rate: 0.99
  max_p95_latency_seconds: 5.0
  max_error_rate: 0.01

# 3. Run in staging first
cow-perf run --traders 100 --duration 1800

# 4. Run in production (10% sample)
cow-perf run --traders 10 --duration 1800
```

---

## Tips and Tricks

### Tip 1: Use Templates as Starting Points

Don't write YAML from scratch - use templates:

```bash
# View available templates
cow-perf scenarios --list-templates

# Create from template
cow-perf config-init --mode template
```

Templates include best-practice settings for common patterns.

---

### Tip 2: Tag Everything

Tags make scenarios discoverable:

```yaml
tags:
  - regression      # For CI/CD
  - short           # Quick tests (<5 min)
  - production      # Production simulation
  - baseline        # For comparisons
```

Find them later:
```bash
cow-perf scenarios --tag regression --tag short
```

---

### Tip 3: Use Descriptive Names

Follow the pattern `<type>-<characteristic>-<variant>` (e.g. `smoke-basic-5traders`). See [naming conventions](scenario-best-practices.md#scenario-naming-conventions) for full guidance.

---

### Tip 4: Document with Descriptions

Add context for future you (and teammates):

```yaml
name: "Production Peak Load Simulation"
description: "Simulates Friday evening peak with 100 concurrent traders over 30 minutes. Used to validate auto-scaling and performance under realistic production load."
```

---

### Tip 5: Start Small, Then Scale

Create scenarios in increasing complexity:

```bash
# 1. Smoke test (2 min, 5 traders)
cow-perf config-init --mode quick --output smoke.yml

# 2. Standard load (10 min, 10 traders)
cow-perf config-init --mode quick --output standard.yml

# 3. Heavy load (30 min, 50 traders)
cow-perf config-init --mode quick --output heavy.yml
```

Run smoke test first, then scale up if it passes.

---

### Tip 6: Save Baselines for Comparison

After creating a scenario, run it and save the results:

```bash
cow-perf run --traders 10 --duration 120 \
  --save-baseline my-scenario-v1
```

Later, compare against the baseline:
```bash
cow-perf run --traders 10 --duration 120 \
  --save-baseline my-scenario-v2

cow-perf report compare my-scenario-v1 my-scenario-v2
```

---

### Tip 7: Organize in Directories

Keep scenarios organized:

```
my-scenarios/
├── smoke/
│   ├── quick-validation.yml
│   └── basic-smoke.yml
├── regression/
│   ├── ci-regression.yml
│   └── nightly-regression.yml
└── stress/
    ├── spike-test.yml
    └── sustained-heavy.yml
```

List specific directories:
```bash
cow-perf scenarios --dir my-scenarios/smoke
```

---

## Troubleshooting

For validation errors (order ratios, invalid trading patterns, missing fields) see [Best Practices: Troubleshooting](scenario-best-practices.md#troubleshooting).

### Problem: Configuration wizard gets stuck

**Cause:** Missing input or EOF

**Fix:** If using piped input, ensure all prompts are answered:
```bash
# All prompts answered
echo -e "Test\nDesc\n10\n60\n30.0" | cow-perf config-init --mode quick
```

For interactive use, just run normally:
```bash
cow-perf config-init --mode quick
```

---

### Problem: Can't find my scenarios

**Cause:** Wrong directory or no scenarios created

**Fix:**
```bash
# Check default directory
cow-perf scenarios

# Check custom directory
cow-perf scenarios --dir /path/to/my/scenarios

# Create first scenario if none exist
cow-perf config-init --mode quick --output my-first-scenario.yml
```

---

### Problem: Scenario validation fails

**Cause:** Missing required fields or invalid values

**Fix:** Run validation to see details:
```bash
cow-perf scenarios --validate my-scenario.yml
```

Common issues:
- Missing `name` field
- Missing order ratios
- Invalid `trading_pattern`
- Negative or zero values where not allowed

---

## Next Steps

Now that you know how to create and use scenarios:

1. **Create your first scenario** - Start with quick mode
2. **Run a test** - Extract parameters and run with `cow-perf run`
3. **Organize your scenarios** - Use tags and directories
4. **Build a test library** - Create scenarios for common use cases
5. **Compare results** - Save baselines and track performance over time

### Further Reading

- [Configuration Reference](configuration-reference.md) - Complete field documentation
- [Best Practices Guide](scenario-best-practices.md) - Guidelines for effective scenarios
- [CLI Reference](cli.md) - All commands and options
- [Template Documentation](cli.md#list-templates) - Built-in templates

---

## Quick Reference Card

```bash
# CREATE scenarios
cow-perf config-init                    # Interactive wizard
cow-perf config-init --mode quick       # Quick start
cow-perf config-init --mode template    # From template
cow-perf config-init --mode existing    # Copy existing

# MANAGE scenarios
cow-perf scenarios                      # List all
cow-perf scenarios --search "spike"     # Search
cow-perf scenarios --tag regression     # Filter by tag
cow-perf scenarios --validate FILE      # Validate

# VIEW templates
cow-perf scenarios --list-templates     # Show available templates

# RUN tests (using scenario parameters)
cow-perf run --traders 10 --duration 60                 # Basic
cow-perf run --traders 10 --duration 60 --save-baseline NAME  # Save results
```

---

**Questions or feedback?** See our [documentation](../README.md) or report issues on GitHub.

**Last Updated:** 2026-03-11
