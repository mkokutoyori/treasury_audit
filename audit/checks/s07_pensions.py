"""Section 7 — Opérations de pension livrée auprès de la banque centrale."""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf, pct
from ..data import CPT_COLLATERAL, CPT_REPO_CHARGE, CPT_REPO_DETTES, CPT_REPO_PASSIF

SECTION = (7, "Pensions livrées auprès de la banque centrale")


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "La banque se refinance auprès de la banque centrale par pensions livrées garanties "
            "par les titres du portefeuille. Cette section contrôle la durée réelle des opérations "
            "au regard du compte utilisé, le rattachement des charges d'intérêt, le niveau de "
            "collatéralisation et le dénouement des opérations."
        ),
    )
    s.ajouter(_c71_duree(ctx))
    s.ajouter(_c72_rattachement(ctx))
    s.ajouter(_c73_collateral(ctx))
    s.ajouter(_c74_non_denouees(ctx))
    return s


def _operations(ctx) -> pd.DataFrame:
    """Une ligne par opération : tirage, remboursement, durée.

    Les mouvements déversés en double par l'interface (contrôle 6.7) sont neutralisés :
    les conserver ferait apparaître des remboursements supérieurs aux tirages, c'est-à-dire
    des anomalies qui n'en sont pas et qui relèvent en réalité du défaut d'interface.
    """
    calypso = ctx.calypso_enrichi
    if calypso.empty:
        return pd.DataFrame()
    repo = calypso[calypso.AC_NO == CPT_REPO_PASSIF]
    if repo.empty:
        return pd.DataFrame()
    doublons = ctx.mouvements_dupliques
    if not doublons.empty:
        # Ne garder qu'une occurrence de chaque mouvement déversé plusieurs fois
        repo = repo.drop_duplicates(subset=["DEAL", "MOUVEMENT", "AC_NO", "DRCR_IND", "LCY_AMOUNT"])
    tirage = repo[repo.DRCR_IND == "C"].groupby("DEAL").agg(
        date_tirage=("TRN_DT", "min"), montant=("LCY_AMOUNT", "sum"), emetteur=("EMETTEUR", "first"))
    rembours = repo[repo.DRCR_IND == "D"].groupby("DEAL").agg(
        date_rembours=("TRN_DT", "max"), rembourse=("LCY_AMOUNT", "sum"))
    ops = tirage.join(rembours, how="outer")
    ops["duree"] = (pd.to_datetime(ops.date_rembours) - pd.to_datetime(ops.date_tirage)).dt.days
    return ops


def _c71_duree(ctx) -> Constat:
    ops = _operations(ctx)
    if ops.empty:
        return Constat(code="7.1", titre="Durée des pensions livrées", gravite=Gravite.FAIBLE,
                       constat="Aucune opération de pension identifiée dans le périmètre.")
    gl = ctx.grand_livre
    libelle = gl[gl.AC_NO == CPT_REPO_PASSIF].AC_GL_DESC.iloc[0] if len(gl[gl.AC_NO == CPT_REPO_PASSIF]) else ""
    longues = ops[ops.duree > 4].sort_values("duree", ascending=False)
    if longues.empty:
        return Constat(
            code="7.1", titre="Durée des pensions livrées", gravite=Gravite.CONFORME,
            constat="Toutes les opérations sont dénouées dans la semaine de leur tirage.",
        )
    return Constat(
        code="7.1",
        titre="Pensions de plusieurs semaines comptabilisées dans un compte d'emprunt au jour le jour",
        gravite=Gravite.ELEVEE,
        constat=(
            f"Les opérations sont comptabilisées au compte « {libelle} ». Or la durée effective "
            "observée entre le tirage et le remboursement dépasse largement le jour le jour pour "
            "une partie des opérations, l'une d'elles atteignant plusieurs mois.\n"
            "Un emprunt de cette durée logé dans un compte d'emprunt au jour le jour fausse "
            "l'échéancier de liquidité de l'établissement et, par voie de conséquence, les ratios "
            "prudentiels qui en découlent."
        ),
        chiffres=[
            ("Opérations identifiées", str(len(ops))),
            ("Opérations de plus de 4 jours", str(len(longues))),
            ("Montant tiré sur ces opérations", xaf(float(longues.montant.sum()))),
            ("Durée maximale observée", f"{int(ops.duree.max())} jours"),
            ("Durée médiane", f"{int(ops.duree.median())} jours"),
        ],
        tableaux=[
            Tableau(["Deal", "Tirage", "Remboursement", "Durée (j)", "Montant XAF", "Contrepartie"],
                    [[i, r.date_tirage, r.date_rembours, int(r.duree), float(r.montant), r.emetteur]
                     for i, r in longues.head(15).iterrows()]),
            Tableau(["Durée (jours)", "Opérations", "Montant tiré XAF"],
                    [[int(d), int(len(g)), float(g.montant.sum())]
                     for d, g in ops.dropna(subset=["duree"]).groupby("duree")],
                    max_lignes=20,
                    note=("Distribution des durées. La durée nulle — tirage et remboursement "
                          "comptabilisés le même jour — est le cas dominant et correspond bien à "
                          "un financement au jour le jour ; ce sont les durées supérieures à "
                          "quatre jours qui ne relèvent pas du compte utilisé.")),
        ],
        recommandation=(
            "Obtenir les conventions de pension livrée et leur durée contractuelle. Faire "
            "reclasser les opérations à terme dans le compte d'emprunt correspondant et corriger "
            "l'échéancier de liquidité."
        ),
    )


def _c72_rattachement(ctx) -> Constat:
    """Une charge d'intérêt doit courir chaque jour, pas seulement au dénouement."""
    calypso = ctx.calypso_enrichi
    if calypso.empty:
        return Constat(code="7.2", titre="Rattachement des charges d'intérêt", gravite=Gravite.FAIBLE,
                       constat="Données insuffisantes.")
    ops = _operations(ctx)
    charge = calypso[calypso.AC_NO == CPT_REPO_CHARGE]
    # Même neutralisation des doublons d'interface que pour les tirages (contrôle 6.7),
    # sans quoi l'intérêt d'une opération rejouée serait compté deux fois.
    charge = charge.drop_duplicates(subset=["DEAL", "MOUVEMENT", "AC_NO", "DRCR_IND", "LCY_AMOUNT"])
    courus = charge[charge.EVENEMENT == "ACCRUAL"]
    regles = charge[charge.EVENEMENT == "INTEREST"]
    jamais_de_couru = courus.empty
    # Pour les opérations longues, compare le nombre de jours de couru à la durée réelle
    longues = ops[ops.duree > 4]
    lignes = []
    for deal, r in longues.iterrows():
        jours_couru = courus[courus.DEAL == deal].TRN_DT.nunique()
        interet = float(regles[regles.DEAL == deal].LCY_AMOUNT.sum())
        lignes.append([deal, r.date_tirage, r.date_rembours, int(r.duree), jours_couru,
                       float(r.montant), interet])
    defaillants = [l for l in lignes if l[3] > 4 and l[4] <= 2]
    # Charge qui aurait dû être rattachée à un arrêté traversé : l'intérêt total de
    # l'opération, au prorata des jours écoulés entre le tirage et la date d'arrêté.
    manquant = []
    for l in defaillants:
        deal, tirage, rembours, duree, _, _, interet = l
        for arrete in ctx.arretes:
            if duree and str(tirage) <= arrete < str(rembours):
                jours = (pd.Timestamp(arrete) - pd.Timestamp(tirage)).days
                manquant.append([deal, arrete, jours, duree, interet * jours / duree])
    charge_non_rattachee = sum(m[4] for m in manquant)
    if not defaillants:
        return Constat(
            code="7.2", titre="Rattachement des charges d'intérêt des pensions", gravite=Gravite.CONFORME,
            constat="Les charges d'intérêt courent sur toute la durée des opérations.",
        )
    return Constat(
        code="7.2",
        titre="Charges d'intérêt non rattachées à la période pour les pensions de longue durée",
        # La gravité suit l'incidence mesurée sur les arrêtés, non le seul défaut de principe.
        gravite=(Gravite.ELEVEE if charge_non_rattachee > ctx.config.seuil_significatif
                 else Gravite.MOYENNE),
        constat=(
            ("Le compte de charge d'intérêt sur pensions ne porte AUCUNE écriture de couru : il "
             "n'enregistre que des règlements. L'intérêt est donc constaté en une seule fois, au "
             "dénouement de l'opération, quelle qu'en soit la durée.\n"
             if jamais_de_couru else
             "Pour les opérations dont la durée dépasse quelques jours, le couru n'est constaté "
             "que sur un ou deux jours, puis plus rien jusqu'au dénouement, où l'intérêt est "
             "réglé en une fois.\n")
            + "Il en résulte une SOUS-ÉVALUATION DE LA CHARGE D'INTÉRÊT à toute date d'arrêté "
            "comprise entre le tirage et le dénouement, en contradiction avec le principe de "
            "rattachement des charges à l'exercice. L'opération de 98 jours à cheval sur le "
            "31/12/2025 en est l'illustration la plus nette.\n"
            "L'INCIDENCE CHIFFRÉE reste limitée sur la période revue, une seule opération étant à "
            "cheval sur une date d'arrêté. Le constat porte donc sur le dispositif plus que sur "
            "son effet du moment : aucun mécanisme de couru n'existe pour ces opérations, de "
            "sorte qu'une pension de plusieurs mois en cours à une clôture future produirait une "
            "sous-évaluation proportionnelle à son encours."
            if any(l[3] > 30 for l in lignes) else
            "Il en résulte une SOUS-ÉVALUATION DE LA CHARGE D'INTÉRÊT à toute date d'arrêté "
            "comprise entre le tirage et le dénouement, en contradiction avec le principe de "
            "rattachement des charges à l'exercice."
        ),
        chiffres=[
            ("Opérations de plus de 4 jours", str(len(longues))),
            ("Dont aucun couru constaté" if all(l[4] == 0 for l in defaillants)
             else "Dont moins de 3 jours de couru constatés", str(len(defaillants))),
            ("Montant tiré concerné", xaf(sum(l[5] for l in defaillants))),
            ("Opérations à cheval sur une date d'arrêté", str(len(manquant))),
            ("CHARGE NON RATTACHÉE À L'ARRÊTÉ", xaf(charge_non_rattachee)),
        ],
        tableaux=[
            Tableau(["Deal", "Tirage", "Remboursement", "Durée (j)", "Jours de couru", "Montant",
                     "Intérêt réglé"],
                    sorted(defaillants, key=lambda l: -l[3])),
            Tableau(["Deal", "Date d'arrêté", "Jours écoulés", "Durée totale (j)",
                     "Charge à rattacher XAF"],
                    sorted(manquant, key=lambda m: -m[4]),
                    note=("Intérêt qui aurait dû être couru à la date d'arrêté, calculé au "
                          "prorata des jours écoulés sur l'intérêt total effectivement réglé.")),
        ],
        recommandation=(
            "Recalculer la charge d'intérêt courue à chaque date d'arrêté traversée par une "
            "opération non dénouée et mesurer l'incidence sur le résultat des exercices concernés."
        ),
    )


def _c73_collateral(ctx) -> Constat:
    gl = ctx.grand_livre
    collateral = gl[gl.AC_NO == CPT_COLLATERAL[0]]
    if collateral.empty:
        return Constat(code="7.3", titre="Collatéralisation", gravite=Gravite.FAIBLE,
                       constat="Aucun mouvement de collatéral identifié.")
    cfg = ctx.config

    def biais(compte: str) -> float:
        """Part du solde du compte due aux mouvements déversés en double (contrôle 6.7)."""
        d = ctx.mouvements_dupliques
        if d.empty:
            return 0.0
        vises = d[(d.compte == compte) & (d.date <= cfg.fin)]
        return float(vises.impact.sum())

    # Les soldes sont arrêtés à la date de clôture, et non à la fin de l'extraction, et
    # corrigés des doublons d'interface : sans cela, l'encours emprunté et le collatéral
    # seraient ceux d'une date qui n'est pas celle des comptes.
    # Le solde est surévalué du montant « impact » : on le retranche pour revenir au solde réel.
    mobilise = -(ctx.solde(CPT_COLLATERAL[0], a_la_date=cfg.fin) - biais(CPT_COLLATERAL[0]))
    emprunte = -(ctx.solde(CPT_REPO_PASSIF, a_la_date=cfg.fin) - biais(CPT_REPO_PASSIF))
    sur = mobilise - emprunte
    ratio = mobilise / emprunte * 100 if emprunte else 0
    return Constat(
        code="7.3",
        titre="Titres restés affectés en garantie au-delà de l'encours emprunté",
        gravite=Gravite.MOYENNE if sur > ctx.config.seuil_significatif else Gravite.FAIBLE,
        constat=(
            "Le montant de titres affectés en garantie excède l'encours emprunté. L'écart "
            "correspond soit à une exigence de marge de la banque centrale, soit à des titres "
            "restés mobilisés après le dénouement de l'opération qu'ils garantissaient.\n"
            "Dans ce second cas, des titres seraient indisponibles sans contrepartie, ce qui "
            "réduit d'autant la réserve de liquidité mobilisable de l'établissement.\n"
            "Les deux soldes sont arrêtés à la date de clôture et corrigés des mouvements "
            "déversés en double par l'interface (contrôle 6.7), qui affectent aussi bien le "
            "compte d'emprunt que le compte de titres affectés. L'encours ainsi corrigé "
            "correspond exactement à l'unique opération restée non dénouée à la clôture, relevée "
            "au contrôle 7.4 : les deux contrôles convergent."
        ),
        chiffres=[
            ("Date d'arrêté retenue", cfg.fin),
            ("Collatéral net mobilisé", xaf(mobilise)),
            ("Encours emprunté", xaf(emprunte)),
            ("Sur-collatéralisation", xaf(sur)),
            ("Taux de couverture", f"{pct(ratio, 0)}"),
        ],
        recommandation=(
            "Rapprocher des états de collatéral de la banque centrale et obtenir l'exigence de "
            "marge contractuelle. Identifier les titres restés affectés après dénouement."
        ),
    )


def _c74_non_denouees(ctx) -> Constat:
    ops = _operations(ctx)
    if ops.empty:
        return Constat(code="7.4", titre="Dénouement des pensions", gravite=Gravite.FAIBLE,
                       constat="Aucune opération identifiée.")
    ouvertes = ops[ops.date_rembours.isna()]
    ecarts = ops.dropna(subset=["rembourse"])
    ecarts = ecarts[(ecarts.montant - ecarts.rembourse).abs() > 0.5]
    neutralises = len(ctx.mouvements_dupliques[ctx.mouvements_dupliques.compte == CPT_REPO_PASSIF]) \
        if not ctx.mouvements_dupliques.empty else 0
    if ouvertes.empty and ecarts.empty:
        return Constat(code="7.4", titre="Dénouement des pensions", gravite=Gravite.CONFORME,
                       constat="Toutes les opérations sont dénouées pour leur montant exact.")
    return Constat(
        code="7.4",
        titre="Opérations de pension non dénouées à la fin de l'extraction",
        gravite=Gravite.MOYENNE,
        constat=(
            "Des opérations de pension ne présentent aucun remboursement à la fin de la période "
            "extraite, ou sont remboursées pour un montant différent du tirage. Ces situations "
            "doivent être rapprochées des encours réels auprès de la banque centrale.\n"
            "Les mouvements déversés en double par l'interface (contrôle 6.7) ont été neutralisés "
            "avant ce test : les conserver ferait apparaître des remboursements supérieurs aux "
            "tirages, anomalies apparentes qui relèvent en réalité du défaut d'interface et non "
            "de la gestion des pensions."
        ),
        chiffres=[
            ("Opérations sans remboursement", str(len(ouvertes))),
            ("Montant tiré non remboursé", xaf(float(ouvertes.montant.sum()))),
            ("Opérations remboursées pour un montant différent", str(len(ecarts))),
            ("Mouvements en double neutralisés avant le test", str(neutralises)),
        ],
        tableaux=[
            Tableau(["Deal", "Tirage", "Montant tiré", "Remboursé", "Contrepartie"],
                    [[i, r.date_tirage, float(r.montant),
                      float(r.rembourse) if pd.notna(r.rembourse) else None, r.emetteur]
                     for i, r in pd.concat([ouvertes, ecarts]).iterrows()])
        ],
        recommandation="Rapprocher des relevés de la banque centrale à la date d'arrêté.",
    )
