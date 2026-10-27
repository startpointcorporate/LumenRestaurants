# French localization audit — Konektag

## Scope
- Vue frontend UI: `frontend/src/locales/fr.js`, `frontend/src/i18n.js`, restaurant views, dialogs and components.
- Frappe messages: `lumen_restaurants/translations/fr.csv`.
- Preserve English source keys, interpolation placeholders, and upstream AGPL-3.0 notices.
- Do not translate ERPNext master data (item groups, product names, customer-entered labels).

## Confirmed architecture
The Vue frontend uses an existing lightweight `t(key, params)` function. Language dictionaries are loaded lazily through `import.meta.glob('./locales/*.js')`. Missing keys fall back to English; installing an additional i18n package is unnecessary.

French strings already exist in `frontend/src/locales/fr.js`, while restaurant-specific Arabic source text is grouped in `frontend/src/messages-restaurant.js`. French server translations are in `lumen_restaurants/translations/fr.csv`.

## Audit checklist
- [ ] Compare every translatable UI key with the French dictionary, including restaurant-specific keys.
- [ ] Scan Vue templates and JavaScript for untranslated literal labels, accessibility text, toast messages and dialogs.
- [ ] Review ambiguous terms against `scripts/i18n/glossary_fr.json`; keep POS terminology consistent.
- [ ] Verify placeholders, punctuation and formatting with the repository's i18n scripts.
- [ ] Distinguish static UI labels from ERPNext user-entered item-group names.
- [ ] Run the Vite build and exercise POS, tables, kitchen, bookings, menu, payments and settings with locale `fr`.
- [ ] Verify lazy-loaded locale updates and cached/service-worker assets on deployment.

## Initial screenshot observations
English examples needing investigation: Dine in, Takeaway, Delivery, Own delivery, Customer (optional), Tap the menu to start the order, Search the menu..., Nothing here yet, Bookings, Kitchen, Insights. Product-group names such as Consumable, Raw Material and Sub Assemblies may be ERPNext master data and must not be silently relabeled.

## Delivery
Submit changes to this branch as a reviewed pull request to `main`; do not deploy to production before functional validation.
