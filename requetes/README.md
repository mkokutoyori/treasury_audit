# Requêtes d'extraction — audit trésorerie

`extractions_complementaires.sql` contient les requêtes construites à partir de celle
fournie par la banque (`actb_history` + `sttb_account` + `cstb_addl_text`). Les colonnes
et leur ordre sont **conservés à l'identique**, pour que les fichiers produits soient
lisibles par les chargeurs existants (`scripts/load.py`).

## Ordre d'exécution recommandé

| # | Requête | Priorité | Volume attendu | Constat instruit |
|---|---|---|---|---|
| 0 | Plan de comptes | **1** | quelques milliers | §8.11, §11.4 — évite de deviner les codes |
| 1 | Comptes de résultat de change | **1** | faible | §11.4 |
| 2 | Écritures complètes de réévaluation | **1** | 30-40 k | §11.4 |
| 3 | Sell-Buy-Back, écritures complètes | **1** | 3-6 k | §11.5 |
| 7 | Soldes aux dates d'arrêté | **1** | faible | tous — lève la limite majeure |
| 4 | 3ᵉ jambe des écritures de migration | 2 | 3-6 lignes | §12.5 |
| 5 | Les 41 comptes de trésorerie, tous modules | 2 | 350-450 k | §12.7 — règle de méthode |
| 6 | Variante incluant la période courante | — | — | si les derniers jours manquent |

Les requêtes 0, 1, 4 et 7 sont **petites et rapides** : elles peuvent être lancées
immédiatement. La 5 est volumineuse et peut attendre.

## Consignes d'export

1. **Encodage UTF-8.** Le fichier `creance_rattaché.csv` était en CP1252 et contenait
   des espaces insécables (`0xA0`), ce qui faisait échouer la lecture.
2. **Numéros de compte et références en texte**, pour préserver les zéros de tête
   (`00110000006`, `099ACO00001`).
3. **Indiquer le format de date** retenu (les extractions reçues en utilisent deux :
   `AAAA-MM-JJ` et `JJ-MMM-AA`).
4. **Découper les fichiers de plus de ~60 000 lignes** en `part_1`, `part_2`… — la
   concaténation est automatique côté analyse.

## Pourquoi une extraction « tous modules »

L'extraction initiale du compte `511800100` était filtrée sur `MODULE = 'MM'`. Les
écritures d'apurement des coupons, passées en module `DE`, y étaient donc invisibles,
ce qui a conduit à un constat erroné — retiré depuis (§8.1 et §11.10 du rapport
d'exploration). Le module `DE` porte les opérations structurantes : apurement des
coupons, corrections, écritures de migration.

> **Règle retenue** : tout constat portant sur le solde ou le comportement d'un compte
> doit être établi sur une extraction du compte **tous modules confondus**.
