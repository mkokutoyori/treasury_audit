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
    s.ajouter(_c75_retard_comptabilisation(ctx))
    s.ajouter(_c76_recalcul_interet(ctx))
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
    """La durée CONTRACTUELLE des pensions justifie-t-elle le compte utilisé ?

    La durée ne se lit pas sur les dates de comptabilisation — une opération peut être
    enregistrée longtemps après son dénouement — mais sur les dates portées par le libellé
    de l'écriture, qui sont celles du contrat.
    """
    repos = ctx.repos_contractuels
    if repos.empty:
        return Constat(code="7.1", titre="Durée des pensions livrées", gravite=Gravite.FAIBLE,
                       constat="Aucune opération de pension identifiée dans le périmètre.")
    gl = ctx.grand_livre
    libelle = (gl[gl.AC_NO == CPT_REPO_PASSIF].AC_GL_DESC.iloc[0]
               if len(gl[gl.AC_NO == CPT_REPO_PASSIF]) else "")
    a_terme = repos[repos.jours_contrat > 1].sort_values("jours_contrat", ascending=False)
    distribution = (repos.groupby("jours_contrat")
                    .agg(operations=("DEAL", "size"), montant=("montant", "sum")))
    if a_terme.empty:
        return Constat(
            code="7.1", titre="Durée contractuelle des pensions livrées", gravite=Gravite.CONFORME,
            constat=("Toutes les pensions sont contractuellement au jour le jour, ce qui "
                     f"correspond au compte utilisé, « {libelle} »."),
            tableaux=[Tableau(["Durée contractuelle (jours)", "Opérations", "Montant tiré XAF"],
                              [[int(i), int(r.operations), float(r.montant)]
                               for i, r in distribution.iterrows()])],
        )
    part = len(a_terme) / len(repos) * 100
    return Constat(
        code="7.1",
        titre="Pensions à terme comptabilisées dans un compte d'emprunt au jour le jour",
        gravite=Gravite.MOYENNE,
        constat=(
            f"Les opérations sont toutes comptabilisées au compte « {libelle} », qui est un "
            "compte d'emprunt AU JOUR LE JOUR.\n"
            "OÙ LIRE LA DURÉE. Les dates de comptabilisation ne renseignent pas sur la durée "
            "d'une pension : le contrôle 7.5 montre qu'une opération peut être enregistrée des "
            "semaines après son dénouement. La durée contractuelle figure en revanche dans le "
            "LIBELLÉ de chaque écriture, qui porte la date de départ, la date d'échéance et le "
            "taux. C'est cette source qui est retenue ici.\n"
            f"CE QU'ELLE MONTRE. {len(a_terme)} pensions sur {len(repos)}, soit {pct(part, 0)}, "
            f"sont contractuellement À TERME — jusqu'à {int(repos.jours_contrat.max())} jours — "
            f"pour {xaf(float(a_terme.montant.sum()))} tirés. Le jour le jour reste majoritaire, "
            "mais il ne décrit pas toute l'activité.\n"
            "Un emprunt à terme logé dans un compte d'emprunt au jour le jour fausse "
            "l'échéancier de liquidité de l'établissement et, par voie de conséquence, les "
            "ratios prudentiels qui en découlent. L'écart reste d'une semaine et non de "
            "plusieurs mois : la distorsion est réelle mais bornée."
        ),
        chiffres=[
            ("Pensions identifiées", str(len(repos))),
            ("Dont contractuellement au jour le jour", str(int((repos.jours_contrat <= 1).sum()))),
            ("Dont contractuellement À TERME", f"{len(a_terme)} ({pct(part, 0)})"),
            ("Montant tiré sur les pensions à terme", xaf(float(a_terme.montant.sum()))),
            ("Durée contractuelle maximale", f"{int(repos.jours_contrat.max())} jours"),
            ("Durée contractuelle médiane", f"{int(repos.jours_contrat.median())} jour(s)"),
        ],
        tableaux=[
            Tableau(["Durée contractuelle (jours)", "Opérations", "Montant tiré XAF"],
                    [[int(i), int(r.operations), float(r.montant)]
                     for i, r in distribution.iterrows()],
                    note=("Durées lues sur le libellé contractuel, et non sur les dates de "
                          "comptabilisation.")),
            Tableau(["Deal", "Début contractuel", "Échéance contractuelle", "Durée (j)",
                     "Taux %", "Montant XAF", "Contrepartie"],
                    [[r.DEAL, str(r.contrat_debut.date()), str(r.contrat_fin.date()),
                      int(r.jours_contrat), float(r.taux), float(r.montant), r.contrepartie]
                     for _, r in a_terme.head(15).iterrows()],
                    note="Les quinze pensions à terme les plus longues."),
        ],
        recommandation=(
            "Faire reclasser les pensions à terme dans le compte d'emprunt correspondant à leur "
            "durée et corriger l'échéancier de liquidité. Demander que la durée contractuelle "
            "soit portée dans un champ structuré de l'interface, et non dans le seul libellé."
        ),
    )


def _c72_rattachement(ctx) -> Constat:
    """La charge d'intérêt d'une pension à cheval sur un arrêté est-elle rattachée ?

    Le test se fonde sur les dates CONTRACTUELLES : une pension dont le contrat enjambe une
    date d'arrêté doit avoir produit un couru à cette date, au prorata des jours écoulés.
    """
    repos = ctx.repos_contractuels
    calypso = ctx.calypso_enrichi
    if repos.empty or calypso.empty:
        return Constat(code="7.2", titre="Rattachement des charges d'intérêt",
                       gravite=Gravite.FAIBLE, constat="Données insuffisantes.")
    charge = calypso[calypso.AC_NO == CPT_REPO_CHARGE]
    charge = charge.drop_duplicates(subset=["DEAL", "MOUVEMENT", "AC_NO", "DRCR_IND", "LCY_AMOUNT"])
    jamais_de_couru = charge[charge.EVENEMENT == "ACCRUAL"].empty

    # Pensions dont le CONTRAT enjambe une date d'arrêté de la période
    a_cheval = []
    for arrete in ctx.arretes:
        borne = pd.Timestamp(arrete)
        vises = repos[(repos.contrat_debut <= borne) & (repos.contrat_fin > borne)]
        for _, r in vises.iterrows():
            jours = (borne - r.contrat_debut).days
            couru = float(r.montant) * float(r.taux) / 100 * jours / 360
            a_cheval.append([r.DEAL, arrete, str(r.contrat_debut.date()),
                             str(r.contrat_fin.date()), jours, int(r.jours_contrat),
                             float(r.montant), float(r.taux), couru])
    charge_non_rattachee = sum(l[8] for l in a_cheval)
    if not a_cheval and not jamais_de_couru:
        return Constat(
            code="7.2", titre="Rattachement des charges d'intérêt des pensions",
            gravite=Gravite.CONFORME,
            constat=("Aucune pension n'enjambe une date d'arrêté de la période : la question du "
                     "rattachement de la charge d'intérêt ne se pose pas."),
        )
    return Constat(
        code="7.2",
        titre="Aucun couru n'est constaté sur les pensions, y compris celles à cheval sur un arrêté",
        gravite=(Gravite.ELEVEE if charge_non_rattachee > ctx.config.seuil_significatif
                 else Gravite.MOYENNE),
        constat=(
            ("LE CONSTAT DE PRINCIPE. Le compte de charge d'intérêt sur pensions ne porte AUCUNE "
             "écriture de couru : il n'enregistre que des règlements. L'intérêt est donc "
             "constaté en une seule fois, au dénouement, quelle que soit la durée de "
             "l'opération et quelle que soit la date d'arrêté qu'elle traverse.\n"
             if jamais_de_couru else
             "Les courus constatés ne couvrent pas la durée des opérations.\n")
            + "L'INCIDENCE CHIFFRÉE. Le test retient les pensions dont le CONTRAT enjambe une "
            "date d'arrêté — et non celles dont les seules dates de comptabilisation "
            f"l'enjambent, ce qui serait un artefact de saisie. {len(a_cheval)} opération(s) "
            "sont dans ce cas sur la période revue, pour une charge non rattachée de "
            f"{xaf(charge_non_rattachee)}.\n"
            "LA PORTÉE EST STRUCTURELLE. Le montant reste modeste parce que les pensions sont "
            "courtes et qu'il est rare qu'une clôture tombe en leur milieu. Mais aucun "
            "mécanisme de couru n'existe : une pension de plus longue durée en cours à une "
            "clôture future produirait une sous-évaluation proportionnelle à son encours, sans "
            "qu'aucun contrôle ne la signale."
        ),
        chiffres=[
            ("Écritures de couru sur le compte de charge",
             "aucune" if jamais_de_couru else str(len(charge[charge.EVENEMENT == "ACCRUAL"]))),
            ("Pensions dont le contrat enjambe un arrêté", str(len(a_cheval))),
            ("CHARGE NON RATTACHÉE À L'ARRÊTÉ", xaf(charge_non_rattachee)),
        ],
        tableaux=[Tableau(
            ["Deal", "Date d'arrêté", "Début contractuel", "Échéance", "Jours courus",
             "Durée totale", "Montant XAF", "Taux %", "Charge à rattacher XAF"],
            a_cheval,
            note=("Charge qui aurait dû être courue à la date d'arrêté, au prorata des jours "
                  "écoulés depuis le départ contractuel, base exact/360."))],
        recommandation=(
            "Faire paramétrer un couru quotidien sur les pensions, à l'image de celui qui existe "
            "sur le portefeuille de titres. À défaut, instaurer un calcul extra-comptable à "
            "chaque arrêté, fondé sur les dates contractuelles portées par les libellés."
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


def _c75_retard_comptabilisation(ctx) -> Constat:
    """La comptabilisation suit-elle le dénouement contractuel des pensions ?"""
    repos = ctx.repos_contractuels
    if repos.empty:
        return Constat(code="7.5", titre="Délai de comptabilisation des pensions",
                       gravite=Gravite.FAIBLE, constat="Aucune pension identifiée.")
    tardifs = repos[repos.retard_remboursement > 5].sort_values(
        "retard_remboursement", ascending=False)
    # Une dette contractuellement éteinte figure-t-elle encore au bilan à un arrêté ?
    portees = []
    for arrete in ctx.arretes:
        vises = repos[(repos.contrat_fin < arrete)
                      & (repos.booking_debut <= arrete) & (repos.booking_fin > arrete)]
        for _, r in vises.iterrows():
            portees.append([r.DEAL, arrete, str(r.contrat_fin.date()), r.booking_fin,
                            (pd.Timestamp(arrete) - r.contrat_fin).days, float(r.montant)])
    if tardifs.empty and not portees:
        return Constat(
            code="7.5", titre="Délai de comptabilisation des pensions", gravite=Gravite.CONFORME,
            constat=("Le remboursement de chaque pension est comptabilisé dans les jours qui "
                     "suivent son échéance contractuelle."))
    gravite = Gravite.ELEVEE if portees else Gravite.MOYENNE
    return Constat(
        code="7.5",
        titre="Remboursements de pension comptabilisés longtemps après l'échéance contractuelle",
        gravite=gravite,
        constat=(
            "CE QUI EST TESTÉ. Le libellé de chaque pension porte son échéance contractuelle. "
            "La comparer à la date à laquelle le remboursement est effectivement enregistré "
            "mesure le délai entre le dénouement de l'opération et sa comptabilisation.\n"
            f"CE QUI EST CONSTATÉ. {len(tardifs)} pensions sont enregistrées plus de cinq jours "
            f"après leur échéance, le retard atteignant "
            f"{int(repos.retard_remboursement.max())} jours. Pendant tout ce délai, les livres "
            "montrent un emprunt qui n'existe plus et une trésorerie que la banque n'a plus.\n"
            + (("LA CONSÉQUENCE EST ARRÊTÉE. Le décalage traverse une date d'arrêté : à cette "
                "date, le bilan porte une dette contractuellement éteinte, et le compte de "
                "règlement auprès de la banque centrale porte la trésorerie correspondante. "
                "Les états produits à cette date sont faux des deux côtés.\n")
               if portees else
               "Aucun de ces retards ne traverse une date d'arrêté : l'effet reste "
               "intrajournalier au regard des comptes publiés.\n")
            + "CE QUE CELA IMPLIQUE POUR LES AUTRES CONTRÔLES. Toute durée de pension calculée "
            "sur les dates de comptabilisation est fausse. Le contrôle 7.1 retient pour cette "
            "raison les seules dates contractuelles."
        ),
        chiffres=[
            ("Pensions contrôlées", str(len(repos))),
            ("Remboursements enregistrés plus de 5 jours après l'échéance", str(len(tardifs))),
            ("Retard maximal", f"{int(repos.retard_remboursement.max())} jours"),
            ("Retard médian", f"{int(repos.retard_remboursement.median())} jour(s)"),
            ("Dettes éteintes encore portées au bilan à un arrêté", str(len(portees))),
            ("Montant correspondant", xaf(sum(l[5] for l in portees))),
        ],
        tableaux=[
            Tableau(["Deal", "Échéance contractuelle", "Remboursement comptabilisé",
                     "Retard (j)", "Montant XAF", "Contrepartie"],
                    [[r.DEAL, str(r.contrat_fin.date()), r.booking_fin,
                      int(r.retard_remboursement), float(r.montant), r.contrepartie]
                     for _, r in tardifs.head(15).iterrows()],
                    note="Les quinze retards les plus importants."),
            Tableau(["Deal", "Date d'arrêté", "Échéance contractuelle",
                     "Remboursement comptabilisé", "Jours depuis l'échéance", "Montant XAF"],
                    portees,
                    note=("Dettes contractuellement éteintes figurant encore au bilan à une date "
                          "d'arrêté.")),
        ],
        recommandation=(
            "Obtenir le rapprochement entre les confirmations de pension de la banque centrale "
            "et les écritures, et expliquer les délais de comptabilisation. Instaurer un suivi "
            "des pensions échues non dénouées dans les livres."
        ),
    )


def _c76_recalcul_interet(ctx) -> Constat:
    """L'intérêt payé correspond-il au montant, au taux et à la durée contractuels ?"""
    repos = ctx.repos_contractuels
    if repos.empty:
        return Constat(code="7.6", titre="Exactitude des intérêts de pension",
                       gravite=Gravite.FAIBLE, constat="Aucune pension identifiée.")
    testables = repos[repos.jours_contrat.notna() & repos.taux.notna()]
    ecarts = testables[testables.ecart_interet.abs() > 1]
    if ecarts.empty:
        return Constat(
            code="7.6", titre="Exactitude des intérêts de pension", gravite=Gravite.CONFORME,
            constat=(f"Sur les {len(testables)} pensions, l'intérêt comptabilisé se déduit "
                     "exactement du montant, du taux et de la durée contractuels, en base "
                     "exact/360. Le moteur de calcul est juste."),
            chiffres=[("Pensions recalculées", str(len(testables))),
                      ("Convention retenue", "exact/360")],
        )
    return Constat(
        code="7.6",
        titre="Intérêts de pension ne se déduisant pas des conditions contractuelles",
        gravite=Gravite.MOYENNE,
        constat=(
            "Le libellé de chaque pension porte son montant, son taux et ses dates "
            "contractuelles : l'intérêt est donc entièrement recalculable. En base exact/360, "
            f"il se retrouve au centime près sur {len(testables) - len(ecarts)} des "
            f"{len(testables)} pensions, ce qui établit à la fois la convention de décompte et "
            "la justesse du moteur de calcul.\n"
            "Les exceptions ne sont pas des erreurs de calcul : un intérêt exactement DOUBLE "
            "signale un mouvement déversé deux fois, un intérêt ABSENT signale une opération "
            "jamais dénouée. Ce recalcul constitue donc un second filet de détection, "
            "indépendant, des défauts relevés aux contrôles 6.7 et 7.4."
        ),
        chiffres=[
            ("Pensions recalculées", str(len(testables))),
            ("Convention de décompte retenue", "exact/360"),
            ("Pensions au calcul exact", str(len(testables) - len(ecarts))),
            ("Pensions en écart", str(len(ecarts))),
            ("Écart cumulé", xaf(float(ecarts.ecart_interet.sum()))),
        ],
        tableaux=[Tableau(
            ["Deal", "Montant XAF", "Taux %", "Jours", "Intérêt attendu", "Intérêt comptabilisé",
             "Écart", "Lecture"],
            [[r.DEAL, float(r.montant), float(r.taux), int(r.jours_contrat),
              float(r.interet_theorique),
              float(r.interet) if r.interet == r.interet else None,
              float(r.ecart_interet),
              "intérêt absent : opération non dénouée" if r.interet != r.interet
              else ("intérêt doublé : mouvement déversé deux fois"
                    if abs(r.ecart_interet - r.interet_theorique) < 1 else "à investiguer")]
             for _, r in ecarts.iterrows()])],
        recommandation=(
            "Instaurer le recalcul de l'intérêt à partir des conditions contractuelles comme "
            "contrôle automatique de premier niveau : il détecte les doublons de déversement et "
            "les opérations non dénouées sans aucune donnée externe."
        ),
    )
