---
name: github-workflow
description: >
  Manage GitHub pull request workflows from Caret. Use this skill when the user
  asks to create PRs, inspect pull requests, check failed GitHub Actions or CI
  workflow runs, fetch workflow logs, summarize or respond to PR comments, store a
  personal GitHub token, or fix issues raised by PR review/CI feedback.
---

# GitHub Workflow

Use this skill to manage GitHub PR and CI workflows with per-user GitHub
tokens. Prefer the bundled helper over `gh`; `gh auth login` uses shared global
state and is not appropriate for multi-user Telegram usage.

Run commands from the repository root:

```bash
python3 .caret/skills/github-workflow/scripts/github_workflow.py --help
```

## Authentication

The helper stores a token per Caret actor under ignored workspace state:
`.caret/github-workflow/tokens/`. It needs `CARET_ADAPTER` and `CARET_USER_ID`,
which Caret provides for adapter-originated tool calls.

Check auth:

```bash
python3 .caret/skills/github-workflow/scripts/github_workflow.py auth status
```

Store a token:

```bash
python3 .caret/skills/github-workflow/scripts/github_workflow.py auth set-token --token-env GITHUB_TOKEN
```

If the token is provided directly by the user, use `--token` only for that one
operation and never print it back. Recommend fine-grained GitHub PATs limited to
the needed repositories.

If auth fails with missing actor metadata, explain that the command must run
from a Caret adapter session such as Telegram, or use `--token` for a one-off
read/write command.

## Required Repository Argument

Always require the user to provide `--repo owner/repo`. Do not infer repository
identity from git remotes unless the user explicitly asks for that.

## Common Tasks

Inspect a PR:

```bash
python3 .caret/skills/github-workflow/scripts/github_workflow.py pr view --repo owner/repo --number 123
```

Create a PR after confirming the write:

```bash
python3 .caret/skills/github-workflow/scripts/github_workflow.py pr create \
  --repo owner/repo \
  --head feature-branch \
  --base main \
  --title "Fix CI failure" \
  --body "Summary..."
```

List comments and review comments:

```bash
python3 .caret/skills/github-workflow/scripts/github_workflow.py pr comments --repo owner/repo --number 123
```

List GitHub Actions workflow runs for a branch or SHA:

```bash
python3 .caret/skills/github-workflow/scripts/github_workflow.py checks list --repo owner/repo --ref feature-branch
```

Fetch workflow-run logs:

```bash
python3 .caret/skills/github-workflow/scripts/github_workflow.py checks logs --repo owner/repo --run-id 123456789
```

Post a PR comment after confirming the write:

```bash
python3 .caret/skills/github-workflow/scripts/github_workflow.py comment create \
  --repo owner/repo \
  --issue-or-pr 123 \
  --body "Fixed in the latest push."
```

Add `--raw` to supported read commands when JSON is more useful than a summary.

## Workflow Rules

- Ask for explicit confirmation immediately before GitHub writes: PR creation,
  posting comments, replying to comments, or any command that changes remote
  GitHub state.
- For CI failures, inspect Actions workflow runs first, fetch logs for failed workflow
  runs, identify the likely failing command, reproduce locally when feasible,
  then patch and test the local fix.
- For review comments, fetch both issue comments and review comments, map
  comments to files/lines when available, make focused code changes, run the
  relevant tests, then draft or post a concise reply only after confirmation.
- Never delete branches, close PRs, merge PRs, dismiss reviews, or change repo
  settings in v1.
- Never print tokens, write tokens into skill files, or include tokens in final
  answers.

## Error Handling

- `missing GitHub token`: ask the user to run `auth set-token`.
- `missing Caret actor identity`: the command is not running from a user-scoped
  adapter context; ask for a one-off token or run from Telegram.
- `HTTP 401`: token is missing, expired, or invalid.
- `HTTP 403`: token lacks permission, SSO approval, or rate limit remains.
- `HTTP 404`: repo/PR/run is missing or token cannot access it.
- Network errors: report that GitHub is unreachable and retry only if useful.
