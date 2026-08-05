#!/usr/bin/env python3
import argparse
import json
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


def split_pages(text: str) -> list[str]:
    pages = text.split("\f")
    if pages and pages[-1] == "":
        pages.pop()
    return pages or [text]


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract embedded PDF text while preserving page numbers.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    if not args.pdf.is_file():
        raise SystemExit(f"Error: PDF does not exist: {args.pdf}")

    pdftotext = require("pdftotext")
    proc = subprocess.run(
        [pdftotext, "-enc", "UTF-8", "-layout", str(args.pdf), "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or "Error: pdftotext failed")

    pages = [{"page": idx, "text": text.strip()} for idx, text in enumerate(split_pages(proc.stdout), start=1)]

    if args.format == "json":
        print(json.dumps({"source": str(args.pdf), "pages": pages}, ensure_ascii=False, indent=2))
        return 0

    print(f"# Extracted PDF Text: {args.pdf}")
    print()
    for page in pages:
        print(f"## Page {page['page']}")
        print()
        print(page["text"] or "[No embedded text extracted]")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
