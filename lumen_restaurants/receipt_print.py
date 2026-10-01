# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
"""Our mark and name at the foot of every receipt the till gives out.

He wants them on every receipt, with no way for a customer to take them off
(2026-09-27: "خلي شعارنا واسمنا اللي تحت دائما موجودة ما يقدر العميل يشيلها
ابدا"), so there is no setting for them, on purpose. The built-in receipt
(ReceiptView.vue) and the receipt printer (receipt_images.py) draw them
themselves. This module adds them where the page comes from an outlet's own
Print Format (the POS Profile's): the till's print and the emailed receipt.
ERPNext's own screens, and its desk print of an invoice, stay ERPNext's.
"""
from __future__ import annotations

import base64
from functools import lru_cache

import frappe

# The kit's receipt cut: pure black, 96 dots, printed 12 mm wide.
MARK_FILE = ("public", "images", "png", "receipt-96px-203dpi.png")


@lru_cache(maxsize=1)
def mark_html():
    with open(frappe.get_app_path("lumen_restaurants", *MARK_FILE), "rb") as f:
        png = base64.b64encode(f.read()).decode()
    return (
        '<div class="lumen-restaurants-mark" style="text-align:center;margin:14px 0 4px;'
        'font:10px/1.4 Arial,sans-serif;color:#000;page-break-inside:avoid">'
        f'<img src="data:image/png;base64,{png}" alt="" '
        'style="width:12mm;height:12mm;display:block;margin:0 auto 2px">'
        "Lumen Restaurants</div>"
    )


def with_mark(html):
    """The page with our mark added just before </body>, or at its end."""
    html = html or ""
    at = html.lower().rfind("</body>")
    return html + mark_html() if at < 0 else html[:at] + mark_html() + html[at:]


@frappe.whitelist()
def print_html(invoice: str):
    """A sale in its outlet's own Print Format, our mark at the foot, for the
    till to print (it used to open /printview, where the mark was missing)."""
    from lumen_restaurants.api.sales import _doctype_of

    doctype = _doctype_of(invoice)
    if not doctype:
        frappe.throw(frappe._("Sale {0} not found").format(invoice))
    doc = frappe.get_doc(doctype, invoice)
    doc.check_permission("print")
    print_format = frappe.db.get_value("POS Profile", doc.get("pos_profile"), "print_format")
    return with_mark(frappe.get_print(doctype, invoice, print_format=print_format or None, doc=doc, no_letterhead=0))


def attach_with_mark(doctype, name, doc, print_format=None):
    """frappe.attach_print, the same attachment an emailed receipt always had,
    with our mark at the foot."""
    from frappe.utils import scrub_urls

    frappe.local.flags.ignore_print_permissions = True
    try:
        html = with_mark(frappe.get_print(doctype, name, print_format=print_format, doc=doc))
    finally:
        frappe.local.flags.ignore_print_permissions = False
    return frappe.attach_print(doctype, name, print_format=print_format, doc=doc, html=scrub_urls(html))
