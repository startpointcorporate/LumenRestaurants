# Bringing a LumenPOS update into Lumen Restaurants

Lumen Restaurants is LumenPOS with the restaurant built in, as an app of its own.
Its history is LumenPOS's history, so every LumenPOS release is merged in like
any other branch. Do it for each LumenPOS release, and before each Lumen
Restaurants release.

## What stays LumenPOS-named on purpose

Only the app's identity and its module are Lumen Restaurants: the Python
package `lumen_restaurants`, the app name and title, the module *Lumen
Restaurants* (folder `lumen_restaurants/lumen_restaurants/`, and the `module`
of every doctype), the dotted paths (imports, hooks, patches, the server methods
the screens call) and the asset URLs (`/assets/lumen_restaurants/...`). The
module needs a name of its own because Frappe maps module names to apps across
the whole bench: two apps with one module name cannot share a bench, and Frappe
Cloud puts many apps on one bench. The internal record names stay LumenPOS's:
the doctypes (such as *LumenPOS Settings*), the custom fields (`lumenpos_*`),
the roles (*LumenPOS Manager*, *LumenPOS Cashier*), the *LumenPOS* workspace and
the browser's offline store. That keeps each merge small, and a site that moves
from LumenPOS keeps its data.

Because the record names are shared, a site runs one of the two apps.
`lumen_restaurants/site_guard.py` refuses either app on a site that runs the
other, before anything is written.

## The steps

1. **Fetch LumenPOS.** `git fetch lumenpos`. The `lumenpos` remote points at the
   LumenPOS repository, and pushing to it is disabled on purpose.
2. **Merge.** `git merge lumenpos/main`. Git follows the folder renames
   (`lumenpos/` to `lumen_restaurants/`, and the module folder
   `lumenpos/lumenpos/` to `lumen_restaurants/lumen_restaurants/`) by itself in
   almost every case.
3. **Give the new code the Lumen Restaurants identity.**
   `node scripts/rename_from_lumenpos.mjs`. It moves anything that still landed
   under an old folder, and renames the dotted paths, the module name, the asset
   URLs and the app name. Running it twice changes nothing.
4. **Resolve the conflicts.**
   - Keep ours, then carry over any real change by hand: `README.md`, `NOTICE`,
     `TRADEMARKS.md`, `frontend/public/manifest.json`, the icons in
     `frontend/public/` (`favicon.svg`, `favicon-*.png`, `pwa-*.png`,
     `app-icon-180.png`, all from the logo kit), `lumen_restaurants/public/images/`
     (the logo kit itself), and the version in `lumen_restaurants/__init__.py`.
   - Delete again if a merge brings them back: `scripts/make_icons.mjs` and
     `frontend/public/icon-192.png` / `icon-512.png` (LumenPOS's icons).
   - Keep both sides: `lumen_restaurants/hooks.py` (the title, the description,
     the two `site_guard` hooks, and the logo hooks: the `after_install` list,
     `website_context`, `add_to_apps_screen`), `lumen_restaurants/patches.txt`
     (our own patches live in `patches/lr_*` folders), `lumen_restaurants/api/session.py` (the
     restaurant switches at the end of `get_bootstrap`), `lumen_restaurants/install.py` (the section
     labels), `lumen_restaurants/www/pos.html` (the title and the icon links) and
     `book.html` (the title, the favicon and the footer mark),
     `frontend/public/sw.js` (the icon names it keeps offline),
     `lumen_restaurants/api/printing.py` (the two `receipt_images` lines:
     the restaurant's logo on top, our mark at the foot),
     `frontend/src/components/ReceiptView.vue` (our mark at the foot),
     `frontend/src/components/NavRail.vue` (the logo), `App.vue` (the product
     name, the router view keyed by the outlet, the table order put down on an
     outlet switch, the restaurant screens sent back to the till at a shop
     outlet), `components/OpenRegisterOverlay.vue` (the same table order rule),
     and `SettingsView.vue` and `messages.js` (the product name).
   - `docs/user-guide.md`: keep our header and the *Lumen Restaurants releases*
     table, take LumenPOS's new sections and rows.
   - A doctype file LumenPOS changed: take its change. Should a conflict land on
     the `"module"` line, the rename script sets it back to Lumen Restaurants.
   - The restaurant's own files (its screens, doctypes and APIs) and
     `site_guard.py`, `branding.py` and `receipt_images.py` do not exist in
     LumenPOS, so they never conflict.
5. **Rebuild the till.** `cd frontend && npm ci && npx vite build`, and commit the
   build in `lumen_restaurants/public/pos`. The build is what the sites run.
6. **Check.**
   - `python3 scripts/check_endpoints.py`: every call from the screens resolves
     to a whitelisted server method.
   - `node scripts/rename_from_lumenpos.mjs --check` reports 0 files.
   - The Python compiles (`python3 -m compileall -q lumen_restaurants`).
7. **Test, then release.** Install on a throwaway site on the benches first,
   then the test sites. Bump the version (`x.y.z-rN` for previews) and add the
   changelog row in `docs/user-guide.md` in the same commit as the code.
