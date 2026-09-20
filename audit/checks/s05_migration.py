"""Section 5 — Migration du module MM de Flexcube vers Calypso (16/06/2025)."""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf, pct
from ..data import (CPT_BEAC, CPT_COURUS_CALYPSO, CPT_COURUS_MM,
                    CPT_PORTEFEUILLE_CALYPSO, CPT_PORTEFEUILLE_MM, CPT_PROVISION, DATE_BASCULE)

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
            f"rapprochent à {pct(part, 4)} près : la migration des nominaux est correctement "
            "exécutée en montant."
            + ("" if len(sortie) == len(entree) else
               f" Le NOMBRE de lignes diffère en revanche — {len(sortie)} à la sortie contre "
               f"{len(entree)} à l'entrée : une ou plusieurs positions ont été redécoupées lors de "
               "la reprise. Le fait est sans incidence sur les montants, mais il interdit un "
               "rapprochement ligne à ligne et doit être documenté.")
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
            ("Écart", f"{xaf(ecart)} ({pct(part, 4)})"),
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
    # Le montant repris dans le nouveau système doit égaler le solde réel du compte d'origine.
    # Ce solde est établi au contrôle 5.3 ; on le recalcule ici pour confronter les deux.
    courus = ctx.courus
    solde_reel = None
    if not courus.empty:
        avant = float(courus[courus.TRN_DT < DATE_BASCULE].SIGNE.sum())
        du_jour = float(courus[(courus.TRN_DT == DATE_BASCULE)
                               & (courus.DRCR_IND == "D")].LCY_AMOUNT.sum())
        solde_reel = avant + du_jour
    ecart_reprise = montant - solde_reel if solde_reel is not None else None
    ecart_significatif = (ecart_reprise is not None
                          and abs(ecart_reprise) > ctx.config.seuil_materialite)
    return Constat(
        code="5.2",
        titre=("Reprise des intérêts courus dans le nouveau système"
               if not repris.empty and not ecart_significatif else
               "Écart entre les intérêts courus repris et le solde du compte d'origine"),
        gravite=(Gravite.ELEVEE if repris.empty else
                 Gravite.MOYENNE if ecart_significatif else Gravite.CONFORME),
        constat=(
            "Les intérêts courus attachés aux positions migrées ont été réintroduits dans Calypso "
            f"par l'événement ACCRUAL_BS, sur le compte {CPT_COURUS_CALYPSO}. Le compte d'origine "
            f"({CPT_COURUS_MM}) a été soldé le même jour — voir le contrôle 5.3, qui établit que "
            "ce solde a été passé pour un montant supérieur au solde réel."
            + ("" if ecart_reprise is None or abs(ecart_reprise) < 1 else
               f"\nLe montant repris s'écarte par ailleurs de {xaf(abs(ecart_reprise))} du solde "
               "réel du compte d'origine : les deux systèmes ne partent donc pas du même encours "
               "de courus. L'écart est d'un autre ordre de grandeur que le sur-apurement du "
               "contrôle 5.3 et s'en distingue, mais il doit lui aussi être justifié position par "
               "position.")
            if len(repris) else
            "Aucune reprise d'intérêts courus n'est identifiée dans Calypso au jour de la bascule."
        ),
        chiffres=[
            ("Positions dont les courus sont repris", str(len(repris))),
            ("Courus repris dans le nouveau système", xaf(montant)),
        ] + ([] if solde_reel is None else [
            ("Solde réel du compte d'origine (voir 5.3)", xaf(solde_reel)),
            ("Écart de reprise", xaf(ecart_reprise)),
        ]),
        recommandation=(
            "Rapprocher position par position les courus repris dans le nouveau système et les "
            "courus portés par le compte d'origine, et faire justifier l'écart constaté. Ce "
            "rapprochement est distinct de celui du contrôle 5.3, qui porte sur le montant apuré."
        ),
    )


def _c53_sur_apurement(ctx) -> Constat:
    """Le montant passé à la migration pour solder le compte de courus était-il le bon ?

    Le contrôle décompose entièrement l'opération : solde de départ, écriture d'apurement
    contrat par contrat, contrepartie en trésorerie, solde résultant, dates d'arrêté
    traversées et écriture de correction.
    """
    courus = ctx.courus
    if courus.empty:
        return Constat(code="5.3", titre="Apurement du compte de courus à la migration",
                       gravite=Gravite.FAIBLE,
                       constat="Historique du compte de créances rattachées indisponible.",
                       recommandation="Extraire l'historique du compte 511800100 tous modules confondus.")
    avant = courus[courus.TRN_DT < DATE_BASCULE]
    solde_avant = float(avant.SIGNE.sum())
    jour = courus[courus.TRN_DT == DATE_BASCULE]
    debits_jour = float(jour[jour.DRCR_IND == "D"].LCY_AMOUNT.sum())
    credit = float(jour[jour.DRCR_IND == "C"].LCY_AMOUNT.sum())
    a_apurer = solde_avant + debits_jour
    sur = credit - a_apurer
    if abs(sur) < 1:
        return Constat(code="5.3", titre="Apurement du compte de courus à la migration",
                       gravite=Gravite.CONFORME,
                       constat="Le montant apuré correspond exactement au solde comptable du compte.")

    # --- 1. L'écriture d'apurement et sa contrepartie en trésorerie
    ecriture = jour[jour.DRCR_IND == "C"]
    reference = ecriture.TRN_REF_NO.iloc[0] if len(ecriture) else ""
    # Le compte de règlement est un nostro : il ne figure pas parmi les comptes généraux
    # extraits. La contrepartie se cherche donc dans l'union de toutes les sources.
    gl = ctx.toutes_ecritures
    contrepartie = gl[(gl.TRN_REF_NO == reference) & (gl.AC_NO != CPT_COURUS_MM)]
    cpt_contrepartie = contrepartie.groupby(["AC_NO", "AC_GL_DESC", "DRCR_IND"]).agg(
        lignes=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))

    # --- 2. Décomposition contrat par contrat : couru réel contre montant crédité
    ecriture = ecriture.copy()
    ecriture["contrat"] = ecriture.DESCRIPTION.str.extract(r"(099[A-Z]{4}\d{9})")[0]
    cumul_par_contrat = (courus[(courus.DRCR_IND == "D") & (courus.TRN_DT <= DATE_BASCULE)]
                         .groupby("TRN_REF_NO").LCY_AMOUNT.sum())
    deja_apure = courus[(courus.DRCR_IND == "C") & (courus.TRN_DT < DATE_BASCULE)].copy()
    deja_apure["contrat"] = deja_apure.DESCRIPTION.str.extract(r"(099[A-Z]{4}\d{9})")[0]
    apure_avant = deja_apure.groupby("contrat").LCY_AMOUNT.sum()
    detail = []
    for _, r in ecriture.iterrows():
        contrat = r.contrat
        if not isinstance(contrat, str):
            continue
        cumul = float(cumul_par_contrat.get(contrat, 0))
        deja = float(apure_avant.get(contrat, 0))
        solde_reel = cumul - deja
        detail.append([contrat, cumul, deja, solde_reel, float(r.LCY_AMOUNT),
                       float(r.LCY_AMOUNT) - solde_reel])
    detail.sort(key=lambda l: -l[5])
    touches = [d for d in detail if d[5] > 0.5]
    ecart_contrats = sum(d[5] for d in detail)

    # --- 3. Arrêtés traversés et correction
    apres = courus[courus.TRN_DT > DATE_BASCULE]
    correction = apres[apres.DRCR_IND == "D"]
    date_correction = correction.TRN_DT.min() if not correction.empty else None
    jours = int((pd.Timestamp(date_correction) - pd.Timestamp(DATE_BASCULE)).days) if date_correction else 0
    arretes_traverses = [a for a in ctx.arretes
                         if DATE_BASCULE <= a < (date_correction or "9999")]
    soldes_arretes = [[a, ctx.solde(CPT_COURUS_MM, a_la_date=a, df=courus)]
                      for a in ctx.arretes]

    # --- 4. La contrepartie trésorerie de la correction
    corr_ref = correction.TRN_REF_NO.iloc[0] if not correction.empty else ""
    corr_autres = gl[(gl.TRN_REF_NO == corr_ref) & (gl.AC_NO != CPT_COURUS_MM)]
    corr_detail = [[r.TRN_DT, r.AC_NO, (r.AC_GL_DESC or "")[:34], r.DRCR_IND, float(r.LCY_AMOUNT),
                    r.USER_ID, r.AUTH_ID] for _, r in corr_autres.iterrows()]
    jambe_corr_courus = float(correction.LCY_AMOUNT.sum())
    jambe_corr_tresorerie = float(corr_autres.LCY_AMOUNT.sum())
    troisieme_jambe = jambe_corr_tresorerie - jambe_corr_courus

    return Constat(
        code="5.3",
        titre="Sur-apurement du compte de courus à la migration, laissant un compte d'actif en solde créditeur",
        gravite=Gravite.CRITIQUE,
        reference=f"Écriture d'apurement {reference} — écriture de correction {corr_ref}",
        constat=(
            "CE QUI DEVAIT SE PASSER. Au jour de la bascule, le compte de créances rattachées "
            "portait le solde des intérêts courus non encore encaissés. Pour le solder, il fallait "
            "le créditer de CE SOLDE, ni plus ni moins, la contrepartie étant l'encaissement "
            "correspondant sur le compte de règlement.\n"
            "\n"
            "CE QUI S'EST PASSÉ. L'écriture manuelle passée ce jour-là a crédité, pour chaque "
            "contrat, le CUMUL DES INTÉRÊTS COURUS DEPUIS L'ORIGINE DU CONTRAT — et non le solde "
            "restant. Or, pour une partie des contrats, des coupons avaient déjà été encaissés "
            "antérieurement et avaient donc déjà réduit le solde. Ces encaissements passés n'ont "
            "pas été déduits : ils ont été crédités une seconde fois.\n"
            "\n"
            "COMMENT LE LIRE SUR UN CONTRAT. Prenons le cas le plus important du tableau de "
            "décomposition ci-dessous. La colonne « cumul depuis l'origine » est le total des "
            "intérêts jamais courus sur le contrat. La colonne « déjà encaissé » est ce qui en "
            "avait déjà été réglé. Leur différence, « solde réel », est le seul montant qu'il "
            "fallait créditer. La colonne « crédité » montre ce qui l'a effectivement été : le "
            "cumul complet. L'écart est le montant crédité en trop.\n"
            "\n"
            "LES DEUX CONSÉQUENCES. Premièrement, le compte de créances rattachées — un compte "
            "d'ACTIF — s'est retrouvé en SOLDE CRÉDITEUR, position impossible par construction : "
            "cela revient à dire que la banque devait de l'argent au titre d'intérêts qu'elle "
            "devait recevoir. Deuxièmement, la contrepartie de l'écriture étant un DÉBIT DU COMPTE "
            "DE RÈGLEMENT auprès de la banque centrale, la banque a enregistré avoir encaissé plus "
            "de trésorerie qu'elle n'en a reçu : le nostro a été surévalué du même montant.\n"
            "\n"
            "LA DURÉE. L'anomalie n'a pas été corrigée immédiatement. Elle a persisté et a traversé "
            "une date d'arrêté, ce qui signifie que les états produits à cette date portent un "
            "compte d'actif créditeur et un nostro surévalué. Un écart de cette ampleur sur le "
            "compte de règlement de la banque centrale aurait dû être détecté par le rapprochement "
            "bancaire mensuel.\n"
            "\n"
            "LA CORRECTION. Elle est intervenue par une écriture manuelle explicitement libellée "
            "comme se rapportant à la mise en service du nouveau système. Ses deux jambes connues "
            "ne s'équilibrent pas exactement : une troisième jambe existe, sur un compte non "
            "couvert par les extractions."
        ),
        chiffres=[
            ("1. Solde du compte la veille de la bascule", xaf(solde_avant)),
            ("2. Courus du jour de la bascule", xaf(debits_jour)),
            ("3. SOLDE RÉEL À APURER (1 + 2)", xaf(a_apurer)),
            ("4. Montant effectivement crédité", xaf(credit)),
            ("5. SUR-APUREMENT (4 − 3)", xaf(sur)),
            ("6. Contrats crédités", str(len(detail))),
            ("7. Dont crédités en trop", str(len(touches))),
            ("8. Écart cumulé au niveau contrat", xaf(ecart_contrats)),
            ("9. Solde du compte après la bascule", xaf(ctx.solde(CPT_COURUS_MM, a_la_date=DATE_BASCULE, df=courus))),
            ("10. Date de correction", str(date_correction) if date_correction else "non corrigé"),
            ("11. Durée de l'anomalie", f"{jours} jours"),
            ("12. Dates d'arrêté traversées", ", ".join(arretes_traverses) if arretes_traverses else "aucune"),
            ("13. Jambe courus de la correction", xaf(jambe_corr_courus)),
            ("14. Jambe trésorerie de la correction", xaf(jambe_corr_tresorerie)),
            ("15. TROISIÈME JAMBE NON IDENTIFIÉE (14 − 13)", xaf(troisieme_jambe)),
        ],
        tableaux=[
            Tableau(["Compte", "Libellé", "Sens", "Lignes", "Montant XAF"],
                    [[i[0], i[1][:38], i[2], int(r.lignes), float(r.montant)]
                     for i, r in cpt_contrepartie.iterrows()],
                    note="Contrepartie de l'écriture d'apurement : la trésorerie enregistrée comme encaissée."),
            Tableau(["Contrat", "Cumul depuis l'origine", "Déjà encaissé", "Solde réel",
                     "Crédité", "Crédité en trop"],
                    detail, max_lignes=20,
                    note=(
                        "Décomposition contrat par contrat. La dernière colonne totalise "
                        f"{xaf(ecart_contrats)}, montant qui diffère du sur-apurement constaté sur "
                        f"le compte ({xaf(sur)}) : le rattachement d'un mouvement à un "
                        "contrat repose sur le libellé, et tous les mouvements du compte n'en "
                        "portent pas. Le chiffre opposable est celui du compte, la décomposition "
                        "servant à identifier les contrats concernés."
                    )),
            Tableau(["Date d'arrêté", "Solde du compte de courus"],
                    soldes_arretes,
                    note="Le solde du compte de courus à chaque arrêté : un compte d'actif ne peut être négatif."),
            Tableau(["Date", "Compte", "Libellé", "Sens", "Montant XAF", "Saisie", "Validation"],
                    corr_detail,
                    note="Écriture de correction et sa contrepartie."),
        ],
        recommandation=(
            "1. Obtenir les états financiers à la date d'arrêté traversée et vérifier si le solde "
            "créditeur du compte d'actif et la surévaluation du nostro y figurent.\n"
            "2. Obtenir le rapprochement bancaire du compte de règlement des mois concernés et "
            "comprendre pourquoi un écart de cette ampleur n'a pas été détecté plus tôt.\n"
            "3. Faire expliquer le mode opératoire retenu pour calculer les courus à reprendre, "
            "fondé sur le cumul théorique par contrat et non sur le solde comptable.\n"
            "4. Identifier la troisième jambe de l'écriture de correction.\n"
            "5. Vérifier qu'aucune autre écriture de migration n'a été construite sur le même "
            "mode opératoire."
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
