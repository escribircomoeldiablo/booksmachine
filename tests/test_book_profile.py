from __future__ import annotations

import unittest

from src.book_profile import ARGUMENTATIVE_PROFILE, MANUAL_PROFILE, get_book_profile


class BookProfileTests(unittest.TestCase):
    def test_get_manual_profile(self) -> None:
        profile = get_book_profile("manual")
        self.assertEqual(profile, MANUAL_PROFILE)
        self.assertEqual(profile.structured_artifact_family, "knowledge")

    def test_get_argumentative_profile(self) -> None:
        profile = get_book_profile("argumentative")
        self.assertEqual(profile, ARGUMENTATIVE_PROFILE)
        self.assertEqual(profile.structured_artifact_family, "argument")
        self.assertTrue(profile.enable_argument_map)
        self.assertFalse(profile.enable_procedural)

    def test_invalid_profile_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "profile must be either"):
            get_book_profile("research")


if __name__ == "__main__":
    unittest.main()
