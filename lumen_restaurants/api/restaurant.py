# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
"""Tables and open orders, for an outlet run as a restaurant.

A retail till sells a basket and is done with it. A restaurant holds the basket
open while people eat, on a table, shared between every device in the place,
and only turns it into money at the end. That open basket is a POS Restaurant
Order, and this module is everything the floor does with it: open one, keep it
saved as the waiter adds to it, move it to another table, pour two together,
cancel it, and finally hand it to the ordinary sale path to be paid.

Nothing here posts an invoice or moves stock. Paying a table order is a normal
`sales.submit_sale` with `order` in the payload, so promotions, loyalty,
cashback, the Z-report and returns all behave exactly as they do on a retail
sale, and there is only ONE place in this app that creates a sale.

Restaurant mode is per outlet: the POS Profile field `lumenpos_restaurant_mode`
(Desk) decides, so a company can run one branch as a cafe and another as a shop
from the same install.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, get_fullname, now_datetime

from lumen_restaurants.api import permissions

TABLE = "POS Restaurant Table"
ORDER = "POS Restaurant Order"


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def enabled(pos_profile):
    """Is this outlet run as a restaurant?"""
    if not pos_profile:
        return False
    return bool(frappe.db.get_value("POS Profile", pos_profile, "lumenpos_restaurant_mode"))


def _assert_outlet(pos_profile):
    """A till may only touch an outlet its user is assigned to."""
    from lumen_restaurants.api.session import _user_profiles

    if not pos_profile:
        frappe.throw(_("No outlet given"))
    if pos_profile not in _user_profiles() and not permissions.is_manager():
        frappe.throw(
            _("You are not assigned to outlet {0}.").format(pos_profile), frappe.PermissionError
        )


def _assert_enabled(pos_profile):
    if not enabled(pos_profile):
        frappe.throw(
            _("Restaurant mode is off for outlet {0}. Turn it on on the POS Profile.").format(
                pos_profile
            )
        )


def _assert_can(capability):
    if not permissions.allowed(capability):
        frappe.throw(
            _("You are not allowed to do that: {0}").format(_(capability)),
            frappe.PermissionError,
        )


def _open_doc(name, ptype="write"):
    doc = frappe.get_doc(ORDER, name)
    doc.check_permission(ptype)
    _assert_outlet(doc.pos_profile)
    return doc


# ---------------------------------------------------------------------------
# The floor
# ---------------------------------------------------------------------------

def _fullnames(users):
    return {user: get_fullname(user) for user in {u for u in users if u}}


@frappe.whitelist()
def get_floor(pos_profile):
    """Every table of this outlet and what is happening on it, plus the orders
    that are not on a table at all (takeaway, delivery)."""
    _assert_outlet(pos_profile)
    tables = frappe.get_all(
        TABLE,
        filters={"pos_profile": pos_profile, "disabled": 0},
        fields=["name", "table_no", "area", "seats"],
        order_by="area asc, table_no asc",
        limit_page_length=0,
    )
    orders = frappe.get_all(
        ORDER,
        filters={"pos_profile": pos_profile, "status": "Open"},
        fields=[
            "name", "table", "table_label", "order_type", "guests", "customer",
            "customer_name", "total", "opened_at", "opened_by", "note", "app_type",
        ],
        order_by="opened_at asc",
        limit_page_length=0,
    )
    names = _fullnames([o.opened_by for o in orders])
    # One query for every order's line count, not one per order: a busy floor
    # polls this every few seconds from every device in the place.
    counts = {}
    if orders:
        rows = frappe.get_all(
            "POS Restaurant Order Item",
            filters={"parent": ("in", [o.name for o in orders])},
            # NOT "as lines": lines is a reserved word in MariaDB and the
            # whole floor screen dies with a syntax error.
            fields=["parent", "count(name) as line_count"],
            group_by="parent",
        )
        counts = {row["parent"]: row["line_count"] for row in rows}
    for order in orders:
        order["opened_by_name"] = names.get(order.opened_by) or order.opened_by
        order["lines"] = counts.get(order.name, 0)
    by_table = {o.table: o for o in orders if o.table}
    for table in tables:
        table["order"] = by_table.get(table["name"])
    return {
        "tables": tables,
        # Takeaway and delivery sit beside the floor, they have no table.
        "loose": [o for o in orders if not o.table],
        # The clock the elapsed times are measured against is the SERVER's, so
        # a tablet with a wrong clock still shows the right "sitting for".
        "now": now_datetime(),
    }


# ---------------------------------------------------------------------------
# An order
# ---------------------------------------------------------------------------

def _as_dict(doc, with_cart=False):
    data = {
        "name": doc.name,
        "pos_profile": doc.pos_profile,
        "table": doc.table,
        "table_label": doc.table_label,
        "order_type": doc.order_type,
        "guests": cint(doc.guests),
        "customer": doc.customer,
        "customer_name": doc.customer_name,
        "status": doc.status,
        "total": flt(doc.total, 2),
        "note": doc.note,
        "app_type": doc.app_type,
        "order_id": doc.order_id,
        "opened_at": doc.opened_at,
        "opened_by": doc.opened_by,
        "opened_by_name": get_fullname(doc.opened_by) if doc.opened_by else None,
        "lines": len(doc.items or []),
    }
    if with_cart:
        data["cart"] = json.loads(doc.cart or "{}")
    return data


@frappe.whitelist()
def open_order(
    pos_profile,
    table=None,
    order_type="Dine in",
    guests=0,
    customer=None,
    note=None,
    app_type=None,
    order_id=None,
):
    """Start serving. No money moves, so no register session is needed: a
    waiter with a tablet can open a table before the till is even manned."""
    _assert_outlet(pos_profile)
    _assert_enabled(pos_profile)
    _assert_can(permissions.OPEN_TABLE)
    if table:
        # Two waiters can tap the same table at the same moment. Locking the
        # table row first makes the second one wait, then fail the check, so a
        # table can never end up with two open orders.
        frappe.db.get_value(TABLE, table, "name", for_update=True)
        twin = frappe.db.exists(ORDER, {"table": table, "status": "Open"})
        if twin:
            frappe.throw(_("That table already has an open order ({0})").format(twin))
    doc = frappe.get_doc(
        {
            "doctype": ORDER,
            "pos_profile": pos_profile,
            "table": table or None,
            "order_type": order_type or "Dine in",
            "guests": cint(guests),
            "customer": customer or None,
            "note": (note or "").strip() or None,
            "app_type": (app_type or "").strip() or None,
            "order_id": (order_id or "").strip() or None,
            "status": "Open",
            "opened_by": frappe.session.user,
            "opened_at": now_datetime(),
            "cart": json.dumps({"lines": []}),
        }
    ).insert()
    return _as_dict(doc, with_cart=True)


@frappe.whitelist()
def get_order(name):
    """Reopen an order on any device, exactly as it was left."""
    return _as_dict(_open_doc(name, "read"), with_cart=True)


@frappe.whitelist()
def list_orders(pos_profile, status="Open", limit=50):
    _assert_outlet(pos_profile)
    return frappe.get_all(
        ORDER,
        filters={"pos_profile": pos_profile, "status": status},
        fields=[
            "name", "table_label", "order_type", "guests", "customer_name",
            "total", "status", "opened_at", "closed_at",
        ],
        order_by="opened_at desc",
        limit_page_length=cint(limit) or 50,
    )


def _derive_items(doc, cart):
    """The readable view of the cart: what was ordered, at what price.

    Indicative, not accounting. Promotions and the basket discount are resolved
    by the server at payment, so the figure on the floor screen can be a little
    above what the guest finally pays. The invoice is the authority, always."""
    doc.set("items", [])
    for line in cart.get("lines") or []:
        qty = flt(line.get("qty"))
        rate = flt(line.get("price")) * (1 - flt(line.get("manual_discount_percent")) / 100.0)
        doc.append(
            "items",
            {
                "item_code": line.get("item_code"),
                "item_name": line.get("item_name"),
                "qty": qty,
                "rate": flt(rate, 2),
                "amount": flt(qty * rate, 2),
                "note": ((line.get("note") or "").strip())[:500] or None,
            },
        )


@frappe.whitelist()
def save_order(name, cart=None, customer=None, guests=None, note=None, order_type=None):
    """Keep the order up to date as the waiter rings items in.

    The till calls this on every change (debounced), so an order survives a
    dropped tablet, a locked screen or a waiter who walks away."""
    doc = _open_doc(name)
    if doc.status != "Open":
        frappe.throw(_("This order is {0} and cannot be changed").format(_(doc.status)))
    if cart is not None:
        if isinstance(cart, str):
            cart = json.loads(cart or "{}")
        doc.cart = json.dumps(cart)
        _derive_items(doc, cart)
    if customer is not None:
        doc.customer = customer or None
        doc.customer_name = (
            frappe.db.get_value("Customer", customer, "customer_name") if customer else None
        )
    if guests is not None:
        doc.guests = cint(guests)
    if note is not None:
        doc.note = (note or "").strip() or None
    if order_type:
        doc.order_type = order_type
    doc.save()
    return _as_dict(doc)


@frappe.whitelist()
def move_order(name, table=None):
    """Move an order to another table, or off the floor entirely (which is what
    a takeaway is)."""
    _assert_can(permissions.MOVE_TABLE)
    doc = _open_doc(name)
    if doc.status != "Open":
        frappe.throw(_("This order is {0}").format(_(doc.status)))
    if table:
        frappe.db.get_value(TABLE, table, "name", for_update=True)
        twin = frappe.db.exists(ORDER, {"table": table, "status": "Open", "name": ("!=", name)})
        if twin:
            frappe.throw(_("That table already has an open order ({0})").format(twin))
    doc.table = table or None
    doc.save()
    return _as_dict(doc)


@frappe.whitelist()
def merge_orders(source, target):
    """Pour one order into another: two tables joined, or a guest who moved.

    The source keeps its number and its history, marked Merged and pointing at
    where it went, so nothing is ever silently erased."""
    _assert_can(permissions.MOVE_TABLE)
    if source == target:
        frappe.throw(_("Pick two different orders"))
    src = _open_doc(source)
    dst = _open_doc(target)
    if src.pos_profile != dst.pos_profile:
        frappe.throw(_("Those orders belong to different outlets"))
    if src.status != "Open" or dst.status != "Open":
        frappe.throw(_("Both orders have to be open"))
    src_cart = json.loads(src.cart or "{}")
    dst_cart = json.loads(dst.cart or "{}")
    dst_cart["lines"] = (dst_cart.get("lines") or []) + (src_cart.get("lines") or [])
    dst.cart = json.dumps(dst_cart)
    _derive_items(dst, dst_cart)
    dst.guests = cint(dst.guests) + cint(src.guests)
    dst.save()
    src.status = "Merged"
    src.merged_into = dst.name
    src.closed_at = now_datetime()
    src.set("items", [])
    src.cart = json.dumps({"lines": []})
    src.save()
    return _as_dict(dst)


@frappe.whitelist()
def cancel_order(name, reason=None):
    """Nobody ate: the guests left, or the order was rung up by mistake.

    A cancelled order that had items on it has to say why. That line is the
    only trail there is, since an order never posted anything to cancel."""
    _assert_can(permissions.CANCEL_ORDER)
    doc = _open_doc(name)
    if doc.status != "Open":
        frappe.throw(_("This order is {0}").format(_(doc.status)))
    if doc.invoices:
        frappe.throw(_("This order has already been billed"))
    reason = (reason or "").strip()
    if doc.items and not reason:
        frappe.throw(_("Give a reason for cancelling an order that has items on it"))
    doc.status = "Cancelled"
    doc.cancel_reason = reason or None
    doc.closed_at = now_datetime()
    doc.save()
    return _as_dict(doc)


def close_order(name, invoice, amount):
    """The order was paid. Called by sales.submit_sale, never by the client.

    The table is free the moment the money is in, which is why this runs on the
    sale itself and not on a later click a cashier could forget."""
    doc = frappe.get_doc(ORDER, name)
    if doc.status != "Open":
        return
    doc.append(
        "invoices",
        {"invoice": invoice, "amount": flt(amount, 2), "billed_at": now_datetime()},
    )
    doc.status = "Closed"
    doc.closed_at = now_datetime()
    doc.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# The tables themselves (Settings)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def list_tables(pos_profile):
    _assert_outlet(pos_profile)
    return frappe.get_all(
        TABLE,
        filters={"pos_profile": pos_profile},
        fields=["name", "table_no", "area", "seats", "disabled"],
        order_by="area asc, table_no asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def save_table(pos_profile, table_no, area=None, seats=4, name=None, disabled=0):
    """Add or edit a table. Governed by the ordinary DocType permissions, so a
    shop can let a supervisor rearrange the floor without making them a manager."""
    _assert_outlet(pos_profile)
    from lumen_restaurants.api.settings import _require

    if name:
        _require(TABLE, "write")
        doc = frappe.get_doc(TABLE, name)
    else:
        _require(TABLE, "create")
        doc = frappe.new_doc(TABLE)
        doc.pos_profile = pos_profile
    doc.table_no = table_no
    doc.area = area
    doc.seats = cint(seats)
    doc.disabled = 1 if cint(disabled) else 0
    doc.save()
    return {"name": doc.name}


@frappe.whitelist()
def delete_table(name):
    from lumen_restaurants.api.settings import _require

    _require(TABLE, "delete")
    doc = frappe.get_doc(TABLE, name)
    _assert_outlet(doc.pos_profile)
    doc.delete()
    return {"deleted": name}
