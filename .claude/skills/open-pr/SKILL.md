---
name: open-pr
description: >
  Open a pull request for the current branch. Writes a structured PR
  description summarising what was built, why, and how to test it.
  Requires the GitHub CLI (gh) to be installed and authenticated.
allowed-tools: Bash, Read
---

# /open-pr — Open a Pull Request

## Step 1 — Verify prerequisites

```bash
gh auth status
```

If not authenticated, tell the user:
"GitHub CLI is not authenticated. Run `gh auth login` first."

```bash
git status --short
```

If there are uncommitted changes, tell the user:
"You have uncommitted changes. Run /save-progress first."

## Step 2 — Check branch

```bash
git branch --show-current
git log main..HEAD --oneline
```

Show the user what commits will be in this PR. If there are no commits
ahead of main, stop: "No new commits to open a PR for."

## Step 3 — Push branch if needed

```bash
git push origin $(git branch --show-current) 2>&1 || \
git push --set-upstream origin $(git branch --show-current)
```

## Step 4 — Generate PR description

Read the git log and diff since branching from main, then write a
structured PR description:

```bash
git diff main...HEAD --stat
git log main...HEAD --oneline
```

PR description template:
```markdown
## Summary
<!-- What does this PR do? 1–3 sentences. -->

## Changes
<!-- Bullet list of the key changes made. Be specific about modules. -->
- 
- 
- 

## Testing
<!-- How was this tested? What should the reviewer run? -->

## Notes for reviewer
<!-- Anything unusual, incomplete, or requiring special attention. -->
```

## Step 5 — Open the PR

```bash
gh pr create \
  --title "<conventional commit style title>" \
  --body "<generated description>" \
  --base main \
  --draft
```

PRs open as drafts by default. Tell the user:
"PR opened as draft. Mark it ready for review when you're satisfied:
  `gh pr ready`"

Show the PR URL.
