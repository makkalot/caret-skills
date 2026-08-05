---
name: safe-delete
description: >
  Review the files in a directory and walk the user through a safe, reversible,
  multi-step cleanup where the user approves what gets deleted before anything is
  removed. Use this skill whenever the user wants to clean up, declutter, free up
  space, "find files I can delete", review documents/images/downloads for deletion,
  remove duplicates, or sort through a folder to decide what is safe to delete —
  even if they don't say the word "skill". Always prefer this skill over running
  rm/del directly, because it adds human approval gates and full reversibility.
---

# Safe-delete: reviewed, reversible cleanup

The job of this skill is to help someone clean out a directory **without ever
losing something they wanted to keep.** Deletion is irreversible and people are
bad at predicting which files turn out to matter, so this workflow replaces "the
agent decides and deletes" with "the agent inventories and recommends, the human
approves, files go to a recoverable quarantine, and only a separate, explicitly
confirmed step removes them for good."

There are five stages. **Stop and wait for the user between stages — never chain
through them autonomously.** The whole value of the skill is the pauses.

```
scan ──▶ APPROVE ──▶ stage ──▶ (verify) ──▶ purge
 │         (human)    │                        │
 read-only            move to quarantine        permanent delete
                      └──────── restore ◀───────┘  (reversible until purge)
```

All operations are run through `scripts/safe_delete.py` (Python 3, standard
library only — nothing to install).

---

## Stage 0 — Confirm the target

Before doing anything, confirm with the user **exactly which directory** to
review, and resolve it to an absolute path. Show them the path and the rough
scale (e.g. run `find <dir> -type f | wc -l` or just note the folder) and get a
clear "yes, that one."

The script refuses the filesystem root and protected system locations outright,
and refuses the user's entire home directory unless `--allow-broad` is passed.
If the user really wants a huge or sensitive root, surface the risk first, then
pass `--allow-broad` only after they confirm.

Never widen the scope on your own. If they say "my Downloads folder," scan
Downloads — not its parent.

---

## Stage 1 — Scan (read-only)

Inventory the directory. This stage **reads only** — it moves and deletes
nothing.

```bash
python scripts/safe_delete.py scan --dir "<absolute/path>"
```

Useful flags:
- `--include-hidden` — also list dotfiles/dotfolders (off by default).
- `--min-size 1048576` — ignore files under N bytes (e.g. only consider ≥1 MB).
- `--blank-actions` — start every row as `keep` instead of prefilling
  suggestions. Use this when the user wants to opt **in** to each deletion
  rather than opt out of suggestions.

This writes two files into the target directory:
- `safe-delete-manifest.csv` — one row per file, the editable approval sheet.
- `safe-delete-report.md` — a human-readable summary.

**How files are classified** (these are *suggestions*, never decisions):
- **junk** — common cruft that is almost always safe: `.DS_Store`, `Thumbs.db`,
  `~$` Office lock files, `*.tmp/.temp/.bak/.old/.part`, things inside
  `__pycache__`/`.cache`. Suggested `delete`.
- **duplicate** — exact byte-for-byte copies (matched by SHA-256). The oldest
  copy is kept; the extras are suggested `delete`.
- **review** — older files with no obvious signal. Suggested `keep`; the human
  decides.
- **keep** — modified in the last 30 days, so more likely to still matter.
  Suggested `keep`.

After scanning, **summarize the report for the user in chat** — total files,
space, counts per category, and the biggest reclaimable items. Don't just dump
the CSV.

---

## Stage 2 — Approval (the human gate)

This is the heart of the skill. The `action` column in the manifest controls
everything downstream: only rows with `action` set to exactly `delete` are ever
touched. Everything else is left alone.

Walk the user through approval. Pick the style that fits the situation:

- **Category at a time** (good default): "I found 23 junk files (40 MB) and 11
  exact duplicates (300 MB). Want me to mark all junk for deletion? Any of these
  duplicates you'd rather keep both copies of?" Then update the `action` column
  accordingly.
- **Item by item** for the `review` bucket or anything ambiguous, especially
  documents, images, and anything irreplaceable. When unsure, default to
  `keep` and ask.
- **User edits it themselves**: tell them they can open
  `safe-delete-manifest.csv` in any spreadsheet app, set `action` to `delete` or
  `keep` per row, save, and tell you when done.

Rules for this stage:
- **Never mark something `delete` without the user having approved it** — either
  a specific file or an explicit "yes, all of that category."
- Treat documents, images, anything in a project folder, and anything modified
  recently as "ask first." Junk and exact duplicates are the only things safe to
  batch-approve, and even then confirm the batch.
- If the user is vague ("just clean it up"), do **not** interpret that as
  blanket approval to delete. Propose a conservative set (junk + duplicates
  only), show it, and ask.

When editing the CSV programmatically, preserve the header and only change the
`action` field. Re-show the user the final list of everything now marked
`delete`, with total size, and get one more "go ahead" before staging.

---

## Stage 3 — Stage (reversible move to quarantine)

Move every approved file into a timestamped quarantine folder. **Nothing is
destroyed** — files are relocated and can be restored.

```bash
python scripts/safe_delete.py stage --manifest "<dir>/safe-delete-manifest.csv" --dir "<dir>"
```

What happens:
- Approved files move to `<dir>/.safe-delete-trash/<timestamp>/`, preserving
  their relative folder structure.
- A `restore-log.json` is written recording every original → quarantine path.
- Symlinks, missing files, and anything resolving outside the base directory are
  skipped (reported, not moved).

Report back what was staged (count + space) and tell the user it's reversible.
The directory now looks "cleaned up" but everything is recoverable.

---

## Stage 4 — Verify, then restore or purge

Give the user a chance to confirm the directory looks right with the files gone.
Offer the two exits clearly:

**Undo (restore everything):**
```bash
python scripts/safe_delete.py restore --batch "<dir>/.safe-delete-trash/<timestamp>"
```
Files return to their original locations; the empty batch is cleaned up.

**Finalize (permanent, irreversible delete):**
```bash
python scripts/safe_delete.py purge --batch "<dir>/.safe-delete-trash/<timestamp>"
```
This is the only command that destroys data. It prints what will be deleted and
requires the user to type `DELETE` to confirm. **Do not pass `--yes` on the
user's behalf** — let them type the confirmation themselves, or relay the prompt
and have them confirm explicitly in chat before you run it.

To see what batches are still in quarantine:
```bash
python scripts/safe_delete.py list --dir "<dir>"
```

A reasonable default is to **leave files in quarantine** rather than purging.
The user can purge later once they're sure, or just delete the
`.safe-delete-trash` folder themselves. Only purge when the user explicitly asks
to free the space for good.

---

## Hard rules (do not break these)

1. **Never delete or `rm` directly.** Always go scan → approve → stage → purge.
   The script is the only path, and purge is the only destructive step.
2. **Never stage a file the user didn't approve.** `action=delete` must trace
   back to an explicit user decision.
3. **Never auto-purge.** Permanent deletion always needs a fresh, explicit
   confirmation, even if they approved staging earlier.
4. **Stay in scope.** Only the directory the user named. Don't follow symlinks
   out of it; don't widen to a parent.
5. **When in doubt, keep it and ask.** A kept junk file costs a few KB. A deleted
   document can be gone forever.

## Example interaction

> **User:** Can you clean up my ~/Downloads folder?
>
> **You:** Run `scan --dir ~/Downloads`. Then: "I went through 412 files
> (8.3 GB). 37 are junk (browser temp + `.DS_Store`, ~50 MB) and there are 18
> exact duplicates (2.1 GB — mostly repeated installer downloads). The other 357
> I'd leave for you to look at. Want me to mark the junk and duplicates for
> deletion, keeping the oldest copy of each duplicate? I won't touch anything
> else."
>
> **User:** Yes, and also delete the .dmg files I haven't opened in a year.
>
> **You:** Update the manifest accordingly, re-show the final delete list with
> total size, confirm, then `stage`. Tell them it's in quarantine and reversible,
> and ask whether to leave it there or purge.
