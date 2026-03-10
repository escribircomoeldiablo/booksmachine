"""Catalog loading for domain-specific family assignment."""

from __future__ import annotations

import json
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_family_catalog_path(domain: str = "astrology") -> Path:
    """Resolve the default catalog path for one domain family inventory."""
    return _project_root() / "config" / "domain_families" / f"{domain}_families.json"


def load_family_catalog(*, domain: str = "astrology", catalog_path: str | None = None) -> list[dict[str, object]]:
    """Load one family catalog from JSON."""
    path = Path(catalog_path) if catalog_path else default_family_catalog_path(domain)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError(f"Family catalog at {path} must be a JSON list.")

    catalog: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        family_id = str(item.get("id", "")).strip()
        label = str(item.get("label", "")).strip()
        aliases = item.get("aliases", [])
        if not family_id or not label:
            continue
        catalog.append(
            {
                "id": family_id,
                "label": label,
                "aliases": [alias.strip() for alias in aliases if isinstance(alias, str) and alias.strip()],
            }
        )
    return catalog
