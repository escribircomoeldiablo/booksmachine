# Structural Profiles

This project supports environment-driven profiles for Structure Pass + Structural Chunker.

## Files

- `profiles/structural_base.env`: default profile for most books.
- `profiles/structural_clean.env`: for clean PDFs with reliable headings.
- `profiles/structural_noisy.env`: for OCR-noisy PDFs.

## Usage

Run with one profile loaded into the current shell:

```bash
set -a
source profiles/structural_base.env
set +a
python run_pipeline.py "books/Your Book.pdf"
```

Switch profile by changing the file name.

## Quick Tuning Rules

- Too few headings detected: lower `STRUCTURE_MIN_HEADING_SCORE`.
- Too many chunks: increase `STRUCTURAL_CHUNKER_TARGET_SIZE`.
- Last chunks too short: increase `STRUCTURAL_CHUNKER_MIN_SIZE`.
