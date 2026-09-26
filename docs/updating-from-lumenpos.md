# Bringing a LumenPOS update into Lumen Restaurants

Lumen Restaurants is LumenPOS with the restaurant built in, as an app of its own.
Its history is LumenPOS's history, so every LumenPOS release is merged in like
any other branch. Do it for each LumenPOS release, and before each Lumen
Restaurants release.

## What stays LumenPOS-named on purpose

Only the app's identity is Lumen Restaurants: the Python package
`lumen_restaurants`, the app name and title, the dotted paths (imports, hooks,
patches, the server methods the screens call) and the asset URLs
(`/assets/lumen_restaurants/...`). The internal record names stay LumenPOS's:
the doctypes (such as *LumenPOS Settings*), the *LumenPOS* module, the custom
fields (`lumenpos_*`), the roles (*LumenPOS Manager*, *LumenPOS Cashier*) and the
browser's offline store. That keeps each merge small, and a site that moves from
LumenPOS keeps its data.

## The steps

1. **Fetch LumenPOS.** `git fetch lumenpos`. The `lumenpos` remote points at the
   LumenPOS repository, and pushing to it is disabled on purpose.
2. **Merge.** `git merge lumenpos/main`. Git follows the package folder rename
   (`lumenpos/` to `lumen_restaurants/`) by itself in almost every case.
3. **Give the new code the Lumen Restaurants identity.**
   `node scripts/rename_from_lumenpos.mjs`. It moves anything that still landed
   under `lumenpos/`, and renames the dotted paths, the asset URLs and the app
   name. Running it twice changes nothing.
4. **Resolve the conflicts.**
   - Keep ours, then carry over any real change by hand: `README.md`, `NOTICE`,
     `TRADEMARKS.md`, `frontend/public/manifest.json`, `frontend/public/icon-*.png`,
     `scripts/make_icons.mjs`, and the version in `lumen_restaurants/__init__.py`.
   - Keep both sides: `lumen_restaurants/api/session.py` (the restaurant switches
     at the end of `get_bootstrap`), `lumen_restaurants/install.py` (the section
     labels), `lumen_restaurants/www/pos.html` and `book.html` (the titles),
     `frontend/src/components/NavRail.vue` (the logo), and `App.vue`,
     `SettingsView.vue` and `messages.js` (the product name).
   - `docs/user-guide.md`: keep our header and the *Lumen Restaurants releases*
     table, take LumenPOS's new sections and rows.
   - The restaurant's own files (its screens, doctypes and APIs) do not exist in
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
