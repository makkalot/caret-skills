#!/usr/bin/env python3
import argparse
import platform
import re
import shutil
import subprocess
import sys
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


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or f"Error running: {' '.join(cmd)}")
    return proc.stdout


def page_count_from_pdfinfo(pdf: Path) -> int | None:
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        return None
    proc = subprocess.run([pdfinfo, str(pdf)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    if proc.returncode != 0:
        return None
    match = re.search(r"^Pages:\s+(\d+)\s*$", proc.stdout, re.MULTILINE)
    return int(match.group(1)) if match else None


def split_pages(text: str) -> list[str]:
    pages = text.split("\f")
    if pages and pages[-1] == "":
        pages.pop()
    return pages or [text]


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a PDF and recommend an analysis route.")
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()

    if not args.pdf.is_file():
        raise SystemExit(f"Error: PDF does not exist: {args.pdf}")

    pdftotext = require("pdftotext")
    text = run([pdftotext, "-enc", "UTF-8", "-layout", str(args.pdf), "-"])
    pages = split_pages(text)
    page_count = page_count_from_pdfinfo(args.pdf) or len(pages)

    per_page_chars = [len(page.strip()) for page in pages]
    text_pages = sum(1 for count in per_page_chars if count >= 80)
    sparse_pages = sum(1 for count in per_page_chars if count < 80)
    total_chars = sum(per_page_chars)

    print(f"PDF: {args.pdf}")
    print(f"Pages: {page_count}")
    print(f"Embedded text characters: {total_chars}")
    print(f"Pages with useful embedded text: {text_pages}")
    print(f"Pages with sparse/empty embedded text: {sparse_pages}")
    print()

    if text_pages == 0:
        print("Recommended route: render pages, OCR, and use localimg for visual inspection.")
    elif sparse_pages > 0:
        print("Recommended route: extract embedded text, then render/OCR sparse pages.")
    else:
        print("Recommended route: extract embedded text first; render selected pages only if layout or visuals matter.")

    missing_optional = [tool for tool in ("pdftoppm", "tesseract") if not shutil.which(tool)]
    if missing_optional:
        print()
        print("Optional tools missing:")
        for tool in missing_optional:
            print(f"- {tool}: {install_hint(tool)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
