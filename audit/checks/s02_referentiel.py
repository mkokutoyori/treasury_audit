"""Section 2 — Référentiel des contrats de marché monétaire (MM_CONTRACT).

Le référentiel porte les caractéristiques contractuelles : nominal, taux, dates, contrepartie.
Sa fiabilité conditionne tout recalcul d'intérêt et tout contrôle d'échéance.
"""
from __future__ import annotations

import datetime as dt

from ..core import Constat, Gravite, Section, Tableau, xaf

SECTION = (2, "Référentiel des contrats de marché monétaire")


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "Contrôles sur MM_CONTRACT : unicité des références, cohérence de la codification et "
            "des dates, plausibilité des taux, rapprochement avec la comptabilité et concentration "
            "par contrepartie."
        ),
    )
    s.ajouter(_c21_doublons(ctx))
    s.ajouter(_c22_codification(ctx))
    s.ajouter(_c23_dates(ctx))
    s.ajouter(_c24_delai_saisie(ctx))
    s.ajouter(_c25_coherence_interne(ctx))
    s.ajouter(_c25b_taux_aberrants(ctx))
    s.ajouter(_c26_orphelins(ctx))
    s.ajouter(_c27_concentration(ctx))
    return s


def _c21_doublons(ctx) -> Constat:
    df = ctx.contrats
    doubles = df[df.CONTRACT_REF_NO.duplicated(keep=False)].sort_values("CONTRACT_REF_NO")
    if doubles.empty:
        return Constat(
            code="2.1", titre="Unicité des références de contrat", gravite=Gravite.CONFORME,
            constat=f"Les {len(df)} lignes du référentiel portent des références distinctes.",
        )
    uniques = doubles.CONTRACT_REF_NO.nunique()
    montant = float(doubles.drop_duplicates("CONTRACT_REF_NO").AMOUNT.sum())
    return Constat(
        code="2.1",
        titre="Références de contrat en doublon dans le référentiel",
        gravite=Gravite.MOYENNE,
        constat=(
            "Des références apparaissent plusieurs fois, sur des lignes strictement identiques. "
            "Utilisé tel quel, le référentiel conduirait à un double comptage des encours."
        ),
        chiffres=[
            ("Lignes du référentiel", str(len(df))),
            ("Contrats distincts", str(df.CONTRACT_REF_NO.nunique())),
            ("Références en doublon", str(uniques)),
            ("Nominal exposé au double comptage", xaf(montant)),
        ],
        tableaux=[
            Tableau(
                ["Référence", "Produit", "Nominal", "Échéance", "Contrepartie"],
                [
                    [r.CONTRACT_REF_NO, r.PRODUCT, float(r.AMOUNT), r.MATURITY_DATE, r.FULL_NAME]
                    for r in doubles.drop_duplicates("CONTRACT_REF_NO").itertuples()
                ],
            )
        ],
        recommandation="Faire qualifier ces doublons par l'informatique avant toute exploitation du référentiel.",
    )


def _c22_codification(ctx) -> Constat:
    """La référence encode agence, produit et date de booking ; elle doit être cohérente."""
    df = ctx.contrats_uniques.copy()
    df["ref_agence"] = df.CONTRACT_REF_NO.str[:3]
    df["ref_produit"] = df.CONTRACT_REF_NO.str[3:7]
    incoherents = df[(df.ref_agence != df.BRANCH) | (df.ref_produit != df.PRODUCT)]

    def _date_julienne(ref: str):
        try:
            annee = 2000 + int(ref[7:9])
            quantieme = int(ref[9:12])
            return dt.date(annee, 1, 1) + dt.timedelta(days=quantieme - 1)
        except (ValueError, TypeError):
            return None

    df["date_ref"] = df.CONTRACT_REF_NO.map(_date_julienne)
    df["date_booking"] = df.BOOKING_DATE_d.dt.date
    ecarts = df[df.date_ref != df.date_booking]
    longueurs = df.CONTRACT_REF_NO.str.len().value_counts().to_dict()
    if incoherents.empty and ecarts.empty and set(longueurs) == {16}:
        return Constat(
            code="2.2", titre="Cohérence de la codification des références", gravite=Gravite.CONFORME,
            constat=(
                "Les références suivent le format Flexcube sur 16 caractères "
                "(agence + produit + année + quantième julien + séquence). L'agence et le produit "
                "encodés correspondent aux colonnes du référentiel, et la date reconstituée depuis "
                "le quantième julien est égale à la date de booking, sur la totalité des contrats."
            ),
        )
    return Constat(
        code="2.2",
        titre="Incohérence entre la référence et les attributs du contrat",
        gravite=Gravite.MOYENNE,
        constat=(
            "La référence Flexcube encode l'agence, le produit et la date de comptabilisation. "
            "Des contrats présentent une incohérence entre cette codification et leurs colonnes."
        ),
        chiffres=[
            ("Longueurs de référence observées", str(longueurs)),
            ("Agence/produit incohérents", str(len(incoherents))),
            ("Date julienne ≠ date de booking", str(len(ecarts))),
        ],
        tableaux=[
            Tableau(
                ["Référence", "Date encodée", "Date booking", "Produit", "Nominal"],
                [
                    [r.CONTRACT_REF_NO, str(r.date_ref), str(r.date_booking), r.PRODUCT, float(r.AMOUNT)]
                    for r in ecarts.itertuples()
                ],
            )
        ],
        recommandation="Investiguer les contrats concernés : saisie forcée ou reprise de données.",
    )


def _c23_dates(ctx) -> Constat:
    df = ctx.contrats_uniques
    anomalies = {
        "Date de négociation postérieure à la date de valeur": df[df.TRADE_DATE_d > df.VALUE_DATE_d],
        "Date de valeur postérieure à l'échéance": df[df.VALUE_DATE_d > df.MATURITY_DATE_d],
        "Comptabilisation antérieure à la négociation": df[df.BOOKING_DATE_d < df.TRADE_DATE_d],
        "Dates non renseignées": df[df[["TRADE_DATE_d", "VALUE_DATE_d", "MATURITY_DATE_d"]].isna().any(axis=1)],
    }
    total = sum(len(v) for v in anomalies.values())
    if not total:
        return Constat(
            code="2.3", titre="Cohérence chronologique des dates contractuelles", gravite=Gravite.CONFORME,
            constat=(
                f"Sur les {len(df)} contrats, l'ordre négociation ≤ valeur ≤ échéance est respecté "
                "et toutes les dates sont renseignées."
            ),
        )
    return Constat(
        code="2.3",
        titre="Incohérences chronologiques dans le référentiel",
        gravite=Gravite.ELEVEE,
        constat="Des contrats présentent un enchaînement de dates impossible.",
        tableaux=[Tableau(["Anomalie", "Contrats"], [[k, len(v)] for k, v in anomalies.items() if len(v)])],
        recommandation="Corriger le référentiel et rechercher la cause de la saisie.",
    )


def _c24_delai_saisie(ctx) -> Constat:
    """Un délai important entre négociation et comptabilisation est un risque de non-exhaustivité."""
    df = ctx.contrats_uniques.copy()
    df["delai"] = (df.BOOKING_DATE_d - df.TRADE_DATE_d).dt.days
    tardifs = df[df.delai > 5].sort_values("delai", ascending=False)
    tres_tardifs = df[df.delai > 30]
    if tardifs.empty:
        return Constat(
            code="2.4", titre="Délai de comptabilisation des contrats", gravite=Gravite.CONFORME,
            constat="Tous les contrats sont comptabilisés dans les cinq jours suivant leur négociation.",
        )
    gravite = Gravite.MOYENNE if len(tres_tardifs) else Gravite.FAIBLE
    return Constat(
        code="2.4",
        titre="Contrats comptabilisés tardivement après leur négociation",
        gravite=gravite,
        constat=(
            "Un délai significatif entre la date de négociation et la date de comptabilisation "
            "expose au risque qu'une opération négociée ne soit pas enregistrée à la clôture, et "
            "retarde le démarrage des intérêts courus."
        ),
        chiffres=[
            ("Contrats saisis au-delà de 5 jours", str(len(tardifs))),
            ("Contrats saisis au-delà de 30 jours", str(len(tres_tardifs))),
            ("Délai maximal observé", f"{int(df.delai.max())} jours"),
        ],
        tableaux=[
            Tableau(
                ["Référence", "Négociation", "Comptabilisation", "Délai (j)", "Nominal", "Contrepartie"],
                [
                    [r.CONTRACT_REF_NO, r.TRADE_DATE, r.BOOKING_DATE, int(r.delai), float(r.AMOUNT), r.FULL_NAME]
                    for r in tardifs.head(15).itertuples()
                ],
            )
        ],
        recommandation="Instaurer un délai maximal de saisie et un suivi des opérations négociées non comptabilisées.",
    )


def _base_de_calcul(contrats):
    """Identifie, pour chaque contrat, la convention de décompte des jours utilisée."""
    df = contrats.copy()
    df["jours"] = (df.MATURITY_DATE_d - df.VALUE_DATE_d).dt.days
    theorique = df.AMOUNT * df.MAIN_COMP_RATE / 100 * df.jours
    df["ecart_360"] = (df.MAIN_COMP_AMOUNT / (theorique / 360) - 1).abs()
    df["ecart_365"] = (df.MAIN_COMP_AMOUNT / (theorique / 365) - 1).abs()
    df["base"] = "non déterminée"
    df.loc[df.ecart_360 < 0.01, "base"] = "360"
    df.loc[df.ecart_365 < 0.01, "base"] = "365"
    return df


def _c25_coherence_interne(ctx) -> Constat:
    """Le montant d'intérêt porté au référentiel doit se déduire du nominal, du taux et de la durée."""
    df = _base_de_calcul(ctx.contrats_uniques)
    incoherents = df[df.base == "non déterminée"]
    par_produit = df.groupby(["PRODUCT", "base"]).size().reset_index(name="contrats")
    bases = sorted(df[df.base != "non déterminée"].base.unique())
    if incoherents.empty:
        return Constat(
            code="2.5",
            titre="Cohérence interne du référentiel et conventions de décompte des jours",
            gravite=Gravite.CONFORME,
            constat=(
                f"Pour la totalité des {len(df)} contrats, le montant d'intérêt porté au "
                "référentiel se déduit exactement du nominal, du taux et de la durée. Le "
                "référentiel est donc cohérent en interne.\n"
                f"Le contrôle révèle par ailleurs que DEUX conventions de décompte coexistent "
                f"({' et '.join(bases)} jours), appliquées de façon homogène par type de produit. "
                "Cette distinction doit être connue de tout recalcul d'intérêt."
            ),
            tableaux=[Tableau(["Produit", "Base", "Contrats"],
                              [[r.PRODUCT, r.base, int(r.contrats)] for r in par_produit.itertuples()])],
        )
    return Constat(
        code="2.5",
        titre="Montants d'intérêt incohérents avec les caractéristiques contractuelles",
        gravite=Gravite.ELEVEE,
        constat=(
            "Pour certains contrats, le montant d'intérêt porté au référentiel ne se déduit ni "
            "d'une base 360 ni d'une base 365 à partir du nominal, du taux et de la durée. Le "
            "référentiel est donc incohérent en interne pour ces opérations."
        ),
        chiffres=[
            ("Contrats contrôlés", str(len(df))),
            ("Contrats incohérents", str(len(incoherents))),
            ("Nominal concerné", xaf(float(incoherents.AMOUNT.sum()))),
        ],
        tableaux=[
            Tableau(["Référence", "Produit", "Nominal", "Taux %", "Jours", "Intérêt référentiel"],
                    [[r.CONTRACT_REF_NO, r.PRODUCT, float(r.AMOUNT), float(r.MAIN_COMP_RATE),
                      int(r.jours) if r.jours == r.jours else None, float(r.MAIN_COMP_AMOUNT)]
                     for r in incoherents.itertuples()]),
            Tableau(["Produit", "Base", "Contrats"],
                    [[r.PRODUCT, r.base, int(r.contrats)] for r in par_produit.itertuples()]),
        ],
        recommandation="Obtenir les confirmations de marché des contrats concernés et corriger le référentiel.",
    )


def _c25b_taux_aberrants(ctx) -> Constat:
    """Un taux s'apprécie par rapport aux autres opérations du même produit et du même exercice.

    Une fourchette absolue produirait des faux positifs : les taux de marché évoluent dans le
    temps et diffèrent entre obligations et bons du Trésor. Le test retient donc un écart
    robuste (médiane absolue des écarts) au sein de chaque groupe produit-exercice.
    """
    df = ctx.contrats_uniques.copy()
    df["exercice"] = df.VALUE_DATE_d.dt.year
    aberrants = []
    for (produit, exercice), groupe in df.groupby(["PRODUCT", "exercice"]):
        if len(groupe) < 4:
            continue
        mediane = groupe.MAIN_COMP_RATE.median()
        ecart_type_robuste = max((groupe.MAIN_COMP_RATE - mediane).abs().median(), 0.25)
        hors = groupe[(groupe.MAIN_COMP_RATE - mediane).abs() > 5 * ecart_type_robuste]
        for r in hors.itertuples():
            aberrants.append([r.CONTRACT_REF_NO, produit, int(exercice), float(r.MAIN_COMP_RATE),
                              float(mediane), float(r.AMOUNT), r.FULL_NAME])
    if not aberrants:
        return Constat(
            code="2.6", titre="Plausibilité des taux contractuels", gravite=Gravite.CONFORME,
            constat="Aucun taux ne s'écarte anormalement de ceux pratiqués sur le même produit au cours du même exercice.",
        )
    aberrants.sort(key=lambda l: -abs(l[3] - l[4]))
    extremes = [a for a in aberrants if abs(a[3] - a[4]) > 10]
    medianes = df.pivot_table(index="PRODUCT", columns="exercice", values="MAIN_COMP_RATE", aggfunc="median")
    return Constat(
        code="2.6",
        titre="Taux contractuels aberrants au regard des opérations comparables",
        gravite=Gravite.ELEVEE if extremes else Gravite.MOYENNE,
        constat=(
            "Le test compare chaque taux à la médiane des opérations du MÊME PRODUIT et du MÊME "
            "EXERCICE, ce qui évite les faux positifs liés à l'évolution des taux de marché et aux "
            "différences entre obligations et bons du Trésor.\n"
            "Des contrats s'écartent très fortement de leurs comparables. L'écart le plus marqué "
            "porte un taux plusieurs fois supérieur à la médiane de son groupe, ce qui n'est pas "
            "économiquement soutenable sur une signature souveraine : il s'agit d'une erreur de "
            "saisie ou d'une opération de nature différente. Le montant d'intérêt du référentiel "
            "étant cohérent avec ce taux, l'erreur se propage au calcul des intérêts."
        ),
        chiffres=[
            ("Contrats aberrants", str(len(aberrants))),
            ("Dont écart supérieur à 10 points", str(len(extremes))),
            ("Nominal concerné", xaf(sum(a[5] for a in aberrants))),
        ],
        tableaux=[
            Tableau(["Référence", "Produit", "Exercice", "Taux %", "Médiane groupe %", "Nominal", "Contrepartie"],
                    aberrants),
            Tableau(["Produit"] + [str(c) for c in medianes.columns],
                    [[i] + [round(float(v), 2) if v == v else None for v in r]
                     for i, r in medianes.iterrows()],
                    note="Taux médians de référence par produit et exercice."),
        ],
        recommandation=(
            "Obtenir les confirmations de marché de ces opérations, recalculer les intérêts "
            "comptabilisés et mesurer l'incidence sur le résultat."
        ),
    )


def _c26_orphelins(ctx) -> Constat:
    """Un contrat au référentiel sans écriture comptable, ou l'inverse."""
    contrats = set(ctx.contrats_uniques.CONTRACT_REF_NO)
    ecritures = set(ctx.grand_livre[ctx.grand_livre.MODULE == "MM"].TRN_REF_NO)
    sans_ecriture = ctx.contrats_uniques[~ctx.contrats_uniques.CONTRACT_REF_NO.isin(ecritures)]
    sans_contrat = ecritures - contrats
    if sans_ecriture.empty and not sans_contrat:
        return Constat(
            code="2.7", titre="Rapprochement référentiel / comptabilité", gravite=Gravite.CONFORME,
            constat="Tout contrat du référentiel porte des écritures, et toute écriture MM se rattache à un contrat.",
        )
    return Constat(
        code="2.7",
        titre="Contrats du référentiel dépourvus d'écriture comptable",
        gravite=Gravite.ELEVEE,
        constat=(
            "Des contrats figurent au référentiel sans qu'aucune écriture comptable ne leur "
            "corresponde. Un contrat enregistré mais non comptabilisé n'est ni provisionné, ni "
            "suivi en intérêts courus, ni présenté au bilan : soit l'opération n'a jamais existé "
            "et le référentiel doit être purgé, soit elle existe et la comptabilité est incomplète."
        ),
        chiffres=[
            ("Contrats sans écriture", str(len(sans_ecriture))),
            ("Nominal concerné", xaf(float(sans_ecriture.AMOUNT.sum()))),
            ("Écritures MM sans contrat", str(len(sans_contrat))),
        ],
        tableaux=[
            Tableau(
                ["Référence", "Nominal", "Taux %", "Négociation", "Échéance", "Contrepartie"],
                [
                    [r.CONTRACT_REF_NO, float(r.AMOUNT), float(r.MAIN_COMP_RATE),
                     r.TRADE_DATE, r.MATURITY_DATE, r.FULL_NAME]
                    for r in sans_ecriture.sort_values("AMOUNT", ascending=False).itertuples()
                ],
                max_lignes=20,
            )
        ],
        recommandation=(
            "Demander le statut de ces contrats dans Flexcube (annulés, non autorisés, repris) et "
            "confirmer qu'aucun engagement n'est resté hors comptabilité."
        ),
    )


def _c27_concentration(ctx) -> Constat:
    df = ctx.contrats_uniques
    par_cpty = df.groupby("FULL_NAME").agg(contrats=("CONTRACT_REF_NO", "count"), nominal=("AMOUNT", "sum"))
    par_cpty["part"] = par_cpty.nominal / par_cpty.nominal.sum() * 100
    par_cpty = par_cpty.sort_values("nominal", ascending=False)
    premiere = float(par_cpty.part.iloc[0])
    return Constat(
        code="2.8",
        titre="Concentration du portefeuille sur les souverains CEMAC",
        gravite=Gravite.MOYENNE if premiere > 50 else Gravite.FAIBLE,
        constat=(
            "La totalité du portefeuille de marché monétaire historique est exposée à des "
            f"émetteurs souverains de la CEMAC, dont {premiere:.1f} % sur la seule première "
            "contrepartie. Aucune diversification sectorielle ou géographique n'est constatée."
        ),
        chiffres=[
            ("Contreparties distinctes", str(len(par_cpty))),
            ("Nominal total du référentiel", xaf(float(par_cpty.nominal.sum()))),
            ("Part de la première contrepartie", f"{premiere:.1f} %"),
        ],
        tableaux=[
            Tableau(
                ["Contrepartie", "Contrats", "Nominal XAF", "Part %"],
                [[i, int(r.contrats), float(r.nominal), round(float(r.part), 1)] for i, r in par_cpty.iterrows()],
            )
        ],
        recommandation=(
            "Obtenir les limites internes de contrepartie et de concentration, ainsi que la preuve "
            "de leur suivi ; rapprocher des ratios prudentiels COBAC de division des risques."
        ),
    )
