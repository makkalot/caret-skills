# PDF Analysis Workflow

## Route Selection

- Searchable text PDF: use `extract_pdf.py` first, then answer from page-preserved text.
- Scanned PDF: use `render_pages.py`, run `ocr_pages.py`, and use `localimg` for visual confirmation when layout matters.
- Layout-heavy PDF: render relevant pages and inspect them with `localimg`.
- Table-heavy PDF: compare extracted text against rendered page images because text extraction can lose columns.
- Forms, invoices, slides, diagrams, signatures, stamps, annotations, or handwriting: render pages and use `localimg`.

## Citation Format

Always preserve page numbers in intermediate files and cite final claims with page references:

- Single page: `p. 4`
- Multiple pages: `pp. 4-6`
- Uncertain OCR/visual observation: `p. 4, OCR/visual inspection`

## Chunking

Chunk by page or natural section boundaries before using token-size chunks. Keep page identifiers with every chunk. For long PDFs, inspect the table of contents or headings first, then process only the relevant page ranges when the user asks a targeted question.

## OCR And Vision

OCR is useful for searchable text output, but it can miss layout, handwriting, stamps, and diagrams. Use rendered page images with `localimg` when the user asks about visual evidence or when OCR confidence seems poor.

## Failure Modes

- Empty embedded text usually means a scanned PDF or image-only pages.
- Garbled text can indicate encoding, columns, or reading-order issues.
- Tables can flatten into misleading row/column order.
- Footnotes, headers, watermarks, and marginal notes can be mixed into body text.
- Low-resolution rendering can hide small text; rerender at a higher DPI when needed.
