# Multilingual localization plan — Konektag

Target locales: French (`fr`), Spanish (`es`), German (`de`) and Italian (`it`).

## Verified baseline
- French, Spanish and German already have frontend dictionaries in `frontend/src/locales/` and Frappe CSV files in `lumen_restaurants/translations/`.
- Italian is not currently listed in `frontend/src/i18n.js` and has neither `frontend/src/locales/it.js` nor `lumen_restaurants/translations/it.csv`.
- The app has a built-in lazy-loading i18n system. No new dependency is needed.

## Implementation
1. Extract all frontend and server translation keys using the upstream scripts in `scripts/i18n/`.
2. Compare keys against `fr`, `es`, `de`, and `it`; report missing, obsolete and untranslated entries.
3. Translate missing entries, preserving placeholders and the upstream i18n glossary rules.
4. For Italian, add a complete `it.js` and `it.csv`, add `it` to `LANGUAGES` and language-name keys in the dictionaries.
5. Check hardcoded Vue labels, toasts, dialogs, help text and accessibility strings.
6. Build the frontend and test each locale in sales, menu, tables, kitchen, bookings, payments, reporting and settings.
7. Submit reviewed changes via PR; do not deploy directly to production.

Note: item names and ERPNext master data are not UI translation keys and should remain as entered.
