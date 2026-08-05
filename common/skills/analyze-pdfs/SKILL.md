---
name: analyze-pdfs
description: Analyze, summarize, query, extract from, OCR, render, or visually inspect PDF files. Use when the user asks about PDF content, scanned PDFs, PDF tables/forms/figures, page-cited summaries, document comparison, or converting PDF pages to images for local vision analysis.
---

# PDF Analysis

Use this skill for PDF analysis. Prefer deterministic extraction before LLM reasoning, preserve page numbers, and cite pages in final answers.

## Workflow

1. Inspect the PDF:

```bash
python3 .caret/skills/analyze-pdfs/scripts/inspect_pdf.py document.pdf
```

2. For searchable PDFs, extract embedded text per page:

```bash
python3 .caret/skills/analyze-pdfs/scripts/extract_pdf.py document.pdf --format markdown > document.extracted.md
```

3. For scanned, visual, layout-heavy, table-heavy, form-like, slide-like, or ambiguous pages, render selected pages:

```bash
python3 .caret/skills/analyze-pdfs/scripts/render_pages.py document.pdf --pages 1,3-5 --out-dir /tmp/pdf-pages
```

4. After rendering pages to images, use the existing `localimg` skill for visual inspection instead of duplicating vision request logic:

```bash
bash .caret/skills/localimg/scripts/describe_image.sh /tmp/pdf-pages/page-003.png "Analyze this PDF page. Preserve visible headings, tables, diagrams, annotations, and cite it as page 3."
```

5. For scanned pages where text is needed, OCR rendered pages:

```bash
python3 .caret/skills/analyze-pdfs/scripts/ocr_pages.py /tmp/pdf-pages/page-003.png --page 3
```

## Dependency Policy

The scripts use only Python standard library plus external command-line tools discovered from `PATH`.

Required as needed:

- `pdftotext` for text extraction
- `pdftoppm` for page rendering
- `tesseract` for OCR

Install external tools:

- macOS: `brew install poppler tesseract`
- Ubuntu/Debian: `apt install poppler-utils tesseract-ocr`
- Fedora: `dnf install poppler-utils tesseract`

Do not require global Python packages. If a future enhancement needs Python libraries, prefer `uv` with skill-local metadata. Fall back to a skill-local `.venv` and pinned requirements only when `uv` is unavailable.

## Analysis Rules

- Use embedded text first for text-heavy searchable PDFs.
- Render pages when visual inspection is more reliable than extracted text.
- Use `localimg` for diagrams, signatures, annotations, layout, screenshots, charts, stamps, handwriting, or other visual evidence.
- Mark OCR-derived text separately from embedded text.
- Preserve page numbers in filenames and extracted output.
- Cite pages in final answers, for example: `p. 3`.
- State uncertainty when extraction, OCR, or image inspection is incomplete.

See `references/pdf-analysis-workflow.md` for detailed heuristics.
