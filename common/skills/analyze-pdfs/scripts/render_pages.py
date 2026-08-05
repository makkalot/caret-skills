#!/usr/bin/env python3
import argparse
import platform
import shutil
import subprocess
from pathlib import Path


def install_hint(tool: str) -> str:
    system = platform.system().lower()
    if system == "darwin":
        return f"Install with: brew install poppler tesseract  # missing {tool}"
    if shutil.which("apt"):
        return f"Install with: sudo apt install poppler-utils tesseract-ocr  # missing {tool}"
    if shutil.which("dnf"):
        return f"Install with: sudo dnf install poppler-utils tesseract  # missing {tool}"
    return f"Install Poppler/Tesseract packages for your platform  # missing {tool}"


def require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise SystemExit(f"Error: required command not found: {tool}\n{install_hint(tool)}")
    return path


def parse_pages(value: str) -> list[int]:
    pages: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            if start < 1 or end < start:
                raise ValueError(f"invalid page range: {part}")
            pages.update(range(start, end + 1))
        else:
            page = int(part)
            if page < 1:
                raise ValueError(f"invalid page number: {part}")
            pages.add(page)
    return sorted(pages)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render selected PDF pages to images.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages", required=True, help="Page list such as 1,3-5")
    parser.add_argument("--out-dir", type=Path, default=Path("/tmp/pdf-pages"))
    parser.add_argument("--format", choices=("png", "jpeg"), default="png")
    parser.add_argument("--dpi", type=int, default=180)
    args = parser.parse_args()

    if not args.pdf.is_file():
        raise SystemExit(f"Error: PDF does not exist: {args.pdf}")
    if args.dpi < 72:
        raise SystemExit("Error: --dpi must be at least 72")

    try:
        pages = parse_pages(args.pages)
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    if not pages:
        raise SystemExit("Error: no pages selected")

    pdftoppm = require("pdftoppm")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rendered: list[Path] = []
    format_flag = "-png" if args.format == "png" else "-jpeg"
    ext = "png" if args.format == "png" else "jpg"

    for page in pages:
        prefix = args.out_dir / f"page-{page:03d}"
        cmd = [pdftoppm, "-r", str(args.dpi), "-f", str(page), "-l", str(page), "-singlefile", format_flag, str(args.pdf), str(prefix)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise SystemExit(proc.stderr.strip() or f"Error: failed to render page {page}")
        rendered.append(prefix.with_suffix(f".{ext}"))

    for path in rendered:
        print(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
