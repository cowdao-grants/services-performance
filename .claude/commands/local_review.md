# Local Review

Set up a local review environment for a colleague's branch and perform systematic code review using SSR principles.

## Git Safety Protocol

### BEFORE ANY GIT OPERATIONS

1. **Verify current state**: `git status` - ensure clean working directory
2. **Check branch**: Confirm you're on the correct branch before making changes
3. **Backup**: Create checkpoint before risky operations
4. **Remote verification**: Confirm remote URLs before fetching

### Safety Commands

```bash
# Always check first
git status
git branch -a
git remote -v

# Safe worktree creation
git worktree add --track -b BRANCH_NAME PATH REMOTE/BRANCH_NAME

# Safe cleanup
git worktree remove PATH --force  # Only if stuck
```

## SSR Review Principles

### Single Responsibility

- Each function/class has one clear purpose
- Components handle single concerns
- Files are cohesively organized

### Separation of Concerns

- Business logic separated from presentation
- Data layer separated from UI logic
- Configuration separated from implementation

### Readability

- Code is self-documenting
- Variable names reveal intent
- Control flow is clear and linear
- Comments explain "why", not "what"

## Critical Checks

### MUST CHECK (Blocking Issues)

- [ ] **Security**: No secrets, API keys, or sensitive data
- [ ] **Tests**: All tests pass, new code has tests
- [ ] **Breaking Changes**: No unintentional API changes
- [ ] **Performance**: No obvious performance regressions
- [ ] **Error Handling**: Proper error boundaries and validation

### SHOULD CHECK (Quality Issues)

- [ ] **Code Style**: Follows project conventions
- [ ] **Documentation**: Public APIs documented
- [ ] **Complexity**: Functions are reasonably sized
- [ ] **Dependencies**: No unnecessary dependencies
- [ ] **Type Safety**: Proper type hints throughout

### NICE TO HAVE (Enhancement Opportunities)

- [ ] **Performance**: Optimization opportunities
- [ ] **Refactoring**: Code could be cleaner
- [ ] **Best Practices**: Modern patterns usage
- [ ] **Documentation**: Additional examples/guides

## Workflow

### Setup Phase

```bash
# 1. Parse input: gh_username:branchName
# 2. Extract ticket from branch name (e.g., eng-1696)
# 3. Create short directory name from ticket

# Safety checks
git status
git remote -v

# Add remote if needed
git remote add USERNAME git@github.com:USERNAME/REPO_NAME

# Fetch and create worktree
git fetch USERNAME
git worktree add -b BRANCH_NAME ~/wt/REPO/TICKET_NAME USERNAME/BRANCH_NAME

# Configure environment
cp .env WORKTREE/
cd WORKTREE && poetry install
```

### Review Phase

1. **Code Analysis**: Apply SSR principles systematically
2. **Critical Checks**: Run through checklist above
3. **Test Execution**: Verify all tests pass
4. **Security Scan**: Check for sensitive data exposure
5. **Performance Review**: Identify potential bottlenecks

### Cleanup Phase

```bash
# When review complete
git worktree remove ~/wt/REPO/TICKET_NAME
git remote remove USERNAME  # If no longer needed
```

## Error Handling

- **Worktree exists**: `git worktree remove PATH` first
- **Remote fetch fails**: Verify username/repo exists
- **Setup fails**: Report error but continue with manual setup
- **Permission denied**: Check SSH keys and repo access

## Example Usage

```bash
/local_review colleague:colleague/eng-1696-feature-branch
```

Creates:

- Remote: `colleague`
- Worktree: `~/wt/cow-performance-testing-suite/eng-1696`
- Configured environment ready for review
