# Audit comptable et fiscal — Congo-Brazzaville (SYSCOHADA)

## Objet
Vérifier que Lumen Restaurants respecte les paramètres comptables et fiscaux de la société ERPNext (Company / POS Profile), sans imposer un référentiel étranger. Aucun déploiement ni modification métier avant tests.

## Constats vérifiés dans le code
- `lumen_restaurants/hooks.py` déclare ERPNext comme dépendance obligatoire.
- `lumen_restaurants/api/sales.py` crée des `POS Invoice` ou `Sales Invoice` suivant `POS Profile.lumenpos_invoice_mode`.
- La construction de la facture reprend `profile.company` et `profile.taxes_and_charges`.
- `invoice.set_missing_values()` puis `invoice.run_method("calculate_taxes_and_totals")` utilisent les mécanismes ERPNext.
- Les entrepôts sont validés par rapport à la société du profil.
- Attention : `_ensure_ignore_pricing_rule(profile)` impose l'ignorance des Pricing Rules ERPNext.
- Attention : `_apply_service_charge(...)` intervient avant le calcul des taxes.
- Une exception de comptabilisation utilise un `income_account` explicite pour les cartes cadeaux ; vérifier le compte et sa société.
- Les modes de paiement, remboursements et écritures de clôture nécessitent un audit approfondi.

## Vérifications indispensables
- [ ] Aucune référence codée en dur à des comptes non OHADA, ni à une société ou une devise étrangère.
- [ ] Ventes, retours, remises, pourboires et frais de service : imputation aux comptes configurés dans ERPNext.
- [ ] TVA : taxes du POS Profile, taxes par article, exonérations, TVA comprise et taxes en cascade.
- [ ] Compatibilité du mode POS Invoice et de la consolidation avec le SYSCOHADA.
- [ ] Compatibilité du mode Sales Invoice et de la comptabilisation immédiate.
- [ ] Paiements espèces, banque, Mobile Money et écarts de caisse : comptes de la société.
- [ ] Montants en XAF, précision, arrondis et rendu de monnaie.
- [ ] Contrôle des factures, mentions obligatoires et éventuelles exigences de fiscalisation propres au Congo.
- [ ] Tests d'intégration sur société fictive Congo (CG), comptes SYSCOHADA, taxes configurées, sans toucher à la production.

## Architecture cible
Lumen Restaurants → factures et paiements ERPNext → comptes et taxes de la Company / POS Profile → grand livre SYSCOHADA → reporting OHADA.

La conformité fiscale congolaise doit être validée indépendamment de la compatibilité comptable. Les taux, exemptions et obligations réglementaires doivent être confirmés auprès d'un professionnel local avant mise en production.
