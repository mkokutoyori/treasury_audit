# Scripts d'exploration

Utilitaires Python/pandas servant de base aux analyses du rapport d'exploration.

- `load.py` — chargement des CSV. **Tous les identifiants et numéros de compte sont lus en
  chaînes de caractères** (`dtype=str`) afin de préserver les zéros de tête. Les fichiers
  découpés en `part_N` sont reconcaténés automatiquement.
  Fonctions : `fx()`, `mm()`, `clp()`, `key()`, `ctr()`.
- `parse_clp.py` — décodage du champ `DESCRIPTION` et de `EXTERNAL_REF_NO` des écritures Calypso
  (Trade Id, Transfer Id, événement, type de produit, émetteur, book, code titre).
  Fonction : `enrich(df)`.

Usage :
```bash
pip install pandas
cd scripts && python3 -c "
from parse_clp import *
c = enrich(clp())
print(c.groupby('CLP_EVENT').LCY_AMOUNT.agg(['size','sum']))
"
```
