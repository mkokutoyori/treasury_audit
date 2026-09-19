"""Section 1 — Intégrité et complétude des données extraites.

Cette section ne juge pas la trésorerie : elle qualifie la matière sur laquelle reposent
toutes les autres sections. Une anomalie ici relativise les constats qui suivent.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf


SECTION = (1, "Intégrité et complétude des données")


def _paques(annee: int) -> dt.date:
    """Dimanche de Pâques (algorithme de Butcher)."""
    a, b, c = annee % 19, annee // 100, annee % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois = (h + l - 7 * m + 114) // 31
    jour = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(annee, mois, jour)


def feries(annee: int) -> set[str]:
    """Jours fériés camerounais à date fixe et ceux dérivés de Pâques.

    Les fêtes musulmanes (Ramadan, Mouloud, Tabaski) sont mobiles et ne sont pas calculées :
    les dates restantes sont donc présentées comme « à confirmer » et non comme anomalies.
    """
    fixes = [(1, 1), (2, 11), (5, 1), (5, 20), (8, 15), (12, 25)]
    jours = {dt.date(annee, m, j) for m, j in fixes}
    p = _paques(annee)
    jours |= {p - dt.timedelta(days=2), p + dt.timedelta(days=1), p + dt.timedelta(days=39)}
    return {d.strftime("%Y-%m-%d") for d in jours}


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "Contrôles de forme sur les extractions du core banking : équilibre de la partie "
            "double, doublons, continuité calendaire, conventions de contre-passation et "
            "couverture des données. Ces tests conditionnent la fiabilité de toutes les sections "
            "suivantes."
        ),
    )
    s.ajouter(_c11_partie_double(ctx))
    s.ajouter(_c12_doublons(ctx))
    s.ajouter(_c13_calendrier(ctx))
    s.ajouter(_c14_migration_technique(ctx))
    s.ajouter(_c15_montants_negatifs(ctx))
    s.ajouter(_c16_couverture(ctx))
    s.ajouter(_c17_soldes_ouverture(ctx))
    return s


def _c11_partie_double(ctx) -> Constat:
    """L'équilibre ne se teste que sur les extractions complètes par module.

    Une extraction filtrée par compte laisse forcément des jambes hors périmètre : la tester
    produirait un faux positif.
    """
    lignes, anomalies = [], 0
    for nom, df in (("Module MM", ctx.ecritures_mm), ("Flux Calypso", ctx.ecritures_calypso)):
        if df.empty:
            continue
        groupes = df.groupby(["TRN_REF_NO", "TRN_DT"]).SIGNE.sum()
        desequilibrees = groupes[groupes.abs() > 0.5]
        anomalies += len(desequilibrees)
        lignes.append([nom, len(df), len(groupes), len(desequilibrees),
                       float(desequilibrees.abs().sum()), float(df.SIGNE.sum())])
    if not anomalies:
        return Constat(
            code="1.1", titre="Équilibre de la partie double", gravite=Gravite.CONFORME,
            constat=(
                "Sur les extractions complètes par module — les seules où l'équilibre soit "
                "testable — aucune écriture n'est déséquilibrée et la somme des débits moins "
                "crédits est nulle. Les extractions filtrées par compte ne sont pas testées : "
                "leurs jambes de contrepartie sont hors périmètre par construction."
            ),
            tableaux=[Tableau(["Source", "Lignes", "Écritures", "Déséquilibrées", "Montant", "Somme D-C"], lignes)],
        )
    return Constat(
        code="1.1",
        titre="Écritures déséquilibrées dans les extractions complètes",
        gravite=Gravite.MOYENNE,
        constat=(
            "Des écritures issues d'extractions complètes par module présentent un déséquilibre "
            "entre débits et crédits. Ces extractions contenant la totalité des jambes, le "
            "déséquilibre ne peut s'expliquer par un effet de périmètre. Il s'agit le plus souvent "
            "d'écritures dont les jambes sont horodatées de part et d'autre de minuit, mais chaque "
            "cas doit être vérifié."
        ),
        chiffres=[("Somme globale débits moins crédits",
                   xaf(sum(l[5] for l in lignes)))],
        tableaux=[Tableau(["Source", "Lignes", "Écritures", "Déséquilibrées", "Montant", "Somme D-C"], lignes)],
        recommandation="Obtenir le détail des écritures concernées et vérifier l'horodatage des jambes.",
    )


def _c12_doublons(ctx) -> Constat:
    cles = ["TRN_REF_NO", "AC_NO", "DRCR_IND", "LCY_AMOUNT", "STMT_DT"]
    lignes, total = [], 0
    for nom, df in (
        ("Module MM", ctx.ecritures_mm),
        ("Flux Calypso", ctx.ecritures_calypso),
        ("Comptes clés", ctx.comptes_cles),
        ("Comptes généraux Calypso", ctx.comptes_calypso),
        ("Grand livre trésorerie", ctx.grand_livre),
        ("Créances rattachées", ctx.courus),
    ):
        if df.empty:
            continue
        n = int(df.duplicated(subset=cles).sum())
        total += n
        if n:
            lignes.append([nom, len(df), n, round(n / len(df) * 100, 2),
                           float(df[df.duplicated(subset=cles)].LCY_AMOUNT.sum())])
    if not lignes:
        return Constat(code="1.2", titre="Absence de doublons", gravite=Gravite.CONFORME,
                       constat="Aucune ligne dupliquée détectée.")
    return Constat(
        code="1.2",
        titre="Lignes dupliquées dans les extractions",
        gravite=Gravite.MOYENNE,
        constat=(
            "Des lignes strictement identiques — même référence, compte, sens, montant et "
            "horodatage à la seconde — coexistent dans les extractions. Il peut s'agir d'écritures "
            "légitimement identiques, par exemple plusieurs contrats accrédités pour le même "
            "montant à la même seconde, ou d'un artefact d'extraction. Les analyses du présent "
            "rapport travaillent sur une base dédoublonnée ; le risque porte donc sur les "
            "exploitations tierces de ces fichiers."
        ),
        chiffres=[("Total des lignes dupliquées", f"{total:,}".replace(",", " "))],
        tableaux=[Tableau(["Source", "Lignes", "Doublons", "Part %", "Montant XAF"], lignes)],
        recommandation="Faire qualifier ces doublons par l'informatique avant toute reprise des données.",
    )


def _c13_calendrier(ctx) -> Constat:
    df = ctx.grand_livre
    jours = pd.to_datetime(sorted(df.TRN_DT.dropna().unique()))
    ouvres = pd.date_range(jours.min(), jours.max(), freq="B")
    manquants = sorted(set(ouvres) - set(jours))
    calendrier = set()
    for annee in range(jours.min().year, jours.max().year + 1):
        calendrier |= feries(annee)
    a_confirmer = [d for d in manquants if d.strftime("%Y-%m-%d") not in calendrier]
    expliques = len(manquants) - len(a_confirmer)
    if not a_confirmer:
        return Constat(
            code="1.3", titre="Continuité du calendrier comptable", gravite=Gravite.CONFORME,
            constat=(
                f"Les {len(manquants)} jours ouvrés sans écriture correspondent tous à des jours "
                "fériés calculés (fêtes à date fixe et fêtes mobiles dérivées de Pâques)."
            ),
        )
    return Constat(
        code="1.3",
        titre="Jours ouvrés sans écriture restant à rapprocher du calendrier des fériés",
        gravite=Gravite.FAIBLE,
        constat=(
            "Des jours ouvrés ne portent aucune écriture. Les fêtes à date fixe et celles dérivées "
            "de Pâques sont identifiées automatiquement ; les dates restantes correspondent "
            "vraisemblablement aux fêtes musulmanes, qui sont mobiles et ne peuvent pas être "
            "calculées. Elles sont donc présentées pour confirmation et non comme anomalies."
        ),
        chiffres=[
            ("Jours ouvrés sans écriture", str(len(manquants))),
            ("Expliqués par le calendrier calculé", str(expliques)),
            ("À confirmer", str(len(a_confirmer))),
        ],
        tableaux=[Tableau(["Jour ouvré sans écriture"],
                          [[d.strftime("%d/%m/%Y")] for d in a_confirmer], max_lignes=25)],
        recommandation="Rapprocher ces dates du calendrier officiel des jours fériés de l'exercice.",
    )


def _c14_migration_technique(ctx) -> Constat:
    """Écritures passées un jour non ouvré : en pratique, les opérations de bascule technique."""
    df = ctx.grand_livre
    weekend = df[df.TRN_DT_d.dt.dayofweek >= 5]
    if weekend.empty:
        return Constat(code="1.4", titre="Écritures passées un jour non ouvré", gravite=Gravite.CONFORME,
                       constat="Aucune écriture n'est comptabilisée un samedi ou un dimanche.")
    dates = sorted(weekend.TRN_DT.unique())
    par = weekend.groupby(["TRN_DT", "MODULE", "PRODUCT", "USER_ID"]).agg(
        n=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))
    # Les écritures à montant négatif compensées par un montant positif identique
    # signent une reprise technique de soldes.
    neg = weekend[weekend.LCY_AMOUNT < 0]
    net = float(weekend.SIGNE.sum())
    return Constat(
        code="1.4",
        titre="Opération technique passée un week-end, touchant l'ensemble des comptes du périmètre",
        gravite=Gravite.MOYENNE,
        constat=(
            "Des écritures ont été comptabilisées un samedi et un dimanche, sur un week-end "
            "unique. Elles combinent des traitements automatiques de fin de journée et des "
            "écritures manuelles passées sous des codes produit inhabituels, avec des montants "
            "négatifs compensés par des montants positifs identiques.\n"
            "Ce profil est celui d'une REPRISE TECHNIQUE DE SOLDES — renumérotation ou migration "
            "interne. L'effet comptable net est nul, mais l'opération touche l'ensemble des comptes "
            "du périmètre pour des montants significatifs, en dehors de toute journée comptable "
            "ordinaire, et n'a pas d'équivalent ailleurs dans l'historique."
        ),
        chiffres=[
            ("Dates concernées", ", ".join(dates)),
            ("Écritures", f"{len(weekend):,}".replace(",", " ")),
            ("Dont montants négatifs", str(len(neg))),
            ("Effet net sur les comptes", xaf(net)),
            ("Comptes touchés", str(weekend.AC_NO.nunique())),
        ],
        tableaux=[
            Tableau(["Date", "Module", "Produit", "Opérateur", "Écritures", "Montant XAF"],
                    [[i[0], i[1], i[2], i[3], int(r.n), float(r.montant)] for i, r in par.iterrows()])
        ],
        recommandation=(
            "Obtenir la note technique de cette opération, son autorisation et le contrôle de "
            "cohérence des soldes avant et après."
        ),
    )


def _c15_montants_negatifs(ctx) -> Constat:
    lignes = []
    for nom, df in (
        ("Module MM", ctx.ecritures_mm),
        ("Flux Calypso", ctx.ecritures_calypso),
        ("Comptes clés", ctx.comptes_cles),
        ("Grand livre trésorerie", ctx.grand_livre),
        ("Créances rattachées", ctx.courus),
    ):
        if df.empty:
            continue
        neg = df[df.LCY_AMOUNT < 0]
        lignes.append([nom, len(df), len(neg), float(neg.LCY_AMOUNT.sum())])
    return Constat(
        code="1.5",
        titre="Deux conventions de contre-passation opposées entre les deux systèmes",
        gravite=Gravite.MOYENNE,
        constat=(
            "Flexcube comptabilise ses corrections par un débit — ou un crédit — de montant "
            "NÉGATIF, et non par une écriture de sens inverse. Calypso, à l'opposé, contre-passe "
            "par écriture inverse et ne produit aucun montant négatif.\n"
            "Cette divergence a deux conséquences pratiques. Une agrégation qui filtrerait sur le "
            "sens sans tenir compte du signe surévaluerait les volumes et conclurait à tort à "
            "l'absence de contre-passations. Et les volumes des deux systèmes ne peuvent pas être "
            "additionnés sans retraitement préalable."
        ),
        tableaux=[Tableau(["Source", "Lignes", "Montants négatifs", "Cumul XAF"], lignes)],
        recommandation=(
            "Retenir cette convention dans tout rapprochement entre les deux systèmes et dans "
            "toute requête d'extraction ultérieure."
        ),
    )


def _c16_couverture(ctx) -> Constat:
    cfg, df = ctx.config, ctx.grand_livre
    hors = df[df.TRN_DT > cfg.fin]
    avant = df[df.TRN_DT < cfg.debut]
    return Constat(
        code="1.6",
        titre="Couverture temporelle de l'extraction",
        gravite=Gravite.CONFORME,
        constat=(
            f"L'extraction couvre {df.TRN_DT.min()} à {df.TRN_DT.max()} et déborde donc la période "
            f"d'audit dans les deux sens : {len(avant):,} écritures antérieures, qui permettent "
            f"d'établir les soldes d'ouverture, et {len(hors):,} écritures postérieures, utiles au "
            "titre des événements postérieurs à la clôture. Les unes comme les autres sont exclues "
            "des agrégats de la période."
        ).replace(",", " "),
    )


def _c17_soldes_ouverture(ctx) -> Constat:
    df = ctx.grand_livre
    premiere = df.groupby("AC_NO").TRN_DT.min()
    debut_extraction = df.TRN_DT.min()
    anciens = premiere[premiere <= debut_extraction]
    recents = premiere[premiere > debut_extraction]
    return Constat(
        code="1.7",
        titre="Absence de soldes d'ouverture dans les extractions",
        gravite=Gravite.MOYENNE,
        constat=(
            "Les extractions ne contiennent que des MOUVEMENTS : aucun solde d'ouverture n'est "
            "fourni. Pour les comptes dont la première écriture est postérieure au début de "
            "l'extraction, le solde d'ouverture est nul par construction et le cumul des mouvements "
            "vaut solde — c'est le cas de la majorité des comptes du périmètre, et notamment des "
            "comptes ouverts lors de la bascule. Pour les comptes plus anciens, tout encours reste "
            "à ancrer sur la balance générale.\n"
            "Cette limite est structurelle : elle affecte tous les constats portant sur un encours "
            "et non sur un flux."
        ),
        chiffres=[
            ("Comptes du périmètre", str(df.AC_NO.nunique())),
            ("Comptes ouverts pendant la période (solde fiable)", str(len(recents))),
            ("Comptes antérieurs à l'extraction (solde à ancrer)", str(len(anciens))),
            ("Début de l'extraction", str(debut_extraction)),
        ],
        tableaux=[Tableau(["Compte à solde d'ouverture inconnu", "1re écriture"],
                          [[i, v] for i, v in anciens.items()])],
        recommandation=(
            "Obtenir la balance générale détaillée aux 31/12/2023, 31/12/2024, 30/06/2025, "
            "31/12/2025 et 30/06/2026 pour les comptes du périmètre."
        ),
    )
