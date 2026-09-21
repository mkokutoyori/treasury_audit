# Moteur d'audit — opérations de marché monétaire (titres)

Revue automatisée des activités titres du département de la trésorerie. Le rapport produit est
un fichier texte qui présente les anomalies relevées, hiérarchisées par gravité.

## Exécution

```bash
python3 audit_titres.py                          # RAPPORT_AUDIT_TITRES.txt
python3 audit_titres.py --sortie mon_rapport.txt
python3 audit_titres.py --debut 2024-01-01 --fin 2024-12-31
python3 audit_titres.py --seuil 10000000         # seuil de matérialité en XAF
```

Dépendance : `pandas`. Les fichiers d'extraction sont lus à la racine du dépôt.

## Organisation

```
audit_titres.py           point d'entrée : charge, exécute, écrit le rapport
audit/
  core.py                 gravités, constats, sections, rendu du rapport texte
  data.py                 chargement des extractions, plan de comptes, paramètres
  checks/
    s01_donnees.py        intégrité et complétude des données
    s02_referentiel.py    référentiel des contrats
    s03_cycle_vie.py      cycle de vie des titres sous Flexcube
    s04_controle_interne.py  séparation des tâches, habilitations, horaires
    s05_migration.py      bascule Flexcube vers Calypso
    s06_calypso.py        manquements du nouveau dispositif
    s07_pensions.py       pensions livrées auprès de la banque centrale
    s08_sbb.py            cessions-rétrocessions
    s09_resultat.py       résultat, classement comptable, rendement
```

**Une section du rapport = un module.** Chaque module expose `SECTION = (numéro, titre)` et
`run(ctx) -> Section`. À l'intérieur, chaque contrôle est une fonction `_cNN_nom(ctx) -> Constat`
appelée depuis `run()`. Un contrôle qui échoue n'interrompt pas le rapport : l'erreur est
consignée dans la section concernée.

## Ajouter un contrôle

```python
def _c310_mon_controle(ctx) -> Constat:
    """Une phrase disant ce que le contrôle vérifie et pourquoi."""
    donnees = ctx.grand_livre[...]
    if rien_a_signaler:
        return Constat(code="3.10", titre="...", gravite=Gravite.CONFORME,
                       constat="Ce qui a été testé et pourquoi c'est satisfaisant.")
    return Constat(
        code="3.10", titre="...", gravite=Gravite.ELEVEE,
        constat="Le constat, ses causes et sa portée.",
        chiffres=[("Libellé", "valeur")],
        tableaux=[Tableau(["Colonne"], [[valeur]])],
        recommandation="Ce qu'il faut obtenir ou corriger.",
    )
```
puis l'appeler depuis `run()`. Les gravités disponibles sont `CRITIQUE`, `ELEVEE`, `MOYENNE`,
`FAIBLE` et `CONFORME` — cette dernière documente la couverture sans alimenter les anomalies.

## Principes retenus

- **Tout contrôle a été vérifié manuellement avant d'être codé.** Le script reproduit une revue
  conduite pas à pas, il ne l'invente pas.
- **Les contrôles sans anomalie sont conservés** : un rapport d'audit doit montrer ce qui a été
  testé, pas seulement ce qui ne va pas.
- **Aucun seuil absolu arbitraire** lorsqu'un test statistique robuste est possible. Les taux,
  par exemple, sont comparés à la médiane des opérations du même produit et du même exercice.
- **Les identifiants sont lus en chaînes de caractères** : les zéros de tête sont significatifs.
- **Les soldes ne sont affirmés que pour les comptes ouverts pendant la période**, dont le solde
  d'ouverture est nul par construction. Pour les autres, le rapport signale la limite.

## Paramètres

`audit/data.py`, classe `Config` : période, seuil de matérialité, seuil de significativité, base
de décompte des jours, tolérance sur le recalcul des courus, plage horaire ouvrable.

## Périmètre actuel et suite

Couvert : opérations de marché monétaire (titres), pensions livrées, cessions-rétrocessions,
migration Flexcube vers Calypso.

À venir : opérations de change (position de change, réévaluation, change clientèle, marges
négociées, conformité à la parité fixe et à la réglementation des changes CEMAC).
