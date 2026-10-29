import unittest

from fastapi import HTTPException

from app.services.quantity_service import normalize_quantity


class QuantityTests(unittest.TestCase):
    def test_kilograms_keep_fraction_rounded_to_grams(self):
        self.assertEqual(normalize_quantity(2.5, "kg"), 2.5)
        self.assertEqual(normalize_quantity("1.23456", "kg"), 1.235)

    def test_pieces_must_be_whole(self):
        self.assertEqual(normalize_quantity(100.0, "pcs"), 100.0)
        with self.assertRaises(HTTPException) as error:
            normalize_quantity(2.5, "pcs")
        self.assertEqual(error.exception.status_code, 422)

    def test_unmatched_lines_accept_any_positive_quantity(self):
        self.assertEqual(normalize_quantity(0.5, None), 0.5)
        for bad in (0, -1, "abc"):
            with self.assertRaises(HTTPException):
                normalize_quantity(bad, None)


if __name__ == "__main__":
    unittest.main()
