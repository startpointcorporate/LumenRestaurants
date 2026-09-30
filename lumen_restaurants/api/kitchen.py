# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
"""The kitchen's side of the counter.

A ticket is what the kitchen sees: the short daily number (or the table), the
items with the guest's notes, and how long it has been waiting. It moves
through New, Preparing, Ready, Done, and each step stamps its time, so the
screen can colour a ticket that is taking too long and the shop can see the
real average.

Tickets are born in two ways. A paid takeaway or delivery sale makes one the
moment the money is in (sales.submit_sale calls after_sale here, in the same
transaction: no payment, no ticket, no number burned). A table sends one every
time the waiter presses "send to kitchen", so a meal can fire mains first and
dessert later as separate tickets under the same table.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from lumen_restaurants.api import restaurant

TICKET = "POS Kitchen Ticket"

# The whole flow, so a wrong jump (Done back to New) is refused loudly.
FLOW = {
    "New": {"Preparing", "Ready", "Cancelled"},
    "Preparing": {"Ready", "Cancelled", "New"},
    "Ready": {"Done", "Preparing"},
    "Done": set(),
    "Cancelled": set(),
}


def _clean_items(items):
    from lumen_restaurants import modifiers

    rows = []
    for row in items or []:
        qty = flt(row.get("qty"))
        name = (row.get("item_name") or "").strip()
        if not name or qty <= 0:
            continue
        choices = modifiers.clean_choices(row.get("modifiers"))
        rows.append(
            {
                "item_name": name,
                "qty": qty,
                "note": (row.get("note") or "").strip()[:400] or None,
                "item_code": row.get("item_code"),
                # The guest's choices, shown under the dish (modifiers.py).
                "modifiers": json.dumps(choices, ensure_ascii=False) if choices else None,
            }
        )
    return rows


def _choices(raw):
    """A ticket line's choices, as the screen and the slip show them."""
    from lumen_restaurants import modifiers

    return modifiers.clean_choices(raw) if raw else []


def _make_ticket(profile_name, order_type, items, order_no=None, table_label=None,
                 source_order=None, invoice=None, note=None):
    rows = _clean_items(items)
    if not rows:
        return None
    doc = frappe.get_doc(
        {
            "doctype": TICKET,
            "pos_profile": profile_name,
            "order_type": order_type or "Takeaway",
            "order_no": str(order_no) if order_no else None,
            "table_label": table_label,
            "source_order": source_order,
            "invoice": invoice,
            "status": "New",
            "note": (note or "").strip() or None,
            "items": rows,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def _working_day(invoice):
    """The day the shift this sale is posted on opened, the day its order
    number belongs to: a shift that sells on past midnight keeps counting
    until it closes (the owner, 2026-10-01). None (today) without a shift."""
    from lumen_restaurants.api import sales

    session = sales._get_custom(invoice, ("lumenpos_session",))
    opened = session and frappe.db.get_value("POS Register Session", session, "opened_at")
    return getdate(opened) if opened else None


def after_sale(invoice, profile, meta):
    """A restaurant sale just posted: hand out the day's number and open the
    kitchen ticket, inside the sale's own transaction.

    `meta` is the payload's `restaurant` block: {order_type, items?}. The
    items for the ticket come from the INVOICE (names the kitchen knows and
    the quantities that were actually paid for). A dish carries its own
    choices and note on its line (modifiers.py), a paid add-on rides on its
    dish instead of being a line of its own; lines from before carry the
    cart's notes, laid over them by item code."""
    from lumen_restaurants import modifiers
    from lumen_restaurants.lumen_restaurants.doctype.pos_daily_counter.pos_daily_counter import next_order_no

    order_type = meta.get("order_type") or "Takeaway"
    notes = {}
    for line in meta.get("notes") or []:
        if line.get("item_code") and (line.get("note") or "").strip():
            notes[line["item_code"]] = line["note"].strip()

    order_no = next_order_no(profile.name, day=_working_day(invoice))
    items = []
    for row in invoice.items:
        if row.get("lr_addon_of"):
            continue
        data = modifiers.row_data(row)
        items.append(
            {
                "item_name": row.item_name,
                "qty": row.qty,
                "item_code": row.item_code,
                "note": data["n"] if row.get("lr_modifiers") else notes.get(row.item_code),
                "modifiers": data["c"],
            }
        )
    ticket = _make_ticket(
        profile.name, order_type, items, order_no=order_no, invoice=invoice.name
    )
    # The number rides on the invoice itself, so the receipt can shout it and
    # the shop can find the sale by it later.
    from lumen_restaurants.api import sales

    sales._set_custom(invoice, ("lumenpos_order_no",), str(order_no))
    frappe.db.set_value(
        invoice.doctype, invoice.name, "lumenpos_order_no", str(order_no),
        update_modified=False,
    )
    # Paper for the kitchen, where a printer is reachable. Never fails the sale.
    if ticket:
        try:
            from lumen_restaurants.api import printing

            printing.auto_print_kitchen(ticket)
        except Exception:
            frappe.log_error(title="LumenPOS kitchen print failed")
    return {"order_no": order_no, "ticket": ticket.name if ticket else None}


@frappe.whitelist()
def send_to_kitchen(order, items, note=None):
    """A table sends what was just added: the waiter's "fire". `items` is the
    DELTA the till worked out (qty minus what was already sent per line)."""
    if isinstance(items, str):
        items = json.loads(items or "[]")
    doc = frappe.get_doc("POS Restaurant Order", order)
    doc.check_permission("write")
    restaurant._assert_outlet(doc.pos_profile)
    if doc.status != "Open":
        frappe.throw(_("This order is {0}").format(_(doc.status)))
    ticket = _make_ticket(
        doc.pos_profile,
        doc.order_type or "Dine in",
        items,
        table_label=doc.table_label or _("Takeaway"),
        source_order=doc.name,
        note=note,
    )
    if not ticket:
        frappe.throw(_("Nothing new to send: everything on this order has already gone to the kitchen"))
    try:
        from lumen_restaurants.api import printing

        printing.auto_print_kitchen(ticket)
    except Exception:
        frappe.log_error(title="LumenPOS kitchen print failed")
    return {"ticket": ticket.name, "items": len(ticket.items)}


@frappe.whitelist()
def board(pos_profile):
    """Everything the kitchen screen shows, one request every few seconds."""
    restaurant._assert_outlet(pos_profile)
    tickets = frappe.get_all(
        TICKET,
        filters={"pos_profile": pos_profile, "status": ("in", ["New", "Preparing", "Ready"])},
        fields=[
            "name", "order_type", "order_no", "table_label", "status",
            "created_at", "started_at", "ready_at", "note",
        ],
        order_by="created_at asc",
        limit_page_length=0,
    )
    items = {}
    if tickets:
        rows = frappe.get_all(
            "POS Kitchen Ticket Item",
            filters={"parent": ("in", [t.name for t in tickets])},
            fields=["parent", "item_name", "qty", "note", "modifiers"],
            order_by="idx asc",
            limit_page_length=0,
        )
        for row in rows:
            items.setdefault(row.parent, []).append(
                {
                    "item_name": row.item_name,
                    "qty": flt(row.qty),
                    "note": row.note,
                    "modifiers": _choices(row.modifiers),
                }
            )
    for ticket in tickets:
        ticket["items"] = items.get(ticket.name, [])
    # Average preparation time today, from real stamps.
    avg = frappe.db.sql(
        """select avg(timestampdiff(second, created_at, ready_at))
           from `tabPOS Kitchen Ticket`
           where pos_profile = %s and ready_at is not null and date(created_at) = %s""",
        (pos_profile, nowdate()),
    )
    avg_seconds = cint(avg[0][0]) if avg and avg[0] and avg[0][0] else 0
    return {"tickets": tickets, "now": now_datetime(), "avg_seconds": avg_seconds}


@frappe.whitelist()
def set_ticket_status(name, status):
    """Advance a ticket. The kitchen taps, the times write themselves."""
    doc = frappe.get_doc(TICKET, name)
    doc.check_permission("write")
    restaurant._assert_outlet(doc.pos_profile)
    if status not in FLOW:
        frappe.throw(_("Unknown status {0}").format(status))
    if status == doc.status:
        return {"status": doc.status}
    if status not in FLOW.get(doc.status, set()):
        frappe.throw(_("A ticket cannot go from {0} to {1}").format(_(doc.status), _(status)))
    doc.status = status
    doc.save(ignore_permissions=True)
    return {"status": doc.status}


@frappe.whitelist()
def ready_calls(pos_profile):
    """What the cashier should be calling out: tickets sitting on Ready."""
    restaurant._assert_outlet(pos_profile)
    return frappe.get_all(
        TICKET,
        filters={"pos_profile": pos_profile, "status": "Ready"},
        fields=["name", "order_no", "table_label", "order_type", "ready_at"],
        order_by="ready_at asc",
        limit_page_length=20,
    )
