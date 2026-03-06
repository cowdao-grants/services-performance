# Commit Changes

Create git commits for session changes.

## Usage

```
/commit [type] [scope] [exclusions]
```

### Examples

| Command | What it does |
|---------|--------------|
| `/commit` | Commit all session changes (default behavior) |
| `/commit fix login bug` | Commit as a fix with message context |
| `/commit feat user auth` | Commit as a feature |
| `/commit folder src/metrics` | Only commit changes in `src/metrics/` |
| `/commit file config.py` | Only commit specific file |
| `/commit exclude tests/` | Commit everything except `tests/` |
| `/commit fix api, exclude logs` | Fix commit, excluding log files |
| `/commit docs readme update` | Documentation commit |

### Supported Types (Conventional Commits)

| Type | Use for |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code restructuring (no behavior change) |
| `test` | Adding/updating tests |
| `chore` | Maintenance, dependencies, config |
| `style` | Formatting, whitespace |

### Filtering Keywords

- `folder <path>` - Only include files in this directory
- `file <path>` - Only include this specific file
- `exclude <pattern>` - Exclude files matching pattern
- `only <pattern>` - Only include files matching pattern

## Git Safety Protocol

### NEVER Without Permission

- Update git config
- Force push to main/master
- Skip hooks (--no-verify)
- Amend without checking authorship

### Check Before Amending

```bash
git log -1 --format='%an %ae'  # Check authorship
git status  # Ensure "Your branch is ahead"
```

## Workflow

### 1. Analyze Changes (parallel)

```bash
git status
git diff
git log -3 --oneline
```

### 2. Plan Commits

- **Only include files relevant to the current session or user request** - Do NOT commit all staged/unstaged changes; focus on what was actually worked on
- If user specified files or a scope, respect that exactly
- Group related files into logical commits
- Draft messages (imperative mood)
- Focus on WHY, not WHAT

### 3. Branch Safety Check

```bash
git branch --show-current
```

**If on `main`, `master`,`develop`,`M1`,`M2`,`M3`,`M4` or `M5`**: STOP and ask the user:
> "You're on the [branch] branch. Are you sure you want to commit directly here instead of a feature branch?"

Only proceed after explicit confirmation.

### 4. Present Plan

"I plan to create [N] commit(s):

- Files: [list]
- Message: [message]
  Shall I proceed?"

### 5. Execute on Confirmation

```bash
git add [specific files]  # Never use -A or .
git commit -m "Message"
git log --oneline -n 3
```

## Important

✗ NO co-author attribution
✗ NO "Generated with Claude"
✗ NO "Co-Authored-By" lines
✓ Write as if user wrote them
✓ Keep commits atomic
✓ Handle pre-commit hooks if they modify files
