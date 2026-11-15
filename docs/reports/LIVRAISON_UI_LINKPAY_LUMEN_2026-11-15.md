# UI native Link Pay — Lumen Restaurants

Date : 2026-11-15. Dépendance native autorisée ; aucun changement konektag-web.

PaymentOverlay affiche Link Pay et un motif métier clair lorsqu'il n'est pas activé. Le même composant couvre SellView, RestaurantSellView et TablesView. Le parcours demande le contexte serveur puis prépare, reprend, actualise, annule et finalise via les RPC konektag_360.link_pay.pos convenues avec360.

- Montant restant et statut canoniques serveur ; espèces prévues prises dans le snapshot natif complet cart.orderSnapshot, sans serializer simplifié.
- Autres cartes, compte client, cartes cadeaux, cashback, crédit magasin, fidélité, échange et devise étrangère exclus ; Link Pay nécessite une connexion et un devis serveur.
- Intent actif/incertain : caisse de cet ordre gelée ; autres tables restent accessibles. Clés distinctes par ordre et UUID de tentative inconnue, scopedPOS/user ; aucune donnée panier/contact persistée.
- Reprise explicitement sélectionnée, empêchée si elle écraserait un autre panier ; réponses asynchrones périmées ignorées. Retour à un ordre recharge son contexte serveur.
- Annulation n'autorise le dégel qu'après réponse serveur ; jamais de déclaration LinkPay dans payments côté navigateur ni passage dans la file offline.
- Paid peut demander une finalisation sous la session réelle du caissier ; Completed avec vrai receipt suit le chemin natif stock/cache/clear puis événement done. Un paiement reçu sans finalisation reste identifié comme tel.
- Liens HTTPS partageables/copiables, composeurs SMS/e-mail et WhatsApp du device. Aucun envoi automatique ni nouveau moteur QR client. Traductions FR réelles ajoutées.

Fichiers : frontend/src/components/LinkPayPanel.vue, LinkPayResume.vue, PaymentOverlay.vue ; stores/linkpay.js et cart.js ; vues Sell/RestaurantSell/Tables ; locales/fr.js. Les assets public/pos sont produits par Vite à partir des sources, jamais édités manuellement.

Validation : npm ci puis npm run build Vite réussis, git diff --check réussi. Avertissement standard de taille de chunk, build non bloqué. Aucun workflow CI préexistant dans ce dépôt ; aucune CI créée pour cette tâche. Aucun test fonctionnel, paiement, commande, message ou mutation production exécuté.

Le restaurant de démonstration ne possède pas encore de canal/accord de collecte approuvé : le bouton doit rester indisponible avec « Link Pay n’est pas encore activé pour cet établissement ». La mise en production coordonnée de l'UI ne constitue pas une activation commerciale de Link Pay.

Nouveaux RPC/backend et bouton Desk relèvent de la livraison360. Source initiale0838201 ; publication main de ce dépôt autorisée par le coordinateur, puis assemblage de l'image commune par360.

Cache natif : version Lumen portée de0.1.0-r18 à0.1.0-r19. Le mécanisme existant www/pos.py estampille pos.js, pos.css et /sw.js ; le service worker crée son cache par cette version. L’image doit embarquer __init__.py avec les assets construits, sans purge manuelle ni nouveau mécanisme.
