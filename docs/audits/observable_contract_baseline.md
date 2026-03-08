# Observable Contract Baseline

Date: 2026-03-08

## Baseline execution status

- Command attempted: `.venv/bin/python run_pipeline.py`
- Result in this workspace: timed out after 45s (`EXIT:124`), no output emitted.
- Isolation run for chunking (`split_into_chunks` over `books/sample_book.txt`) also timed out after 20s.

Given that runtime behavior is currently blocked in this environment, the observable contract is frozen from:
- current source implementation in `src/pipeline.py`
- deterministic smoke tests added in `tests/test_pipeline_contract.py`

## Observable contract (frozen)

- Output path directory: `OUTPUT_FOLDER` (default: `outputs`)
- Output filename pattern: `<input_stem>_summary.txt`
- Output path construction: `Path(output_folder) / f"{Path(input_path).stem}_summary.txt"`
- Per-chunk structure:
  - each chunk block starts with `## Chunk <n>`
  - chunk numbering starts at `1` and increments by `1`
  - chunk header is followed by a newline and the chunk summary text
- Separator between chunk blocks: `\n\n---\n\n`
- No trailing separator after the last chunk

## Expected error semantics

- Empty chunk list in pipeline raises:
  - `ValueError("No readable content found in: <source_path>")`
- Missing API key in `ask_llm(prompt)` raises:
  - `RuntimeError("Missing OPENAI_API_KEY environment variable.")`
- Empty LLM response raises:
  - `RuntimeError("LLM returned an empty response.")`
