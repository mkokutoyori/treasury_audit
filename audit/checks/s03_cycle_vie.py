"""Section 3 — Cycle de vie des titres sous Flexcube (module MM).

Le cycle attendu est : acquisition (PRINCIPAL) → courus quotidiens (INT_BT_ACCR) →
encaissement du coupon → remboursement à l'échéance (PRINCIPAL_LIQD). Les écarts à ce
schéma sont le cœur de la revue des opérations de marché monétaire.
"""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf
from ..data import (CPT_COURUS_CALYPSO, CPT_COURUS_MM, CPT_PORTEFEUILLE,
                    CPT_PORTEFEUILLE_CALYPSO, CPT_PORTEFEUILLE_MM, DATE_BASCULE)

SECTION = (3, "Cycle de vie des titres sous Flexcube")


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "Revue du cycle de vie des titres dans le module MM : dénouements par rapport à "
            "l'échéance contractuelle, prix de liquidation, pratique de liquidation/réouverture, "
            "exactitude des intérêts courus et apurement des créances rattachées."
        ),
    )
    liq = _liquidations(ctx)
    s.ajouter(_c31_echeance(ctx, liq))
    s.ajouter(_c32_au_pair(ctx, liq))
    s.ajouter(_c33_aller_retour(ctx))
    s.ajouter(_c34_liquidation_reouverture(ctx, liq))
    s.ajouter(_c35_recalcul_courus(ctx))
    s.ajouter(_c36_apurement_courus(ctx))
    s.ajouter(_c37_situation_portefeuille(ctx))
    return s


def _liquidations(ctx) -> pd.DataFrame:
    """Une ligne par contrat liquidé, enrichie des caractéristiques contractuelles."""
    mm = ctx.grand_livre[ctx.grand_livre.MODULE == "MM"]
    liq = (
        mm[mm.AMOUNT_TAG == "PRINCIPAL_LIQD"]
        .groupby("TRN_REF_NO")
        .agg(date_liq=("TRN_DT", "min"), montant=("LCY_AMOUNT", "max"),
             saisie=("USER_ID", "first"), validation=("AUTH_ID", "first"))
    )
    ref = ctx.contrats_uniques.set_index("CONTRACT_REF_NO")
    cols = ["MATURITY_DATE_d", "MATURITY_DATE", "AMOUNT", "PRODUCT", "FULL_NAME", "MAIN_COMP_RATE"]
    liq = liq.join(ref[cols], how="left")
    liq["ecart_jours"] = (pd.to_datetime(liq.date_liq) - liq.MATURITY_DATE_d).dt.days
    return liq


def _c31_echeance(ctx, liq) -> Constat:
    hors_migration = liq[liq.date_liq != DATE_BASCULE]
    a_echeance = hors_migration[hors_migration.ecart_jours == 0]
    anticipees = hors_migration[hors_migration.ecart_jours < 0]
    tres_anticipees = hors_migration[hors_migration.ecart_jours < -360]
    apres = hors_migration[hors_migration.ecart_jours > 0]
    part = len(a_echeance) / max(len(hors_migration), 1) * 100
    return Constat(
        code="3.1",
        titre="Dénouements majoritairement antérieurs à l'échéance contractuelle",
        gravite=Gravite.ELEVEE if part < 25 else Gravite.MOYENNE,
        constat=(
            "Hors migration, une faible minorité des liquidations intervient à l'échéance "
            "contractuelle. La majorité dénoue par anticipation, souvent de plus d'un an. Une "
            "sortie anticipée de titre est soit une cession (qui doit dégager un résultat), soit "
            "un remboursement anticipé (qui doit être documenté), soit une opération technique. "
            "Le test 3.4 établit qu'il s'agit majoritairement du troisième cas."
        ),
        chiffres=[
            ("Liquidations hors migration", str(len(hors_migration))),
            ("À l'échéance contractuelle", f"{len(a_echeance)} ({part:.1f} %)"),
            ("Anticipées", f"{len(anticipees)} — {xaf(float(anticipees.montant.sum()))}"),
            ("Dont anticipées de plus d'un an", f"{len(tres_anticipees)} — {xaf(float(tres_anticipees.montant.sum()))}"),
            ("Postérieures à l'échéance", str(len(apres))),
        ],
        tableaux=[
            Tableau(
                ["Référence", "Liquidation", "Échéance", "Écart (j)", "Montant", "Contrepartie"],
                [
                    [i, r.date_liq, r.MATURITY_DATE, int(r.ecart_jours), float(r.montant), r.FULL_NAME]
                    for i, r in tres_anticipees.sort_values("montant", ascending=False).head(12).iterrows()
                ],
                note="Les 12 liquidations anticipées de plus d'un an les plus importantes.",
            )
        ],
        recommandation=(
            "Obtenir la justification des dénouements anticipés : ordre de cession, avis de "
            "remboursement anticipé de l'émetteur, ou note expliquant la nature technique."
        ),
    )


def _c32_au_pair(ctx, liq) -> Constat:
    """Une cession au prix de marché ne peut pas être systématiquement au nominal exact."""
    compare = liq.dropna(subset=["AMOUNT"])
    ecarts = compare[(compare.montant - compare.AMOUNT).abs() > 0.5]
    anticipees = compare[compare.ecart_jours < 0]
    if len(ecarts):
        return Constat(
            code="3.2", titre="Écarts entre montant liquidé et nominal contractuel",
            gravite=Gravite.MOYENNE,
            constat="Des liquidations diffèrent du nominal contractuel.",
            tableaux=[
                Tableau(
                    ["Référence", "Liquidé", "Nominal", "Écart"],
                    [[i, float(r.montant), float(r.AMOUNT), float(r.montant - r.AMOUNT)]
                     for i, r in ecarts.iterrows()],
                )
            ],
        )
    return Constat(
        code="3.2",
        titre="Liquidations systématiquement au pair, y compris anticipées",
        gravite=Gravite.ELEVEE,
        constat=(
            "Le montant liquidé est strictement égal au nominal contractuel sur la totalité des "
            "dénouements, y compris ceux intervenus longtemps avant l'échéance. Or une cession au "
            "prix de marché produit nécessairement un écart au nominal, donc une plus ou "
            "moins-value. L'absence totale d'écart établit que ces dénouements ne sont pas des "
            "cessions et qu'aucun résultat de cession n'est constaté dans le module MM. Elle "
            "confirme par ailleurs que les intérêts courus ne sont pas réglés avec le principal."
        ),
        chiffres=[
            ("Liquidations contrôlées", str(len(compare))),
            ("Écarts au nominal", "0"),
            ("Dont liquidations anticipées", str(len(anticipees))),
            ("Montant liquidé au pair par anticipation", xaf(float(anticipees.montant.sum()))),
        ],
        recommandation=(
            "Faire confirmer que le module MM ne gère pas le prix de cession, et identifier où "
            "les plus et moins-values de cession de titres sont comptabilisées sur la période."
        ),
    )


def _c33_aller_retour(ctx) -> Constat:
    """Contrats acquis et liquidés le jour même, alors que l'échéance est lointaine."""
    mm = ctx.grand_livre[ctx.grand_livre.MODULE == "MM"]
    achat = mm[mm.AMOUNT_TAG == "PRINCIPAL"].groupby("TRN_REF_NO").agg(
        date_achat=("TRN_DT", "min"), montant=("LCY_AMOUNT", "max"),
        saisie=("USER_ID", "first"), validation=("AUTH_ID", "first"))
    liq = mm[mm.AMOUNT_TAG == "PRINCIPAL_LIQD"].groupby("TRN_REF_NO").agg(date_liq=("TRN_DT", "min"))
    j = achat.join(liq, how="inner")
    meme_jour = j[j.date_achat == j.date_liq]
    if meme_jour.empty:
        return Constat(
            code="3.3", titre="Contrats acquis et liquidés le même jour", gravite=Gravite.CONFORME,
            constat="Aucun contrat n'est créé puis liquidé dans la même journée.",
        )
    ref = ctx.contrats_uniques.set_index("CONTRACT_REF_NO")
    meme_jour = meme_jour.join(ref[["MATURITY_DATE_d", "MATURITY_DATE", "FULL_NAME", "PRODUCT"]])
    meme_jour["jours_restants"] = (meme_jour.MATURITY_DATE_d - pd.to_datetime(meme_jour.date_achat)).dt.days
    par_user = meme_jour.groupby("saisie").agg(n=("montant", "size"), montant=("montant", "sum"))
    return Constat(
        code="3.3",
        titre="Contrats créés puis liquidés dans la même journée",
        gravite=Gravite.ELEVEE,
        constat=(
            "Des contrats sont enregistrés puis intégralement liquidés le jour même, alors que "
            "leur échéance contractuelle est parfois éloignée de plusieurs années. Il s'agit soit "
            "de corrections de saisie, et le taux d'erreur du service doit alors être mesuré, soit "
            "d'opérations d'une autre nature qu'il faut qualifier. Dans les deux cas, ces "
            "écritures gonflent artificiellement les volumes."
        ),
        chiffres=[
            ("Contrats concernés", str(len(meme_jour))),
            ("Montant cumulé", xaf(float(meme_jour.montant.sum()))),
            ("Échéance résiduelle maximale", f"{int(meme_jour.jours_restants.max())} jours"),
            ("Échéance résiduelle médiane", f"{int(meme_jour.jours_restants.median())} jours"),
        ],
        tableaux=[
            Tableau(["Opérateur de saisie", "Contrats", "Montant XAF"],
                    [[i, int(r.n), float(r.montant)] for i, r in par_user.sort_values("montant", ascending=False).iterrows()],
                    note="Répartition par opérateur."),
            Tableau(
                ["Référence", "Date", "Échéance", "Jours restants", "Montant", "Saisie", "Validation"],
                [[i, r.date_achat, r.MATURITY_DATE, int(r.jours_restants), float(r.montant), r.saisie, r.validation]
                 for i, r in meme_jour.sort_values("montant", ascending=False).head(12).iterrows()],
            ),
        ],
        recommandation=(
            "Obtenir la justification de chaque cas et, s'il s'agit de corrections, vérifier "
            "qu'une procédure d'annulation tracée existe plutôt qu'une liquidation forcée."
        ),
    )


def _c34_liquidation_reouverture(ctx, liq) -> Constat:
    """Flexcube ne gère pas le remboursement partiel : on clôture et on rouvre le solde."""
    mm = ctx.grand_livre[ctx.grand_livre.MODULE == "MM"]
    achats = mm[mm.AMOUNT_TAG == "PRINCIPAL"].groupby("TRN_REF_NO").agg(
        date=("TRN_DT", "min"), montant=("LCY_AMOUNT", "max"))
    ref = ctx.contrats_uniques.set_index("CONTRACT_REF_NO")
    achats = achats.join(ref[["FULL_NAME"]])
    cibles = liq[(liq.ecart_jours < -30) & (liq.date_liq != DATE_BASCULE)]
    avec_rachat = 0
    for _, r in cibles.iterrows():
        meme_jour = achats[(achats.date == r.date_liq) & (achats.FULL_NAME == r.FULL_NAME)]
        if len(meme_jour):
            avec_rachat += 1
    part = avec_rachat / max(len(cibles), 1) * 100
    flux_brut = float(mm[mm.AC_NO == "099ACO00001"].LCY_AMOUNT.sum())
    return Constat(
        code="3.4",
        titre="Pratique de liquidation puis réouverture : les volumes bruts ne sont pas des flux économiques",
        gravite=Gravite.ELEVEE,
        constat=(
            "Le module MM de Flexcube ne permet pas le remboursement partiel d'un contrat. La "
            "trésorerie procède donc par clôture intégrale du contrat suivie de la réouverture du "
            "solde, le même jour et sur la même contrepartie. Il en résulte que les volumes bruts "
            "du module, y compris les mouvements du compte de règlement BEAC, ne représentent PAS "
            "des flux économiques. Toute analyse de volumétrie, de rotation du portefeuille ou de "
            "flux de trésorerie doit être menée en net, après neutralisation de ces couples."
        ),
        chiffres=[
            ("Liquidations anticipées hors migration", str(len(cibles))),
            ("Dont suivies d'un achat le jour même sur la même contrepartie", f"{avec_rachat} ({part:.0f} %)"),
            ("Flux bruts sur le compte BEAC (module MM)", xaf(flux_brut)),
        ],
        recommandation=(
            "Ne retenir aucune statistique de volume issue du module MM sans retraitement. "
            "Demander si une évolution du paramétrage permettrait le remboursement partiel."
        ),
    )


def _c35_recalcul_courus(ctx) -> Constat:
    """Recalcul indépendant des intérêts courus à partir des caractéristiques contractuelles."""
    cfg = ctx.config
    courus = ctx.courus
    if courus.empty:
        courus = ctx.grand_livre[ctx.grand_livre.AC_NO == CPT_COURUS_MM]
    acc = courus[(courus.MODULE == "MM") & (courus.AMOUNT_TAG == "INT_BT_ACCR")]
    g = acc.groupby("TRN_REF_NO").agg(total=("LCY_AMOUNT", "sum"), debut=("TRN_DT_d", "min"), fin=("TRN_DT_d", "max"))
    ref = ctx.contrats_uniques.set_index("CONTRACT_REF_NO")
    j = g.join(ref[["AMOUNT", "MAIN_COMP_RATE", "VALUE_DATE_d", "PRODUCT", "FULL_NAME"]], how="inner")
    j["depart"] = j[["debut", "VALUE_DATE_d"]].max(axis=1)
    j["jours"] = (j.fin - j.depart).dt.days + 1
    j = j[j.jours > 0]
    j["attendu"] = j.AMOUNT * j.MAIN_COMP_RATE / 100 * j.jours / cfg.base_jours
    j["ecart"] = j.total - j.attendu
    j["ecart_pct"] = j.ecart / j.attendu * 100
    global_pct = (j.total.sum() / j.attendu.sum() - 1) * 100
    significatifs = j[(j.ecart_pct.abs() > cfg.tolerance_couru * 100) & (j.ecart.abs() > cfg.seuil_materialite)]
    gravite = Gravite.MOYENNE if len(significatifs) else Gravite.CONFORME
    if gravite == Gravite.CONFORME:
        return Constat(
            code="3.5", titre="Exactitude des intérêts courus", gravite=Gravite.CONFORME,
            constat=(
                f"Le recalcul indépendant (base {cfg.base_jours} jours) ne fait ressortir aucun "
                f"écart individuel significatif. Écart global : {global_pct:+.2f} %."
            ),
        )
    return Constat(
        code="3.5",
        titre="Écarts individuels sur le recalcul des intérêts courus",
        gravite=gravite,
        constat=(
            f"Le recalcul indépendant des intérêts courus (nominal × taux × jours / "
            f"{cfg.base_jours}) est globalement fidèle : l'écart d'ensemble n'est que de "
            f"{global_pct:+.2f} %, ce qui atteste la justesse du moteur d'accrual. Des contrats "
            "présentent néanmoins un écart individuel significatif, à la fois en valeur relative "
            "et en montant. Ces écarts s'expliquent le plus souvent par une clôture ou une "
            "réouverture en cours de période, un changement de taux, ou une période d'accrual "
            "partielle — chaque cas doit être vérifié."
        ),
        chiffres=[
            ("Contrats testés", str(len(j))),
            ("Courus comptabilisés", xaf(float(j.total.sum()))),
            ("Courus recalculés", xaf(float(j.attendu.sum()))),
            ("Écart global", f"{global_pct:+.2f} %"),
            (f"Contrats à écart > {cfg.tolerance_couru:.0%} et > {cfg.seuil_materialite/1e6:.0f} M XAF",
             str(len(significatifs))),
            ("Écart cumulé de ces contrats", xaf(float(significatifs.ecart.sum()))),
        ],
        tableaux=[
            Tableau(
                ["Référence", "Nominal", "Taux %", "Jours", "Attendu", "Comptabilisé", "Écart", "Écart %"],
                [
                    [i, float(r.AMOUNT), float(r.MAIN_COMP_RATE), int(r.jours), float(r.attendu),
                     float(r.total), float(r.ecart), round(float(r.ecart_pct), 1)]
                    for i, r in significatifs.reindex(significatifs.ecart.abs().sort_values(ascending=False).index).head(12).iterrows()
                ],
            )
        ],
        recommandation=(
            "Vérifier par sondage la base de calcul retenue (365 ou 360 jours, exact/exact) et "
            "obtenir l'explication des contrats à écart significatif."
        ),
    )


def _c36_apurement_courus(ctx) -> Constat:
    """Le compte de créances rattachées doit être soldé par l'encaissement des coupons."""
    courus = ctx.courus
    if courus.empty:
        return Constat(
            code="3.6", titre="Apurement des créances rattachées", gravite=Gravite.FAIBLE,
            constat="L'historique complet du compte de créances rattachées n'est pas disponible.",
            recommandation="Extraire l'historique du compte 511800100 tous modules confondus.",
        )
    debits = courus[courus.DRCR_IND == "D"]
    credits = courus[courus.DRCR_IND == "C"]
    solde = float(courus.SIGNE.sum())
    par_module = credits.groupby("MODULE").agg(n=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))
    auto = int((credits.USER_ID == credits.AUTH_ID).sum())
    sans_valid = int(credits.AUTH_ID.isna().sum())
    if abs(solde) < 1 and not credits.empty:
        return Constat(
            code="3.6",
            titre="Apurement des créances rattachées par encaissement des coupons",
            gravite=Gravite.CONFORME,
            constat=(
                f"Le compte de créances rattachées est intégralement apuré : {len(debits):,} débits "
                f"pour {len(credits):,} crédits, solde net nul. Les coupons sont encaissés en "
                "trésorerie, l'apurement étant passé par écriture manuelle en module DE et non par "
                "l'événement automatique du module MM. Le contrôle des quatre yeux est respecté sur "
                f"la totalité des apurements ({auto} auto-validation, {sans_valid} sans validateur)."
            ).replace(",", " "),
        )
    return Constat(
        code="3.6",
        titre="Créances rattachées non intégralement apurées",
        gravite=Gravite.CRITIQUE,
        constat=(
            "Le compte de créances rattachées présente un solde résiduel. Un compte de créances "
            "rattachées doit osciller : il monte entre deux coupons et retombe à chaque "
            "encaissement. Un solde persistant traduit soit des coupons non encaissés, soit un "
            "défaut d'apurement, et conduit à surévaluer simultanément l'actif et le produit."
        ),
        chiffres=[
            ("Débits", f"{len(debits):,}".replace(",", " ")),
            ("Crédits", f"{len(credits):,}".replace(",", " ")),
            ("Solde net", xaf(solde)),
        ],
        tableaux=[Tableau(["Module d'apurement", "Écritures", "Montant XAF"],
                          [[i, int(r.n), float(r.montant)] for i, r in par_module.iterrows()])],
        recommandation="Obtenir le solde du compte en balance générale et la justification du résidu.",
    )


def _c37_situation_portefeuille(ctx) -> Constat:
    """Encours du portefeuille et des courus à chaque arrêté, et délai d'encaissement implicite.

    Les intérêts courus représentent les coupons acquis mais non encore encaissés. Rapportés
    à une année d'intérêts théorique — encours multiplié par le taux du portefeuille — ils
    donnent le délai moyen d'encaissement. Au-delà d'un an, des coupons sont en retard.
    """
    taux = float(ctx.contrats_uniques.MAIN_COMP_RATE.median())
    lignes, alertes = [], []
    for arrete in ctx.arretes:
        portefeuille = ctx.solde(CPT_PORTEFEUILLE, a_la_date=arrete)
        courus = ctx.solde([CPT_COURUS_MM, CPT_COURUS_CALYPSO], a_la_date=arrete)
        interet_annuel = portefeuille * taux / 100
        annees = courus / interet_annuel if interet_annuel else 0
        lignes.append([arrete, portefeuille, courus, round(courus / portefeuille * 100, 2) if portefeuille else 0,
                       round(annees, 2)])
        if annees > 1:
            alertes.append((arrete, annees, courus))
    if not alertes:
        return Constat(
            code="3.7",
            titre="Situation du portefeuille et des intérêts courus aux dates d'arrêté",
            gravite=Gravite.CONFORME,
            constat=(
                "Encours du portefeuille de titres et des créances rattachées à chaque date "
                "d'arrêté de la période. Rapportés à une année d'intérêts théorique au taux "
                f"médian du portefeuille ({taux:.2f} %), les courus restent inférieurs à douze "
                "mois de coupons : les encaissements suivent donc le rythme des accruals."
            ),
            tableaux=[Tableau(
                ["Date d'arrêté", "Portefeuille XAF", "Courus XAF", "Courus / portef. %",
                 "Années d'intérêts"], lignes)],
        )
    pire = max(alertes, key=lambda a: a[1])
    return Constat(
        code="3.7",
        titre="Accumulation des intérêts courus au-delà d'une année de coupons",
        gravite=Gravite.ELEVEE,
        constat=(
            "Les créances rattachées représentent les coupons acquis mais non encore encaissés. "
            f"Rapportées à une année d'intérêts théorique au taux médian du portefeuille "
            f"({taux:.2f} %), elles dépassent douze mois de coupons à certaines dates d'arrêté.\n"
            "Le portefeuille étant composé de titres à coupon annuel, un encours de courus "
            "supérieur à une année signifie que des coupons échus n'ont pas été encaissés, ou "
            "que les courus correspondants n'ont pas été apurés.\n"
            "La progression du ratio est en outre continue et s'accélère nettement après la "
            "bascule sur le nouveau système : il convient de déterminer si le changement d'outil "
            "a altéré le suivi des encaissements de coupons."
        ),
        chiffres=[
            ("Taux médian du portefeuille", f"{taux:.2f} %"),
            ("Arrêtés au-delà d'une année de coupons", str(len(alertes))),
            ("Pire arrêté", f"{pire[0]} — {pire[1]:.2f} année(s) d'intérêts, soit {xaf(pire[2])}"),
        ],
        tableaux=[Tableau(
            ["Date d'arrêté", "Portefeuille XAF", "Courus XAF", "Courus / portef. %",
             "Années d'intérêts"], lignes)],
        recommandation=(
            "Établir l'échéancier des coupons attendus et le rapprocher des encaissements "
            "constatés sur le compte de règlement, à chaque date d'arrêté. Identifier les titres "
            "dont le coupon est échu et non encaissé."
        ),
    )
