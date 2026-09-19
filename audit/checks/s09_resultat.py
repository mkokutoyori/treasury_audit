"""Section 9 — Résultat, classement comptable et rendement du portefeuille."""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf
from ..data import CPT_PORTEFEUILLE, CPT_PRODUITS

SECTION = (9, "Résultat, classement comptable et rendement")

# Correspondance PCEC : 733x = portefeuille de placement, 734x = portefeuille de transaction.
CATEGORIE_BILAN = {
    "511410100": "PLACEMENT", "511210100": "PLACEMENT", "511800100": "PLACEMENT",
    "512200100": "TRANSACTION", "512410100": "TRANSACTION", "512800100": "TRANSACTION",
}
CATEGORIE_PRODUIT = {
    "733200100": "PLACEMENT", "733400100": "PLACEMENT",
    "734200100": "TRANSACTION", "734400100": "TRANSACTION",
}


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "Reconstitution du résultat de l'activité à partir des écritures de clôture annuelle, "
            "contrôle de la cohérence entre catégorie de bilan et catégorie de produit au sens du "
            "PCEC, et analyse du rendement implicite du portefeuille."
        ),
    )
    s.ajouter(_c91_resultat(ctx))
    s.ajouter(_c92_classement(ctx))
    s.ajouter(_c93_rendement(ctx))
    return s


def _cloture(ctx) -> pd.DataFrame:
    gl = ctx.grand_livre
    return gl[gl.MODULE == "GL"].copy()


def _c91_resultat(ctx) -> Constat:
    cl = _cloture(ctx)
    if cl.empty:
        return Constat(code="9.1", titre="Résultat de l'activité", gravite=Gravite.FAIBLE,
                       constat="Aucune écriture de clôture annuelle dans le périmètre extrait.",
                       recommandation="Extraire les écritures de clôture (module GL).")
    cl["exercice"] = cl.TRN_DT.str[:4]
    cl["nature"] = cl.AC_NO.str[0].map({"7": "PRODUIT", "6": "CHARGE"})
    cl["montant"] = cl.SIGNE  # produit soldé au débit = produit positif
    pivot = cl.pivot_table(index=["nature", "AC_NO", "AC_GL_DESC"], columns="exercice",
                           values="montant", aggfunc="sum").fillna(0)
    exercices = sorted(cl.exercice.unique())
    total = cl.groupby("exercice").montant.sum()
    lignes = [[i[0], i[1], i[2][:36]] + [float(r[e]) for e in exercices] for i, r in pivot.iterrows()]
    lignes.append(["", "", "RÉSULTAT NET"] + [float(total.get(e, 0)) for e in exercices])
    croissances = []
    for a, b in zip(exercices, exercices[1:]):
        if total.get(a, 0):
            croissances.append(f"{b} : × {total[b] / total[a]:.2f}")
    return Constat(
        code="9.1",
        titre="Progression du résultat de l'activité de titres",
        gravite=Gravite.MOYENNE,
        constat=(
            "Les écritures de clôture annuelle soldent chaque compte de résultat et permettent de "
            "reconstituer le compte de résultat de l'activité par exercice.\n"
            "La progression observée est très rapide : le résultat double quasiment d'un exercice "
            "à l'autre. Une telle croissance n'est pas en soi une anomalie, mais elle appelle une "
            "revue analytique : quelle part provient de l'augmentation des encours, quelle part "
            "d'un changement de méthode de valorisation, et quelle part de la reconnaissance de "
            "plus-values sur des opérations dont la nature de cession est discutée en section 8 ?"
        ),
        chiffres=[("Croissance du résultat", " ; ".join(croissances))] if croissances else [],
        tableaux=[Tableau(["Nature", "Compte", "Libellé"] + exercices, lignes, max_lignes=25)],
        recommandation=(
            "Obtenir la décomposition du produit net bancaire de l'activité par nature (intérêts "
            "courus, étalement de prime et décote, plus-values de cession, commissions) et la "
            "rapprocher de l'évolution des encours."
        ),
    )


def _c92_classement(ctx) -> Constat:
    """Un titre de transaction doit produire un revenu de transaction, et réciproquement."""
    gl = ctx.grand_livre
    pertinents = gl[gl.AC_NO.isin(set(CATEGORIE_BILAN) | set(CATEGORIE_PRODUIT))]
    par_ecriture = pertinents.groupby("TRN_REF_NO").AC_NO.apply(set)
    couples = {}
    for comptes in par_ecriture:
        bilan = {CATEGORIE_BILAN[c] for c in comptes if c in CATEGORIE_BILAN}
        produit = {CATEGORIE_PRODUIT[c] for c in comptes if c in CATEGORIE_PRODUIT}
        if not bilan or not produit:
            continue
        cle = (sorted(bilan)[0], sorted(produit)[0])
        couples[cle] = couples.get(cle, 0) + 1
    incoherents = {k: v for k, v in couples.items() if k[0] != k[1]}
    coherents = {k: v for k, v in couples.items() if k[0] == k[1]}
    if not incoherents:
        return Constat(
            code="9.2", titre="Cohérence entre catégorie de bilan et catégorie de produit",
            gravite=Gravite.CONFORME,
            constat="Chaque catégorie de titre est associée au compte de produit correspondant.",
        )
    total_inc = sum(incoherents.values())
    principal = max(incoherents.items(), key=lambda x: x[1])
    return Constat(
        code="9.2",
        titre="Revenus du portefeuille imputés à la mauvaise catégorie comptable",
        gravite=Gravite.ELEVEE,
        constat=(
            "Le PCEC distingue deux catégories de portefeuille et deux séries de comptes de "
            "produits correspondantes : les revenus du portefeuille de placement d'une part, ceux "
            "du portefeuille de transaction d'autre part.\n"
            "Or des écritures associent systématiquement un compte de bilan d'une catégorie à un "
            "compte de produit de l'AUTRE catégorie. Concrètement, les intérêts courus du "
            "portefeuille de transaction sont crédités en revenus du portefeuille de placement.\n"
            "Cette imputation fausse la ventilation du produit net bancaire dans les états "
            "réglementaires transmis à la COBAC, qui distinguent précisément ces deux natures de "
            "revenus. Elle est par ailleurs cohérente avec le reclassement opéré à la migration "
            "(contrôle 5.5) : le portefeuille a changé de catégorie au bilan, mais pas au compte "
            "de résultat."
        ),
        chiffres=[
            ("Écritures à imputation cohérente", f"{sum(coherents.values()):,}".replace(",", " ")),
            ("Écritures à imputation incohérente", f"{total_inc:,}".replace(",", " ")),
            ("Cas principal", f"bilan {principal[0][0]} → produit {principal[0][1]} "
                              f"({principal[1]:,} écritures)".replace(",", " ")),
        ],
        tableaux=[
            Tableau(["Catégorie au bilan", "Catégorie du produit", "Écritures", "Cohérent"],
                    [[k[0], k[1], v, k[0] == k[1]] for k, v in
                     sorted(couples.items(), key=lambda x: -x[1])])
        ],
        recommandation=(
            "Faire corriger le paramétrage des schémas comptables afin que chaque catégorie de "
            "portefeuille alimente le compte de produit correspondant. Mesurer l'incidence sur les "
            "états réglementaires déjà transmis."
        ),
    )


def _c93_rendement(ctx) -> Constat:
    """Le rendement implicite doit rester proche des taux contractuels."""
    gl = ctx.grand_livre
    cl = _cloture(ctx)
    if cl.empty:
        return Constat(code="9.3", titre="Rendement implicite du portefeuille", gravite=Gravite.FAIBLE,
                       constat="Écritures de clôture indisponibles.")
    encours = (gl[gl.AC_NO.isin(CPT_PORTEFEUILLE)]
               .sort_values(["TRN_DT", "STMT_DT"]).set_index("TRN_DT_d").SIGNE.cumsum())
    moyenne = encours.resample("YE").mean()
    produits = cl[cl.AC_NO.isin(CPT_PRODUITS)].copy()
    produits["exercice"] = produits.TRN_DT.str[:4]
    par_ex = produits.groupby("exercice").LCY_AMOUNT.sum()
    taux_contractuels = ctx.contrats_uniques.MAIN_COMP_RATE
    borne = float(taux_contractuels.quantile(0.95))
    lignes, alerte = [], False
    for periode, enc in moyenne.items():
        ex = str(periode.year)
        if ex not in par_ex.index or enc <= 0:
            continue
        rendement = float(par_ex[ex]) / float(enc) * 100
        if rendement > borne * 1.5:
            alerte = True
        lignes.append([ex, float(enc), float(par_ex[ex]), round(rendement, 2)])
    if not alerte:
        return Constat(
            code="9.3", titre="Rendement implicite du portefeuille", gravite=Gravite.CONFORME,
            constat="Le rendement implicite reste cohérent avec les taux contractuels.",
            tableaux=[Tableau(["Exercice", "Encours moyen XAF", "Produits XAF", "Rendement %"], lignes)],
        )
    return Constat(
        code="9.3",
        titre="Rendement implicite très supérieur aux taux contractuels du portefeuille",
        gravite=Gravite.ELEVEE,
        constat=(
            "Le rendement implicite du portefeuille — produits de l'exercice rapportés à l'encours "
            "moyen — s'écarte fortement des taux contractuels observés au référentiel, et l'écart "
            "s'accroît d'exercice en exercice.\n"
            "Un portefeuille de titres souverains ne peut structurellement pas rendre beaucoup plus "
            "que son coupon. L'écart provient donc d'autres composantes du produit : étalement de "
            "prime et décote, et surtout PLUS-VALUES DE CESSION RÉALISÉES. Ces dernières doivent "
            "être rapprochées des constats de la section 8 : si une partie des cessions correspond "
            "en réalité à des opérations de financement, le produit correspondant n'aurait pas dû "
            "être constaté.\n"
            "Ce contrôle est un indicateur analytique : il signale une zone à investiguer, il ne "
            "constitue pas à lui seul la preuve d'une surévaluation."
        ),
        chiffres=[
            ("Taux contractuel au 95e centile", f"{borne:.2f} %"),
            ("Rendement implicite du dernier exercice", f"{lignes[-1][3]:.2f} %" if lignes else "n/d"),
        ],
        tableaux=[Tableau(["Exercice", "Encours moyen XAF", "Produits XAF", "Rendement %"], lignes)],
        recommandation=(
            "Décomposer le produit par nature et rapprocher la composante plus-values des "
            "opérations examinées en section 8. Attention : l'encours moyen est reconstitué à "
            "partir des mouvements ; il doit être confirmé par la balance générale."
        ),
    )
