# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
# Lumen Restaurants 0.1.0-r5: the logo in the ERPNext desk bar and on the login
# page of an existing site (a new one gets it at install). Only while Navbar
# Settings has no logo of its own, see branding.py. The lr_ folder keeps
# Lumen Restaurants' own patches apart from LumenPOS's version folders.
from lumen_restaurants.branding import set_desk_logo


def execute():
    set_desk_logo()
