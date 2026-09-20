"""Modules de contrôle. Chaque module expose SECTION = (numero, titre) et run(ctx) -> Section."""
from . import (
    s01_donnees,
    s02_referentiel,
    s03_cycle_vie,
    s04_controle_interne,
    s05_migration,
    s06_calypso,
    s07_pensions,
    s08_sbb,
    s09_resultat,
    s10_coherence,
    s11_portefeuille,
    s12_comptes_annexes,
)

MODULES = [
    s01_donnees,
    s02_referentiel,
    s03_cycle_vie,
    s04_controle_interne,
    s05_migration,
    s06_calypso,
    s07_pensions,
    s08_sbb,
    s09_resultat,
    s10_coherence,
    s11_portefeuille,
    s12_comptes_annexes,
]
