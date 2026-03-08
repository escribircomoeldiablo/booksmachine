from __future__ import annotations

import argparse

from src.pipeline import process_book


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the books summary pipeline.")
    parser.add_argument("input_path", nargs="?", default="books/sample_book.txt")
    parser.add_argument("--mode", choices=["full", "smoke"], default="full")
    parser.add_argument("--max-chunks", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    process_book(
        args.input_path,
        mode=args.mode,
        max_chunks=args.max_chunks,
        dry_run=args.dry_run,
        verbose=not args.quiet,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
