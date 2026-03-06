# Create Pull Request

Create a draft pull request with comprehensive context gathered from the codebase.

## Usage

```
/create_pr [base_branch] [options]
```

### Examples

| Command | What it does |
|---------|--------------|
| `/create_pr` | Create PR from current branch to auto-detected base |
| `/create_pr develop` | Create PR targeting `develop` branch |
| `/create_pr main` | Create PR targeting `main` branch |
| `/create_pr feature/m1 to develop` | Compare specific branches |
| `/create_pr --reviewer @username` | Specify reviewer upfront |

---

## Step 0: Prerequisites Check (MUST RUN FIRST)

**Before doing anything else, verify the environment is ready:**

```bash
# 1. Check gh authentication
gh auth status 2>&1
```

**If output contains "not logged in" or errors:**
- STOP the workflow immediately
- Tell the user:
  ```
  GitHub CLI is not authenticated. Please run:

  gh auth login

  Then follow the prompts to authenticate. After that, run /create_pr again.
  ```
- Do NOT proceed with any other steps

**If authenticated, continue. Check for default repo:**

```bash
# 2. Check if repo is set
gh repo view --json nameWithOwner -q '.nameWithOwner' 2>&1
```

**If errors about "no default repository":**
- Tell the user:
  ```
  No default repository set. Please run:

  gh repo set-default

  And select the appropriate repository.
  ```
- Do NOT proceed

**If both pass, continue to Step 1.**

---

## Step 1: Check for Uncommitted Changes

```bash
git status --porcelain
```

If there are uncommitted changes, warn the user:
```
You have uncommitted changes. Do you want to:
1. Continue anyway (uncommitted changes won't be in the PR)
2. Stop so I can commit first
```

---

## Step 2: Determine Branches

```bash
# Get current branch
git branch --show-current

# Check if branch has upstream
git rev-parse --abbrev-ref @{upstream} 2>/dev/null

# List available branches for base detection
git branch -r --list 'origin/*' | head -20
```

**Branch detection priority:**
1. User-provided base branch (from arguments)
2. Check if branch tracks a remote and find parent
3. `develop` if it exists
4. `feature/m1-*` branches if on a feature branch
5. `main` or `master` as fallback

**Verify base branch exists:**
```bash
git rev-parse --verify origin/{base_branch} 2>/dev/null
```

If comparing specific branches (e.g., "branch-x to branch-y"), use those explicitly.

---

## Step 3: Push Branch if Needed

```bash
# Check if branch exists on remote
git ls-remote --heads origin $(git branch --show-current)
```

**If branch not on remote:**
```bash
git push -u origin $(git branch --show-current)
```

---

## Step 4: Extract Ticket Context

**From branch name:**
- Pattern: `{user}/{ticket-id}-{description}` → extract ticket ID
- Example: `jefferson/cow-587-metrics-framework` → `COW-587`
- Regex: `[Cc][Oo][Ww]-\d+`

**Check for local context files:**
```bash
# Look for ticket documentation (case-insensitive)
ls thoughts/tickets/ 2>/dev/null | grep -i "COW-"

# Look for related plans
ls thoughts/plans/*.md 2>/dev/null

# Look for research
ls thoughts/research/*.md 2>/dev/null
```

If ticket file found (e.g., `thoughts/tickets/COW-587.md`), read it to extract:
- Problem statement (from Summary section)
- Deliverables
- Acceptance criteria

---

## Step 5: Analyze Changes

```bash
# Get commit messages (best summary of work done)
git log {base_branch}..HEAD --oneline
git log {base_branch}..HEAD --format="%s%n%b" | head -100

# Get diff stats
git diff {base_branch}...HEAD --stat

# Get full diff (for detailed analysis)
git diff {base_branch}...HEAD
```

**Analysis steps:**
1. Read commit messages first - they summarize intent
2. Review the diff stats for scope
3. Identify:
   - New features added
   - Bugs fixed
   - Files modified/created/deleted
   - Breaking changes
   - Dependencies added

---

## Step 6: Gather Reviewer Options

**ONLY if gh is authenticated (verified in Step 0):**

```bash
# Get collaborators with their GitHub usernames (NOT display names)
gh api repos/:owner/:repo/collaborators --jq '.[].login' 2>/dev/null
```

**If API call fails or returns empty, try:**
```bash
# Get from recent PR authors (these are GitHub usernames)
gh pr list --state all --limit 20 --json author --jq '.[].author.login' | sort -u
```

**If still no results:**
- Skip reviewer assignment
- Tell user: "Could not fetch collaborators. You can add a reviewer manually after PR creation."

**Present options with AskUserQuestion:**
```
Who should review this PR?

Options:
1. @username1
2. @username2
3. @username3
4. Skip reviewer (add manually later)
5. Other (I'll type the username)
```

**IMPORTANT:** Only use GitHub usernames (e.g., `luizhatem`), NOT display names (e.g., "Luiz Gustavo").

---

## Step 7: Generate PR Description

Use the project's PR template format (`.github/pull_request_template.md`):

```markdown
## Summary

[1-3 sentences: what this PR does and why]
[Reference the ticket/issue if applicable]

## Changes

- [Specific change 1]
- [Specific change 2]
- [Group by area if many changes]

## How to Test

1. [Concrete step with actual commands]
2. [Another step]
3. [Expected outcome]

## Checklist

- [ ] Tests pass locally (`poetry run pytest`)
- [ ] Linting passes (`poetry run ruff check .`)
- [ ] Type checking passes (`poetry run mypy .`)
- [ ] Documentation updated (if needed)
- [ ] Breaking changes documented (if any)

## Breaking Changes

[List any breaking changes, or "None"]

## Related Issues

[Link to Linear ticket if detected]
- Closes COW-XXX (if applicable)
```

---

## Step 8: Create Draft PR

```bash
# Write body to temp file to avoid shell escaping issues
cat > /tmp/pr_body.md << 'PREOF'
{generated_description}
PREOF

# Create the PR
gh pr create \
  --draft \
  --base {base_branch} \
  --title "{title}" \
  --body-file /tmp/pr_body.md
```

**If reviewer was selected (and is a valid username):**
```bash
gh pr create \
  --draft \
  --base {base_branch} \
  --title "{title}" \
  --body-file /tmp/pr_body.md \
  --reviewer {reviewer_username}
```

---

## Step 9: Return Result

After successful creation:

```
PR created successfully!

URL: {pr_url}
Status: Draft

Next steps:
1. Review the PR description on GitHub
2. Complete any unchecked items in the checklist
3. When ready, mark as "Ready for Review"
```

---

## Title Generation

Generate title from (in priority order):
1. Ticket title (if found in `thoughts/tickets/`)
2. First commit message on the branch
3. Branch name description (cleaned up)

**Format:** `{type}: {description}`

| Type | When to use |
|------|-------------|
| `feat` | New feature or functionality |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code restructuring (no behavior change) |
| `chore` | Maintenance, config, dependencies |
| `test` | Adding or updating tests |
| `style` | Formatting, whitespace |

---

## Context Sources (Priority Order)

| Source | What to extract |
|--------|-----------------|
| `thoughts/tickets/COW-XXX.md` | Problem statement, deliverables, acceptance criteria |
| `thoughts/plans/*.md` | Implementation approach, decisions made |
| `thoughts/research/*.md` | Background context, alternatives considered |
| Commit messages | What was done and why |
| Diff | Actual code changes |

---

## Important Rules

- Create PRs as **draft** by default
- NO "Generated by AI/Claude" or similar attribution
- NO "Co-Authored-By" lines
- Write as if the developer wrote it naturally
- Keep descriptions scannable but comprehensive
- Focus on the "why" as much as the "what"
- Link to Linear tickets when detected from branch name

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| "gh: not logged in" | Run `gh auth login` and follow prompts |
| "no default repository" | Run `gh repo set-default` and select repo |
| "branch not found on remote" | Run `git push -u origin {branch}` |
| "reviewer not found" | Use GitHub username, not display name |
| "base branch doesn't exist" | Check spelling, use `git branch -r` to list |
