# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
"""Reservations: the till's book, and the public page's letterbox.

Staff reservations are Confirmed the moment they are written, because a person
took them. The public page writes Requested ones, and they wait in a tray on
the reservations screen until somebody confirms or declines: the page promises
the customer a call back, never a table. Guests never read anything.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_time, getdate, now_datetime, nowdate

from lumenpos.api import restaurant

RES = "POS Table Reservation"


def _settings():
    doc = frappe.get_cached_doc("LumenPOS Settings")
    return frappe._dict(
        open=str(doc.get("booking_open") or "12:00:00")[:8],
        close=str(doc.get("booking_close") or "23:30:00")[:8],
        slot=cint(doc.get("booking_slot_minutes")) or 30,
        days=cint(doc.get("booking_days_ahead")) or 14,
        max_guests=cint(doc.get("booking_max_guests")) or 12,
        title=(doc.get("booking_title") or "").strip(),
        subtitle=(doc.get("booking_subtitle") or "").strip(),
        logo=(doc.get("booking_logo") or "").strip(),
        color=(doc.get("booking_color") or "#1463ff").strip() or "#1463ff",
    )


# ---------------------------------------------------------------------------
# The till's book
# ---------------------------------------------------------------------------

@frappe.whitelist()
def day(pos_profile, date=None):
    """One day of the book, plus the tray of online requests (any day)."""
    restaurant._assert_outlet(pos_profile)
    date = getdate(date) if date else getdate(nowdate())
    rows = frappe.get_all(
        RES,
        filters={"pos_profile": pos_profile, "reservation_date": date},
        fields=[
            "name", "customer_name", "phone", "reservation_time", "guests",
            "table", "status", "source", "note", "seated_order",
        ],
        order_by="reservation_time asc",
        limit_page_length=0,
    )
    tables = {
        t.name: (f"{t.area} {t.table_no}".strip() if t.area else t.table_no)
        for t in frappe.get_all(
            "POS Restaurant Table",
            filters={"pos_profile": pos_profile},
            fields=["name", "table_no", "area"],
        )
    }
    for row in rows:
        row["table_label"] = tables.get(row.table)
        row["reservation_time"] = str(row.reservation_time)[:5]
    requested = frappe.get_all(
        RES,
        filters={"pos_profile": pos_profile, "status": "Requested"},
        fields=[
            "name", "customer_name", "phone", "reservation_date",
            "reservation_time", "guests", "note",
        ],
        order_by="reservation_date asc, reservation_time asc",
        limit_page_length=50,
    )
    for row in requested:
        row["reservation_time"] = str(row.reservation_time)[:5]
    return {"date": str(date), "rows": rows, "requested": requested, "now": now_datetime()}


@frappe.whitelist()
def requested_count(pos_profile):
    """The badge on the rail: online requests waiting for a person."""
    restaurant._assert_outlet(pos_profile)
    return frappe.db.count(RES, {"pos_profile": pos_profile, "status": "Requested"})


@frappe.whitelist()
def save_reservation(payload):
    """Create or edit one, from the till. Staff entries are Confirmed at birth:
    a person just took them."""
    if isinstance(payload, str):
        payload = json.loads(payload)
    pos_profile = payload.get("pos_profile")
    restaurant._assert_outlet(pos_profile)
    if payload.get("name"):
        doc = frappe.get_doc(RES, payload["name"])
        if doc.pos_profile != pos_profile:
            frappe.throw(_("That reservation belongs to another outlet"))
    else:
        doc = frappe.new_doc(RES)
        doc.pos_profile = pos_profile
        doc.source = "Till"
        doc.status = "Confirmed"
    doc.customer_name = payload.get("customer_name")
    doc.phone = payload.get("phone")
    doc.reservation_date = getdate(payload.get("reservation_date") or nowdate())
    doc.reservation_time = str(payload.get("reservation_time") or "19:00")
    doc.guests = cint(payload.get("guests")) or 2
    doc.table = payload.get("table") or None
    doc.note = (payload.get("note") or "").strip() or None
    doc.save()
    return {"name": doc.name}


@frappe.whitelist()
def set_reservation_status(name, status):
    """Confirm a request, seat an arrival, record a no-show, or cancel.

    Seating with a table attached opens the table order there and then, so the
    host presses one button and the till is already on it."""
    if status not in ("Confirmed", "Seated", "No show", "Cancelled"):
        frappe.throw(_("Unknown status {0}").format(status))
    doc = frappe.get_doc(RES, name)
    doc.check_permission("write")
    restaurant._assert_outlet(doc.pos_profile)
    opened = None
    if status == "Seated" and doc.table and not frappe.db.exists(
        "POS Restaurant Order", {"table": doc.table, "status": "Open"}
    ):
        opened = restaurant.open_order(
            doc.pos_profile,
            table=doc.table,
            order_type="Dine in",
            guests=doc.guests or 0,
            note=_("Reservation {0}").format(doc.customer_name),
        )
        doc.seated_order = opened["name"]
    doc.status = status
    doc.save(ignore_permissions=True)
    return {"status": doc.status, "order": opened}


# ---------------------------------------------------------------------------
# The public page's letterbox
# ---------------------------------------------------------------------------

def _outlet_bookable(pos_profile):
    if not pos_profile or not frappe.db.exists("POS Profile", pos_profile):
        return False
    return bool(frappe.db.get_value("POS Profile", pos_profile, "lumenpos_online_booking"))


@frappe.whitelist(allow_guest=True)
def book_online(pos_profile=None, customer_name=None, phone=None, reservation_date=None,
                reservation_time=None, guests=None, note=None, website=None):
    """The public form posts here. Writes ONE Requested row and answers with a
    reference; it reads nothing back to the guest and promises only a call.

    `website` is the honeypot: humans never see the field, bots fill it."""
    if (website or "").strip():
        return {"ok": True, "ref": "RSV"}  # a bot leaves happy and empty handed
    if not _outlet_bookable(pos_profile):
        frappe.throw(_("Online booking is not available for this branch"))
    cfg = _settings()

    customer_name = (customer_name or "").strip()[:80]
    phone = "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+")[:16]
    if len(customer_name) < 2:
        frappe.throw(_("Write your name"))
    if len(phone) < 9:
        frappe.throw(_("Write a phone number we can reach you on"))

    date = getdate(reservation_date)
    today = getdate(nowdate())
    if date < today or date > add_days(today, cfg.days):
        frappe.throw(_("Pick a day within the next {0} days").format(cfg.days))
    try:
        moment = get_time(str(reservation_time))
    except Exception:
        frappe.throw(_("Pick a time"))
    if not (get_time(cfg.open) <= moment <= get_time(cfg.close)):
        frappe.throw(_("We take bookings between {0} and {1}").format(cfg.open[:5], cfg.close[:5]))
    people = cint(guests) or 2
    if people < 1 or people > cfg.max_guests:
        frappe.throw(_("For more than {0} guests, call the branch").format(cfg.max_guests))

    # A letterbox, not a firehose: a phone or an address that keeps stuffing it
    # today is politely told to call instead.
    ip = getattr(frappe.local, "request_ip", None) or ""
    flooded = frappe.db.count(
        RES,
        {
            "source": "Online",
            "creation": (">=", str(today)),
            "phone": phone,
        },
    ) >= 5
    if not flooded and ip:
        flooded = frappe.db.count(
            RES, {"source": "Online", "creation": (">=", str(today)), "created_ip": ip}
        ) >= 15
    if flooded:
        frappe.throw(_("Too many requests today. Call the branch and we will book you in"))

    doc = frappe.get_doc(
        {
            "doctype": RES,
            "pos_profile": pos_profile,
            "customer_name": customer_name,
            "phone": phone,
            "reservation_date": date,
            "reservation_time": str(reservation_time),
            "guests": people,
            "note": (note or "").strip()[:300] or None,
            "status": "Requested",
            "source": "Online",
            "created_ip": ip[:45] or None,
        }
    )
    doc.insert(ignore_permissions=True)
    frappe.db.commit()  # nosemgrep: a guest request must survive its own response
    return {"ok": True, "ref": doc.name.split("-")[-1]}
