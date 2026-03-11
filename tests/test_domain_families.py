from __future__ import annotations

import unittest

from src.domain_families import load_family_catalog


class DomainFamiliesTests(unittest.TestCase):
    def test_load_family_catalog_preserves_controlled_patterns(self) -> None:
        catalog = load_family_catalog()
        planetary_phases = next(item for item in catalog if item["id"] == "planetary_phases")

        self.assertIn("controlled_patterns", planetary_phases)
        self.assertIn("heliacal morning rise", planetary_phases["controlled_patterns"])


if __name__ == "__main__":
    unittest.main()
