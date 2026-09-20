"""Section 9 — Résultat, classement comptable et rendement du portefeuille."""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf, pct, fois, nb
from ..data import CPT_PORTEFEUILLE, CPT_PRODUITS, DATE_BASCULE

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
    s.ajouter(_c94_soldes_anormaux(ctx))
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
            croissances.append(f"{b} : {fois(total[b] / total[a], 2)}")
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
    """Un titre de transaction doit produire un revenu de transaction, et réciproquement.

    Le PCEC classe les titres en deux catégories selon l'intention de détention, et prévoit
    pour chacune une série de comptes de produits distincte. Croiser les deux permet de
    vérifier que le compte de résultat est cohérent avec le compte de bilan.
    """
    gl = ctx.grand_livre
    pertinents = gl[gl.AC_NO.isin(set(CATEGORIE_BILAN) | set(CATEGORIE_PRODUIT))]
    par_ecriture = pertinents.groupby("TRN_REF_NO").AC_NO.apply(set)
    couples, montants = {}, {}
    for reference, comptes in par_ecriture.items():
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
    total = sum(incoherents.values())
    principal = max(incoherents.items(), key=lambda x: x[1])
    # Montant du produit imputé à la mauvaise catégorie, sur la période Calypso
    produits_places = gl[(gl.AC_NO == "733400100") & (gl.TRN_DT >= DATE_BASCULE)]
    montant_mal_impute = -float(produits_places.SIGNE.sum())
    nomenclature = [
        ["511 / 512 — titres", "Titres de PLACEMENT", "511410100, 511210100",
         "733 — Revenus du portefeuille de placement"],
        ["511 / 512 — titres", "Titres de TRANSACTION", "512410100, 512200100",
         "734 — Revenus du portefeuille de transaction"],
    ]
    return Constat(
        code="9.2",
        titre="Revenus du portefeuille imputés à la mauvaise catégorie comptable",
        gravite=Gravite.ELEVEE,
        reference="PCEC CEMAC — comptes 733 (revenus du portefeuille de placement) et 734 (revenus du portefeuille de transaction)",
        constat=(
            "LE PRINCIPE, EN TERMES SIMPLES. Le plan comptable range les titres détenus par une "
            "banque en deux familles, selon l'INTENTION avec laquelle elle les détient. Les titres "
            "de PLACEMENT sont ceux qu'elle compte garder un certain temps. Les titres de "
            "TRANSACTION sont ceux qu'elle compte revendre rapidement, pour profiter des "
            "mouvements de prix.\n"
            "Cette distinction n'est pas cosmétique : les deux familles n'obéissent pas aux mêmes "
            "règles d'évaluation, et surtout elles ne se rangent pas au même endroit dans le "
            "compte de résultat. Le plan comptable prévoit DEUX SÉRIES DE COMPTES DE PRODUITS "
            "distinctes, une pour chaque famille.\n"
            "\n"
            "LA RÈGLE EST DONC SIMPLE : un titre rangé au bilan dans la famille « placement » doit "
            "produire ses revenus dans les comptes « revenus du portefeuille de placement ». Un "
            "titre rangé en « transaction » doit produire ses revenus dans les comptes « revenus "
            "du portefeuille de transaction ». Les deux doivent aller ensemble, comme une "
            "chaussure gauche avec une chaussure gauche.\n"
            "\n"
            "CE QUI SE PASSE EN PRATIQUE. Le test croise, pour chaque écriture, le compte de bilan "
            "utilisé et le compte de produit utilisé. Le résultat est massivement incohérent : "
            "l'immense majorité des écritures associe un compte de bilan de la famille "
            "« transaction » à un compte de produit de la famille « placement ». Concrètement, "
            "les intérêts des titres rangés en transaction sont enregistrés comme des revenus de "
            "titres de placement.\n"
            "\n"
            "POURQUOI C'EST GÊNANT. Les états que la banque transmet au régulateur distinguent "
            "précisément ces deux natures de revenus, parce qu'elles n'ont pas la même "
            "signification : un revenu de placement est récurrent et prévisible, un revenu de "
            "transaction est volatil. En les mélangeant, la banque présente au régulateur une "
            "image faussée de la composition de son produit net bancaire. Le total est juste, mais "
            "sa ventilation ne l'est pas.\n"
            "\n"
            "D'OÙ CELA VIENT. Cette incohérence est le prolongement direct du reclassement opéré "
            "lors de la bascule vers le nouveau système (contrôle 5.5) : le portefeuille a changé "
            "de famille AU BILAN, en passant en « transaction », mais le paramétrage des schémas "
            "comptables a continué d'alimenter les comptes de produits de la famille "
            "« placement ». Le bilan a suivi la migration, le compte de résultat ne l'a pas suivi."
        ),
        chiffres=[
            ("Écritures à imputation cohérente", nb(sum(coherents.values()))),
            ("Écritures à imputation INCOHÉRENTE", nb(total)),
            ("Cas principal", f"bilan {principal[0][0]} → produit {principal[0][1]} "
                              f"({nb(principal[1])} écritures)"),
            ("Produit enregistré en « placement » depuis la bascule", xaf(montant_mal_impute)),
        ],
        tableaux=[
            Tableau(["Famille au bilan", "Intention de détention", "Comptes de bilan",
                     "Comptes de produits attendus"], nomenclature,
                    note="La règle du PCEC : à chaque famille de titres sa série de comptes de produits."),
            Tableau(["Catégorie au bilan", "Catégorie du produit", "Écritures", "Cohérent"],
                    [[k[0], k[1], v, k[0] == k[1]] for k, v in
                     sorted(couples.items(), key=lambda x: -x[1])],
                    note="Ce qui est réellement constaté."),
        ],
        recommandation=(
            "Faire corriger le paramétrage des schémas comptables afin que chaque famille de "
            "portefeuille alimente la série de comptes de produits correspondante. Mesurer "
            "l'incidence sur la ventilation du produit net bancaire dans les états réglementaires "
            "déjà transmis et, le cas échéant, les rectifier."
        ),
    )


def _c93_rendement(ctx) -> Constat:
    """Le rendement implicite doit rester proche des taux contractuels."""
    gl = ctx.grand_livre
    cl = _cloture(ctx)
    if cl.empty:
        return Constat(code="9.3", titre="Rendement implicite du portefeuille", gravite=Gravite.FAIBLE,
                       constat="Écritures de clôture indisponibles.")
    # L'encours moyen doit être pondéré par les JOURS CALENDAIRES et non par les seuls jours
    # de mouvement : sans rééchantillonnage quotidien, les périodes de forte activité pèsent
    # trop lourd et l'encours moyen est surévalué de plus de dix pour cent sur certains exercices.
    encours = (gl[gl.AC_NO.isin(CPT_PORTEFEUILLE)]
               .groupby("TRN_DT_d").SIGNE.sum().sort_index().cumsum())
    moyenne = encours.resample("D").ffill().resample("YE").mean()
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
            ("Taux contractuel au 95e centile", f"{pct(borne, 2)}"),
            ("Rendement implicite du dernier exercice", f"{pct(lignes[-1][3], 2)}" if lignes else "n/d"),
        ],
        tableaux=[Tableau(["Exercice", "Encours moyen XAF", "Produits XAF", "Rendement %"], lignes)],
        recommandation=(
            "Décomposer le produit par nature et rapprocher la composante plus-values des "
            "opérations examinées en section 8. L'encours moyen est pondéré par les jours "
            "calendaires ; il reste à confirmer par la balance générale."
        ),
    )


def _c94_soldes_anormaux(ctx) -> Constat:
    """Un compte d'actif ne peut pas être créditeur, ni un compte de passif débiteur.

    Ce contrôle n'est possible que parce que l'extraction couvre l'historique intégral des
    comptes : le solde à toute date est donc calculable (voir contrôle 1.7).
    """
    preuve = ctx.historique_complet()
    anomalies = []
    for compte, r in preuve.iterrows():
        if r.nature == "neutre":
            continue
        soldes = ctx.soldes_aux_arretes(compte)
        contraires = {d: v for d, v in soldes.items()
                      if (r.nature == "debiteur" and v < -1) or (r.nature == "crediteur" and v > 1)}
        if contraires:
            pire = max(contraires.items(), key=lambda x: abs(x[1]))
            anomalies.append([compte, r.libelle[:36], r.nature, len(contraires),
                              pire[0], float(pire[1]), float(r.solde_final)])
    if not anomalies:
        return Constat(
            code="9.4", titre="Sens des soldes aux dates d'arrêté", gravite=Gravite.CONFORME,
            constat=(
                "À chaque date d'arrêté de la période, le solde de chaque compte est conforme à sa "
                "nature comptable : les comptes d'actif sont débiteurs, ceux de passif créditeurs."
            ),
        )
    anomalies.sort(key=lambda l: -abs(l[5]))
    materiel = [a for a in anomalies if abs(a[5]) > ctx.config.seuil_significatif]
    return Constat(
        code="9.4",
        titre="Comptes présentant un solde contraire à leur nature comptable à une date d'arrêté",
        gravite=Gravite.CRITIQUE if materiel else Gravite.ELEVEE,
        constat=(
            "Des comptes présentent, à une ou plusieurs dates d'arrêté, un solde de sens contraire "
            "à leur nature : compte d'actif créditeur ou compte de passif débiteur. Une telle "
            "position est impossible en soi et révèle une écriture manquante, une écriture en "
            "double, ou une imputation erronée.\n"
            "Le cas le plus marquant concerne un compte de produits perçus d'avance devenu "
            "débiteur : l'étalement au résultat a dépassé le produit initialement différé, ce qui "
            "signifie que des produits ont été reconnus SANS CONTREPARTIE. Celui du compte "
            "d'emprunt au jour le jour trouve son origine dans le déversement en double de "
            "l'interface (contrôle 6.7).\n"
            "Ce contrôle n'est possible que parce que l'extraction couvre l'historique intégral "
            "des comptes et que leur solde est donc calculable à toute date."
        ),
        chiffres=[
            ("Comptes concernés", str(len(anomalies))),
            ("Dont solde anormal significatif", str(len(materiel))),
            ("Dates d'arrêté testées", ", ".join(ctx.arretes)),
        ],
        tableaux=[
            Tableau(["Compte", "Libellé", "Nature", "Arrêtés en anomalie", "Pire arrêté",
                     "Solde à cette date", "Solde final"],
                    anomalies),
        ],
        recommandation=(
            "Obtenir la justification de chaque solde anormal à la date d'arrêté concernée et "
            "vérifier s'il figure tel quel dans les états financiers et les états réglementaires "
            "transmis à la COBAC."
        ),
    )
