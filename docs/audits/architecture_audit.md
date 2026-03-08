# Architecture Audit

Date: 2026-03-08
Scope: `run_pipeline.py`, `src/`, `tests/`

## 1. Executive Summary

- Refactor objective status:
  - `src/pipeline.py` is now a thin orchestrator.
  - `src/compiler.py` is active and used by the pipeline.
  - Filesystem persistence remains in `src/utils.py`.
  - `src/ai_client.py` preserves public API `ask_llm(prompt)`.
  - `src/extractor.py` was removed.
- Runtime status:
  - Non-progress loop in `split_into_chunks` was mitigated with a local fix in `src/chunker.py`.
  - Terminal micro-fragmentation in `split_into_chunks` was mitigated with a tail-close condition.
  - `run_pipeline.py` no longer times out in chunking; execution now advances to LLM prerequisite validation.

## 2. Current Repository Structure (Relevant)

```text
.
├── run_pipeline.py
├── books/
│   └── sample_book.txt
├── docs/
│   └── audits/
│       ├── architecture_audit.md
│       └── observable_contract_baseline.md
├── tests/
│   ├── test_chunker.py
│   └── test_pipeline_contract.py
└── src/
    ├── __init__.py
    ├── ai_client.py
    ├── chunker.py
    ├── compiler.py
    ├── config.py
    ├── loader.py
    ├── pipeline.py
    ├── summarizer.py
    └── utils.py
```

## 3. Module Responsibilities

- `run_pipeline.py`: entrypoint invoking `process_book("books/sample_book.txt")`.
- `src/pipeline.py`: orchestration only (`load -> chunk -> summarize -> compile -> save`).
- `src/compiler.py`: final summary formatting and output path construction.
- `src/utils.py`: filesystem helpers (`ensure_dir`, `read_text`, `save_text`).
- `src/loader.py`: input loading for `.txt` and `.pdf`.
- `src/chunker.py`: deterministic overlapping chunk creation.
- `src/summarizer.py`: prompt building + delegating to LLM client.
- `src/ai_client.py`: OpenAI call with prereq checks and retry loop.

## 4. Public API Snapshot

- `src.pipeline.process_book(path: str) -> str`
- `src.compiler.compile_chunk_summaries(summaries: list[str]) -> str`
- `src.compiler.build_output_path(input_path: str, output_folder: str) -> str`
- `src.loader.load_text_file(path: str) -> str`
- `src.loader.load_pdf_file(path: str) -> str`
- `src.loader.load_book(path: str) -> str`
- `src.chunker.split_into_chunks(text: str, chunk_size: int = 1800, overlap: int = 200) -> list[str]`
- `src.summarizer.build_summary_prompt(chunk_text: str) -> str`
- `src.summarizer.summarize_chunk(chunk_text: str) -> str`
- `src.ai_client.ask_llm(prompt: str) -> str`
- `src.utils.ensure_dir(path: str) -> None`
- `src.utils.read_text(path: str) -> str`
- `src.utils.save_text(path: str, content: str) -> None`

## 5. Dependency Graph and Cycle Check

Static imports inside `src/`:

- `__init__` -> (none)
- `ai_client` -> `config`
- `chunker` -> (none)
- `compiler` -> (none)
- `config` -> (none)
- `loader` -> (none)
- `pipeline` -> `chunker`, `compiler`, `config`, `loader`, `summarizer`, `utils`
- `summarizer` -> `ai_client`
- `utils` -> (none)

Cycle check result: no circular imports detected.

## 6. Observable Contract Status

Based on `tests/test_pipeline_contract.py` and `docs/audits/observable_contract_baseline.md`:

- Output filename pattern remains `<input_stem>_summary.txt`.
- Output directory remains `OUTPUT_FOLDER` (default `outputs`).
- Final summary format remains `## Chunk n` blocks joined by `\n\n---\n\n`.
- `process_book` still raises `ValueError("No readable content found in: <source_path>")` when chunk list is empty.

## 7. Findings (Ordered by Severity)

### F1 (Closed) Non-progress loop in chunk generation

- Location: `src/chunker.py:49-64`
- Evidence:
  - Before fix: reproduction on `books/sample_book.txt` showed repeated pointer (`start=32`, `end=232`) and `run_pipeline.py` timeout (`EXIT:124`).
  - After fix: short input uses single-chunk short-circuit (`text_len <= chunk_size`) and pointer update enforces monotonic advance (`next_start >= current_start + 1`).
- Resolution:
  - Local pointer-update fix in `split_into_chunks` plus short-input early return.
  - No API changes, no module responsibility changes.

### F2 (Mitigated) Contract tests previously did not exercise chunker progress

- Location: `tests/test_pipeline_contract.py`
- Evidence:
  - Added `tests/test_chunker.py` covering termination/progress-oriented scenarios and border validations.
- Residual impact:
  - Current tests verify determinism, termination, and empty-chunk absence; deeper semantic quality checks for split quality are still limited.

### F3 (Closed) Tail micro-chunk fragmentation after first chunker fix

- Location: `src/chunker.py`
- Evidence:
  - Before second fix: `books/ancient_astrology_test.txt` (~18k chars) produced `212` chunks with tiny tail chunks (e.g., `... 9, 8, 7, ... 1`).
  - After second fix: same file produces `12` chunks, tail is stable (`... 1798, 1794, 430`), and `tiny<=20` count is `0`.
  - Large PDF preflight dropped from `1057` to `858` detected chunks in dry-run.
- Resolution:
  - Added terminal close rule when `candidate_start = end - overlap` is non-progressive (`candidate_start <= start`), forcing `end = text_len`.
  - Kept existing defensive progress guard for non-terminal iterations.

## 8. Validation Executed

Commands run with `.venv/bin/python`:

- Before fix:
  - `timeout 20s .venv/bin/python run_pipeline.py` -> `RUN_PIPELINE_EXIT:124`
  - pointer trace reproduction -> `start=32`, `end=232` repeated
- After fix:
  - `.venv/bin/python -m unittest discover -s tests -q` -> `OK (15 tests)`
  - `.venv/bin/python -m compileall -q src run_pipeline.py tests` -> `OK`
  - `timeout 20s .venv/bin/python run_pipeline.py` -> `RUN_PIPELINE_AFTER_EXIT:1` with `RuntimeError: Missing OPENAI_API_KEY environment variable.` (expected prereq error, no chunking hang)
  - chunk comparison script:
    - `short chunks 1 empty False`
    - `medium chunks 4 empty False`
    - `long chunks 217 empty False`
    - exact 200-char overlap fully preserved on `medium` (`3/3`)
  - short-case trace -> `single_chunk_short_circuit`
  - Import cycle script -> `CYCLES none`
- After second chunker fix:
  - `.venv/bin/python run_pipeline.py books/ancient_astrology_test.txt --dry-run`:
    - `Total chunks detected: 12`
    - `LLM calls expected: 12`
  - `.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf" --dry-run`:
    - `Total chunks detected: 858`
    - `LLM calls expected: 858`
  - chunk distribution check on ancient test text:
    - `chunks 12`
    - `tail [1793, 1797, 1790, 1795, 1795, 1796, 1799, 1798, 1794, 430]`
    - `tiny<=20 0`

## 9. Recommended Next Action

Keep the local chunker fixes and continue tuning chunk-count efficiency on very large PDFs if budget pressure remains high.
