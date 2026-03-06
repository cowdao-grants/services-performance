# README.md Restructuring - Implementation Plan

## Objective

Condense the [README.md](<http://README.md>) (currently 2099 lines) by splitting content into multiple focused documentation files, keeping only the project overview and basic usage in the main README.

## Goals

1. **Simplify **[**README.md**](<http://README.md>): Keep only essential information for new users
2. **Improve Documentation Structure**: Organize content by topic in separate files
3. **Enhance Discoverability**: Make it easier to find specific documentation
4. **Add **[**CLAUDE.md**](<http://CLAUDE.md>): Create navigation guide to help Claude Code navigate the project
5. **Document Setup Process**: Clearly document the 5 setup steps with troubleshooting notes

## Current State Analysis

### [README.md](<http://README.md>) Structure (2099 lines)

The current README contains:

* Project overview and features
* Quick start guide
* Comprehensive CLI documentation
* Configuration reference (all options explained)
* Scenario examples
* Baseline testing documentation
* Fork mode setup instructions
* Development guide
* Testing documentation
* Architecture details
* Order generation module documentation
* Conditional orders guide
* User simulation documentation
* Docker setup
* Contributing guidelines
* Roadmap

### Existing Documentation

* `docs/architecture.md` (361 lines): System architecture overview
* `docs/development.md` (665 lines): Development guidelines
* Git submodules: services, hooks-trampoline, watch-tower

## Proposed New Structure

### 1\. [README.md](<http://README.md>) (Condensed - Target: \~150-200 lines)

Keep only:

* **Project Title and Description** (3-5 lines)
* **Key Features** (bullet list, 5-8 items)
* **Prerequisites** (Docker, Python 3.13, Poetry, ETH RPC URL)
* **Quick Start** (5 setup steps + basic usage example)
* **Documentation Links** (table of contents linking to other docs)
* **Contributing** (brief note with link to [development.md](<http://development.md>))
* **License**

Remove/Move to other files:

* Detailed CLI documentation → `docs/cli-usage.md`
* Configuration reference → `docs/configuration.md`
* All examples → `docs/examples.md`
* Testing guide → `docs/testing.md`
* Architecture details → Already in `docs/architecture.md`
* Order generation details → `docs/order-generation.md`
* Conditional orders → `docs/conditional-orders.md`
* User simulation → `docs/user-simulation.md`

### 2\. docs/setup.md (NEW - Target: \~200-250 lines)

**Content:**

* **Prerequisites** (detailed requirements)
* **Step-by-Step Setup**:
  1. **Git Submodule Init and Update**
     * Command: `git submodule update --init --recursive`
     * What it does: Initializes services, hooks-trampoline, watch-tower
     * Troubleshooting: submodule clone failures
  2. **Set ETH_RPC_URL Environment Variable**
     * Command: `export ETH_RPC_URL="https://mainnet.infura.io/v3/YOUR_KEY"`
     * Where to get an RPC URL (Infura, Alchemy, etc.)
     * Why it's needed: Anvil fork mode requires mainnet state
  3. **Run docker-compose up -d**
     * Command: `docker-compose up -d`
     * Services started: Anvil (port 8545), Orderbook (port 8080)
     * **Important Note**: Orderbook may show as "unhealthy" initially
       * Root cause: Orderbook compilation takes 5-10 minutes
       * How to check: `docker-compose logs -f orderbook`
       * Wait for: "Listening on 0.0.0.0:8080" message
     * Troubleshooting: port conflicts, Docker memory limits
  4. **Setup Python Virtual Environment**
     * Commands:

       ```bash
       poetry install
       source .venv/bin/activate  # or: poetry shell
       ```
     * Verify: `which python` should show `.venv/bin/python`
     * Troubleshooting: Poetry not found, Python version mismatch
  5. **Run cow-perf**
     * Verify installation: `cow-perf version`
     * Basic test: `cow-perf run --config configs/scenarios/test-funded-scenario.yml`
     * Expected output: Performance test results
* **Additional Step: Run Tests**
  * Unit tests: `pytest -m unit`
  * Integration tests: `pytest -m integration`
  * All tests: `pytest`
  * With coverage: `pytest --cov=src/cow_performance --cov-report=html`
* **Verification Checklist**:
  - [ ] Submodules cloned successfully
  - [ ] ETH_RPC_URL environment variable set
  - [ ] Docker services running (anvil, orderbook)
  - [ ] Orderbook healthy and responding
  - [ ] Virtual environment activated
  - [ ] cow-perf command available
  - [ ] Tests passing
* **Troubleshooting Common Issues**:
  * Orderbook compilation timeout
  * RPC URL rate limiting
  * Docker resource constraints
  * Python version mismatches

### 3\. docs/cli-usage.md (NEW - Target: \~300-400 lines)

**Content from **[**README.md**](<http://README.md>):

* CLI commands overview
* `cow-perf run` command with all options
* `cow-perf version` command
* Command-line flags and arguments
* Output format options (table, JSON, Prometheus)
* Examples of CLI usage
* Integration with Prometheus/Grafana

### 4\. docs/configuration.md (NEW - Target: \~400-500 lines)

**Content from **[**README.md**](<http://README.md>):

* Configuration file format (YAML)
* Network configuration section
* API configuration section
* Output configuration section
* Wallet configuration section
* Order type ratios configuration
* Token configuration
* Trader behavior parameters
* Complete configuration reference
* Configuration examples

### 5\. docs/examples.md (NEW - Target: \~300-400 lines)

**Content from **[**README.md**](<http://README.md>):

* Basic scenario examples
* Advanced scenario examples
* Baseline testing examples
* Fork mode examples
* Multi-trader scenarios
* Custom token pair examples
* Prometheus integration example

### 6\. docs/testing.md (NEW - Target: \~250-300 lines)

**Content from **[**README.md**](<http://README.md>):

* Testing overview
* Unit tests (`pytest -m unit`)
* Integration tests (`pytest -m integration`)
* E2E tests (`pytest -m e2e`)
* Coverage reporting
* Writing new tests
* Test fixtures and helpers
* CI/CD integration

### 7\. docs/order-generation.md (NEW - Target: \~300-350 lines)

**Content from **[**README.md**](<http://README.md>):

* Order generation module overview
* OrderFactory class documentation
* Market orders
* Limit orders
* Order parameters
* Token pair selection
* Amount calculation
* Order signing (EIP-712)
* Order validation

### 8\. docs/conditional-orders.md (NEW - Target: \~250-300 lines)

**Content from **[**README.md**](<http://README.md>):

* Conditional orders overview
* ComposableCow integration
* TWAP orders
* Stop-loss orders
* Good-after-time orders
* Custom conditional logic
* Testing conditional orders

### 9\. docs/user-simulation.md (NEW - Target: \~300-350 lines)

**Content from **[**README.md**](<http://README.md>):

* User simulation architecture
* TraderSimulator class
* TraderOrchestrator class
* TraderAccount state management
* Order lifecycle tracking
* Concurrent trader simulation
* Behavior patterns
* Performance considerations

### 10\. [CLAUDE.md](<http://CLAUDE.md>) (NEW - Target: \~400-500 lines)

**Purpose**: Navigation guide for Claude Code

**Content**:

* **Project Overview**: Quick summary, tech stack, key capabilities
* **Quick Start for Claude**: The 5 setup steps + testing commands
* **Project Structure**: Directory tree with file descriptions
* **Key Files and Their Purpose**: Table mapping files to functions
* **Common Development Tasks**:
  * Adding new order types
  * Adding CLI commands
  * Adding metrics
  * Debugging order submission
* **Environment Details**:
  * Docker services and ports
  * Wallet funding mechanism
  * Token addresses and storage slots
* **Known Issues**: Link to issues/ directory
* **Git Submodules**: What they are and how to update
* **Documentation Files**: Map of all docs and their content
* **Useful Commands Reference**: Quick command cheatsheet
* **Tips for Claude**:
  * Always read before editing
  * Run tests after changes
  * Check code quality
  * Reference line numbers
  * Use existing patterns

## Implementation Steps

### Phase 1: Create New Documentation Files

1. **Create docs/setup.md**
   * Extract setup instructions from README
   * Add detailed 5-step setup guide
   * Add orderbook compilation note
   * Add verification checklist
   * Add troubleshooting section
2. **Create docs/cli-usage.md**
   * Extract CLI documentation from README
   * Organize by command
   * Add comprehensive examples
3. **Create docs/configuration.md**
   * Extract configuration reference from README
   * Organize by section
   * Add complete option descriptions
4. **Create docs/examples.md**
   * Extract all examples from README
   * Organize by complexity
   * Add scenario descriptions
5. **Create docs/testing.md**
   * Extract testing documentation from README
   * Add test writing guide
   * Add coverage instructions
6. **Create docs/order-generation.md**
   * Extract order generation docs from README
   * Add API reference
   * Add examples
7. **Create docs/conditional-orders.md**
   * Extract conditional order docs from README
   * Add implementation guide
   * Add examples
8. **Create docs/user-simulation.md**
   * Extract user simulation docs from README
   * Add architecture details
   * Add usage guide

### Phase 2: Create [CLAUDE.md](<http://CLAUDE.md>)

1. **Create **[**CLAUDE.md**](<http://CLAUDE.md>)
   * Write project overview
   * Document 5 setup steps
   * Create project structure map
   * List key files with descriptions
   * Add common tasks guide
   * Add command reference
   * Add tips for Claude

### Phase 3: Condense [README.md](<http://README.md>)

1. **Rewrite **[**README.md**](<http://README.md>)
   * Keep project title and description
   * Keep key features list
   * Keep prerequisites
   * Keep quick start (reference [setup.md](<http://setup.md>) for details)
   * Add documentation table of contents with links
   * Keep brief contributing note
   * Keep license
2. **Verify all content is migrated**
   * Cross-reference old README with new docs
   * Ensure no content is lost
   * Update internal links

### Phase 4: Update Cross-References

1. **Update links in all files**
   * Update README links to point to new docs
   * Update docs/ links to point to other docs
   * Ensure [CLAUDE.md](<http://CLAUDE.md>) links are correct
2. **Update contributing guide**
   * Reference new documentation structure
   * Update [development.md](<http://development.md>) if needed

### Phase 5: Testing and Validation

1. **Review all documentation**
   * Check for broken links
   * Verify formatting
   * Test code examples
2. **Get feedback**
   * Review with team
   * Ensure clarity and completeness

## File Changes Summary

| Action | File | Lines | Notes |
| -- | -- | -- | -- |
| **MODIFY** | `README.md` | 2099 → \~150-200 | Condense to essentials only |
| **CREATE** | `docs/setup.md` | \~200-250 | Detailed 5-step setup guide |
| **CREATE** | `docs/cli-usage.md` | \~300-400 | CLI documentation |
| **CREATE** | `docs/configuration.md` | \~400-500 | Configuration reference |
| **CREATE** | `docs/examples.md` | \~300-400 | Usage examples |
| **CREATE** | `docs/testing.md` | \~250-300 | Testing guide |
| **CREATE** | `docs/order-generation.md` | \~300-350 | Order generation docs |
| **CREATE** | `docs/conditional-orders.md` | \~250-300 | Conditional orders guide |
| **CREATE** | `docs/user-simulation.md` | \~300-350 | User simulation docs |
| **CREATE** | `CLAUDE.md` | \~400-500 | Project navigation guide |
| **KEEP** | `docs/architecture.md` | 361 | Already well-structured |
| **KEEP** | `docs/development.md` | 665 | Already well-structured |

**Total new documentation**: \~2,700-3,350 lines across 9 new files
**Net documentation change**: +600-1,250 lines (better organized)

## Benefits

1. **Improved Onboarding**: New users see concise README with clear setup steps
2. **Better Organization**: Content organized by topic, easier to find
3. **Maintainability**: Smaller files easier to update and maintain
4. **Claude Navigation**: [CLAUDE.md](<http://CLAUDE.md>) helps AI navigate project efficiently
5. **Comprehensive Setup Guide**: Step-by-step instructions with troubleshooting
6. **Reduced Cognitive Load**: Users only read what they need

## Risks and Mitigations

| Risk | Mitigation |
| -- | -- |
| Broken links after restructuring | Phase 4 ensures all links updated |
| Content loss during migration | Phase 3 includes content verification |
| Users expect everything in README | Add clear navigation in README |
| Increased file maintenance | Better organization reduces overall maintenance |

## Success Criteria

- [ ] [README.md](<http://README.md>) reduced to \~150-200 lines
- [ ] All 8 new documentation files created
- [ ] [CLAUDE.md](<http://CLAUDE.md>) created with comprehensive navigation
- [ ] 5-step setup guide clearly documented with orderbook compilation note
- [ ] All cross-references and links working
- [ ] No content lost from original README
- [ ] Documentation reviewed and approved
- [ ] Tests still pass (no code changes, but verify docs accuracy)

## Timeline Estimate

* **Phase 1**: Create new documentation files (\~3-4 hours)
* **Phase 2**: Create [CLAUDE.md](<http://CLAUDE.md>) (\~1 hour)
* **Phase 3**: Condense [README.md](<http://README.md>) (\~1 hour)
* **Phase 4**: Update cross-references (\~30 minutes)
* **Phase 5**: Testing and validation (\~30 minutes)

**Total**: \~5-6 hours of focused work

## Next Steps

1. Review this plan with team
2. Get approval to proceed
3. Create branch: `docs/restructure-readme`
4. Execute phases 1-5
5. Create pull request
6. Review and merge

---

## Notes

* This restructuring does not change any code, only documentation
* All existing documentation content will be preserved
* The goal is organization, not rewriting
* [CLAUDE.md](<http://CLAUDE.md>) is a new concept to help AI navigate the project
* Setup guide should be actionable and include common pitfalls (like orderbook compilation delay)

## Metadata
- URL: [https://linear.app/bleu-builders/issue/COW-608/readmemd-restructuring-implementation-plan](https://linear.app/bleu-builders/issue/COW-608/readmemd-restructuring-implementation-plan)
- Identifier: COW-608
- Status: Todo
- Priority: No priority
- Assignee: jefferson@bleu.studio
- Project: [cow-performance-testing-suite](https://linear.app/bleu-builders/project/cow-performance-testing-suite-76a5f7d55e4d).
- Created: 2026-01-27T15:16:32.157Z
- Updated: 2026-01-27T19:39:15.755Z
