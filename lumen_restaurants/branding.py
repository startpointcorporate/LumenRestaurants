# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
"""The Lumen Restaurants logo in ERPNext's own screens (reference/brand-kit).

- The browser tab and the loading screen: `website_context` in hooks.py. The
  last app's value wins over ERPNext's, and Website Settings (Favicon, Splash
  Image) still override it, as for any site.
- The desk bar and the login page: Navbar Settings, App Logo. Set here once,
  on install and by a patch on existing sites, and only while it is empty, so
  an admin's own logo is never replaced and clearing the field brings
  ERPNext's back. Not the `app_logo_url` hook: with a third app declaring one,
  Frappe shows its own framework logo instead of any of them.
- Frappe v15's apps screen (/apps) and sidebar app switcher:
  `add_to_apps_screen` in hooks.py, gated by can_open_till below.
"""
import frappe

APP_ICON = "/assets/lumen_restaurants/images/svg/app-icon.svg"


def set_desk_logo():
    if not frappe.db.get_single_value("Navbar Settings", "app_logo"):
        frappe.db.set_value("Navbar Settings", "Navbar Settings", "app_logo", APP_ICON)
        frappe.clear_cache()


def after_install():
    set_desk_logo()


def can_open_till():
    """The Lumen Restaurants tile on the apps screen: for a signed-in user who
    may ring up a sale at one outlet at least."""
    if frappe.session.user == "Guest" or not frappe.has_permission("POS Invoice", "create"):
        return False
    from lumen_restaurants.api.session import _user_profiles

    return bool(_user_profiles())
