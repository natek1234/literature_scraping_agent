---
name: save-progress
description: >
  Stage, commit, and optionally push all current changes following the
  project's conventional commit standards. Run after completing any
  meaningful unit of work. Enforces branch safety rules — never commits
  directly to main or develop.
allowed-tools: Bash, Read
---

# /save-progress — Stage, Commit & Push

## Step 1 — Safety check

```bash
git branch --show-current
```

If the current branch is `main` or `develop`, stop immediately and tell
the user:

"You are on a protected branch (`main` or `develop`). Direct commits to
this branch are not allowed. Please create a feature branch first:
  `git checkout -b feat/your-feature-name`"

Do not proceed until the user is on a non-protected branch.

## Step 2 — Check for changes

```bash
git status --short
git diff --stat HEAD
```

If there are no changes, tell the user "Nothing to commit — working tree
is clean." and stop.

## Step 3 — Run pre-commit checks

Run these in order. If any fail, show the error and stop — do not commit
broken code.

```bash
# Format check
python -m black --check src/ tests/

# Lint
python -m ruff check src/ tests/

# Type check (fast mode)
python -m mypy src/ --no-error-summary

# Tests
python -m pytest tests/ -x -q --no-header
```

If formatting fails, auto-fix it first:
```bash
python -m black src/ tests/
python -m ruff check --fix src/ tests/
```
Then re-run the checks. If lint or type errors remain after auto-fix,
show them to the user and stop.

## Step 4 — Stage changes

```bash
git add -A
git status --short
```

Show the user exactly what is staged. Never stage `.env`, `outputs/`, or
`*.pyc` files. If any of these are accidentally staged, unstage them:
```bash
git reset HEAD .env outputs/ "*.pyc" 2>/dev/null || true
```

## Step 5 — Generate commit message

Read the staged diff and write a conventional commit message:

```bash
git diff --cached --stat
git diff --cached
```

Follow this format strictly:
```
<type>(<scope>): <short description under 72 chars>

<optional body — what changed and why, not how>

Co-Authored-By: Claude <noreply@anthropic.com>
```

Types:
- `feat` — new feature or capability
- `fix` — bug fix
- `refactor` — restructuring without behaviour change
- `test` — adding or updating tests
- `docs` — documentation only
- `chore` — build system, deps, config
- `perf` — performance improvement

Scope = the module or component changed (e.g. `scorer`, `nasa-ntrs`,
`semantic-scholar`, `zotero-writer`, `excel-writer`, `query-builder`,
`deduplicator`, `config`, `models`, `pipeline`, `cli`).

Good examples:
```
feat(nasa-ntrs): implement NASA NTRS REST client with pagination

Queries ntrs.nasa.gov/api/citations/search with offset-based pagination.
Returns PaperRecord with nasa_ntrs_id, source_type set to technical_report.
Never caps section_fit_score for NTRS records regardless of abstract presence.
```

```
fix(scorer): handle null kunze_dimension for S4 papers

Papers assigned to S4 sections now raise a WARNING and default to "maybe"
inclusion_decision when kunze_dimension is null, rather than silently
passing through with an incomplete record.
```

## Step 6 — Commit

```bash
git commit -m "<generated message>"
```

Show the user the full commit message before executing and ask:
"Commit with this message? (yes / edit / cancel)"

If "edit" — show the message and ask the user to provide a revised version.
If "cancel" — unstage with `git reset HEAD` and stop.
If "yes" — proceed.

## Step 7 — Push (optional)

After committing, ask:
"Push to origin/`<branch-name>`? (yes / no)"

If yes:
```bash
git push origin $(git branch --show-current)
```

If the branch has no upstream yet:
```bash
git push --set-upstream origin $(git branch --show-current)
```

Show the remote URL and branch name after pushing.
