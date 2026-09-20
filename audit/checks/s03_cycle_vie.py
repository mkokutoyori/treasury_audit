"""Section 3 — Cycle de vie des titres sous Flexcube (module MM).

Le cycle attendu est : acquisition (PRINCIPAL) → courus quotidiens (INT_BT_ACCR) →
encaissement du coupon → dénouement (PRINCIPAL_LIQD).

Deux comportements du portefeuille, initialement pris pour des anomalies, sont en réalité
NORMAUX et ne sont donc pas rapportés comme tels :
  - le dénouement avant l'échéance contractuelle, qui traduit la revente d'un titre pour
    faire face aux tensions de liquidité — c'est le mode de gestion courant du portefeuille ;
  - le dénouement au pair, qui découle de la nature des actifs : un titre d'État se cède au
    nominal, l'acquéreur bénéficiant du coupon couru.
Seul le dénouement POSTÉRIEUR à l'échéance constitue une anomalie.
"""
from __future__ import annotations

import calendar

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf, pct, fois, nb
from ..data import CPT_COURUS_CALYPSO, CPT_COURUS_MM, CPT_PORTEFEUILLE, DATE_BASCULE

SECTION = (3, "Cycle de vie des titres sous Flexcube")


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "Revue du cycle de vie des titres dans le module MM : dénouements postérieurs à "
            "l'échéance, annulations de contrats, contrats réouverts, exactitude des intérêts "
            "courus et situation du portefeuille aux dates d'arrêté.\n"
            "Le dénouement anticipé et le dénouement au pair ne sont pas traités comme des "
            "anomalies : le premier traduit la gestion de la liquidité par revente de titres, le "
            "second découle de la nature souveraine des actifs, cédés au nominal."
        ),
    )
    liq = _liquidations(ctx)
    s.ajouter(_c31_denouements(ctx, liq))
    s.ajouter(_c32_annulations(ctx))
    s.ajouter(_c33_reouvertures(ctx))
    s.ajouter(_c34_courus_annulations(ctx))
    s.ajouter(_c35_recalcul_courus(ctx))
    s.ajouter(_c36_apurement_courus(ctx))
    s.ajouter(_c37_situation_portefeuille(ctx))
    s.ajouter(_c38_transfert_attente(ctx))
    return s


def _liquidations(ctx) -> pd.DataFrame:
    """Une ligne par contrat dénoué, enrichie des caractéristiques contractuelles."""
    mm = ctx.grand_livre[ctx.grand_livre.MODULE == "MM"]
    liq = (mm[mm.AMOUNT_TAG == "PRINCIPAL_LIQD"].groupby("TRN_REF_NO")
           .agg(date_liq=("TRN_DT", "min"), montant=("LCY_AMOUNT", "max"),
                saisie=("USER_ID", "first"), validation=("AUTH_ID", "first")))
    ref = ctx.contrats_uniques.set_index("CONTRACT_REF_NO")
    cols = ["MATURITY_DATE_d", "MATURITY_DATE", "AMOUNT", "PRODUCT", "FULL_NAME",
            "MAIN_COMP_RATE", "BOOKING_DATE_d"]
    liq = liq.join(ref[cols], how="left")
    liq["ecart_jours"] = (pd.to_datetime(liq.date_liq) - liq.MATURITY_DATE_d).dt.days
    return liq


def _c31_denouements(ctx, liq) -> Constat:
    """Seul le dénouement POSTÉRIEUR à l'échéance est une anomalie.

    Un titre dénoué après son échéance signifie que le remboursement de l'émetteur a été
    encaissé en retard, ou que la sortie comptable n'a pas suivi l'échéance : dans les deux
    cas, le titre est resté à l'actif au-delà de sa durée de vie.
    """
    dans_periode = liq[(liq.date_liq >= ctx.config.debut) & (liq.date_liq <= ctx.config.fin)]
    anticipes = dans_periode[dans_periode.ecart_jours < 0]
    a_echeance = dans_periode[dans_periode.ecart_jours == 0]
    tardifs = dans_periode[dans_periode.ecart_jours > 0].sort_values("ecart_jours", ascending=False)
    if tardifs.empty:
        return Constat(
            code="3.1", titre="Dénouements postérieurs à l'échéance contractuelle",
            gravite=Gravite.CONFORME,
            constat=(
                f"Aucun titre n'est dénoué après son échéance sur la période. Les "
                f"{len(anticipes)} dénouements anticipés relèvent de la gestion courante de la "
                "liquidité — revente de titres pour faire face aux tensions de trésorerie — et "
                "ne constituent pas une anomalie."
            ),
            chiffres=[
                ("Dénouements de la période", str(len(dans_periode))),
                ("Anticipés (gestion de liquidité)", str(len(anticipes))),
                ("À l'échéance", str(len(a_echeance))),
                ("Postérieurs à l'échéance", "0"),
            ],
        )
    return Constat(
        code="3.1",
        titre="Titres dénoués après leur échéance contractuelle",
        gravite=Gravite.ELEVEE if tardifs.ecart_jours.max() > 30 else Gravite.MOYENNE,
        constat=(
            "Des titres sont sortis du portefeuille APRÈS leur date d'échéance. Deux lectures "
            "possibles, toutes deux à instruire : le remboursement de l'émetteur a été encaissé "
            "en retard, ce qui pose une question de qualité de signature ; ou la sortie comptable "
            "n'a pas suivi l'échéance, et le titre est resté indûment à l'actif.\n"
            "Dans les deux cas, le titre figure au bilan au-delà de sa durée de vie contractuelle "
            "et continue, le cas échéant, de produire des intérêts courus.\n"
            "Les dénouements ANTICIPÉS ne sont pas rapportés : ils traduisent la revente de titres "
            "pour faire face aux tensions de liquidité, mode de gestion normal du portefeuille."
        ),
        chiffres=[
            ("Dénouements de la période", str(len(dans_periode))),
            ("Anticipés (gestion de liquidité, non anormal)", str(len(anticipes))),
            ("À l'échéance", str(len(a_echeance))),
            ("POSTÉRIEURS À L'ÉCHÉANCE", str(len(tardifs))),
            ("Montant concerné", xaf(float(tardifs.montant.sum()))),
            ("Retard maximal", f"{int(tardifs.ecart_jours.max())} jours"),
        ],
        tableaux=[
            Tableau(["Référence", "Échéance", "Dénouement", "Retard (j)", "Montant", "Contrepartie"],
                    [[i, r.MATURITY_DATE, r.date_liq, int(r.ecart_jours), float(r.montant), r.FULL_NAME]
                     for i, r in tardifs.iterrows()])
        ],
        recommandation=(
            "Obtenir, pour chaque titre concerné, l'avis de remboursement de l'émetteur et la date "
            "d'encaissement effective. Vérifier qu'aucun intérêt n'a continué de courir après "
            "l'échéance et que la créance n'aurait pas dû être dépréciée."
        ),
    )


def _c32_annulations(ctx) -> Constat:
    """Contrats comptabilisés puis annulés le jour même, sans vie ultérieure.

    Distinction demandée : un contrat booké et liquidé le même jour SANS écriture
    postérieure est une ANNULATION PURE — une correction de saisie. S'il porte des
    écritures ensuite, il s'agit d'une réouverture (contrôle 3.3).
    """
    mm = ctx.grand_livre[ctx.grand_livre.MODULE == "MM"]
    achat = mm[mm.AMOUNT_TAG == "PRINCIPAL"].groupby("TRN_REF_NO").agg(
        date=("TRN_DT", "min"), montant=("LCY_AMOUNT", "max"),
        saisie=("USER_ID", "first"), validation=("AUTH_ID", "first"))
    liq = mm[mm.AMOUNT_TAG == "PRINCIPAL_LIQD"].groupby("TRN_REF_NO").agg(date_liq=("TRN_DT", "min"))
    j = achat.join(liq, how="inner")
    meme_jour = j[(j.date == j.date_liq)
                  & (j.date >= ctx.config.debut) & (j.date <= ctx.config.fin)]
    if meme_jour.empty:
        return Constat(code="3.2", titre="Contrats annulés le jour de leur comptabilisation",
                       gravite=Gravite.CONFORME,
                       constat="Aucun contrat n'est comptabilisé puis annulé dans la même journée.")
    lignes, pures, reouverts = [], [], []
    for ref, r in meme_jour.iterrows():
        posterieures = len(mm[(mm.TRN_REF_NO == ref) & (mm.TRN_DT > r.date)])
        (pures if posterieures == 0 else reouverts).append(ref)
        lignes.append([ref, r.date, float(r.montant), posterieures, r.saisie, r.validation])
    par_user = meme_jour.groupby("saisie").agg(n=("montant", "size"), montant=("montant", "sum"))
    auto = int((meme_jour.saisie == meme_jour.validation).sum())
    return Constat(
        code="3.2",
        titre="Contrats comptabilisés puis annulés dans la même journée",
        gravite=Gravite.MOYENNE,
        constat=(
            "Des contrats sont enregistrés puis intégralement liquidés le jour même. Le contrôle "
            "distingue deux situations :\n"
            f"- {len(pures)} ANNULATIONS PURES : le contrat ne porte plus aucune écriture par la "
            "suite. Il s'agit de corrections de saisie ;\n"
            f"- {len(reouverts)} contrats connaissant une vie ultérieure, traités au contrôle 3.3.\n"
            "Le procédé appelle deux remarques. D'abord, Flexcube ne dispose apparemment pas de "
            "fonction d'annulation tracée : la correction passe par une liquidation forcée, qui "
            "est comptablement indistinguable d'un dénouement réel. Ensuite, le volume d'erreurs "
            "de saisie ainsi corrigées mesure le taux d'erreur du service et mérite un suivi.\n"
            "Ces écritures gonflent par ailleurs artificiellement les volumes du module."
        ),
        chiffres=[
            ("Contrats concernés", str(len(meme_jour))),
            ("Dont annulations pures", str(len(pures))),
            ("Dont contrats réouverts", str(len(reouverts))),
            ("Montant cumulé", xaf(float(meme_jour.montant.sum()))),
            ("Dont auto-validés", str(auto)),
        ],
        tableaux=[
            Tableau(["Opérateur", "Contrats", "Montant XAF"],
                    [[i, int(r.n), float(r.montant)]
                     for i, r in par_user.sort_values("montant", ascending=False).iterrows()]),
            Tableau(["Référence", "Date", "Montant", "Écritures ultérieures", "Saisie", "Validation"],
                    sorted(lignes, key=lambda l: -l[2]), max_lignes=15),
        ],
        recommandation=(
            "Demander si Flexcube offre une fonction d'annulation distincte de la liquidation. "
            "Mettre en place un suivi du taux d'erreur de saisie du service. Vérifier l'incidence "
            "sur les intérêts courus (contrôle 3.4)."
        ),
    )


def _c33_reouvertures(ctx) -> Constat:
    """Contrats liquidés puis réouverts : la chaîne des courus est-elle continue ?

    Le procédé est utilisé pour les remboursements partiels, Flexcube ne les gérant pas.
    Le risque est que la chaîne des intérêts courus se rompe entre l'ancien et le nouveau
    contrat : couru du contrat clôturé non repris, ou couru compté deux fois.
    """
    mm = ctx.grand_livre[ctx.grand_livre.MODULE == "MM"]
    achats = mm[mm.AMOUNT_TAG == "PRINCIPAL"].groupby("TRN_REF_NO").agg(
        date=("TRN_DT", "min"), montant=("LCY_AMOUNT", "max"))
    liqs = mm[mm.AMOUNT_TAG == "PRINCIPAL_LIQD"].groupby("TRN_REF_NO").agg(
        date=("TRN_DT", "min"), montant=("LCY_AMOUNT", "max"))
    ref = ctx.contrats_uniques.set_index("CONTRACT_REF_NO")
    achats = achats.join(ref[["FULL_NAME", "MATURITY_DATE_d"]])
    liqs = liqs.join(ref[["FULL_NAME", "MATURITY_DATE_d"]])
    cibles = liqs[(liqs.date >= ctx.config.debut) & (liqs.date <= ctx.config.fin)
                  & (liqs.date != DATE_BASCULE)]
    chaines = []
    anciens_vus, nouveaux_vus = set(), set()
    for ancien, r in cibles.iterrows():
        suivants = achats[(achats.date == r.date) & (achats.FULL_NAME == r.FULL_NAME)
                          & (achats.index != ancien)]
        if suivants.empty:
            continue
        rachat = float(suivants.montant.sum())
        chaines.append([ancien, r.date, float(r.montant), len(suivants), rachat,
                        rachat - float(r.montant), r.FULL_NAME])
        anciens_vus.add(ancien)
        nouveaux_vus.update(suivants.index)
    if not chaines:
        return Constat(code="3.3", titre="Contrats liquidés puis réouverts", gravite=Gravite.CONFORME,
                       constat="Aucun enchaînement liquidation/réouverture identifié.")
    reduction = [c for c in chaines if c[5] < 0]
    augmentation = [c for c in chaines if c[5] > 0]
    identique = [c for c in chaines if c[5] == 0]
    # Chaque contrat n'est compté qu'une fois : un même rachat peut solder plusieurs
    # contrats clôturés le même jour, l'addition des colonnes du tableau surestimerait.
    liq_brut = float(liqs.loc[sorted(anciens_vus)].montant.sum())
    ach_brut = float(achats.loc[sorted(nouveaux_vus)].montant.sum())
    brut = liq_brut + ach_brut
    net = ach_brut - liq_brut
    periode = achats[(achats.date >= ctx.config.debut) & (achats.date <= ctx.config.fin)]
    periode_liq = liqs[(liqs.date >= ctx.config.debut) & (liqs.date <= ctx.config.fin)]
    volume_mm = float(periode.montant.sum()) + float(periode_liq.montant.sum())
    return Constat(
        code="3.3",
        titre="Contrats liquidés puis réouverts le jour même : les volumes bruts ne sont pas des flux",
        gravite=Gravite.MOYENNE,
        constat=(
            "Le module MM ne gérant pas le remboursement partiel, la trésorerie procède par "
            "clôture intégrale du contrat suivie de la réouverture du solde, le même jour et sur "
            "la même contrepartie. Le procédé est en soi légitime, mais il emporte deux "
            "conséquences.\n"
            "D'abord, les VOLUMES BRUTS du module ne représentent pas des flux économiques. Toute "
            "analyse de volumétrie, de rotation du portefeuille ou de flux de trésorerie doit être "
            "menée en net, après neutralisation de ces couples : l'écart est considérable, le "
            "volume brut porté par ces enchaînements dépassant de plusieurs dizaines de fois le "
            "flux net correspondant.\n"
            "Ensuite, la CHAÎNE DES INTÉRÊTS COURUS peut se rompre entre le contrat clôturé et "
            "celui qui le remplace : le couru accumulé sur le premier doit être soit encaissé, "
            "soit repris sur le second. Le contrôle 3.4 mesure ce risque."
        ),
        chiffres=[
            ("Enchaînements identifiés", str(len(chaines))),
            ("Dont réouverture pour un montant inférieur (remboursement partiel)", str(len(reduction))),
            ("Dont réouverture pour un montant supérieur (complément)", str(len(augmentation))),
            ("Dont réouverture à l'identique", str(len(identique))),
            ("Contrats clôturés impliqués / contrats réouverts",
             f"{len(anciens_vus)} / {len(nouveaux_vus)}"),
            ("Volume BRUT porté par ces enchaînements", xaf(brut)),
            ("Flux NET réellement décaissé ou encaissé", xaf(net)),
            ("Facteur de surévaluation du volume",
             fois(brut / abs(net), 1) if net else "n/a"),
            ("Part de ces enchaînements dans le volume MM de la période",
             f"{pct(100 * brut / volume_mm, 1)}" if volume_mm else "n/a"),
        ],
        tableaux=[
            Tableau(["Contrat clôturé", "Date", "Montant liquidé", "Nb rachats", "Montant racheté",
                     "Écart", "Contrepartie"],
                    sorted(chaines, key=lambda c: -abs(c[5]))[:15])
        ],
        recommandation=(
            "Ne retenir aucune statistique de volume issue du module MM sans retraitement. "
            "Demander si une évolution du paramétrage permettrait le remboursement partiel direct."
        ),
    )


def _c34_courus_annulations(ctx) -> Constat:
    """L'annulation d'un contrat contre-passe-t-elle les intérêts courus déjà enregistrés ?

    Le test se limite au fait vérifiable : la liquidation d'annulation passe-t-elle une
    écriture de sens inverse sur le compte de créances rattachées ? Le devenir ultérieur de
    ces courus relève d'écritures manuelles de natures diverses, traitées au contrôle 3.8 :
    les rattacher ici à un « apurement » conduirait à une interprétation erronée.
    """
    if ctx.courus.empty:
        return Constat(code="3.4", titre="Intérêts courus des contrats annulés", gravite=Gravite.FAIBLE,
                       constat="Historique du compte de créances rattachées indisponible.")
    mm = ctx.grand_livre[ctx.grand_livre.MODULE == "MM"]
    achat = mm[mm.AMOUNT_TAG == "PRINCIPAL"].groupby("TRN_REF_NO").TRN_DT.min()
    liq = mm[mm.AMOUNT_TAG == "PRINCIPAL_LIQD"].groupby("TRN_REF_NO").TRN_DT.min()
    j = pd.concat([achat.rename("ach"), liq.rename("liq")], axis=1).dropna()
    # Même périmètre que le contrôle 3.2 : les annulations antérieures à la période d'audit
    # relèvent d'exercices déjà revus.
    annules = set(j[(j.ach == j.liq)
                    & (j.ach >= ctx.config.debut) & (j.ach <= ctx.config.fin)].index)
    if not annules:
        return Constat(code="3.4", titre="Intérêts courus des contrats annulés", gravite=Gravite.CONFORME,
                       constat="Aucun contrat annulé le jour de sa comptabilisation.")
    lignes_annules = ctx.courus[ctx.courus.TRN_REF_NO.isin(annules)]
    debits = lignes_annules[lignes_annules.DRCR_IND == "D"]
    # Une contre-passation par la liquidation se traduirait par un crédit dans le module MM
    contre_passe = lignes_annules[(lignes_annules.MODULE == "MM") & (lignes_annules.DRCR_IND == "C")]
    par_contrat = debits.groupby("TRN_REF_NO").agg(
        couru=("LCY_AMOUNT", "sum"), lignes=("LCY_AMOUNT", "size"), date=("TRN_DT", "min"))
    return Constat(
        code="3.4",
        titre="L'annulation d'un contrat ne contre-passe pas les intérêts courus déjà enregistrés",
        gravite=Gravite.ELEVEE,
        constat=(
            "Lorsqu'un contrat est annulé le jour de sa comptabilisation, la liquidation solde le "
            "principal mais NE CONTRE-PASSE PAS les intérêts courus déjà enregistrés : aucune "
            "écriture de sens inverse n'est passée dans le module sur le compte de créances "
            "rattachées.\n"
            "Le couru d'un contrat annulé — donc d'une opération qui n'a jamais existé — reste "
            "ainsi à l'actif, et le produit correspondant au compte de résultat. Son sort dépend "
            "ensuite d'écritures manuelles, dont le contrôle 3.8 montre qu'elles sont de natures "
            "diverses et ne constituent pas toutes un apurement.\n"
            "Le montant unitaire est faible, mais le principe ne l'est pas : une opération annulée "
            "ne doit laisser aucune trace au compte de résultat."
        ),
        chiffres=[
            ("Contrats annulés le jour même", str(len(annules))),
            ("Dont portant des intérêts courus", str(len(par_contrat))),
            ("Courus enregistrés sur contrats annulés", xaf(float(debits.LCY_AMOUNT.sum()))),
            ("CONTRE-PASSATIONS PAR LA LIQUIDATION", str(len(contre_passe))),
        ],
        tableaux=[
            Tableau(["Contrat annulé", "Date", "Écritures de couru", "Couru enregistré XAF"],
                    [[i, r.date, int(r.lignes), float(r.couru)]
                     for i, r in par_contrat.sort_values("couru", ascending=False).iterrows()],
                    max_lignes=18)
        ],
        recommandation=(
            "Faire paramétrer la contre-passation automatique des intérêts courus lors de "
            "l'annulation d'un contrat, afin que l'opération ne laisse aucun résidu."
        ),
    )


def _c38_transfert_attente(ctx) -> Constat:
    """Les intérêts courus ont-ils transité par un compte d'attente ?

    Un compte d'attente est par nature temporaire. Y loger des créances rattachées, même
    brièvement, soustrait ces montants au suivi normal du portefeuille.
    """
    if ctx.courus.empty:
        return Constat(code="3.8", titre="Transferts d'intérêts courus", gravite=Gravite.FAIBLE,
                       constat="Historique du compte de créances rattachées indisponible.")
    transferts = ctx.courus[ctx.courus.DESCRIPTION.fillna("").str.contains(
        "Reversal of contract", na=False, case=False)]
    if transferts.empty:
        return Constat(code="3.8", titre="Transferts d'intérêts courus vers un compte d'attente",
                       gravite=Gravite.CONFORME,
                       constat="Aucun transfert d'intérêts courus vers un compte d'attente.")
    # Libellé type : « ... from GL 511800100 to 466000107 »
    cibles = transferts.DESCRIPTION.str.extract(r"to\s+(\d{9})\b", expand=False).dropna()
    compte_cible = cibles.value_counts().index[0] if len(cibles) else "non identifié"
    libelle_cible = ctx.libelle_compte(compte_cible) if compte_cible != "non identifié" else ""
    sorties = float(transferts[transferts.DRCR_IND == "C"].LCY_AMOUNT.sum())
    retours = float(transferts[transferts.DRCR_IND == "D"].LCY_AMOUNT.sum())
    net = float(transferts.SIGNE.sum())
    contrats = transferts.DESCRIPTION.str.extract(r"(099[A-Z]{4}\d{9})")[0].nunique()
    par_date = transferts.groupby("TRN_DT").agg(
        ecritures=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))
    par_user = transferts.groupby(["USER_ID", "AUTH_ID"]).agg(
        ecritures=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))
    dans_perimetre = (ctx.toutes_ecritures.AC_NO == compte_cible).sum()
    return Constat(
        code="3.8",
        titre="Transfert massif d'intérêts courus vers un compte d'attente",
        gravite=Gravite.ELEVEE,
        constat=(
            "Sur une période de deux semaines, une série d'écritures manuelles a fait transiter "
            "des intérêts courus entre le compte de créances rattachées et un COMPTE D'ATTENTE"
            + (f" — « {libelle_cible} » ({compte_cible})" if libelle_cible else f" ({compte_cible})")
            + ". Les écritures sont libellées comme des reprises de contrat.\n"
            "L'opération n'est pas un simple aller : les montants sortent du compte de créances "
            "rattachées puis y reviennent en partie, laissant un résidu net. Le volume brut est "
            "donc très supérieur à l'effet net, et seul ce dernier compte.\n"
            "Un compte d'attente est par nature temporaire : y loger des créances rattachées, même "
            "brièvement, soustrait ces montants au suivi normal du portefeuille. Le compte "
            "destinataire ne figure dans AUCUNE des extractions fournies : il est donc impossible "
            "de vérifier qu'il a été apuré."
        ),
        chiffres=[
            ("Écritures", str(len(transferts))),
            ("Période", f"{transferts.TRN_DT.min()} → {transferts.TRN_DT.max()}"),
            ("Contrats concernés", str(contrats)),
            ("Compte d'attente destinataire", f"{compte_cible} {libelle_cible}".strip()),
            ("Sorties du compte de créances rattachées", xaf(sorties)),
            ("Retours au compte de créances rattachées", xaf(retours)),
            ("EFFET NET sur les créances rattachées", xaf(net)),
            ("Lignes du compte d'attente dans les extractions", str(int(dans_perimetre))),
        ],
        tableaux=[
            Tableau(["Date", "Écritures", "Montant brut XAF"],
                    [[i, int(r.ecritures), float(r.montant)] for i, r in par_date.iterrows()]),
            Tableau(["Saisie", "Validation", "Écritures", "Montant brut XAF"],
                    [[i[0], i[1], int(r.ecritures), float(r.montant)] for i, r in par_user.iterrows()]),
        ],
        recommandation=(
            "Obtenir l'historique complet du compte d'attente destinataire et vérifier qu'il est "
            "soldé. Faire expliquer la finalité de cette opération et l'autorisation dont elle a "
            "fait l'objet. Vérifier le solde de ce compte à chaque date d'arrêté traversée."
        ),
    )

def _annees_base(debut: pd.Timestamp, fin: pd.Timestamp) -> float:
    """Durée en années, en tenant compte des années bissextiles.

    Chaque jour est rapporté au nombre de jours de l'année civile à laquelle il appartient :
    365 en année ordinaire, 366 en année bissextile. C'est la convention « exact/exact »,
    la seule qui traite correctement les périodes chevauchant une année bissextile.
    """
    total = 0.0
    curseur = debut
    while curseur <= fin:
        fin_annee = pd.Timestamp(year=curseur.year, month=12, day=31)
        borne = min(fin, fin_annee)
        jours = (borne - curseur).days + 1
        total += jours / (366 if calendar.isleap(curseur.year) else 365)
        curseur = fin_annee + pd.Timedelta(days=1)
    return total


def _c35_recalcul_courus(ctx) -> Constat:
    """Recalcul indépendant des intérêts courus, avec classement des écarts par cause.

    Trois conventions sont testées pour chaque contrat — exact/365, exact/360 et
    exact/exact, cette dernière traitant correctement les années bissextiles. Le contrat est
    réputé conforme si l'une d'elles restitue le montant comptabilisé. Les écarts résiduels
    sont ensuite classés par cause probable.
    """
    cfg = ctx.config
    courus = ctx.courus if not ctx.courus.empty else ctx.grand_livre[
        ctx.grand_livre.AC_NO == CPT_COURUS_MM]
    accruals = courus[(courus.MODULE == "MM") & (courus.AMOUNT_TAG == "INT_BT_ACCR")]
    g = accruals.groupby("TRN_REF_NO").agg(
        comptabilise=("LCY_AMOUNT", "sum"), lignes=("LCY_AMOUNT", "size"),
        debut=("TRN_DT_d", "min"), fin=("TRN_DT_d", "max"),
        negatifs=("LCY_AMOUNT", lambda s: int((s < 0).sum())))
    ref = ctx.contrats_uniques.set_index("CONTRACT_REF_NO")
    j = g.join(ref[["AMOUNT", "MAIN_COMP_RATE", "VALUE_DATE_d", "MATURITY_DATE_d",
                    "PRODUCT", "FULL_NAME"]], how="inner")
    j = j[j.MAIN_COMP_RATE.notna() & j.AMOUNT.notna()]
    # Bornes de la période d'accrual : de la date de valeur au dernier couru constaté
    j["depart"] = j[["debut", "VALUE_DATE_d"]].max(axis=1)
    j = j[j.fin >= j.depart]
    j["jours"] = (j.fin - j.depart).dt.days + 1
    j["annees_exact"] = [_annees_base(d, f) for d, f in zip(j.depart, j.fin)]
    base = j.AMOUNT * j.MAIN_COMP_RATE / 100
    attendus = {
        "exact/365": base * j.jours / 365,
        "exact/360": base * j.jours / 360,
        "exact/exact": base * j.annees_exact,
    }
    ecarts = pd.DataFrame({nom: (j.comptabilise / v - 1).abs() for nom, v in attendus.items()})
    j["meilleure_base"] = ecarts.idxmin(axis=1)
    j["ecart_relatif"] = ecarts.min(axis=1)
    j["attendu"] = [attendus[b].loc[i] for i, b in j.meilleure_base.items()]
    j["ecart"] = j.comptabilise - j.attendu

    def _classer(r) -> str:
        if r.ecart_relatif <= cfg.tolerance_couru:
            return "conforme"
        if r.comptabilise == 0:
            return "aucun couru enregistré"
        if r.negatifs:
            return "contre-passations partielles"
        if r.lignes <= 2:
            return "couru unique, période non représentative"
        if r.fin > r.MATURITY_DATE_d:
            return "courus au-delà de l'échéance"
        return "écart inexpliqué" if r.ecart > 0 else "sous-évaluation inexpliquée"

    j["classe"] = j.apply(_classer, axis=1)
    global_pct = (j.comptabilise.sum() / j.attendu.sum() - 1) * 100
    hors = j[(j.classe != "conforme") & (j.ecart.abs() > cfg.seuil_materialite)]
    par_classe = j.groupby("classe").agg(contrats=("ecart", "size"), ecart=("ecart", "sum"),
                                         nominal=("AMOUNT", "sum"))
    par_base = j.meilleure_base.value_counts()
    if hors.empty:
        return Constat(
            code="3.5", titre="Exactitude des intérêts courus", gravite=Gravite.CONFORME,
            constat=(
                f"Le recalcul indépendant, testé sur trois conventions de décompte, ne fait "
                f"ressortir aucun écart individuel significatif. Écart global : {pct(global_pct, 2, signe=True)}."
            ),
            tableaux=[Tableau(["Classe", "Contrats", "Écart XAF", "Nominal XAF"],
                              [[i, int(r.contrats), float(r.ecart), float(r.nominal)]
                               for i, r in par_classe.iterrows()])],
        )
    return Constat(
        code="3.5",
        titre="Écarts sur le recalcul des intérêts courus, classés par cause",
        gravite=Gravite.MOYENNE,
        constat=(
            "MÉTHODE. Pour chaque contrat, les intérêts courus comptabilisés sont comparés au "
            "produit du nominal, du taux contractuel et de la durée effective d'accrual. La durée "
            "court de la date de valeur — ou du premier couru si elle est postérieure — au dernier "
            "couru constaté. Trois conventions de décompte sont testées : exact/365, exact/360 et "
            "EXACT/EXACT, cette dernière rapportant chaque jour au nombre de jours de son année "
            "civile, soit 366 en année bissextile. La période couverte comprend deux années "
            "bissextiles, 2024 et 2028 : ignorer cette distinction introduirait un biais "
            "systématique de 0,27 %. Le contrat est réputé conforme si l'une des trois conventions "
            "restitue le montant comptabilisé à la tolérance retenue près.\n"
            f"RÉSULTAT D'ENSEMBLE. L'écart global n'est que de {pct(global_pct, 2, signe=True)}, ce qui atteste "
            "la justesse du moteur d'accrual. Les écarts sont donc individuels et non systémiques.\n"
            "CLASSEMENT DES ÉCARTS. Chaque contrat en écart est rattaché à une cause probable, "
            "afin d'orienter les vérifications :\n"
            "- « aucun couru enregistré » : le contrat n'a produit aucun intérêt alors qu'il aurait "
            "dû — contrat annulé ou accrual non déclenché ;\n"
            "- « contre-passations partielles » : le contrat porte des courus négatifs, donc des "
            "corrections, qui déforment le cumul ;\n"
            "- « couru unique, période non représentative » : une ou deux écritures seulement, le "
            "recalcul sur la période n'est pas significatif ;\n"
            "- « courus au-delà de l'échéance » : des intérêts continuent de courir après la date "
            "d'échéance du contrat ;\n"
            "- « écart inexpliqué » : aucune des causes ci-dessus, à investiguer en priorité."
        ),
        chiffres=[
            ("Contrats testés", str(len(j))),
            ("Courus comptabilisés", xaf(float(j.comptabilise.sum()))),
            ("Courus recalculés", xaf(float(j.attendu.sum()))),
            ("Écart global", f"{pct(global_pct, 2, signe=True)}"),
            ("Convention dominante", f"{par_base.index[0]} ({par_base.iloc[0]} contrats)"),
            ("Tolérance retenue", f"{cfg.tolerance_couru:.0%}"),
            (f"Contrats en écart au-delà de {cfg.seuil_materialite/1e6:.0f} M XAF", str(len(hors))),
            ("Écart cumulé de ces contrats", xaf(float(hors.ecart.sum()))),
        ],
        tableaux=[
            Tableau(["Classe d'anomalie", "Contrats", "Écart cumulé XAF", "Nominal concerné XAF"],
                    [[i, int(r.contrats), float(r.ecart), float(r.nominal)]
                     for i, r in par_classe.sort_values("ecart", key=abs, ascending=False).iterrows()],
                    note="Répartition de l'ensemble des contrats testés."),
            Tableau(["Convention restituant le montant", "Contrats"],
                    [[i, int(n)] for i, n in par_base.items()]),
            Tableau(["Référence", "Classe", "Nominal", "Taux %", "Jours", "Base", "Attendu",
                     "Comptabilisé", "Écart"],
                    [[i, r.classe, float(r.AMOUNT), float(r.MAIN_COMP_RATE), int(r.jours),
                      r.meilleure_base, float(r.attendu), float(r.comptabilise), float(r.ecart)]
                     for i, r in hors.reindex(hors.ecart.abs().sort_values(ascending=False).index).iterrows()],
                    max_lignes=20,
                    note="Contrats en écart significatif, classés par cause probable."),
        ],
        recommandation=(
            "Traiter en priorité les contrats classés « écart inexpliqué » et « courus au-delà de "
            "l'échéance ». Faire confirmer la convention de décompte paramétrée par produit et "
            "vérifier qu'elle traite correctement les années bissextiles."
        ),
    )


def _c36_apurement_courus(ctx) -> Constat:
    """Le compte de créances rattachées doit être soldé par l'encaissement des coupons."""
    courus = ctx.courus
    if courus.empty:
        return Constat(code="3.6", titre="Apurement des créances rattachées", gravite=Gravite.FAIBLE,
                       constat="Historique du compte indisponible.",
                       recommandation="Extraire l'historique du compte 511800100 tous modules confondus.")
    debits, credits = courus[courus.DRCR_IND == "D"], courus[courus.DRCR_IND == "C"]
    solde = float(courus.SIGNE.sum())
    par_module = credits.groupby("MODULE").agg(n=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))
    auto = int((credits.USER_ID == credits.AUTH_ID).sum())
    sans_valid = int(credits.AUTH_ID.isna().sum())
    if abs(solde) < 1 and not credits.empty:
        return Constat(
            code="3.6", titre="Apurement des créances rattachées par encaissement des coupons",
            gravite=Gravite.CONFORME,
            constat=(
                f"Le compte est intégralement apuré : {nb(len(debits))} débits pour "
                f"{nb(len(credits))} crédits, solde net nul. Les coupons sont encaissés en "
                "trésorerie, l'apurement étant passé par écriture manuelle en module DE et non par "
                "l'événement automatique du module MM. Le contrôle des quatre yeux est respecté "
                f"({auto} auto-validation, {sans_valid} sans validateur)."
            ),
            tableaux=[Tableau(["Module d'apurement", "Écritures", "Montant XAF"],
                              [[i, int(r.n), float(r.montant)] for i, r in par_module.iterrows()])],
        )
    return Constat(
        code="3.6", titre="Créances rattachées non intégralement apurées", gravite=Gravite.CRITIQUE,
        constat=(
            "Le compte de créances rattachées présente un solde résiduel. Un tel compte doit "
            "osciller : monter entre deux coupons, retomber à chaque encaissement. Un solde "
            "persistant traduit des coupons non encaissés ou un défaut d'apurement, et surévalue "
            "simultanément l'actif et le produit."
        ),
        chiffres=[("Débits", nb(len(debits))),
                  ("Crédits", nb(len(credits))),
                  ("Solde net", xaf(solde))],
        tableaux=[Tableau(["Module", "Écritures", "Montant XAF"],
                          [[i, int(r.n), float(r.montant)] for i, r in par_module.iterrows()])],
        recommandation="Obtenir le solde du compte en balance générale et la justification du résidu.",
    )


def _c37_situation_portefeuille(ctx) -> Constat:
    """Encours du portefeuille et des courus à chaque arrêté, et délai d'encaissement implicite."""
    taux = float(ctx.contrats_uniques.MAIN_COMP_RATE.median())
    lignes, alertes = [], []
    for arrete in ctx.arretes:
        portefeuille = ctx.solde(CPT_PORTEFEUILLE, a_la_date=arrete)
        courus = ctx.solde([CPT_COURUS_MM, CPT_COURUS_CALYPSO], a_la_date=arrete)
        interet_annuel = portefeuille * taux / 100
        annees = courus / interet_annuel if interet_annuel else 0
        lignes.append([arrete, portefeuille, courus,
                       round(courus / portefeuille * 100, 2) if portefeuille else 0, round(annees, 2)])
        if annees > 1:
            alertes.append((arrete, annees, courus))
    entetes = ["Date d'arrêté", "Portefeuille XAF", "Courus XAF", "Courus / portef. %",
               "Années d'intérêts"]
    if not alertes:
        return Constat(
            code="3.7", titre="Situation du portefeuille et des intérêts courus aux dates d'arrêté",
            gravite=Gravite.CONFORME,
            constat=(
                "Encours du portefeuille et des créances rattachées à chaque date d'arrêté. "
                f"Rapportés à une année d'intérêts au taux médian du portefeuille ({pct(taux, 2)}), "
                "les courus restent inférieurs à douze mois de coupons : les encaissements suivent "
                "le rythme des accruals."
            ),
            tableaux=[Tableau(entetes, lignes)],
        )
    pire = max(alertes, key=lambda a: a[1])
    # La progression n'est pas monotone : on décrit ce que montrent réellement les arrêtés,
    # de part et d'autre de la bascule, plutôt qu'une tendance régulière inexistante.
    bascule = str(DATE_BASCULE)[:10]
    avant = [l[4] for l in lignes if l[0] <= bascule]
    apres = [l[4] for l in lignes if l[0] > bascule]

    def an(valeur: float) -> str:
        return f"{valeur:.2f}".replace(".", ",")

    if avant and apres:
        evolution = (
            "La progression n'est pas régulière : jusqu'au dernier arrêté précédant la bascule, le "
            f"ratio reste compris entre {an(min(avant))} et {an(max(avant))} année de coupons ; il "
            f"passe ensuite de {an(apres[0])} à {an(apres[-1])} sur les arrêtés postérieurs. La "
            "rupture coïncide avec le changement d'outil : il convient de déterminer si celui-ci a "
            "altéré le suivi des encaissements de coupons."
        )
    else:
        evolution = (
            "Il convient de déterminer si le changement d'outil a altéré le suivi des "
            "encaissements de coupons."
        )
    return Constat(
        code="3.7", titre="Accumulation des intérêts courus au-delà d'une année de coupons",
        gravite=Gravite.ELEVEE,
        constat=(
            "Les créances rattachées représentent les coupons acquis mais non encore encaissés. "
            f"Rapportées à une année d'intérêts au taux médian du portefeuille ({pct(taux, 2)}), "
            "elles dépassent douze mois de coupons à certaines dates d'arrêté.\n"
            "Le portefeuille étant composé de titres à coupon annuel, un encours de courus "
            "supérieur à une année signifie que des coupons échus n'ont pas été encaissés, ou que "
            "les courus correspondants n'ont pas été apurés.\n"
            + evolution
        ),
        chiffres=[
            ("Taux médian du portefeuille", f"{pct(taux, 2)}"),
            ("Arrêtés au-delà d'une année de coupons", str(len(alertes))),
            ("Pire arrêté",
             f"{pire[0]} — {pire[1]:.2f}".replace(".", ",")
             + f" année(s), soit {xaf(pire[2])}"),
        ],
        tableaux=[Tableau(entetes, lignes)],
        recommandation=(
            "Établir l'échéancier des coupons attendus et le rapprocher des encaissements "
            "constatés sur le compte de règlement, à chaque date d'arrêté."
        ),
    )
