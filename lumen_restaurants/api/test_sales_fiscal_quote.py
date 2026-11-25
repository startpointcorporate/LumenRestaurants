from types import SimpleNamespace
from unittest import TestCase

import frappe

from lumen_restaurants.api.sales import _assert_fiscal_quote, _fiscal_fingerprint, fiscal_totals


class TestSalesFiscalQuote(TestCase):
    def setUp(self):
        self.invoice = SimpleNamespace(
            doctype="Sales Invoice",
            company="Restaurant",
            customer="Walk-in",
            pos_profile="Till",
            currency="XAF",
            conversion_rate=1,
            items=[
                SimpleNamespace(item_code="Meal", uom="Nos", qty=1, rate=100000,
                                net_amount=100000, item_tax_rate='{"VAT":18}')
            ],
            taxes=[],
            net_total=100000,
            grand_total=118900,
            rounded_total=118900,
            rounding_adjustment=0,
            total_taxes_and_charges=18900,
            precision=lambda _key: 2,
            get=lambda _key: None,
        )
        for account, rate, amount, kind, row in (
            ("VAT", 18, 18000, "On Net Total", None),
            ("Surcharge", 5, 900, "On Previous Row Amount", 1),
        ):
            self.invoice.taxes.append(SimpleNamespace(
                description=account,
                account_head=account,
                rate=rate,
                charge_type=kind,
                row_id=row,
                included_in_print_rate=0,
                tax_amount_after_discount_amount=amount,
                precision=lambda _key: 2,
            ))

    def test_fiscal_breakdown_keeps_the_erpnext_amount_and_reference(self):
        totals = fiscal_totals(self.invoice)
        self.assertEqual(totals["payable"], 118900)
        self.assertEqual([tax["amount"] for tax in totals["taxes"]], [18000, 900])
        self.assertEqual(totals["taxes"][1]["row_id"], 1)

    def test_quote_rejects_changed_allocation_even_at_equal_payable(self):
        fingerprint = _fiscal_fingerprint(self.invoice)
        self.invoice.taxes[0].description = "Taxe"
        _assert_fiscal_quote(self.invoice, {"fiscal_fingerprint": fingerprint})
        self.invoice.taxes[0].tax_amount_after_discount_amount -= 1
        self.invoice.taxes[1].tax_amount_after_discount_amount += 1
        with self.assertRaises(frappe.ValidationError):
            _assert_fiscal_quote(self.invoice, {"fiscal_fingerprint": fingerprint})

    def test_offline_quoted_amount_is_checked_at_sync(self):
        with self.assertRaises(frappe.ValidationError):
            _assert_fiscal_quote(self.invoice, {"offline_tax_free_amount": 118900})
        self.invoice.taxes = []
        _assert_fiscal_quote(self.invoice, {"offline_tax_free_amount": 118900})
        with self.assertRaises(frappe.ValidationError):
            _assert_fiscal_quote(self.invoice, {"offline_tax_free_amount": 100000})
