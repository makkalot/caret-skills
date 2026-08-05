#!/usr/bin/env python3
"""
safe_delete.py — a reversible, human-approved cleanup workflow.

Subcommands:
  scan     Inventory a directory (read-only), detect duplicates, classify files,
           and write an editable manifest (CSV) plus a human-readable summary.
  stage    Read an approved manifest and MOVE files marked action=delete into a
           timestamped quarantine folder. Reversible. Nothing is destroyed.
  list     Show the quarantine batches that currently exist.
  restore  Move a quarantined batch back to its original locations.
  purge    PERMANENTLY delete a quarantine batch. The only destructive command.
           Requires explicit confirmation.

Design rule: no file is ever permanently removed without (a) appearing in a
manifest, (b) being moved to quarantine first, and (c) a separate purge that is
explicitly confirmed. Every step writes a log.

Pure standard library. No external dependencies.
"""

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

QUARANTINE_DIRNAME = ".safe-delete-trash"
MANIFEST_FIELDS = [
    "action",
    "category",
    "reason",
    "path",
    "size_bytes",
    "size_human",
    "modified",
    "sha256",
]

# Filenames / patterns that are very commonly safe junk. These are only
# *suggestions* — the human still approves. Kept conservative on purpose.
JUNK_EXACT = {".DS_Store", "Thumbs.db", "desktop.ini", ".localized"}
JUNK_SUFFIXES = (
    ".tmp",
    ".temp",
    ".bak",
    ".old",
    ".swp",
    ".swo",
    ".crdownload",
    ".part",
)
JUNK_PREFIXES = ("~$",)  # Office lock files
JUNK_DIR_PARTS = {"__pycache__", ".cache", ".Trash", QUARANTINE_DIRNAME}


# Roots we refuse to scan/stage without --allow-broad, because a mistake here is
# catastrophic. We always refuse the filesystem root outright.
def _system_roots():
    roots = {
        "/",
        "/home",
        "/Users",
        "/etc",
        "/usr",
        "/bin",
        "/var",
        "/System",
        "/Library",
    }
    # Windows-ish guards (harmless on posix)
    roots |= {"C:\\", "C:/"}
    return {os.path.normpath(r) for r in roots}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def human_size(n: int) -> str:
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < step:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= step
    return f"{n:.1f} PB"


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def guard_root(target: Path, allow_broad: bool) -> None:
    norm = os.path.normpath(str(target.resolve()))
    if norm == os.path.normpath(str(Path(target.anchor or "/").resolve())):
        sys.exit("REFUSED: refusing to operate on the filesystem root.")
    if norm in _system_roots():
        sys.exit(f"REFUSED: '{norm}' is a protected system location.")
    if norm == os.path.normpath(str(Path.home())) and not allow_broad:
        sys.exit(
            "REFUSED: that is your entire home directory. "
            "Pass --allow-broad only if you really mean it."
        )


def classify(path: Path, rel: Path, dup_role: str):
    """Return (category, reason, suggested_action)."""
    name = path.name
    if dup_role == "duplicate":
        return ("duplicate", "Exact byte-for-byte copy of another kept file", "delete")
    if name in JUNK_EXACT:
        return ("junk", f"Common system/cruft file ({name})", "delete")
    if name.startswith(JUNK_PREFIXES):
        return ("junk", "Temporary lock file", "delete")
    if name.endswith(JUNK_SUFFIXES):
        return ("junk", f"Temporary/backup file ({path.suffix})", "delete")
    if any(part in JUNK_DIR_PARTS for part in rel.parts):
        return ("junk", "Inside a cache/build directory", "delete")

    # Age signal — recently touched files are more likely to matter.
    try:
        age_days = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).days
    except OSError:
        age_days = 0
    if age_days <= 30:
        return ("keep", f"Modified recently ({age_days}d ago)", "keep")

    return ("review", f"Needs a human decision (last modified {age_days}d ago)", "keep")


# --------------------------------------------------------------------------- #
# scan
# --------------------------------------------------------------------------- #
def cmd_scan(args):
    target = Path(args.dir).expanduser()
    if not target.is_dir():
        sys.exit(f"Not a directory: {target}")
    guard_root(target, args.allow_broad)

    out_csv = (
        Path(args.out).expanduser() if args.out else target / "safe-delete-manifest.csv"
    )
    out_md = (
        Path(args.report).expanduser()
        if args.report
        else target / "safe-delete-report.md"
    )

    # 1) collect files (skip symlinks, skip our own quarantine + outputs)
    files = []  # (path, rel, size, mtime)
    skip_names = {out_csv.name, out_md.name}
    for root, dirs, names in os.walk(target, followlinks=False):
        # prune quarantine dir from traversal
        dirs[:] = [d for d in dirs if d != QUARANTINE_DIRNAME]
        if not args.include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith(".")]
        for n in names:
            if n in skip_names:
                continue
            if not args.include_hidden and n.startswith("."):
                # still allow known junk dotfiles through, they're useful to flag
                if n not in JUNK_EXACT:
                    continue
            p = Path(root) / n
            if p.is_symlink() or not p.is_file():
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size < args.min_size:
                continue
            files.append((p, p.relative_to(target), st.st_size, st.st_mtime))

    if not files:
        print("No files matched. (Try --include-hidden or a lower --min-size.)")
        return

    # 2) duplicate detection — only hash within same-size groups (fast)
    by_size = defaultdict(list)
    for rec in files:
        by_size[rec[2]].append(rec)

    dup_role = {}  # path -> "duplicate" | "original"
    for size, group in by_size.items():
        if len(group) < 2:
            continue
        by_hash = defaultdict(list)
        for p, rel, sz, mt in group:
            try:
                by_hash[sha256_of(p)].append((p, rel, sz, mt))
            except OSError:
                continue
        for digest, same in by_hash.items():
            if len(same) < 2:
                continue
            # keep the oldest copy as the "original", flag the rest
            same.sort(key=lambda r: r[3])
            dup_role[same[0][0]] = "original"
            for p, *_ in same[1:]:
                dup_role[p] = "duplicate"

    # 3) classify + compute hashes for the manifest (cheap if already done)
    hash_cache = {}

    def get_hash(p):
        if p in hash_cache:
            return hash_cache[p]
        try:
            hash_cache[p] = sha256_of(p)
        except OSError:
            hash_cache[p] = ""
        return hash_cache[p]

    rows = []
    counts = defaultdict(int)
    reclaim = defaultdict(int)
    for p, rel, size, mtime in sorted(files, key=lambda r: str(r[1])):
        cat, reason, suggested = classify(p, rel, dup_role.get(p, ""))
        counts[cat] += 1
        if suggested == "delete":
            reclaim[cat] += size
        rows.append(
            {
                "action": suggested if not args.blank_actions else "keep",
                "category": cat,
                "reason": reason,
                "path": str(p),
                "size_bytes": size,
                "size_human": human_size(size),
                "modified": iso(mtime),
                "sha256": get_hash(p)[:16] if cat == "duplicate" else "",
            }
        )

    # 4) write manifest
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(rows)

    # 5) write human-readable report
    total = sum(r["size_bytes"] for r in rows)
    suggested_del = [r for r in rows if r["action"] == "delete"]
    suggested_bytes = sum(r["size_bytes"] for r in suggested_del)
    lines = [
        f"# Safe-delete review — {target}",
        f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        f"- **{len(rows)}** files, **{human_size(total)}** total",
        f"- **{len(suggested_del)}** suggested for deletion "
        f"(**{human_size(suggested_bytes)}** reclaimable)",
        "",
        "## By category",
        "",
        "| Category | Files | Reclaimable if deleted |",
        "|---|---:|---:|",
    ]
    for cat in ("junk", "duplicate", "review", "keep"):
        if counts[cat]:
            lines.append(f"| {cat} | {counts[cat]} | {human_size(reclaim[cat])} |")
    lines += [
        "",
        "## Suggested deletions (largest first)",
        "",
        "| Action | Category | Size | File | Why |",
        "|---|---|---:|---|---|",
    ]
    for r in sorted(suggested_del, key=lambda r: -r["size_bytes"])[:50]:
        lines.append(
            f"| {r['action']} | {r['category']} | {r['size_human']} | "
            f"`{r['path']}` | {r['reason']} |"
        )
    lines += [
        "",
        "## Next step",
        "",
        f"1. Open `{out_csv.name}` and set each row's **action** to `delete` or `keep`.",
        "2. Then stage the approved deletions (reversible move to quarantine):",
        "",
        f'   `python safe_delete.py stage --manifest "{out_csv}"`',
        "",
        "Nothing is removed until you stage, and even then it's only moved to a "
        "quarantine folder you can restore from.",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Scanned {len(rows)} files ({human_size(total)}).")
    print(
        f"  junk={counts['junk']}  duplicate={counts['duplicate']}  "
        f"review={counts['review']}  keep={counts['keep']}"
    )
    print(
        f"  suggested delete: {len(suggested_del)} files "
        f"({human_size(suggested_bytes)} reclaimable)"
    )
    print(f"Manifest: {out_csv}")
    print(f"Report:   {out_md}")


# --------------------------------------------------------------------------- #
# stage
# --------------------------------------------------------------------------- #
def cmd_stage(args):
    manifest = Path(args.manifest).expanduser()
    if not manifest.is_file():
        sys.exit(f"Manifest not found: {manifest}")

    with open(manifest, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    to_delete = [r for r in rows if (r.get("action") or "").strip().lower() == "delete"]
    if not to_delete:
        sys.exit("No rows marked action=delete. Edit the manifest first.")

    # Determine the common base dir = the target the manifest came from.
    base = (
        Path(args.dir).expanduser()
        if args.dir
        else Path(os.path.commonpath([r["path"] for r in to_delete])).parent
    )
    guard_root(base, args.allow_broad)

    qroot = (
        Path(args.quarantine).expanduser()
        if args.quarantine
        else base / QUARANTINE_DIRNAME
    )
    batch = qroot / now_stamp()
    batch.mkdir(parents=True, exist_ok=True)

    log = {
        "created": datetime.now(timezone.utc).isoformat(),
        "base": str(base.resolve()),
        "items": [],
    }
    moved = errors = 0
    moved_bytes = 0
    for r in to_delete:
        src = Path(r["path"]).expanduser()
        if not src.exists():
            print(f"  skip (gone): {src}")
            continue
        if src.is_symlink():
            print(f"  skip (symlink): {src}")
            continue
        # path-escape guard: only move things under base
        if not is_within(src, base):
            print(f"  skip (outside base): {src}")
            continue
        try:
            rel = src.resolve().relative_to(base.resolve())
        except ValueError:
            rel = Path(src.name)
        dst = batch / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            size = src.stat().st_size
            shutil.move(str(src), str(dst))
            log["items"].append(
                {
                    "original": str(src.resolve()),
                    "quarantine": str(dst.resolve()),
                    "size_bytes": size,
                }
            )
            moved += 1
            moved_bytes += size
        except OSError as e:
            print(f"  ERROR moving {src}: {e}")
            errors += 1

    (batch / "restore-log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")

    print(f"\nStaged {moved} file(s), {human_size(moved_bytes)} into quarantine.")
    if errors:
        print(f"  {errors} error(s) — see messages above.")
    print(f"Quarantine batch: {batch}")
    print("\nThis is reversible. To undo:")
    print(f'  python safe_delete.py restore --batch "{batch}"')
    print("To permanently delete this batch (NOT reversible):")
    print(f'  python safe_delete.py purge --batch "{batch}"')


# --------------------------------------------------------------------------- #
# list / restore / purge
# --------------------------------------------------------------------------- #
def _batches(qroot: Path):
    if not qroot.is_dir():
        return []
    out = []
    for d in sorted(qroot.iterdir()):
        log = d / "restore-log.json"
        if d.is_dir() and log.is_file():
            data = json.loads(log.read_text(encoding="utf-8"))
            n = len(data.get("items", []))
            sz = sum(i.get("size_bytes", 0) for i in data.get("items", []))
            out.append((d, n, sz, data.get("created", "?")))
    return out


def cmd_list(args):
    base = Path(args.dir).expanduser() if args.dir else Path.cwd()
    qroot = (
        Path(args.quarantine).expanduser()
        if args.quarantine
        else base / QUARANTINE_DIRNAME
    )
    batches = _batches(qroot)
    if not batches:
        print(f"No quarantine batches under {qroot}")
        return
    print(f"Quarantine batches under {qroot}:\n")
    for d, n, sz, created in batches:
        print(f"  {d.name}   {n} files   {human_size(sz)}   (staged {created})")


def cmd_restore(args):
    batch = Path(args.batch).expanduser()
    log_file = batch / "restore-log.json"
    if not log_file.is_file():
        sys.exit(f"No restore-log.json in {batch}")
    data = json.loads(log_file.read_text(encoding="utf-8"))
    restored = errors = 0
    for item in data.get("items", []):
        src = Path(item["quarantine"])
        dst = Path(item["original"])
        if not src.exists():
            print(f"  skip (gone): {src}")
            continue
        if dst.exists():
            print(f"  skip (original path occupied): {dst}")
            errors += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dst))
            restored += 1
        except OSError as e:
            print(f"  ERROR restoring {dst}: {e}")
            errors += 1
    print(f"Restored {restored} file(s).")
    if errors:
        print(f"  {errors} could not be restored (see above).")
    else:
        # clean up empty batch
        shutil.rmtree(batch, ignore_errors=True)
        print(f"Removed empty quarantine batch {batch}")


def cmd_purge(args):
    batch = Path(args.batch).expanduser()
    if not batch.is_dir():
        sys.exit(f"Not a batch directory: {batch}")
    log_file = batch / "restore-log.json"
    if not log_file.is_file():
        sys.exit(
            f"Refusing to purge {batch}: no restore-log.json (not a staged batch)."
        )
    data = json.loads(log_file.read_text(encoding="utf-8"))
    n = len(data.get("items", []))
    sz = sum(i.get("size_bytes", 0) for i in data.get("items", []))
    print(f"About to PERMANENTLY delete {n} file(s), {human_size(sz)}, from:")
    print(f"  {batch}")
    print("This cannot be undone.")
    if not args.yes:
        ans = input('Type "DELETE" to confirm: ').strip()
        if ans != "DELETE":
            sys.exit("Aborted. Nothing was deleted.")
    shutil.rmtree(batch)
    print(f"Purged {batch}")


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def build_parser():
    p = argparse.ArgumentParser(description="Reversible, human-approved file cleanup.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Inventory a directory and write a manifest.")
    s.add_argument("--dir", required=True)
    s.add_argument("--out", help="Manifest CSV path.")
    s.add_argument("--report", help="Markdown report path.")
    s.add_argument(
        "--min-size", type=int, default=0, help="Ignore files smaller than N bytes."
    )
    s.add_argument("--include-hidden", action="store_true")
    s.add_argument(
        "--blank-actions",
        action="store_true",
        help="Default every action to 'keep' instead of prefilling suggestions.",
    )
    s.add_argument("--allow-broad", action="store_true")
    s.set_defaults(func=cmd_scan)

    st = sub.add_parser(
        "stage", help="Move approved (action=delete) files to quarantine."
    )
    st.add_argument("--manifest", required=True)
    st.add_argument(
        "--dir", help="Base directory (defaults to manifest's common root)."
    )
    st.add_argument(
        "--quarantine", help="Quarantine root (default: <base>/.safe-delete-trash)."
    )
    st.add_argument("--allow-broad", action="store_true")
    st.set_defaults(func=cmd_stage)

    ls = sub.add_parser("list", help="List quarantine batches.")
    ls.add_argument("--dir")
    ls.add_argument("--quarantine")
    ls.set_defaults(func=cmd_list)

    r = sub.add_parser(
        "restore", help="Restore a quarantine batch to original locations."
    )
    r.add_argument("--batch", required=True)
    r.set_defaults(func=cmd_restore)

    pg = sub.add_parser("purge", help="Permanently delete a quarantine batch.")
    pg.add_argument("--batch", required=True)
    pg.add_argument(
        "--yes", action="store_true", help="Skip the interactive confirmation."
    )
    pg.set_defaults(func=cmd_purge)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
