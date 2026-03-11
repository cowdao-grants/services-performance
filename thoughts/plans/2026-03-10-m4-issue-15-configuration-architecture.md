# M4-Issue-15: Scenario Configuration System - Architecture Proposal

**Date:** 2026-03-10
**Status:** Architecture Design Phase
**Depends on:** M4-Issue-14 (Predefined Test Scenarios) - ✅ Complete

## Executive Summary

M4-Issue-14 delivered a solid foundation: scenario models, validation, CLI commands, and 15 predefined scenarios. M4-Issue-15 builds on this to create an **enterprise-grade configuration system** with inheritance, templates, profiles, and intelligent defaults.

This document proposes the architecture **without implementation details** - focusing on component responsibilities, data flow, and design principles.

**Key Design Decision:** Configuration is **project-scoped** - all configuration files live within the project folder. No user-level defaults or global configuration files outside the project. This ensures reproducibility, easier sharing, and better team collaboration.

---

## What's Already Done (M4-Issue-14 Foundation)

### ✅ Core Infrastructure (Ready to Build On)

| Component | Location | What It Does | Status |
|-----------|----------|--------------|--------|
| **ScenarioConfig** | `cli/commands/scenarios.py:571` | Pydantic model with all scenario fields, ratio/pattern validation | ✅ Complete |
| **SuccessCriteria** | `cli/commands/scenarios.py` | Success criteria model (4 metrics) | ✅ Complete |
| **SuccessCriteriaValidator** | `scenarios/validation.py:192` | Validates test results against criteria | ✅ Complete |
| **YAML Loader** | `load_scenario_from_yaml()` | Loads and validates YAML files | ✅ Complete |
| **CLI Commands** | `scenarios` command group | List, validate, create-template | ✅ Complete |
| **Predefined Scenarios** | `configs/scenarios/` | 15 scenarios with metadata | ✅ Complete |
| **Test Coverage** | `tests/unit/test_scenarios*.py` | 80+ tests for models and validation | ✅ Complete |

### Key Strengths of Existing System
- **Strong Pydantic validation** - Type safety, automatic validation
- **Rich metadata** - Tags, resource requirements, success criteria
- **CLI integration** - Filter by tags, search, validate
- **Well-tested** - Comprehensive unit test coverage

### What's Missing (Gaps for M4-Issue-15)
- ❌ **No scenario inheritance** - Can't extend/compose scenarios
- ❌ **No configuration profiles** - Can't have dev/staging/prod in one file
- ❌ **No templates** - Can't quickly create scenarios from patterns
- ❌ **No interactive generator** - Must manually write YAML
- ❌ **No defaults hierarchy** - No project-wide defaults system
- ❌ **Limited env var support** - Only basic pydantic-settings, no `${VAR:-default}`
- ❌ **No advanced validation** - No semantic checks, token validation, warnings
- ❌ **No configuration reference** - No comprehensive field documentation

---

## Architecture Principles

### 1. **Separation of Concerns**
Each component has a single, clear responsibility:
- **Loaders** read and parse files
- **Resolvers** handle inheritance and composition
- **Validators** check correctness
- **Generators** create new configurations
- **Documenters** produce reference material

### 2. **Layered Configuration**
Configuration is resolved in layers, from lowest to highest priority:
```
Built-in Defaults (code)
    ↓
Project Defaults (.cow-perf-defaults.yml)
    ↓
Scenario File (my-test.yml)
    ↓
Profile Override (--profile staging)
    ↓
CLI Arguments (--traders 50)
```

**Note:** No user-level defaults outside the project. Everything stays within the project folder for better isolation and reproducibility.

### 3. **Declarative Over Imperative**
Users declare **what** they want, not **how** to achieve it:
- Templates define patterns
- Inheritance expresses relationships
- Profiles specify environments
- The system resolves complexity

### 4. **Fail Fast, Fail Clear**
Validation happens early with actionable feedback:
- Syntax errors → Show line numbers
- Schema errors → Show field path and expected type
- Semantic errors → Explain the logical problem
- Warnings → Suggest improvements

### 5. **Progressive Disclosure**
Simple things are simple, complex things are possible:
- Basic scenario: Just a YAML file
- Reuse: Add `extends: base-scenario`
- Multi-env: Add `profiles:` section
- Advanced: Full defaults hierarchy + env vars + templates

---

## Proposed Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        User Input                            │
│  (YAML file, CLI args, environment variables)                │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Configuration Loader                      │
│  Orchestrates the entire loading and resolution process      │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                   ↓
┌──────────────┐  ┌──────────────┐   ┌──────────────┐
│   File       │  │  Template    │   │  Defaults    │
│   Reader     │  │  Expander    │   │  Resolver    │
└──────┬───────┘  └──────┬───────┘   └──────┬───────┘
       ↓                  ↓                   ↓
       └──────────────────┴───────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                  Environment Substitutor                     │
│  Replaces ${VAR} and ${VAR:-default} with actual values      │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   Inheritance Resolver                       │
│  Processes 'extends' chains, merges parent configs           │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Profile Selector                          │
│  Applies profile-specific overrides if --profile specified   │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Configuration Merger                      │
│  Deep merges all layers respecting precedence                │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Configuration Validator                   │
│  Multi-level validation: syntax → schema → semantic          │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    ScenarioConfig Instance                   │
│  Fully validated, ready-to-use configuration object          │
└─────────────────────────────────────────────────────────────┘
```

---

## Detailed Component Design

### 1. Configuration Loader (Orchestrator)

**Responsibility:** Coordinates the entire loading process

**Interface:**
```
ConfigurationLoader
├── load(scenario_path, profile=None, overrides={}) → ScenarioConfig
├── load_with_defaults(scenario_path, ...) → ScenarioConfig
└── validate_only(scenario_path) → ValidationResult
```

**Behavior:**
1. Discovers and loads default files (project → built-in)
2. Reads scenario file
3. Processes templates if referenced
4. Substitutes environment variables
5. Resolves inheritance chain
6. Applies profile if specified
7. Merges all layers
8. Validates result
9. Returns ScenarioConfig instance

**Key Design Decision:** The loader is **stateless** - each load operation is independent. This makes it testable and predictable.

---

### 2. File Reader

**Responsibility:** Read and parse configuration files from disk

**Interface:**
```
FileReader
├── read_yaml(path) → dict
├── read_json(path) → dict
└── discover_defaults() → list[Path]
```

**Behavior:**
- Reads YAML and JSON files
- Returns raw dictionaries (not validated objects)
- Discovers default files in standard locations:
  - `./.cow-perf-defaults.yml` (project)
  - Built-in defaults (embedded in code)

**Error Handling:**
- YAML syntax errors → Show line number and column
- Missing files → Clear "file not found" message
- Permission errors → Actionable instructions

---

### 3. Template Expander

**Responsibility:** Expand template references into full configurations

**Concept:**
Templates are **parameterized scenario skeletons** for common patterns:
```yaml
# User writes this:
template: ramp-up-load-test
parameters:
  start_rate: 5
  target_rate: 50
  duration: 600

# System expands to full scenario config
```

**Template Types:**
1. **Pattern Templates** - `ramp-up`, `spike`, `sustained-load`
2. **Use Case Templates** - `regression-test`, `stress-test`, `smoke-test`
3. **Custom Templates** - User-defined in `.cow-perf/templates/`

**Template Storage:**
```
configs/templates/           # Built-in templates
  ├── ramp-up.template.yml
  ├── spike.template.yml
  └── sustained-load.template.yml

.cow-perf/templates/         # Project-specific custom templates
  └── custom-pattern.template.yml
```

**Template Structure:**
```yaml
# Template file
template_metadata:
  name: ramp-up-load-test
  description: Gradually increase load to find breaking point
  parameters:
    - name: start_rate
      type: float
      required: true
      description: Starting orders per minute
    - name: target_rate
      type: float
      required: true
    - name: duration
      type: int
      default: 600

# Template body (uses ${param_name} syntax)
name: ${name:-Ramp Up Load Test}
description: Ramp from ${start_rate} to ${target_rate} orders/min
num_traders: ${num_traders:-10}
duration: ${duration}
trading_pattern: ramp_up
base_rate: ${start_rate}
target_rate: ${target_rate}
# ... rest of config
```

**Design Decision:** Templates are **expanded early** in the pipeline, before inheritance resolution. This allows templates to be extended.

---

### 4. Environment Substitutor

**Responsibility:** Replace environment variable references with actual values

**Syntax Support:**
```yaml
# Simple reference
api_url: ${API_URL}

# With default value
api_url: ${API_URL:-http://localhost:8080}

# Nested in strings
description: "Test on ${ENV_NAME:-development} environment"
```

**Behavior:**
1. Scan configuration for `${...}` patterns
2. For each match:
   - If `:-` present: Use env var or default
   - If no `:-`: Require env var exists (fail if missing)
3. Support `.env` file loading
4. Validate expanded values make sense

**Security Consideration:** Only substitute in **value positions**, not keys or structural elements. Prevents injection attacks.

---

### 5. Inheritance Resolver

**Responsibility:** Process `extends` chains and merge parent configurations

**Concept:**
Scenarios can inherit from other scenarios:
```yaml
# base-load-test.yml
name: Base Load Test
num_traders: 10
duration: 300
trading_pattern: constant_rate
base_rate: 60

# my-test.yml
extends: base-load-test
name: My Custom Test
num_traders: 20  # Override
# Inherits: duration, trading_pattern, base_rate
```

**Inheritance Types:**

1. **Single Inheritance:**
   ```yaml
   extends: base-scenario
   ```

2. **Path-based:**
   ```yaml
   extends: ../shared/base-scenario.yml
   ```

3. **Built-in:**
   ```yaml
   extends: builtin:light-load
   ```

**Resolution Algorithm:**
1. Load child scenario
2. If `extends` present:
   - Load parent scenario (recursively resolve its `extends`)
   - Merge parent into child (child wins conflicts)
3. Return merged configuration

**Circular Dependency Detection:**
- Track visited scenarios in resolution chain
- Fail with clear error if cycle detected

**Merge Strategy (Deep Merge):**
- **Primitives** (strings, numbers, bools) → Child overrides parent
- **Lists** → Child replaces parent (no appending - too complex)
- **Dicts** → Deep merge recursively
- **Special case:** `tags` → Union of parent and child tags

---

### 6. Profile Selector

**Responsibility:** Apply environment-specific overrides from profiles

**Concept:**
Single file can contain multiple environment configurations:
```yaml
# Base configuration
name: My Test
num_traders: 10
duration: 300

# Environment-specific overrides
profiles:
  dev:
    num_traders: 3
    duration: 30

  staging:
    num_traders: 10
    duration: 300

  prod:
    num_traders: 50
    duration: 1800
    metadata:
      resources:
        min_memory_gb: 16
```

**Usage:**
```bash
cow-perf run --config my-test.yml --profile prod
```

**Behavior:**
1. Load base configuration (everything outside `profiles:`)
2. If `--profile` specified:
   - Extract profile section
   - Merge profile into base (profile wins)
3. Return merged configuration

**Design Decision:** Profiles are **shallow overrides** - they modify the base config but don't have their own inheritance. Keeps complexity manageable.

---

### 7. Configuration Merger

**Responsibility:** Combine multiple configuration layers into one

**Merging Order (lowest to highest priority):**
1. Built-in defaults (hardcoded)
2. Project defaults (`.cow-perf-defaults.yml`)
3. Scenario file
4. Profile override
5. CLI arguments

**Merge Rules:**
- **Explicit values** always override defaults
- **None/null** in child doesn't clear parent value
- **Empty string** in child does clear parent value
- **Lists** are replaced, not merged
- **Dicts** are deep-merged

**Example:**
```yaml
# Built-in defaults
num_traders: 10
duration: 60

# Project defaults (.cow-perf-defaults.yml)
duration: 120
tags: [team-test]

# Scenario file (my-test.yml)
name: My Test
num_traders: 20

# Result after merge:
name: My Test
num_traders: 20        # Scenario file (highest priority)
duration: 120          # Project defaults
tags: [team-test]      # Project defaults
```

---

### 8. Configuration Validator

**Responsibility:** Multi-level validation with clear error reporting

**Validation Levels:**

#### Level 1: Syntax Validation
- YAML/JSON parsing
- Catches: Invalid YAML, wrong indentation, unclosed quotes
- Error format: Line number, column, description

#### Level 2: Schema Validation (Pydantic)
- Field presence (required fields)
- Type checking (string, int, float, list, etc.)
- Basic constraints (min, max, regex patterns)
- Catches: Missing required fields, wrong types
- Error format: Field path, expected type, actual value

#### Level 3: Semantic Validation (Business Logic)
- Cross-field validation
- Logical consistency checks
- Catches: Ratios don't sum to 1.0, target_rate < start_rate
- Error format: Field names involved, logical problem, suggestion

#### Level 4: Reference Validation (External Dependencies)
- Token addresses exist and are valid checksums
- File paths referenced exist
- Catches: Invalid token addresses, missing files
- Error format: Reference identifier, problem, suggested fix

#### Level 5: Warning System (Non-blocking)
- Performance concerns (very high rates)
- Resource warnings (insufficient memory)
- Best practice violations
- Format: Warning icon, description, recommendation

**Validation Result:**
```python
@dataclass
class ConfigValidationResult:
    valid: bool
    errors: list[ValidationError]      # Blocking issues
    warnings: list[ValidationWarning]  # Non-blocking suggestions

    def display(self, console):
        # Rich formatted output with colors, context, suggestions
```

**Error Display Philosophy:**
- **Show context** - What was being validated
- **Explain problem** - What went wrong and why it matters
- **Suggest fix** - How to correct it
- **Link docs** - Where to learn more

---

### 9. Configuration Generator

**Responsibility:** Interactive CLI wizard to create new scenarios

**User Experience Flow:**
```
$ cow-perf config init

🎯 Create New Performance Test Scenario

Choose a starting point:
  1. Quick start (minimal config)
  2. From template (ramp-up, spike, sustained)
  3. From existing scenario (customize a predefined one)
  4. Advanced (full configuration)

[User selects option 2: From template]

📋 Available Templates:
  1. ramp-up-load-test - Gradually increase load
  2. spike-test - Sudden load burst
  3. sustained-load - Long-running stability test
  4. regression-test - CI/CD optimized

[User selects option 1: ramp-up]

⚙️  Template Parameters:

  Scenario name: [My Ramp Up Test]
  Description: [Load test ramping from 5 to 50 orders/min]

  Start rate (orders/min): [5]
  Target rate (orders/min): [50]
  Ramp duration (seconds): [600]

  Number of traders: [10]

  Add success criteria? [Y/n]: y
  Min success rate (0-1): [0.90]
  Max P95 latency (seconds): [10]

✅ Configuration created: my-ramp-up-test.yml

Next steps:
  • Review: cat my-ramp-up-test.yml
  • Validate: cow-perf scenarios --validate my-ramp-up-test.yml
  • Run: cow-perf run --config my-ramp-up-test.yml
```

**Command Structure:**
```
cow-perf config init [OPTIONS]

Options:
  --name TEXT              Scenario name
  --template TEXT          Use template
  --from-scenario TEXT     Copy existing scenario
  --output PATH            Output file path
  --interactive / --batch  Interactive wizard or batch mode
```

**Generator Modes:**

1. **Quick Start Mode:**
   - Minimal questions (name, duration, traders, rate)
   - Generates simplest valid config
   - Best for: Quick tests, learning

2. **Template Mode:**
   - Choose template
   - Fill template parameters
   - Optionally customize further
   - Best for: Common patterns

3. **From Existing:**
   - Select predefined scenario
   - Override specific fields
   - Save as new file
   - Best for: Variations on existing tests

4. **Advanced Mode:**
   - Full configuration wizard
   - All options exposed
   - Expert users

**Output:**
- Generated YAML file with inline comments
- Validation passed before saving
- Next steps guidance printed

---

### 10. Defaults System

**Responsibility:** Provide sensible defaults at multiple levels

**Default File Locations:**

1. **Built-in Defaults (Code):**
   ```python
   DEFAULT_SCENARIO_CONFIG = {
       "num_traders": 10,
       "duration": 60,
       "startup_interval": 0.1,
       "trading_pattern": "constant_rate",
       "base_rate": 60,
       "market_order_ratio": 0.7,
       "limit_order_ratio": 0.3,
       # ... etc
   }
   ```

2. **Project Defaults (`.cow-perf-defaults.yml`):**
   - Project-specific settings
   - Shared across team (committed to git)
   - Example: Token pairs, network config, API URLs
   - Located at project root

**Defaults File Structure:**
```yaml
# .cow-perf-defaults.yml (project)

# Network defaults
network:
  rpc_url: ${RPC_URL:-http://localhost:8545}
  chain_id: 1

# Common test parameters
test_defaults:
  num_traders: 10
  duration: 300
  startup_interval: 0.1

# Common token pairs
token_pairs:
  - sell_token: WETH
    buy_token: DAI
    weight: 0.5
  - sell_token: WETH
    buy_token: USDC
    weight: 0.5

# Default tags
tags:
  - internal-testing
  - team-performance
```

**Precedence Rules:**
- Built-in defaults < Project defaults < Scenario file
- Defaults are **baseline** - always overridable
- Validation happens **after** merging all defaults
- Everything stays within the project folder (no user-level config)

---

## Data Flow Example

Let's trace a complete configuration loading scenario:

**User runs:**
```bash
cow-perf run --config my-test.yml --profile staging --traders 20
```

**Step-by-step flow:**

1. **ConfigurationLoader.load()** called with:
   - `scenario_path=my-test.yml`
   - `profile=staging`
   - `overrides={num_traders: 20}`

2. **DefaultsResolver.discover()** finds:
   - Built-in defaults (code)
   - `./.cow-perf-defaults.yml` (exists)

3. **FileReader.read_yaml()** reads `my-test.yml`:
   ```yaml
   extends: base-load-test
   name: My Test
   num_traders: 15

   profiles:
     staging:
       duration: 300
   ```

4. **TemplateExpander.expand()** - no template, skips

5. **EnvironmentSubstitutor.substitute()** - no `${...}`, skips

6. **InheritanceResolver.resolve()** sees `extends`:
   - Loads `base-load-test.yml`
   - `base-load-test.yml` has no extends
   - Merges: base + my-test (my-test wins conflicts)
   - Result has `duration: 600` from base, `num_traders: 15` from child

7. **ProfileSelector.apply()** sees `--profile staging`:
   - Extracts staging profile: `{duration: 300}`
   - Merges into config
   - Result now has `duration: 300` (profile override)

8. **ConfigurationMerger.merge_all()** combines:
   - Built-in defaults → Project defaults → Scenario → Profile
   - Result: Full config with all fields populated

9. **CLI overrides applied:**
   - `num_traders: 20` (CLI argument overrides everything)

10. **ConfigurationValidator.validate()** performs:
    - Schema validation (Pydantic)
    - Semantic validation (ratios, patterns)
    - Reference validation (if needed)
    - Returns ValidationResult

11. **ScenarioConfig instance** created and returned

12. **CLI** executes test with final config

**Final Configuration:**
```yaml
name: My Test
num_traders: 20          # CLI override
duration: 300            # Profile override
trading_pattern: constant_rate  # From base-load-test
base_rate: 60            # From defaults
# ... etc
```

---

## Key Design Decisions & Trade-offs

### 1. Template Expansion vs. Dynamic Templates

**Decision:** Templates are **expanded early** into full configs

**Alternative Considered:** Templates as runtime objects that generate configs on-demand

**Rationale:**
- Expanded templates can be saved, version controlled, inspected
- Simpler mental model - templates → configs → validation
- Easier debugging - see full config after expansion
- Allows templates to be extended via inheritance

**Trade-off:** Template changes don't affect already-expanded configs (this is actually desirable for reproducibility)

---

### 2. Inheritance: Single vs. Multiple

**Decision:** Support **single inheritance** only (one `extends` per file)

**Alternative Considered:** Multiple inheritance (`extends: [base1, base2]`)

**Rationale:**
- Single inheritance is easier to reason about
- No ambiguity in merge order
- Most use cases satisfied by single inheritance + profiles
- Can still achieve composition via inheritance chains

**Trade-off:** Some reuse scenarios require intermediate files

---

### 3. Profile Overrides: Shallow vs. Deep Inheritance

**Decision:** Profiles are **shallow overrides** - just merge into base

**Alternative Considered:** Profiles as full scenarios with their own inheritance

**Rationale:**
- Profiles are for **environment variations**, not full scenario definitions
- Shallow overrides are predictable
- Reduces nesting complexity
- Covers 95% of use cases

**Trade-off:** Complex multi-environment configs might need separate files

---

### 4. Validation: Fail Fast vs. Collect All Errors

**Decision:** **Collect all errors** at each level, then display together

**Alternative Considered:** Fail on first error

**Rationale:**
- Better UX - user fixes multiple issues at once
- Reduces frustration ("why didn't you tell me about error 2?")
- Modern IDEs work this way

**Trade-off:** Slightly more complex validator logic

---

### 5. Environment Variables: String-only vs. Type-aware

**Decision:** **String substitution only** - `${VAR}` always produces string

**Alternative Considered:** Type-aware substitution (interpret "true" as bool, "123" as int)

**Rationale:**
- Predictable behavior - what you see is what you get
- YAML type coercion happens after substitution
- Avoids subtle bugs from type interpretation
- Users can still use YAML's own type coercion

**Trade-off:** Slightly more verbose env var usage

---

### 6. Defaults Files: Shared Format vs. Separate Schema

**Decision:** Defaults files use **same format as scenario files** (partial ScenarioConfig)

**Alternative Considered:** Defaults-specific schema with different structure

**Rationale:**
- Single format to learn
- Can copy-paste between defaults and scenarios
- Defaults are just "partial scenarios"
- Easier documentation

**Trade-off:** Defaults files might have fields that don't make sense (like `name`)

---

## Error Handling Strategy

### Error Categories

1. **User Errors** (expected, recoverable)
   - Invalid YAML syntax → Show line/column + explanation
   - Missing required field → Show field path + example
   - Invalid value → Show valid range + suggestion
   - File not found → Show search path, suggest create

2. **Configuration Errors** (semantic issues)
   - Circular inheritance → Show inheritance chain
   - Conflicting values → Show conflict + precedence rules
   - Failed validation → Show all errors + how to fix

3. **System Errors** (unexpected)
   - File permission denied → Show path + permission fix
   - Disk full → Clear message + cleanup suggestions
   - Network timeout (if fetching remote configs) → Retry logic

### Error Display Format

**Good Error Example:**
```
❌ Configuration Validation Failed

1. Invalid order type ratio (semantic error)

   File: my-test.yml
   Field: order_types

   Problem: Order type ratios must sum to 1.0

   Found:
     market: 0.7
     limit: 0.4
     Total: 1.1  ← Too high!

   Fix: Adjust ratios to sum to exactly 1.0:
     market: 0.6
     limit: 0.4

2. Missing required field (schema error)

   File: my-test.yml
   Field: trading_pattern

   Problem: 'trading_pattern' is required

   Valid values: constant_rate, burst, random_interval

   Example:
     trading_pattern: constant_rate
     base_rate: 60

📖 Documentation: https://docs.cow-perf.io/config-reference
```

---

## Testing Strategy

### Unit Tests (Component-level)

Each component has isolated tests:

1. **FileReader** tests:
   - Read valid YAML/JSON
   - Handle syntax errors
   - Discover default files
   - Handle missing files

2. **TemplateExpander** tests:
   - Expand simple templates
   - Handle template parameters
   - Validate required parameters
   - Handle template not found

3. **EnvironmentSubstitutor** tests:
   - Simple substitution `${VAR}`
   - Default values `${VAR:-default}`
   - Missing variables error
   - Nested substitution

4. **InheritanceResolver** tests:
   - Single inheritance
   - Multi-level chains
   - Circular dependency detection
   - Merge behavior (primitives, lists, dicts)

5. **ProfileSelector** tests:
   - Apply profile override
   - Profile not found error
   - Deep merge behavior

6. **ConfigurationMerger** tests:
   - Precedence order correct
   - Deep merge logic
   - Special cases (tags union, etc.)

7. **ConfigurationValidator** tests:
   - All validation levels
   - Error collection and display
   - Warning generation

8. **ConfigurationGenerator** tests:
   - Generate from template
   - Generate from existing
   - Interactive mode (mocked input)
   - Output validation

### Integration Tests (End-to-end)

1. **Simple Load:**
   - Load basic scenario file
   - No inheritance, no profiles
   - Verify correct config produced

2. **Inheritance Chain:**
   - Child extends parent extends grandparent
   - Verify correct merge at each level

3. **Multi-layer Defaults:**
   - Built-in + user + project + scenario
   - Verify precedence order

4. **Profile Override:**
   - Load with profile selection
   - Verify profile values override base

5. **Full Pipeline:**
   - Defaults + inheritance + profile + CLI overrides
   - Verify final config matches expected

6. **Error Scenarios:**
   - Invalid YAML → Clear error
   - Missing parent → Clear error
   - Circular inheritance → Detected
   - Validation failure → All errors shown

---

## Documentation Requirements

### 1. Configuration Reference

**Auto-generated from Pydantic models:**
```markdown
# Configuration Reference

## ScenarioConfig

### name (string, required)
The human-readable name of the scenario.

**Example:**
```yaml
name: My Load Test
```

### num_traders (integer, default: 10)
Number of concurrent traders to simulate.

**Valid range:** 1-1000

**Examples:**
```yaml
num_traders: 10   # Light load
num_traders: 50   # Medium load
num_traders: 200  # Heavy load
```

**Related:**
- More traders = more load
- Consider resources (see metadata.resources)

... (continue for all fields)
```

### 2. Configuration Guide

**User-focused tutorial:**
- Quick start (minimal config)
- Adding inheritance
- Using profiles
- Environment variables
- Templates
- Advanced patterns

### 3. Template Gallery

**Catalog of available templates:**
- What each template does
- Parameters it accepts
- Example usage
- When to use it

### 4. Example Configurations

**`examples/` directory:**
- `simple.yml` - Minimal working config
- `advanced.yml` - All features demonstrated
- `multi-stage.yml` - Complex multi-phase test
- `comparison.yml` - With baseline comparison
- `ci-cd.yml` - Optimized for CI/CD
- `production.yml` - Production-ready config

### 5. Best Practices Guide

- Configuration organization
- Reuse strategies (inheritance vs. templates vs. profiles)
- Security (env vars for secrets)
- Performance considerations
- Debugging tips

---

## Implementation Phasing

### Phase 1: Enhanced Validation (Foundation)
- Semantic validation
- Warning system
- Token address validation
- Error display improvements

### Phase 2: Environment Variables
- Advanced substitution (`${VAR:-default}`)
- `.env` file support
- Validation after substitution

### Phase 3: Inheritance System
- Single inheritance (`extends`)
- Deep merge logic
- Circular dependency detection

### Phase 4: Defaults Hierarchy
- Project defaults file (`.cow-perf-defaults.yml`)
- Precedence resolution (built-in → project → scenario → profile → CLI)
- CLI overrides integration

### Phase 5: Profiles
- Profile definition in scenario files
- Profile selection via CLI
- Profile merge logic

### Phase 6: Templates
- Template structure definition
- Built-in templates (ramp-up, spike, sustained)
- Template expansion logic
- Template parameter validation

### Phase 7: Configuration Generator
- Interactive CLI wizard
- Template-based generation
- Copy-from-existing mode
- Output validation

### Phase 8: Documentation
- Auto-generated reference
- Configuration guide
- Example configurations
- Best practices guide

---

## Success Criteria

**Technical:**
- [ ] All validation levels implemented
- [ ] Inheritance chains work (depth 3+)
- [ ] Profile overrides apply correctly
- [ ] Template expansion works
- [ ] Env var substitution handles all cases
- [ ] Defaults hierarchy resolves correctly
- [ ] Config generator produces valid configs
- [ ] Error messages are actionable
- [ ] 90%+ test coverage

**Usability:**
- [ ] Simple configs are truly simple (≤15 lines)
- [ ] Common patterns have templates
- [ ] Configuration wizard completes in <2 minutes
- [ ] Error messages lead to fixes without docs
- [ ] Examples cover 90% of use cases

**Documentation:**
- [ ] Complete configuration reference
- [ ] Step-by-step guide with examples
- [ ] Template gallery with descriptions
- [ ] Best practices guide
- [ ] Troubleshooting section

---

## Open Questions

1. **Template Discovery:** Should users be able to publish/share templates? If so, how?

2. **Remote Configs:** Should we support loading configs from URLs (for shared team configs)?

3. **Configuration Validation API:** Should we expose validation as a library API for integration with other tools?

4. **IDE Integration:** Should we provide JSON Schema files for IDE autocomplete/validation?

5. **Migration Tool:** When we change config schema, should we provide an auto-migration tool?

---

## Next Steps

1. Review this architecture with stakeholders
2. Get feedback on design decisions
3. Prioritize implementation phases
4. Begin Phase 1 implementation (Enhanced Validation)
5. Update thoughts/INDEX.md with this plan

---

## References

- M4-Issue-14 Implementation: `thoughts/plans/m4-issue-14-predefined-scenarios-plan.md`
- Existing Models: `src/cow_performance/cli/commands/scenarios.py`
- Existing Validation: `src/cow_performance/scenarios/validation.py`
- Issue Description: `issues/description/m4-issue-15-scenario-configuration-system.md`
