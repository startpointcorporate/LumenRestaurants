# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
"""The public booking page, /book/<outlet>.

The link a restaurant puts on its social media, so it has to look like the
restaurant, not like us: the settings give it the name, the logo, the colour
and the welcome line. It is open to guests, but only for an outlet whose POS
Profile has switched public booking ON, and everything it submits lands as a
Requested reservation that a person confirms from the till. It promises the
customer a call, never a table.
"""

import json

import frappe
from frappe.utils import add_days, cint, nowdate

no_cache = 1


def get_context(context):
    from lumenpos.api.reservations import _outlet_bookable, _settings

    outlet = frappe.form_dict.get("outlet") or ""
    context.outlet = outlet
    context.available = _outlet_bookable(outlet)
    cfg = _settings()

    company = frappe.db.get_value("POS Profile", outlet, "company") if context.available else None
    context.title = cfg.title or company or "Booking"
    context.subtitle = cfg.subtitle
    context.logo = cfg.logo
    context.color = cfg.color if cfg.color.startswith("#") and len(cfg.color) in (4, 7) else "#1463ff"
    context.max_guests = cfg.max_guests
    context.csrf_token = frappe.sessions.get_csrf_token()

    # The days and the time slots are laid out server side, so the page is one
    # file of plain HTML and the browser has nothing to compute.
    days = []
    for offset in range(cfg.days):
        date = add_days(nowdate(), offset)
        days.append({"value": str(date), "label": frappe.utils.formatdate(date, "EEE d MMM")})
    context.days = days

    slots = []
    start_h, start_m = cint(cfg.open[:2]), cint(cfg.open[3:5])
    end_h, end_m = cint(cfg.close[:2]), cint(cfg.close[3:5])
    minute = start_h * 60 + start_m
    end = end_h * 60 + end_m
    while minute <= end:
        hh, mm = divmod(minute, 60)
        slots.append(f"{hh:02d}:{mm:02d}")
        minute += cfg.slot or 30
    context.slots = slots
    context.days_json = json.dumps(days)
    context.slots_json = json.dumps(slots)
    return context
