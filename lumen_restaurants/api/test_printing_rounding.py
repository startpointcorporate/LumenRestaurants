from unittest import TestCase
from unittest.mock import patch

from lumen_restaurants.api.printing import INIT, FEED_CUT, build_receipt_bytes


class TestThermalRounding(TestCase):
    def test_native_rounding_is_printed_on_bills_and_receipts(self):
        for is_bill in (False, True):
            for adjustment, shown in ((0.02, b"+0.02"), (-0.02, b"-0.02"), (0, None)):
                with self.subTest(is_bill=is_bill, adjustment=adjustment):
                    receipt = {
                        "company": "Restaurant", "name": "TEST-1", "posting_date": "2026-11-25",
                        "posting_time": "12:00", "customer_name": "Walk-in", "items": [],
                        "is_bill": is_bill, "currency": "XAF", "grand_total": 23912 - adjustment,
                        "rounded_total": 23912, "rounding_adjustment": adjustment, "precision": 2,
                    }
                    with (
                        patch("lumen_restaurants.api.printing.receipt_images.logo_bytes", return_value=b""),
                        patch("lumen_restaurants.api.printing.receipt_images.mark_bytes", return_value=b""),
                        patch("lumen_restaurants.api.printing._", side_effect=lambda text: text),
                    ):
                        output = build_receipt_bytes(receipt)
                    self.assertTrue(output.startswith(INIT))
                    self.assertTrue(output.endswith(FEED_CUT))
                    self.assertEqual(b"BILL" in output, is_bill)
                    self.assertIn(b"XAF 23,912.00", output)
                    rows = [row for row in output.splitlines() if b"Rounding adjustment" in row]
                    if shown:
                        self.assertEqual(len(rows), 1)
                        self.assertTrue(rows[0].endswith(shown))
                        self.assertIn(b"23,911.98" if adjustment > 0 else b"23,912.02", output)
                        self.assertLess(output.index(rows[0]), output.index(b"TOTAL"))
                    else:
                        self.assertEqual(rows, [])
                        self.assertNotIn(b"Total before rounding", output)
