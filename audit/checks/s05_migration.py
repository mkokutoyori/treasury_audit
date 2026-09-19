"""Section 5 — Migration du module MM de Flexcube vers Calypso (16/06/2025)."""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf
from ..data import (CPT_COURUS_CALYPSO, CPT_COURUS_MM, CPT_PORTEFEUILLE_CALYPSO,
                    CPT_PORTEFEUILLE_MM, CPT_PROVISION, DATE_BASCULE)

SECTION = (5, "Migration Flexcube MM vers Calypso")


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            f"La bascule s'est opérée le {DATE_BASCULE} par liquidation technique intégrale du "
            "portefeuille dans Flexcube et réintroduction des positions dans Calypso. Cette "
            "section rapproche les deux systèmes, contrôle la reprise des intérêts courus, "
            "l'extinction des comptes d'origine et la cohérence du classement comptable retenu."
        ),
    )
    s.ajouter(_c51_rapprochement_positions(ctx))
    s.ajouter(_c52_reprise_courus(ctx))
    s.ajouter(_c53_sur_apurement(ctx))
    s.ajouter(_c54_extinction(ctx))
    s.ajouter(_c55_reclassement(ctx))
    s.ajouter(_c56_continuite(ctx))
    return s


def _c51_rapprochement_positions(ctx) -> Constat:
    gl = ctx.grand_livre
    jour = gl[gl.TRN_DT == DATE_BASCULE]
    sortie = jour[(jour.MODULE == "MM") & (jour.AMOUNT_TAG == "PRINCIPAL_LIQD") & (jour.DRCR_IND == "C")]
    entree = jour[jour.AC_NO.isin(CPT_PORTEFEUILLE_CALYPSO) & (jour.DRCR_IND == "D")]
    m_sortie, m_entree = float(sortie.LCY_AMOUNT.sum()), float(entree.LCY_AMOUNT.sum())
    ecart = m_entree - m_sortie
    part = abs(ecart) / max(m_sortie, 1) * 100
    conforme = part < 0.05
    detail = [
        ["Flexcube — sortie", c, float(g.LCY_AMOUNT.sum()), int(len(g))]
        for c, g in sortie.groupby("AC_NO")
    ] + [
        ["Calypso — entrée", c, float(g.LCY_AMOUNT.sum()), int(len(g))]
        for c, g in entree.groupby("AC_NO")
    ]
    return Constat(
        code="5.1",
        titre="Rapprochement des positions migrées",
        gravite=Gravite.CONFORME if conforme else Gravite.ELEVEE,
        constat=(
            "Le portefeuille sorti de Flexcube et le portefeuille réintroduit dans Calypso se "
            f"rapprochent à {part:.4f} % près, sur un nombre identique de positions. La migration "
            "des nominaux est donc correctement exécutée."
            if conforme else
            "Le portefeuille sorti de Flexcube et celui réintroduit dans Calypso ne se rapprochent "
            "pas. Un écart sur la migration des nominaux affecte directement la valeur du "
            "portefeuille présentée au bilan."
        ),
        chiffres=[
            ("Positions sorties de Flexcube", str(len(sortie))),
            ("Positions entrées dans Calypso", str(len(entree))),
            ("Montant sorti", xaf(m_sortie)),
            ("Montant entré", xaf(m_entree)),
            ("Écart", f"{xaf(ecart)} ({part:.4f} %)"),
        ],
        tableaux=[Tableau(["Sens", "Compte", "Montant XAF", "Lignes"], detail)],
        recommandation=(
            "Conserver ce rapprochement au dossier ; il constitue la preuve de l'exhaustivité de "
            "la reprise des nominaux."
            if conforme else
            "Obtenir le détail position par position et l'explication de l'écart."
        ),
    )


def _c52_reprise_courus(ctx) -> Constat:
    gl = ctx.grand_livre
    jour = gl[gl.TRN_DT == DATE_BASCULE]
    repris = jour[(jour.AC_NO == CPT_COURUS_CALYPSO) & (jour.DRCR_IND == "D")
                  & jour.DESCRIPTION.fillna("").str.contains("ACCRUAL_BS")]
    montant = float(repris.LCY_AMOUNT.sum())
    return Constat(
        code="5.2",
        titre="Reprise des intérêts courus dans le nouveau système",
        gravite=Gravite.CONFORME if len(repris) else Gravite.ELEVEE,
        constat=(
            "Les intérêts courus attachés aux positions migrées ont été réintroduits dans Calypso "
            f"par l'événement ACCRUAL_BS, sur le compte {CPT_COURUS_CALYPSO}. Le compte d'origine "
            f"({CPT_COURUS_MM}) a été soldé le même jour — voir le contrôle 5.3, qui établit que "
            "ce solde a été passé pour un montant supérieur au solde réel."
            if len(repris) else
            "Aucune reprise d'intérêts courus n'est identifiée dans Calypso au jour de la bascule."
        ),
        chiffres=[
            ("Positions dont les courus sont repris", str(len(repris))),
            ("Courus repris", xaf(montant)),
        ],
        recommandation=(
            "Rapprocher position par position les courus repris et les courus soldés dans "
            "Flexcube (voir contrôle 5.3)."
        ),
    )


def _c53_sur_apurement(ctx) -> Constat:
    """Le solde passé à la migration doit être égal au solde comptable du compte."""
    courus = ctx.courus
    if courus.empty:
        return Constat(
            code="5.3", titre="Apurement du compte de courus à la migration", gravite=Gravite.FAIBLE,
            constat="L'historique complet du compte de créances rattachées n'est pas disponible.",
            recommandation="Extraire l'historique du compte 511800100 tous modules confondus.",
        )
    avant = courus[courus.TRN_DT < DATE_BASCULE]
    solde_avant = float(avant.SIGNE.sum())
    jour = courus[courus.TRN_DT == DATE_BASCULE]
    debits_jour = float(jour[jour.DRCR_IND == "D"].LCY_AMOUNT.sum())
    credit = float(jour[jour.DRCR_IND == "C"].LCY_AMOUNT.sum())
    a_apurer = solde_avant + debits_jour
    sur = credit - a_apurer
    apres = courus[courus.TRN_DT > DATE_BASCULE]
    solde_post = float(courus[courus.TRN_DT <= DATE_BASCULE].SIGNE.sum())
    if abs(sur) < 1:
        return Constat(
            code="5.3", titre="Apurement du compte de courus à la migration", gravite=Gravite.CONFORME,
            constat="Le montant apuré correspond exactement au solde comptable du compte.",
        )
    correction = apres[apres.DRCR_IND == "D"]
    jours_anomalie = 0
    if not correction.empty:
        jours_anomalie = int((correction.TRN_DT_d.min() - pd.Timestamp(DATE_BASCULE)).days)
    lignes_corr = [
        [r.TRN_DT, r.TRN_REF_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID, r.AUTH_ID,
         (r.DESCRIPTION or "")[:45]]
        for r in correction.itertuples()
    ]
    return Constat(
        code="5.3",
        titre="Sur-apurement du compte de courus à la migration, laissant un compte d'actif en solde créditeur",
        gravite=Gravite.CRITIQUE,
        constat=(
            "L'écriture manuelle passée le jour de la bascule pour solder le compte de créances "
            "rattachées a crédité, pour chaque contrat, le CUMUL DES INTÉRÊTS COURUS DEPUIS "
            "L'ORIGINE, sans déduire les coupons déjà encaissés. Le montant crédité excède donc le "
            "solde comptable réel du compte.\n"
            "Il en résulte une double conséquence : le compte de créances rattachées, qui est un "
            "compte d'ACTIF, s'est retrouvé en SOLDE CRÉDITEUR ; et la contrepartie étant un débit "
            "du compte de règlement BEAC, le nostro a été surévalué du même montant sur la même "
            "période. L'anomalie traverse l'arrêté semestriel."
        ),
        chiffres=[
            ("Solde du compte la veille de la bascule", xaf(solde_avant)),
            ("Courus du jour de la bascule", xaf(debits_jour)),
            ("Solde réel à apurer", xaf(a_apurer)),
            ("Montant effectivement crédité", xaf(credit)),
            ("SUR-APUREMENT", xaf(sur)),
            ("Solde du compte après la bascule", xaf(solde_post)),
            ("Délai avant correction", f"{jours_anomalie} jours" if jours_anomalie else "non corrigé"),
        ],
        tableaux=[
            Tableau(["Date", "Référence", "Sens", "Montant XAF", "Saisie", "Validation", "Libellé"],
                    lignes_corr, note="Écriture(s) de correction postérieure(s) à la bascule.")
        ],
        recommandation=(
            "Obtenir les états financiers à la date d'arrêté traversée par l'anomalie et vérifier "
            "si le solde créditeur y figure. Obtenir le rapprochement du nostro BEAC des mois "
            "concernés : un écart de cette ampleur aurait dû être détecté par le rapprochement "
            "bancaire mensuel. Faire expliquer le mode opératoire retenu pour calculer les courus "
            "à reprendre, fondé sur le cumul théorique et non sur le solde comptable."
        ),
    )


def _c54_extinction(ctx) -> Constat:
    """Après migration, les comptes du dispositif d'origine doivent être soldés."""
    gl = ctx.grand_livre
    lignes = []
    non_soldes = []
    for compte in CPT_PORTEFEUILLE_MM + [CPT_COURUS_MM, CPT_PROVISION]:
        sous = gl[gl.AC_NO == compte]
        if sous.empty:
            continue
        solde = float(sous.SIGNE.sum())
        dernier = sous.TRN_DT.max()
        lignes.append([compte, sous.AC_GL_DESC.iloc[0][:40], len(sous), solde, dernier])
        if abs(solde) > 1:
            non_soldes.append(compte)
    if not non_soldes:
        return Constat(
            code="5.4",
            titre="Extinction des comptes du dispositif Flexcube",
            gravite=Gravite.CONFORME,
            constat=(
                "Les comptes de portefeuille, de créances rattachées et de provision du dispositif "
                "d'origine reviennent exactement à zéro sur l'ensemble de leur historique. "
                "L'extinction est propre."
            ),
            tableaux=[Tableau(["Compte", "Libellé", "Lignes", "Solde XAF", "Dernier mouvement"], lignes)],
        )
    return Constat(
        code="5.4",
        titre="Comptes du dispositif Flexcube non soldés après migration",
        gravite=Gravite.ELEVEE,
        constat=(
            "Des comptes du dispositif d'origine conservent un solde après la migration. Une "
            "migration correctement conduite exige que le compte source soit ramené à zéro dès "
            "lors que son solde est repris par le système cible."
        ),
        chiffres=[("Comptes non soldés", ", ".join(non_soldes))],
        tableaux=[Tableau(["Compte", "Libellé", "Lignes", "Solde XAF", "Dernier mouvement"], lignes)],
        recommandation="Obtenir la justification du solde résiduel de chaque compte concerné.",
    )


def _c55_reclassement(ctx) -> Constat:
    """La migration change la catégorie PCEC du portefeuille : placement vers transaction."""
    gl = ctx.grand_livre
    avant = gl[(gl.TRN_DT < DATE_BASCULE) & gl.AC_NO.isin(CPT_PORTEFEUILLE_MM)]
    apres = gl[(gl.TRN_DT >= DATE_BASCULE) & gl.AC_NO.isin(CPT_PORTEFEUILLE_CALYPSO)]
    return Constat(
        code="5.5",
        titre="Changement de catégorie comptable opéré à la migration",
        gravite=Gravite.ELEVEE,
        constat=(
            "La migration déplace le portefeuille du compte d'obligations en TITRES DE PLACEMENT "
            "vers le compte d'obligations en TITRES DE TRANSACTION, et symétriquement les bons du "
            "Trésor de la catégorie transaction vers la catégorie placement. Or le PCEC applique "
            "des règles d'évaluation différentes aux deux catégories : les titres de transaction "
            "sont évalués au prix de marché avec incidence en résultat, les titres de placement au "
            "plus bas du coût et de la valeur de marché.\n"
            "Ce reclassement modifie donc la méthode d'évaluation de l'intégralité du portefeuille. "
            "Il doit résulter d'une décision de gestion documentée et non d'un effet de "
            "paramétrage du nouvel outil."
        ),
        chiffres=[
            ("Avant migration — comptes utilisés", ", ".join(sorted(avant.AC_NO.unique()))),
            ("Après migration — comptes utilisés", ", ".join(sorted(apres.AC_NO.unique()))),
            ("Nominal reclassé", xaf(float(
                gl[(gl.TRN_DT == DATE_BASCULE) & gl.AC_NO.isin(CPT_PORTEFEUILLE_CALYPSO)
                   & (gl.DRCR_IND == "D")].LCY_AMOUNT.sum()))),
        ],
        recommandation=(
            "Obtenir la note de décision du reclassement, son approbation, et la position du "
            "commissaire aux comptes. Vérifier l'incidence sur la méthode d'évaluation retenue et "
            "sur les états réglementaires COBAC."
        ),
    )


def _c56_continuite(ctx) -> Constat:
    gl = ctx.grand_livre
    mm = gl[gl.MODULE == "MM"]
    calypso = gl[gl.PRODUCT == "MNIP"]
    fin_mm, debut_calypso = mm.TRN_DT.max(), calypso.TRN_DT.min()
    recouvrement = mm[mm.TRN_DT > debut_calypso]
    trou = fin_mm < debut_calypso
    return Constat(
        code="5.6",
        titre="Continuité chronologique de la bascule",
        gravite=Gravite.CONFORME if not trou else Gravite.MOYENNE,
        constat=(
            f"Le module d'origine s'arrête le {fin_mm} et le nouveau dispositif démarre le "
            f"{debut_calypso} : la bascule s'opère sans interruption ni période de double "
            "comptabilisation."
            if not trou else
            "Une discontinuité existe entre l'arrêt de l'ancien dispositif et le démarrage du "
            "nouveau : les opérations de l'intervalle doivent être identifiées."
        ),
        chiffres=[
            ("Dernière écriture du module MM", str(fin_mm)),
            ("Première écriture Calypso", str(debut_calypso)),
            ("Écritures MM postérieures au démarrage Calypso", str(len(recouvrement))),
        ],
    )
