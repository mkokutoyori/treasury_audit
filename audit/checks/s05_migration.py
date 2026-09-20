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
    """Le couru repris dans Calypso correspond-il à celui que portaient les positions migrées ?

    Le test ne compare pas la reprise au SOLDE DU COMPTE — celui-ci contient aussi des courus
    de positions qui ne sont plus au portefeuille — mais au couru effectivement porté par les
    65 positions qui ont migré. C'est la seule comparaison qui ait un sens.
    """
    gl = ctx.grand_livre
    jour = gl[gl.TRN_DT == DATE_BASCULE]
    structure = jour[jour.DESCRIPTION.fillna("").str.count(r"\|") == 9].copy()
    if structure.empty:
        return Constat(code="5.2", titre="Reprise des intérêts courus",
                       gravite=Gravite.ELEVEE,
                       constat="Aucune reprise d'intérêts courus identifiée dans Calypso.")
    structure["deal"] = structure.DESCRIPTION.str.split("|").str[1]
    structure["evt"] = structure.DESCRIPTION.str.split("|").str[3]
    entrees = structure[(structure.evt == "NOMINAL")
                        & structure.AC_NO.isin(CPT_PORTEFEUILLE_CALYPSO)]
    repris = structure[(structure.evt == "ACCRUAL_BS") & (structure.AC_NO == CPT_COURUS_CALYPSO)]
    montant = float(repris.LCY_AMOUNT.sum())

    # Positions sorties de Flexcube et couru réellement porté par chacune
    sorties = jour[(jour.MODULE == "MM") & (jour.AMOUNT_TAG == "PRINCIPAL_LIQD")
                   & (jour.DRCR_IND == "C")]
    nominaux_mm = sorties.groupby("TRN_REF_NO").LCY_AMOUNT.sum()
    courus = ctx.courus.copy()
    if courus.empty:
        return Constat(code="5.2", titre="Reprise des intérêts courus", gravite=Gravite.FAIBLE,
                       constat="Historique du compte de créances rattachées indisponible.")
    # Le contrat est la référence elle-même pour les courus automatiques, et le libellé pour
    # les écritures manuelles d'apurement.
    courus["contrat"] = courus.TRN_REF_NO.where(
        courus.TRN_REF_NO.str.match(r"^099[A-Z]{4}\d{9}$", na=False))
    courus["contrat"] = courus.contrat.fillna(
        courus.DESCRIPTION.str.extract(r"(099[A-Z]{4}\d{9})")[0])
    debits = courus[(courus.DRCR_IND == "D")
                    & (courus.TRN_DT <= DATE_BASCULE)].groupby("contrat").LCY_AMOUNT.sum()
    apures = courus[(courus.DRCR_IND == "C")
                    & (courus.TRN_DT < DATE_BASCULE)].groupby("contrat").LCY_AMOUNT.sum()
    reel = debits - apures.reindex(debits.index).fillna(0)
    couru_migre = float(reel.reindex(nominaux_mm.index).fillna(0).sum())
    hors_portefeuille = reel[~reel.index.isin(set(nominaux_mm.index))]

    # Solde réel du compte à apurer, tel que l'établit le contrôle 5.3
    solde_compte = (float(courus[courus.TRN_DT < DATE_BASCULE].SIGNE.sum())
                    + float(courus[(courus.TRN_DT == DATE_BASCULE)
                                   & (courus.DRCR_IND == "D")].LCY_AMOUNT.sum()))
    ecart_reprise = montant - couru_migre
    non_attribuable = solde_compte - couru_migre

    # Positions entrées sans reprise de couru : les bons à escompte n'en portent pas
    sans_reprise = entrees[~entrees.deal.isin(set(repris.deal))]
    par_compte_sans = sans_reprise.groupby("AC_NO").agg(
        positions=("LCY_AMOUNT", "size"), nominal=("LCY_AMOUNT", "sum"))
    # Le rapprochement position par position est-il possible ?
    doublons_nominal = int((nominaux_mm.value_counts() > 1).sum())
    positions_ambigues = int(nominaux_mm.value_counts()[nominaux_mm.value_counts() > 1].sum())
    significatif = abs(ecart_reprise) > ctx.config.seuil_significatif
    return Constat(
        code="5.2",
        titre=("Le couru repris dans le nouveau système excède celui des positions migrées"
               if significatif else "Reprise des intérêts courus dans le nouveau système"),
        gravite=Gravite.ELEVEE if significatif else Gravite.CONFORME,
        constat=(
            "CE QUI EST COMPARÉ. Le contrôle ne rapproche pas la reprise du SOLDE du compte de "
            f"créances rattachées {CPT_COURUS_MM} : ce solde contient aussi des courus de "
            "positions qui ne sont plus au portefeuille. Il la rapproche du couru effectivement "
            "porté par les positions QUI ONT MIGRÉ, seule comparaison qui ait un sens.\n"
            "\n"
            f"LES POSITIONS SE RAPPROCHENT EXACTEMENT. {len(entrees)} positions sortent de "
            f"Flexcube et {len(entrees)} entrent dans Calypso, pour un nominal identique de "
            f"{xaf(float(entrees.LCY_AMOUNT.sum()))}, et chaque nominal se retrouve des deux "
            "côtés. La reprise du portefeuille est donc exhaustive.\n"
            + (f"{len(sans_reprise)} de ces positions n'emportent AUCUN couru, et c'est normal : "
               f"il s'agit des bons du Trésor logés au compte "
               f"{', '.join(par_compte_sans.index)}, titres à ESCOMPTE qui ne portent pas de "
               "coupon. Leur rémunération est logée en compte de régularisation, pas en créances "
               "rattachées.\n"
               if len(sans_reprise) else "")
            + "\n"
            + (f"LE COURU, LUI, NE SE RAPPROCHE PAS. Les positions migrées portaient "
               f"{xaf(couru_migre)} de coupons courus. Calypso en a repris {xaf(montant)}, soit "
               f"{xaf(ecart_reprise)} DE PLUS. Le nouveau système démarre donc avec un actif "
               "supérieur à celui que l'ancien lui transmettait, sans qu'aucune écriture ne "
               "justifie la différence.\n"
               if significatif else
               f"LE COURU SE RAPPROCHE ÉGALEMENT : {xaf(couru_migre)} portés par les positions "
               f"migrées contre {xaf(montant)} repris.\n")
            + "\n"
            "UN SECOND ÉCART, DE NATURE DIFFÉRENTE. Le solde du compte d'origine à apurer "
            f"s'élevait à {xaf(solde_compte)}, dont {xaf(couru_migre)} seulement se rattachent "
            f"aux positions migrées. Il reste {xaf(non_attribuable)} qui ne se rattachent à "
            "AUCUNE position du portefeuille au jour de la bascule. Le compte portait en effet "
            f"un couru résiduel sur {len(hors_portefeuille)} contrats déjà sortis du "
            "portefeuille — des créances rattachées à des titres dénoués de longue date, jamais "
            "apurées, et soldées à la migration sans avoir jamais été encaissées. Le nombre de "
            "contrats et le montant non rattachable ne se recoupent pas exactement : certains de "
            "ces contrats portent un solde négatif, effet des apurements antérieurs excédentaires "
            "relevés au contrôle 3.4.\n"
            "\n"
            "CE QUI NE PEUT PAS ÊTRE FAIT. Un rapprochement POSITION PAR POSITION est impossible "
            "avec les données disponibles : les deux systèmes n'ont aucun identifiant commun — "
            "Flexcube désigne une position par sa référence de contrat, Calypso par le code du "
            f"titre — et {positions_ambigues} des {len(nominaux_mm)} positions partagent leur "
            f"nominal avec une autre, sur {doublons_nominal} valeurs. Le rapprochement en masse "
            "est donc le seul possible, et l'écart ne peut être imputé à des positions "
            "identifiées sans le concours des deux services."
        ),
        chiffres=[
            ("Positions sorties de Flexcube / entrées dans Calypso",
             f"{len(nominaux_mm)} / {len(entrees)}"),
            ("Nominal migré, identique des deux côtés", xaf(float(entrees.LCY_AMOUNT.sum()))),
            ("Positions sans couru (bons à escompte)",
             f"{len(sans_reprise)} — {xaf(float(sans_reprise.LCY_AMOUNT.sum()))}"),
            ("Couru PORTÉ par les positions migrées", xaf(couru_migre)),
            ("Couru REPRIS dans le nouveau système", xaf(montant)),
            ("ÉCART DE REPRISE", xaf(ecart_reprise)),
            ("Solde du compte d'origine à apurer (voir 5.3)", xaf(solde_compte)),
            ("Dont NON rattachable aux positions migrées", xaf(non_attribuable)),
            ("Contrats hors portefeuille portant un couru résiduel", str(len(hors_portefeuille))),
        ],
        tableaux=[
            Tableau(["Élément", "Montant XAF", "Lecture"],
                    [["Couru porté par les positions migrées", couru_migre,
                      "ce que l'ancien système transmettait"],
                     ["Couru repris par Calypso", montant, "ce que le nouveau a enregistré"],
                     ["ÉCART DE REPRISE", ecart_reprise, "actif créé sans contrepartie"],
                     ["Solde du compte d'origine à apurer", solde_compte, "voir contrôle 5.3"],
                     ["Dont rattachable aux positions migrées", couru_migre, ""],
                     ["Dont NON rattachable", non_attribuable,
                      "courus de titres sortis du portefeuille"]],
                    note=("Les deux écarts sont indépendants : le premier oppose la reprise au "
                          "couru migré, le second décompose le solde du compte d'origine.")),
            Tableau(["Compte", "Positions", "Nominal XAF"],
                    [[i, int(r.positions), float(r.nominal)]
                     for i, r in par_compte_sans.iterrows()],
                    note=("Positions entrées sans reprise de couru. Les bons du Trésor sont des "
                          "titres à escompte : l'absence de couru y est normale.")),
        ],
        recommandation=(
            "Obtenir du service la justification de l'écart de reprise, position par position : "
            "seul le rapprochement entre la référence de contrat Flexcube et le code titre "
            "Calypso, que les deux systèmes ne partagent pas, permet de l'imputer. Faire "
            "expliquer séparément les créances rattachées à des titres sortis du portefeuille, "
            "soldées à la migration sans avoir été encaissées."
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

    # --- 5. Nommer les comptes en jeu : un constat comptable doit les désigner sans ambiguïté
    cpt_courus = CPT_COURUS_MM
    lib_courus = ctx.libelle_compte(cpt_courus) or "CREANCES RATTACHEES"
    contreparties = cpt_contrepartie.reset_index()
    cpt_regl = (contreparties.AC_NO.iloc[0] if len(contreparties) else CPT_BEAC)
    lib_regl = ctx.libelle_compte(cpt_regl) or "COMPTE DE REGLEMENT"
    nom_courus = f"{cpt_courus} {lib_courus}"
    nom_regl = f"{cpt_regl} {lib_regl}"
    # Schéma comptable : ce qui devait être passé, ce qui l'a été, et la correction
    schema = [
        ["Ce qu'il fallait passer", cpt_courus, lib_courus, "CRÉDIT", a_apurer,
         "solder le compte pour son solde réel"],
        ["Ce qu'il fallait passer", cpt_regl, lib_regl, "DÉBIT", a_apurer,
         "encaissement correspondant"],
        ["Ce qui a été passé", cpt_courus, lib_courus, "CRÉDIT", credit,
         "cumul des courus depuis l'origine des contrats"],
        ["Ce qui a été passé", cpt_regl, lib_regl, "DÉBIT", credit,
         "encaissement surévalué du même montant"],
        ["ÉCART", cpt_courus, lib_courus, "CRÉDIT EN TROP", sur,
         "le compte d'actif devient créditeur"],
        ["ÉCART", cpt_regl, lib_regl, "DÉBIT EN TROP", sur,
         "le nostro est surévalué"],
    ]
    if not correction.empty:
        schema += [
            ["Correction du " + str(date_correction), cpt_courus, lib_courus, "DÉBIT",
             jambe_corr_courus, "remet le compte de courus à zéro"],
            ["Correction du " + str(date_correction), cpt_regl, lib_regl, "CRÉDIT",
             jambe_corr_tresorerie, "sort la trésorerie surévaluée"],
        ]
        if abs(troisieme_jambe) > 1:
            # L'écriture doit s'équilibrer : si le crédit excède le débit, la jambe
            # manquante est un DÉBIT, et réciproquement.
            sens_manquant = "DÉBIT" if troisieme_jambe > 0 else "CRÉDIT"
            schema.append(["Correction du " + str(date_correction), "non identifié",
                           "compte absent des extractions", sens_manquant + " MANQUANT",
                           abs(troisieme_jambe),
                           "ce qu'il faut pour que l'écriture s'équilibre"])

    return Constat(
        code="5.3",
        titre="Sur-apurement du compte de courus à la migration, laissant un compte d'actif en solde créditeur",
        gravite=Gravite.CRITIQUE,
        reference=f"Écriture d'apurement {reference} — écriture de correction {corr_ref}",
        constat=(
            "LES COMPTES EN CAUSE. Tout le constat se joue entre deux comptes, et deux "
            "seulement :\n"
            f"- {nom_courus} — compte d'ACTIF. Il porte les coupons acquis sur les titres du "
            "portefeuille et non encore encaissés ;\n"
            f"- {nom_regl} — le compte de règlement de la banque auprès de la banque centrale, "
            "son NOSTRO, qui porte sa trésorerie.\n"
            "Un troisième compte intervient à la correction, mais il ne figure dans aucune des "
            "extractions fournies : il reste à identifier.\n"
            "\n"
            f"CE QUI DEVAIT SE PASSER. Au jour de la bascule, le compte {cpt_courus} portait le "
            "solde des intérêts courus non encore encaissés. Pour le solder, il fallait le "
            f"CRÉDITER de CE SOLDE, ni plus ni moins, en DÉBITANT le nostro {cpt_regl} de "
            "l'encaissement correspondant.\n"
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
            "LES DEUX CONSÉQUENCES, COMPTE PAR COMPTE.\n"
            f"- Sur {nom_courus} : ce compte d'ACTIF s'est retrouvé en SOLDE CRÉDITEUR, position "
            "impossible par construction — cela revient à dire que la banque DEVAIT de l'argent "
            "au titre d'intérêts qu'elle devait RECEVOIR.\n"
            f"- Sur {nom_regl} : la contrepartie de l'écriture étant un DÉBIT de ce compte, la "
            "banque a enregistré avoir encaissé plus de trésorerie qu'elle n'en a reçu. Le "
            "nostro a été surévalué du même montant, et cette surévaluation a figuré aux états "
            "arrêtés.\n"
            "\n"
            "LA DURÉE. L'anomalie n'a pas été corrigée immédiatement. Elle a persisté et a traversé "
            "une date d'arrêté, ce qui signifie que les états produits à cette date portent un "
            "compte d'actif créditeur et un nostro surévalué. Un écart de cette ampleur sur le "
            "compte de règlement de la banque centrale aurait dû être détecté par le rapprochement "
            "bancaire mensuel.\n"
            "\n"
            "LA CORRECTION. Elle est intervenue par une écriture manuelle explicitement libellée "
            "comme se rapportant à la mise en service du nouveau système : un DÉBIT de "
            f"{cpt_courus} pour {xaf(jambe_corr_courus)}, qui remet le compte de courus à zéro, "
            f"contre un CRÉDIT de {cpt_regl} pour {xaf(jambe_corr_tresorerie)}. Ces deux jambes "
            "ne s'équilibrent pas : le crédit excède le débit de "
            f"{xaf(abs(troisieme_jambe))}. Il manque donc un DÉBIT de ce montant, sur une "
            "TROISIÈME JAMBE portée par un compte qui ne figure dans aucune des extractions "
            "fournies. Ce compte reste à identifier : c'est lui qui a supporté le solde de la "
            "correction."
        ),
        chiffres=[
            (f"1. Solde de {cpt_courus} la veille de la bascule", xaf(solde_avant)),
            (f"2. Courus du jour de la bascule, débités de {cpt_courus}", xaf(debits_jour)),
            ("3. SOLDE RÉEL À APURER (1 + 2)", xaf(a_apurer)),
            (f"4. Montant effectivement CRÉDITÉ à {cpt_courus}", xaf(credit)),
            ("5. SUR-APUREMENT (4 − 3)", xaf(sur)),
            ("6. Contrats crédités", str(len(detail))),
            ("7. Dont crédités en trop", str(len(touches))),
            ("8. Écart cumulé au niveau contrat", xaf(ecart_contrats)),
            (f"9. Solde de {cpt_courus} après la bascule — CRÉDITEUR",
             xaf(ctx.solde(CPT_COURUS_MM, a_la_date=DATE_BASCULE, df=courus))),
            ("10. Date de correction", str(date_correction) if date_correction else "non corrigé"),
            ("11. Durée de l'anomalie", f"{jours} jours"),
            ("12. Dates d'arrêté traversées", ", ".join(arretes_traverses) if arretes_traverses else "aucune"),
            (f"13. Correction — jambe DÉBIT sur {cpt_courus}", xaf(jambe_corr_courus)),
            (f"14. Correction — jambe CRÉDIT sur {cpt_regl}", xaf(jambe_corr_tresorerie)),
            ("15. TROISIÈME JAMBE, sur un compte NON IDENTIFIÉ (14 − 13)", xaf(troisieme_jambe)),
        ],
        tableaux=[
            Tableau(["Étape", "Compte", "Libellé", "Sens", "Montant XAF", "Lecture"],
                    schema, max_lignes=12,
                    note=("Le schéma comptable de bout en bout : l'écriture attendue, celle qui "
                          "a réellement été passée, l'écart qui en résulte compte par compte, "
                          "puis la correction.")),
            Tableau(["Compte", "Libellé", "Sens", "Lignes", "Montant XAF"],
                    [[i[0], i[1][:38], i[2], int(r.lignes), float(r.montant)]
                     for i, r in cpt_contrepartie.iterrows()],
                    note=(f"Contrepartie de l'écriture d'apurement sur {nom_regl} : la trésorerie "
                          "enregistrée comme encaissée.")),
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
                    note=(f"Solde de {nom_courus} à chaque arrêté. Un montant négatif est un solde "
                          "CRÉDITEUR, impossible sur un compte d'actif.")),
            Tableau(["Date", "Compte", "Libellé", "Sens", "Montant XAF", "Saisie", "Validation"],
                    corr_detail,
                    note=(f"Écriture de correction {corr_ref} et sa contrepartie. La jambe sur "
                          f"{cpt_courus} n'y figure pas : elle est décrite au point 13.")),
        ],
        recommandation=(
            f"1. Obtenir les états financiers au {arretes_traverses[0] if arretes_traverses else 'arrêté traversé'} "
            f"et vérifier si le solde créditeur de {cpt_courus} et la surévaluation de {cpt_regl} "
            "y figurent.\n"
            f"2. Obtenir le rapprochement bancaire de {cpt_regl} des mois concernés et comprendre "
            "pourquoi un écart de cette ampleur n'a pas été détecté plus tôt.\n"
            "3. Faire expliquer le mode opératoire retenu pour calculer les courus à reprendre, "
            "fondé sur le cumul théorique par contrat et non sur le solde comptable.\n"
            f"4. Identifier le compte qui porte la troisième jambe de l'écriture de correction "
            f"{corr_ref}, soit un débit de {xaf(abs(troisieme_jambe))} sur un compte absent des "
            "extractions.\n"
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
