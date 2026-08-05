---
name: xci-kanban
description: >
  Inspect and modify the XCI Kanban API at app.xci.ro. Use this skill when the
  user asks to view boards, columns, members, tags, cards, in-progress work, add
  or update tasks/cards, assign tags, move cards between columns, or otherwise
  manage the kanban via the XCI API.
---

# XCI Kanban

Use this skill to operate the XCI Kanban REST API through the bundled CLI.
The API uses Swagger 2.0, base URL `https://app.xci.ro/api/v1`, and Bearer JWT
authentication.

## Setup

This skill does not require installing Python packages. The bundled CLI uses
only the Python 3 standard library (`argparse`, `json`, `urllib`, `os`, `sys`).
Do not install `requests` or other packages just to use this skill.

Confirm Python is available:

```bash
python3 --version
```

If `python3` is missing, ask the user to install Python 3 before continuing.

If future changes require Python packages, always recommend a skill-local
virtual environment instead of installing packages globally:

```bash
python3 -m venv .caret/skills/xci-kanban/.venv
. .caret/skills/xci-kanban/.venv/bin/activate
python -m pip install "<package>"
```

Use the venv's Python when running package-dependent helpers:

```bash
.caret/skills/xci-kanban/.venv/bin/python .caret/skills/xci-kanban/scripts/xci_kanban.py list-boards
```

## API Token

The XCI API requires a Bearer JWT. Check whether a token is already configured:

```bash
printenv XCI_API_TOKEN
```

If that prints nothing, ask the user to provide a JWT or set it in the shell:

```bash
export XCI_API_TOKEN="<jwt>"
```

The CLI also accepts a one-off token:

```bash
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py --token "<jwt>" list-boards
```

Do not invent credentials, search for credentials, or write the token into the
skill files. Avoid printing the token back to the user. If the API returns
`HTTP 401`, report that the token is missing, expired, or invalid and ask for a
fresh token.

Test authentication with a read-only request:

```bash
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py list-boards
```

If this succeeds, use the returned board IDs for later commands. If it fails
with a network/DNS error, report that the API is not reachable from the current
environment.

## Quick Start

Run commands from the repository root:

```bash
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py list-boards
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py show-board --board-id 1
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py show-in-progress --board-id 1
```

The script prints readable summaries by default. Add `--raw` to print the API
JSON response unchanged.

If the user did not provide a board ID, run `list-boards` first and choose the
board only when the result is unambiguous. If multiple boards are returned, ask
which board to use.

## Common Tasks

Inspect:

```bash
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py list-columns --board-id 1
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py list-cards --board-id 1
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py list-members --board-id 1
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py list-tags --board-id 1
```

Create a card:

```bash
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py create-card \
  --board-id 1 \
  --column-id 3 \
  --title "Fix login bug" \
  --description "The login form fails on submit" \
  --tag-id 2
```

Move a card:

```bash
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py move-card \
  --board-id 1 \
  --card-id 42 \
  --column-id 4
```

Update card fields:

```bash
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py update-card \
  --board-id 1 \
  --card-id 42 \
  --title "Updated title"
```

Manage tags:

```bash
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py create-tag --board-id 1 --name Bug --color "#ef4444"
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py assign-tag --board-id 1 --card-id 42 --tag-id 2
python3 .caret/skills/xci-kanban/scripts/xci_kanban.py remove-tag --board-id 1 --card-id 42 --tag-id 2
```

## Workflow Rules

- For destructive operations such as deleting cards or tags, confirm the exact
  board/card/tag first unless the user already provided an explicit delete
  instruction with IDs.
- When the user refers to cards by title or status, inspect the board first and
  resolve the relevant IDs before modifying anything.
- For "in progress", use `show-in-progress`; it matches column names containing
  common in-progress terms such as `progress`, `doing`, `active`, or `started`.
  If no matching column exists, list columns and ask which column to use.
- Summarize API changes with the card/tag IDs and new state.

## Error Handling

- `Missing token. Set XCI_API_TOKEN or pass --token.`: ask the user for the JWT
  or ask them to export `XCI_API_TOKEN`.
- `HTTP 401`: token is absent, expired, malformed, or not accepted.
- `HTTP 403`: the user is authenticated but lacks permission for that board,
  card, or tag.
- `HTTP 404`: resolve IDs again with list commands; the board/card/tag may not
  exist or may not be accessible.
- `HTTP 400`: inspect the request body and required IDs; do not retry blindly.
- Network/DNS errors: state that the API is unreachable from this environment
  and retry only if the user asks.

## References

- `references/api-reference.md` contains endpoint and payload notes.
- `references/swagger.json` is the fetched Swagger document from
  `https://app.xci.ro/swagger/doc.json`.
