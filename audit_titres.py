#!/usr/bin/env python3
"""Revue automatisée des opérations de marché monétaire (titres) du département trésorerie.

Le rapport est produit au format texte. Chaque section du rapport correspond à un module de
contrôle indépendant (audit/checks/). Pour ajouter un contrôle, il suffit d'ajouter une
fonction dans le module de la section concernée et de l'appeler depuis run().

Usage :
    python3 audit_titres.py [--sortie RAPPORT.txt] [--debut AAAA-MM-JJ] [--fin AAAA-MM-JJ]
"""
from __future__ import annotations

import argparse
import sys

from audit.checks import MODULES
from audit.core import Rapport, executer
from audit.data import Config, Contexte

LIMITES = [
    "Les extractions ne contiennent que des mouvements : aucun solde d'ouverture n'est fourni. "
    "Pour les comptes ouverts pendant la période, le cumul des mouvements vaut solde ; pour les "
    "autres, tout encours reste à ancrer sur la balance générale.",
    "Le référentiel des deals du nouveau système n'a pas été fourni. Nominal, taux, échéance et "
    "contrepartie des opérations postérieures à la bascule ne sont connus qu'indirectement, par "
    "le libellé des écritures.",
    "Aucune donnée de marché n'est disponible : les valorisations et les dépréciations ne peuvent "
    "pas faire l'objet d'un recalcul indépendant.",
    "Une extraction filtrée par module peut faire apparaître une anomalie inexistante. Tous les "
    "contrôles portant sur le solde d'un compte sont établis sur une extraction tous modules "
    "confondus.",
]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sortie", default="RAPPORT_AUDIT_TITRES.txt",
                        help="fichier texte produit (défaut : RAPPORT_AUDIT_TITRES.txt)")
    parser.add_argument("--debut", default=Config.debut, help="début de la période d'audit")
    parser.add_argument("--fin", default=Config.fin, help="fin de la période d'audit")
    parser.add_argument("--seuil", type=float, default=Config.seuil_materialite,
                        help="seuil de matérialité en XAF")
    args = parser.parse_args(argv)

    config = Config(debut=args.debut, fin=args.fin, seuil_materialite=args.seuil)
    contexte = Contexte(config=config)

    print("Chargement des extractions...", file=sys.stderr)
    _ = contexte.grand_livre  # force le chargement principal pour mesurer le temps ici
    print(f"  {len(contexte.grand_livre):,} lignes de grand livre".replace(",", " "), file=sys.stderr)

    print("Exécution des contrôles...", file=sys.stderr)
    sections = executer(MODULES, contexte)

    rapport = Rapport(
        titre="Rapport d'audit — opérations de marché monétaire (titres)",
        perimetre="Département de la trésorerie — gestion des investissements sur les marchés financiers",
        periode=f"{config.debut} au {config.fin}",
        sections=sections,
        avertissements=LIMITES,
    )
    texte = rapport.rendu()
    with open(args.sortie, "w", encoding="utf-8") as fichier:
        fichier.write(texte)

    anomalies = rapport.toutes_anomalies
    print(f"\nRapport écrit dans {args.sortie}", file=sys.stderr)
    print(f"  {len(sections)} sections, {len(anomalies)} anomalies relevées.", file=sys.stderr)
    for section in sections:
        if section.erreurs:
            print(f"  ! Section {section.numero} : {'; '.join(section.erreurs)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
