#!/usr/bin/env python3
import argparse
import json
import platform
import re
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


def infer_page(path: Path, fallback: int) -> int:
    match = re.search(r"page[-_]?(\d+)", path.stem, re.IGNORECASE)
    return int(match.group(1)) if match else fallback


def collect_images(paths: list[Path]) -> list[Path]:
    images: list[Path] = []
    for path in paths:
        if path.is_dir():
            images.extend(sorted(p for p in path.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}))
        elif path.is_file():
            images.append(path)
        else:
            raise SystemExit(f"Error: image path does not exist: {path}")
    return images


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR rendered PDF page images with Tesseract.")
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--lang", default="eng")
    parser.add_argument("--page", type=int, help="Page number for a single input image")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    tesseract = require("tesseract")
    images = collect_images(args.images)
    if not images:
        raise SystemExit("Error: no image files found")
    if args.page is not None and len(images) != 1:
        raise SystemExit("Error: --page can only be used with a single image")

    pages = []
    for idx, image in enumerate(images, start=1):
        page_num = args.page if args.page is not None else infer_page(image, idx)
        proc = subprocess.run(
            [tesseract, str(image), "stdout", "-l", args.lang],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            raise SystemExit(proc.stderr.strip() or f"Error: OCR failed for {image}")
        pages.append({"page": page_num, "image": str(image), "text": proc.stdout.strip(), "source": "ocr"})

    if args.format == "json":
        print(json.dumps({"pages": pages}, ensure_ascii=False, indent=2))
        return 0

    print("# OCR Text")
    print()
    for page in pages:
        print(f"## Page {page['page']} (OCR)")
        print()
        print(page["text"] or "[No OCR text extracted]")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
