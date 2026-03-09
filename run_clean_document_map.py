from __future__ import annotations

import argparse
import json

from src.document_map_cleaner import clean_document_map_sidecar_payload
from src.utils import save_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean a DocumentMap sidecar JSON.")
    parser.add_argument("input_path", help="Path to *_document_map.json sidecar")
    parser.add_argument(
        "--output-path",
        default=None,
        help="Optional output path (defaults to overwrite input file)",
    )
    parser.add_argument(
        "--max-section-size-chars",
        type=int,
        default=200000,
        help="Validation limit for section length",
    )
    args = parser.parse_args()

    payload = json.loads(open(args.input_path, "r", encoding="utf-8").read())
    cleaned = clean_document_map_sidecar_payload(
        payload,
        max_section_size_chars=args.max_section_size_chars,
    )
    destination = args.output_path or args.input_path
    save_text(destination, json.dumps(cleaned, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
