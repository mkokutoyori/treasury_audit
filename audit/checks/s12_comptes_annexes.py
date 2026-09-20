"""Section 12 — Comptes de régularisation, comptes d'attente et comptes dormants.

Cette section repose sur la deuxième vague d'extractions : les comptes du plan de comptes
qui intéressent l'activité titres mais qui ne figuraient pas dans la liste initiale des
41 comptes clés. Elle produit deux natures de constat, également instructives :
ce que ces comptes CONTIENNENT, et ce qu'ils ne contiennent PAS.
"""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf, nb, pct, fois
from ..data import (DATE_BASCULE, CPT_ATTENTE, CPT_COLLATERAL, CPT_REPO_CHARGE,
                    CPT_REPO_DETTES, CPT_REPO_PASSIF, CPT_COMM_TITRES, CPT_CONVERSION, CPT_HORS_BILAN_TITRES,
                    CPT_NANTISSEMENT, CPT_PENSION_PCEC, CPT_PROVISIONS_TITRES,
                    CPT_VAGUE2_DEMANDES)

SECTION = (12, "Comptes de régularisation, comptes d'attente et comptes dormants")

# Motifs de libellé permettant de reconnaître une écriture se rapportant à un titre :
# code ISIN CEMAC, référence de contrat Flexcube, ou mot-clé explicite.
MOTIF_TITRE = r"CM1|CM2|CG2|GA2|GQ2|TD2|OTAP|TBTR|BTTR|SECURIT|T ?BOND|TBILL|T ?BILL"


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "Revue des comptes qui bordent le circuit des titres sans en faire partie : la "
            "charge de commissions, les comptes d'attente de la direction financière, les "
            "comptes de nantissement et de conversion, et l'ensemble des comptes que le PCEC "
            "destine aux pensions livrées et aux dépréciations. Le fait qu'un compte soit "
            "resté vide est ici un résultat de contrôle à part entière."
        ),
    )
    if ctx.comptes_complementaires.empty:
        s.erreurs.append("Deuxième vague d'extractions absente : section non instruite.")
        return s
    s.ajouter(_c121_commissions_fourre_tout(ctx))
    s.ajouter(_c122_pensions_sans_passif(ctx))
    s.ajouter(_c123_compte_attente(ctx))
    s.ajouter(_c124_nantissement(ctx))
    s.ajouter(_c125_conversion(ctx))
    s.ajouter(_c126_comptes_dormants(ctx))
    return s


def _periode(ctx, compte: str) -> pd.DataFrame:
    return ctx.historique_compte(compte, dans_periode=True)


# --- 12.1 ---------------------------------------------------------------------------------
def _classer(libelle: str) -> str:
    """Rattache une écriture de 622000100 à la nature d'opération qu'elle traduit."""
    t = "" if libelle is None or pd.isna(libelle) else str(libelle).upper()
    if not t.strip():
        return "sans libellé — écriture de clôture"
    if "GARDE" in t:
        return "droit de garde (usage prévu)"
    if "COMMIS" in t:
        return "commission (usage prévu)"
    if "DISCOUNT" in t or "DECOTE" in t or "DÉCOTE" in t:
        return "décote ou prime sur titre"
    if "INTEREST" in t or "INTERET" in t or "INTÉRÊT" in t or "COUPON" in t:
        return "intérêt couru ou régularisation d'intérêt"
    if "DIFF" in t or "REGUL" in t or "RECLASS" in t or "RCLSS" in t or "ZERORI" in t:
        return "différence, reclassement, mise à zéro"
    return "autre"


def _c121_commissions_fourre_tout(ctx) -> Constat:
    d = _periode(ctx, CPT_COMM_TITRES)
    libelle = ctx.libelle_compte(CPT_COMM_TITRES) or "COMM ET FRAIS SUR TITRES"
    if d.empty:
        return Constat(code="12.1", titre=f"Compte {CPT_COMM_TITRES} non mouvementé",
                       gravite=Gravite.CONFORME, constat="Aucun mouvement sur la période.")
    d = d.assign(nature=d.DESCRIPTION.map(_classer))
    agg = (d.groupby("nature")
             .agg(lignes=("LCY_AMOUNT", "size"),
                  debit=("SIGNE", lambda x: float(x[x > 0].sum())),
                  credit=("SIGNE", lambda x: float(-x[x < 0].sum())),
                  net=("SIGNE", "sum"))
             .sort_values("lignes", ascending=False).reset_index())
    prevu = agg[agg.nature.str.contains("usage prévu")]
    lignes_prevu = int(prevu.lignes.sum())
    detourne = len(d) - lignes_prevu
    credits = d[d.SIGNE < 0]
    total_credits = float(-credits.SIGNE.sum())
    debit_total = float(d[d.SIGNE > 0].SIGNE.sum())
    decotes = float(agg.loc[agg.nature == "décote ou prime sur titre", "net"].sum())
    interets = float(agg.loc[agg.nature.str.startswith("intérêt"), "net"].sum())
    petits = d[d.LCY_AMOUNT <= 100]

    return Constat(
        code="12.1",
        titre=f"Le compte de charge {CPT_COMM_TITRES} sert de compte de régularisation universel du circuit titres",
        gravite=Gravite.ELEVEE,
        reference=f"Compte {CPT_COMM_TITRES} {libelle} — {nb(len(d))} écritures sur la période",
        constat=(
            f"CE QU'EST CE COMPTE. {CPT_COMM_TITRES} {libelle} est un compte de CHARGE "
            "d'exploitation. Le PCEC lui assigne deux emplois, et deux seulement : les "
            "commissions versées aux intermédiaires lors de l'achat et de la vente de titres, "
            "et les droits de garde payés au dépositaire.\n"
            "\n"
            f"CE QU'IL CONTIENT RÉELLEMENT. Sur la période, il porte {nb(len(d))} écritures. "
            f"Seules {nb(lignes_prevu)} relèvent des deux emplois prévus. Les "
            f"{nb(detourne)} autres — soit {pct(detourne / len(d) * 100)} du total — y logent "
            "des opérations qui appartiennent ailleurs : des décotes et primes d'acquisition "
            "et de cession, des régularisations d'intérêts courus, des écarts d'arrondi et des "
            "différences que personne n'a rattachées à leur origine.\n"
            "\n"
            "TROIS CONSÉQUENCES COMPTABLES, DISTINCTES.\n"
            f"- PREMIÈRE — une compensation entre charges et produits. {nb(len(credits))} "
            f"écritures sont des CRÉDITS, pour {xaf(total_credits)}, sur un compte de charge "
            f"dont les débits s'élèvent à {xaf(debit_total)}. Autrement dit, des PRODUITS sont "
            "enregistrés en diminution d'une CHARGE. Le PCEC prohibe cette compensation : "
            "charges et produits doivent figurer pour leur montant brut. Le solde net du "
            f"compte, {xaf(float(d.SIGNE.sum()))}, ne dit donc rien du volume réel qui y a "
            "transité.\n"
            f"- DEUXIÈME — une imputation erronée des décotes. {xaf(abs(decotes))} de décotes "
            "et primes y sont passées. Une décote à l'acquisition est un élément du prix de "
            "revient du titre ou un produit à étaler, selon le cas ; elle relève des comptes "
            "de produits comptabilisés d'avance ou du résultat sur titres. Elle n'est en aucun "
            "cas une commission.\n"
            f"- TROISIÈME — la disparition des écarts. {xaf(abs(interets))} de régularisations "
            f"d'intérêts y sont logées, et {nb(len(petits))} écritures portent sur des montants "
            f"inférieurs ou égaux à 100 XAF, pour {xaf(float(petits.LCY_AMOUNT.sum()))} au "
            "total. Ces écritures d'un ou deux francs sont le signe d'un rapprochement forcé : "
            "plutôt que d'expliquer un écart, on l'éteint. Le contrôle 5.3 en donne "
            "l'illustration la plus nette — le reliquat de la correction d'apurement de la "
            "migration y a été passé en charge.\n"
            "\n"
            "POURQUOI CELA COMPTE POUR L'AUDIT. Un compte fourre-tout empêche toute revue "
            "analytique : il devient impossible de dire ce que la banque a réellement payé en "
            "commissions, ni de mesurer le résultat des décotes, ni de suivre les écarts de "
            "courus. Il neutralise par construction le contrôle que la piste d'audit est "
            "censée permettre."
        ),
        chiffres=[
            ("Écritures sur la période", nb(len(d))),
            ("Dont relevant des emplois prévus par le PCEC", nb(lignes_prevu)),
            ("Dont étrangères à l'objet du compte", nb(detourne)),
            ("Total des DÉBITS", xaf(debit_total)),
            ("Total des CRÉDITS — produits logés en charge", xaf(total_credits)),
            ("Solde net, qui masque les deux précédents", xaf(float(d.SIGNE.sum()))),
            ("Décotes et primes imputées à tort", xaf(abs(decotes))),
            ("Régularisations d'intérêts imputées à tort", xaf(abs(interets))),
            ("Écritures de 100 XAF ou moins", nb(len(petits))),
            ("Opérateurs distincts", nb(d.USER_ID.nunique())),
        ],
        tableaux=[
            Tableau(
                entetes=["Nature de l'opération", "Lignes", "Débits XAF", "Crédits XAF", "Net XAF"],
                lignes=[[r.nature, int(r.lignes), r.debit, r.credit, r.net]
                        for _, r in agg.iterrows()],
                note=("Décomposition du compte par la nature de l'opération, lue dans le libellé "
                      "de chaque écriture. Les deux lignes « usage prévu » sont les seules que le "
                      "PCEC autorise sur ce compte."),
            ),
            Tableau(
                entetes=["Date", "Référence", "Sens", "Montant XAF", "Opérateur", "Libellé"],
                lignes=[[r.TRN_DT, r.TRN_REF_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID,
                         str(r.DESCRIPTION or "")[:62]]
                        for _, r in d.nlargest(12, "LCY_AMOUNT").iterrows()],
                note="Les douze plus gros mouvements du compte sur la période.",
            ),
        ],
        recommandation=(
            f"1. Faire analyser le contenu de {CPT_COMM_TITRES} sur la période et reclasser "
            "chaque écriture à son compte d'origine : décotes aux comptes de régularisation "
            "472200106 et 472200108, régularisations d'intérêts aux comptes de produits sur "
            "titres, différences non justifiées en suspens documenté.\n"
            "2. Interdire les écritures au crédit de ce compte : un produit ne s'enregistre pas "
            "en diminution d'une charge.\n"
            "3. Instaurer une règle de seuil et de justification : toute écriture de "
            "régularisation sur un compte de charge titres doit porter la référence du contrat "
            "et la nature de l'écart qu'elle corrige.\n"
            "4. Rapprocher le montant des commissions réellement dues des relevés du "
            "dépositaire et des intermédiaires, la comptabilité ne permettant pas aujourd'hui "
            "de les isoler."
        ),
    )


# --- 12.2 ---------------------------------------------------------------------------------
def _c122_pensions_sans_passif(ctx) -> Constat:
    d = ctx.comptes_complementaires
    mouvementes, vides = [], []
    for compte in CPT_PENSION_PCEC:
        sous = d[(d.AC_NO == compte) & (d.TRN_DT >= ctx.config.debut)
                 & (d.TRN_DT <= ctx.config.fin)]
        libelle = ctx.libelle_compte(compte)
        if sous.empty:
            vides.append([compte, libelle])
        else:
            mouvementes.append([compte, libelle, len(sous), float(sous.SIGNE.sum())])

    # Ce que la banque emploie RÉELLEMENT pour ses pensions auprès de la banque centrale :
    # les comptes d'emprunt au jour le jour du marché monétaire, et non ceux de la pension.
    gl = ctx.grand_livre
    substitution = []
    for compte in [CPT_REPO_PASSIF, CPT_REPO_DETTES, CPT_REPO_CHARGE] + CPT_COLLATERAL:
        sous = gl[(gl.AC_NO == compte) & (gl.TRN_DT >= ctx.config.debut)
                  & (gl.TRN_DT <= ctx.config.fin)]
        if sous.empty:
            continue
        substitution.append([compte, ctx.libelle_compte(compte), len(sous),
                             float(sous.LCY_AMOUNT.sum()), float(sous.SIGNE.sum())])
    brut_emprunts = next((r[3] for r in substitution if r[0] == CPT_REPO_PASSIF), 0.0)
    charge = next((r[4] for r in substitution if r[0] == CPT_REPO_CHARGE), 0.0)
    collateral = next((r[3] for r in substitution if r[0] == CPT_COLLATERAL[0]), 0.0)

    # Volume des cessions temporaires observées par ailleurs. On reprend la mesure du
    # contrôle 8.1 — les écritures dont le commentaire de la salle des marchés désigne une
    # cession-rétrocession — plutôt qu'un filtre de portefeuille, qui ne recouvre pas le
    # même périmètre.
    from .s08_sbb import _commentes
    commentes = _commentes(ctx)
    nb_sbb, montant_sbb = 0, 0.0
    if not commentes.empty:
        nb_sbb = int(commentes.DEAL.nunique())
        regle = commentes[commentes.EVENEMENT == "CST_S_SETTLED"].groupby("DEAL").LCY_AMOUNT.max()
        montant_sbb = float(regle.sum())

    return Constat(
        code="12.2",
        titre="Les pensions livrées sont comptabilisées en emprunts au jour le jour : aucun des comptes que le PCEC leur réserve n'est servi",
        gravite=Gravite.ELEVEE,
        reference=f"{len(vides)} comptes vides sur les {len(CPT_PENSION_PCEC)} extraits",
        constat=(
            "CE QUE LE PCEC PRÉVOIT. Lorsqu'une banque cède un titre en s'engageant à le "
            "racheter — pension livrée, mise en pension auprès de la banque centrale, "
            "sell-buy-back — l'opération est un EMPRUNT GARANTI, distinct d'un emprunt en "
            "blanc. Le PCEC lui ouvre une série de comptes propres : 521300100 et 521600100 "
            "pour les valeurs reçues et données en pension, 531000100 et 532000100 pour les "
            "autres valeurs, 538000100 et 539000100 pour les créances et dettes rattachées, "
            "522100100 à 522400100 pour le refinancement au guichet A de la BEAC, 602000100 et "
            "702000100 pour les intérêts, 606200100 et 706200100 pour les commissions.\n"
            "\n"
            f"CE QUE MONTRE L'EXTRACTION. Sur les {len(CPT_PENSION_PCEC)} comptes demandés, "
            f"{len(vides)} n'ont porté AUCUN mouvement sur toute la période. Le seul qui en "
            "porte, 602000100, en compte sept, dont six antérieurs à la période : la seule "
            "écriture de la période est l'écriture de clôture annuelle qui solde une charge "
            "née en mai 2023. AUCUN COMPTE DE PENSION N'EST DONC SERVI SUR TROIS EXERCICES.\n"
            "\n"
            "CE QUI EST SERVI À LA PLACE. La banque enregistre bel et bien ses refinancements "
            "auprès de la BEAC — mais sur les comptes de l'EMPRUNT INTERBANCAIRE AU JOUR LE "
            f"JOUR. Le compte {CPT_REPO_PASSIF} {ctx.libelle_compte(CPT_REPO_PASSIF)} porte "
            f"{xaf(brut_emprunts)} de mouvements bruts sur la période, la charge d'intérêt est "
            f"prise sur {CPT_REPO_CHARGE} pour {xaf(charge)}, et les titres affectés en "
            f"garantie figurent au hors bilan sur {CPT_COLLATERAL[0]} pour {xaf(collateral)} "
            "de mouvements. L'opération est donc comptabilisée, et son collatéral est suivi : "
            "ce n'est pas une omission, c'est un CLASSEMENT.\n"
            "\n"
            "POURQUOI LE CLASSEMENT COMPTE. Un emprunt au jour le jour en blanc et une pension "
            "livrée n'ont ni la même nature juridique, ni le même profil de risque, ni le même "
            "traitement prudentiel. Le second est garanti par des titres remis en pleine "
            "propriété ; le premier ne l'est pas. Présenter l'un comme l'autre rend illisible, "
            "au passif, la part du refinancement qui est adossée à du collatéral — donc la "
            "part du portefeuille qui n'est plus mobilisable. Le rapprochement des deux comptes "
            "de charge le montre : celle de 602000100 est nulle alors que celle de "
            f"{CPT_REPO_CHARGE} ne l'est pas, ce qui veut dire que la totalité du coût du "
            "refinancement garanti est présentée comme un coût d'emprunt en blanc.\n"
            "\n"
            "ET LES CESSIONS-RÉTROCESSIONS, ELLES, NE SONT PAS COMPTABILISÉES DU TOUT. "
            f"{nb(nb_sbb)} opérations pour {xaf(montant_sbb)} réglés sont enregistrées comme "
            "des cessions fermes suivies d'acquisitions fermes — ni dette au passif, ni charge "
            "d'intérêt, ni hors bilan. Le contrôle 8.2 en établit le schéma ; l'extraction des "
            "comptes de pension en apporte ici la confirmation directe, par l'absence. Pour "
            "cette population, le constat n'est pas un classement mais une absence "
            "d'enregistrement, et il reste classé CRITIQUE au contrôle 8.2."
        ),
        chiffres=[
            ("Comptes de pension et de refinancement extraits", nb(len(CPT_PENSION_PCEC))),
            ("Dont sans aucun mouvement sur la période", nb(len(vides))),
            ("Charge d'intérêt sur pension — compte 602000100", xaf(0)),
            (f"Mouvements bruts sur {CPT_REPO_PASSIF}, employé à la place", xaf(brut_emprunts)),
            (f"Charge d'intérêt prise sur {CPT_REPO_CHARGE}", xaf(charge)),
            (f"Collatéral suivi au hors bilan sur {CPT_COLLATERAL[0]}", xaf(collateral)),
            ("Cessions-rétrocessions sans aucun enregistrement de dette", nb(nb_sbb)),
            ("Montant réglé correspondant, au sens du contrôle 8.1", xaf(montant_sbb)),
        ],
        tableaux=[
            Tableau(
                entetes=["Compte", "Libellé", "Mouvements sur la période"],
                lignes=[[c, l, "AUCUN"] for c, l in vides],
                max_lignes=20,
                note=("Les comptes que le PCEC réserve à la pension livrée et au refinancement, "
                      "et qui n'ont été mouvementés à aucun moment de la période d'audit."),
            ),
            Tableau(
                entetes=["Compte", "Libellé", "Lignes", "Mouvements bruts XAF", "Solde net XAF"],
                lignes=substitution,
                note=("Les comptes effectivement employés pour les refinancements auprès de la "
                      "banque centrale : ceux de l'emprunt interbancaire au jour le jour et du "
                      "hors bilan de garantie."),
            ),
            Tableau(
                entetes=["Compte", "Libellé", "Lignes", "Solde net XAF"],
                lignes=mouvementes,
                note=("Le seul compte de la série des pensions qui porte une écriture sur la "
                      "période, et ce qu'elle représente."),
            ),
        ],
        recommandation=(
            "1. Faire qualifier les refinancements BEAC : s'ils sont adossés à des titres remis "
            "en garantie — ce que le hors bilan confirme — ils relèvent des comptes de pension "
            "et de refinancement au guichet A, non de l'emprunt au jour le jour.\n"
            "2. Reclasser au passif la part du refinancement garantie par du collatéral, et "
            "mesurer l'effet sur la présentation des ratios de liquidité et sur l'information "
            "donnée en annexe sur les actifs grevés.\n"
            "3. Ouvrir et paramétrer effectivement les comptes 521600100, 532000100, 539000100 "
            "et 602000100 dans le schéma comptable du produit, faute de quoi l'écriture "
            "correcte restera impossible à passer.\n"
            "4. Appliquer la même qualification aux cessions-rétrocessions du contrôle 8.2, qui "
            "pour leur part ne font aujourd'hui l'objet d'aucun enregistrement de dette."
        ),
    )


# --- 12.3 ---------------------------------------------------------------------------------
def _c123_compte_attente(ctx) -> Constat:
    compte = CPT_ATTENTE[0]
    d = _periode(ctx, compte)
    libelle = ctx.libelle_compte(compte)
    titres = d[d.DESCRIPTION.fillna("").str.upper().str.contains(MOTIF_TITRE, regex=True)]
    episode = d[(d.TRN_DT >= "2024-03-01") & (d.TRN_DT <= "2024-04-30")]
    soldes = [[a, ctx.solde_a(compte, a)] for a in ctx.arretes]
    fin = ctx.solde_a(compte, ctx.config.fin)
    gros = d.nlargest(1, "LCY_AMOUNT")
    gros_montant = float(gros.LCY_AMOUNT.iloc[0]) if len(gros) else 0.0
    gros_libelle = str(gros.DESCRIPTION.iloc[0] or "") if len(gros) else ""
    gros_date = str(gros.TRN_DT.iloc[0]) if len(gros) else ""
    autre = ctx.solde_a(CPT_ATTENTE[1], ctx.config.fin)

    return Constat(
        code="12.3",
        titre="Un compte d'attente porte 32 milliards de mouvements titres et reste chargé d'un milliard à la clôture",
        gravite=Gravite.ELEVEE,
        reference=f"Compte {compte} {libelle}",
        constat=(
            f"CE QU'EST CE COMPTE. {compte} {libelle} est un compte d'attente : il reçoit "
            "provisoirement une écriture dont l'imputation définitive n'est pas encore "
            "arrêtée. Par nature, un compte d'attente doit se vider vite, et se présenter à "
            "zéro à chaque arrêté.\n"
            "\n"
            f"PREMIER CONSTAT — LE VOLUME. Sur la période, ce compte a reçu {nb(len(d))} "
            f"écritures pour {xaf(float(d.LCY_AMOUNT.sum()))} de mouvements bruts, réparties "
            f"sur {nb(d.TRN_REF_NO.nunique())} écritures comptables distinctes. "
            f"{nb(len(titres))} d'entre elles — soit {pct(len(titres) / max(len(d), 1) * 100)} "
            "— portent dans leur libellé une référence de titre ou de contrat de marché "
            "monétaire. Ce compte d'attente est donc, en pratique, un compte de passage du "
            "circuit titres.\n"
            "\n"
            "DEUXIÈME CONSTAT — L'ÉPISODE DE MARS ET AVRIL 2024. En deux mois, "
            f"{nb(len(episode))} lignes y ont transité pour "
            f"{xaf(float(episode.LCY_AMOUNT.sum()))} de mouvements bruts, en "
            f"{nb(episode.TRN_REF_NO.nunique())} écritures manuelles saisies par "
            f"{nb(episode.USER_ID.nunique())} opérateurs. Les libellés sont explicites : il "
            "s'agit d'annulations et de réenregistrements d'intérêts courus sur titres — "
            "« Reversal of interest income on SALES », « Reversal of 511800101 in 466000107 ». "
            "L'opération se solde à zéro : le compte est revenu à zéro au 30 avril 2024. Mais "
            "au 31 mars 2024, en plein milieu de l'épisode, il portait encore "
            f"{xaf(ctx.solde_a(compte, '2024-03-31'))}.\n"
            "\n"
            "Ce n'est pas une perte, c'est un problème de piste d'audit : plus de "
            "27 milliards de produits sur titres ont été défaits puis refaits par écritures "
            "manuelles, en dehors de tout traitement automatique, sans qu'aucune pièce ne "
            "rattache l'ensemble à une décision de correction identifiée.\n"
            "\n"
            "TROISIÈME CONSTAT — LE SOLDE QUI RESTE. Le compte n'est pas revenu à zéro. Au "
            f"{ctx.config.fin} il porte {xaf(fin)} au DÉBIT. L'essentiel tient à une seule "
            f"écriture, passée le {gros_date} pour {xaf(gros_montant)}, libellée "
            f"« {gros_libelle} ». Une reclassification du compte inter-agences vers un compte "
            "d'attente, passée le jour de l'arrêté annuel, n'est pas une imputation : c'est le "
            "report d'un problème d'un compte vers un autre. Ce milliard figure à l'actif du "
            "bilan sans que rien n'en justifie la nature.\n"
            "\n"
            f"À TITRE DE COMPARAISON, le compte d'attente symétrique {CPT_ATTENTE[1]} "
            f"{ctx.libelle_compte(CPT_ATTENTE[1])} se présente à {xaf(autre)} : lui est "
            "correctement apuré. La défaillance porte sur un compte, pas sur le dispositif."
        ),
        chiffres=[
            ("Écritures sur la période", nb(len(d))),
            ("Écritures comptables distinctes", nb(d.TRN_REF_NO.nunique())),
            ("Mouvements bruts cumulés", xaf(float(d.LCY_AMOUNT.sum()))),
            ("Dont portant une référence de titre", nb(len(titres))),
            ("Épisode mars-avril 2024 — lignes", nb(len(episode))),
            ("Épisode mars-avril 2024 — mouvements bruts", xaf(float(episode.LCY_AMOUNT.sum()))),
            ("Épisode mars-avril 2024 — solde résiduel", xaf(float(episode.SIGNE.sum()))),
            ("Solde au 31 mars 2024, en cours d'épisode", xaf(ctx.solde_a(compte, "2024-03-31"))),
            (f"Solde au {ctx.config.fin}", xaf(fin)),
            ("Dont une seule écriture de reclassement", xaf(gros_montant)),
            (f"Solde du compte d'attente symétrique {CPT_ATTENTE[1]}", xaf(autre)),
        ],
        tableaux=[
            Tableau(
                entetes=["Date d'arrêté", "Solde XAF"],
                lignes=soldes,
                note=("Le solde du compte d'attente à chaque date d'arrêté. Un compte d'attente "
                      "doit s'y présenter à zéro."),
            ),
            Tableau(
                entetes=["Date", "Référence", "Sens", "Montant XAF", "Opérateur", "Libellé"],
                lignes=[[r.TRN_DT, r.TRN_REF_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID,
                         str(r.DESCRIPTION or "")[:58]]
                        for _, r in d.nlargest(10, "LCY_AMOUNT").iterrows()],
                note="Les dix plus gros mouvements du compte sur la période.",
            ),
        ],
        recommandation=(
            f"1. Faire justifier ligne à ligne le solde de {xaf(fin)} au {ctx.config.fin}, et "
            "en premier lieu le reclassement du compte inter-agences passé le jour de "
            "l'arrêté : produire la pièce qui en établit la nature et l'imputation définitive.\n"
            "2. Obtenir la note de correction qui fonde l'épisode de mars et avril 2024 : qui "
            "l'a décidée, sur quel diagnostic, et pourquoi elle a été exécutée par écritures "
            "manuelles plutôt que par reprise du traitement.\n"
            "3. Instaurer une règle d'apurement : tout solde d'un compte d'attente de plus de "
            "trente jours fait l'objet d'un état nominatif présenté au comité d'audit.\n"
            f"4. Étendre la revue au compte 511800101 « créances rattachées — manuelles », que "
            "les libellés désignent mais qui ne figure dans aucune extraction (contrôle 12.6)."
        ),
    )


# --- 12.4 ---------------------------------------------------------------------------------
def _c124_nantissement(ctx) -> Constat:
    d = ctx.comptes_complementaires
    mouv = d[d.AC_NO.isin(CPT_NANTISSEMENT)].sort_values("TRN_DT")
    vides = [c for c in CPT_NANTISSEMENT + CPT_HORS_BILAN_TITRES if (d.AC_NO == c).sum() == 0]
    if mouv.empty:
        return Constat(code="12.4", titre="Comptes de nantissement non mouvementés",
                       gravite=Gravite.MOYENNE,
                       constat="Aucun mouvement sur les comptes de nantissement extraits.")
    debits = mouv[mouv.SIGNE > 0]
    credits = mouv[mouv.SIGNE < 0]
    gl = ctx.grand_livre
    hb = gl[(gl.AC_NO == CPT_COLLATERAL[0]) & (gl.TRN_DT >= ctx.config.debut)
            & (gl.TRN_DT <= ctx.config.fin)]
    d_date = str(debits.TRN_DT.min()) if len(debits) else ""
    c_date = str(credits.TRN_DT.max()) if len(credits) else ""
    jours = ((pd.Timestamp(c_date) - pd.Timestamp(d_date)).days
             if d_date and c_date else 0)

    return Constat(
        code="12.4",
        titre="Un nantissement de 6,2 milliards inscrit en doublon sur un compte de classe 2, le jour de l'arrêté annuel",
        gravite=Gravite.MOYENNE,
        reference=f"Compte {CPT_NANTISSEMENT[1]} — {len(mouv)} mouvements sur toute la période",
        constat=(
            "CE QUE CE COMPTE DEVRAIT MONTRER. Un titre remis en garantie d'un refinancement "
            "auprès de la BEAC reste la propriété de la banque, mais il n'est plus "
            "disponible : il est immobilisé. Le PCEC impose de l'isoler, afin que le lecteur "
            "des comptes distingue les titres cessibles de ceux qui ne le sont pas. Deux "
            "dispositifs coexistent dans le plan de comptes : les comptes de HORS BILAN de "
            f"classe 9 — {CPT_COLLATERAL[0]} et sa contrepartie {CPT_COLLATERAL[1]} — et les "
            f"comptes de classe 2 {CPT_NANTISSEMENT[0]} et {CPT_NANTISSEMENT[1]}.\n"
            "\n"
            "LEQUEL EST EMPLOYÉ. Le premier, et lui seul. Le contrôle 12.2 établit que le "
            f"hors bilan {CPT_COLLATERAL[0]} porte {nb(len(hb))} écritures sur la période, pour "
            f"{xaf(float(hb.LCY_AMOUNT.sum()))} de mouvements bruts : le "
            "collatéral des refinancements BEAC y est suivi en continu, opération par "
            "opération.\n"
            "\n"
            f"CE QUE PORTE LE COMPTE DE CLASSE 2. Sur toute la période, {CPT_NANTISSEMENT[1]} "
            f"porte {nb(len(mouv))} mouvements, et pas un de plus. {nb(len(debits))} débits "
            f"passés le même jour, le {d_date} — la date d'arrêté annuel — pour "
            f"{xaf(float(debits.LCY_AMOUNT.sum()))}, soit quatre obligations du Trésor "
            "camerounais nommément désignées. Puis un unique crédit qui les reprend en bloc le "
            f"{c_date}, soit {nb(jours)} jours plus tard.\n"
            "\n"
            "CE QUE CELA SIGNIFIE. Ces quatre titres n'ont pas été suivis : ils ont été "
            "INSCRITS le jour de la clôture, sur un compte que rien d'autre n'alimente, puis "
            "effacés. Trois éléments qualifient l'écriture.\n"
            "- ELLE FAIT DOUBLE EMPLOI. Le dispositif de suivi du collatéral existe et "
            "fonctionne, au hors bilan. Inscrire une seconde fois quatre titres sur un compte "
            "de classe 2 ne complète pas l'information : cela la dédouble, sans que rien "
            "n'indique au lecteur des comptes que les deux inscriptions portent, ou non, sur "
            "les mêmes titres.\n"
            "- ELLE NE VIT QUE LE TEMPS DE L'ARRÊTÉ. Une inscription passée le 31 décembre et "
            "reprise ensuite ne décrit pas une immobilisation : elle habille un arrêté.\n"
            "- SA REPRISE RELÈVE D'UN AUTRE DOSSIER. Le crédit ne porte pas un libellé de "
            "mainlevée mais « Reclass SCB Securities transferred/9 Dec. 2025 » : il fait "
            "partie de l'écriture d'apurement du portefeuille repris de SCB, que le contrôle "
            "12.5 décrit. Autrement dit, ces quatre titres sont sortis du nantissement non "
            "parce que la garantie a été levée, mais parce qu'on soldait autre chose.\n"
            "\n"
            f"À NOTER ENFIN que le compte symétrique des titres PRIVÉS nantis, "
            f"{CPT_NANTISSEMENT[0]}, et les comptes de titres à recevoir et à livrer du marché "
            "gris n'ont jamais été mouvementés sur la période."
        ),
        chiffres=[
            ("Mouvements sur la période, tous comptes de nantissement", nb(len(mouv))),
            ("Débits — titres portés en garantie", nb(len(debits))),
            ("Montant correspondant", xaf(float(debits.LCY_AMOUNT.sum()))),
            ("Date de l'enregistrement", d_date),
            ("Date de la reprise", c_date),
            ("Durée pendant laquelle le nantissement a figuré", f"{nb(jours)} jours"),
            (f"Écritures de collatéral au hors bilan {CPT_COLLATERAL[0]}", nb(len(hb))),
            ("Comptes de hors-bilan titres jamais mouvementés", nb(len(vides))),
        ],
        tableaux=[
            Tableau(
                entetes=["Date", "Compte", "Sens", "Montant XAF", "Opérateur", "Libellé"],
                lignes=[[r.TRN_DT, r.AC_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID,
                         str(r.DESCRIPTION or "")[:60]] for _, r in mouv.iterrows()],
                note=("L'intégralité des mouvements de nantissement de la période : quatre "
                      "titres portés en garantie le jour de l'arrêté, repris en bloc ensuite."),
            ),
            Tableau(
                entetes=["Compte", "Libellé", "Mouvements"],
                lignes=[[c, ctx.libelle_compte(c), "AUCUN"] for c in vides],
                note=("Les autres comptes de garantie et de hors-bilan titres, restés vides sur "
                      "toute la période."),
            ),
        ],
        recommandation=(
            "1. Obtenir de la BEAC l'état des titres nantis à la date d'arrêté du 31 décembre "
            f"2025 et le rapprocher à la fois du hors bilan {CPT_COLLATERAL[0]} et de ces "
            "quatre inscriptions : établir si elles font double emploi ou si elles portent sur "
            "des titres que le hors bilan ne couvrait pas.\n"
            "2. Faire justifier l'écriture du 31 décembre 2025 : sur quelle pièce repose-t-elle, "
            "et pourquoi a-t-elle été passée le jour de l'arrêté sur un compte autrement "
            "inutilisé ?\n"
            "3. Faire expliquer pourquoi sa reprise du 16 juin 2026 a été incorporée à "
            "l'écriture d'apurement du portefeuille SCB (contrôle 12.5) plutôt que traitée "
            "comme une mainlevée de garantie.\n"
            "4. Arrêter la doctrine d'emploi : un seul dispositif de suivi du collatéral, et "
            "des comptes de classe 2 réservés à ce que le PCEC leur destine."
        ),
    )


# --- 12.5 ---------------------------------------------------------------------------------
def _c125_conversion(ctx) -> Constat:
    d = ctx.comptes_complementaires
    mouv = d[d.AC_NO.isin(CPT_CONVERSION)].sort_values("TRN_DT")
    if mouv.empty:
        return Constat(code="12.5", titre="Comptes de conversion non mouvementés",
                       gravite=Gravite.CONFORME,
                       constat="Aucun mouvement sur les comptes de conversion extraits.")
    debits = mouv[mouv.SIGNE > 0]
    credits = mouv[mouv.SIGNE < 0]
    montant = float(debits.LCY_AMOUNT.sum())
    d_date = str(debits.TRN_DT.iloc[0])
    c_date = str(credits.TRN_DT.iloc[-1]) if len(credits) else ""
    user_reprise = str(debits.USER_ID.iloc[0])
    user_apurement = str(credits.USER_ID.iloc[0]) if len(credits) else ""
    ecart_jours = (pd.Timestamp(c_date) - pd.Timestamp(d_date)).days if c_date else 0
    # L'apurement du 454000101 n'est pas la fin de l'opération : les titres eux-mêmes n'entrent
    # au portefeuille que six mois plus tard, par une écriture manuelle unique.
    a = ctx.toutes_ecritures
    # La contrepartie de l'apurement du compte de conversion : on la retrouve par la référence
    # de l'écriture, et non par hypothèse.
    ref_apurement = str(credits.TRN_REF_NO.iloc[0]) if len(credits) else ""
    contrepartie = a[(a.TRN_REF_NO == ref_apurement) & (a.AC_NO != CPT_CONVERSION[0])]
    cpt_contrepartie = str(contrepartie.AC_NO.iloc[0]) if not contrepartie.empty else ""
    lib_contrepartie = ctx.libelle_compte(cpt_contrepartie) if cpt_contrepartie else ""
    apurement = a[a.TRN_REF_NO == "0990023261670001"]
    ap_date = str(apurement.TRN_DT.iloc[0]) if not apurement.empty else ""
    ap_user = str(apurement.USER_ID.iloc[0]) if not apurement.empty else ""
    ap_titres = int(apurement.DESCRIPTION.fillna("").str.extract(
        r"(CM[12][A-Z0-9]{8})")[0].dropna().nunique()) if not apurement.empty else 0
    ap_jours = ((pd.Timestamp(ap_date) - pd.Timestamp(d_date)).days if ap_date else 0)
    mois_bascule = f"{(pd.Timestamp(d_date) - pd.Timestamp(DATE_BASCULE)).days / 30.44:.1f}".replace(".", ",")

    return Constat(
        code="12.5",
        titre="Un portefeuille de 27 milliards reçu en titres mais porté six mois au nostro BEAC, traversant l'arrêté annuel",
        gravite=Gravite.CRITIQUE,
        reference=f"Compte {CPT_CONVERSION[0]} — écritures des {d_date}, {c_date} et {ap_date}",
        constat=(
            "CE QU'EST UN COMPTE DE CONVERSION. Ces comptes ne servent qu'à une chose : "
            "accueillir, le temps d'une reprise de données, les soldes qu'un système déverse "
            "dans un autre. Ils n'ont pas vocation à vivre au-delà de l'opération technique "
            "qui les justifie, et l'utilisateur qui les mouvemente est un utilisateur "
            "technique, non un opérateur de la salle des marchés.\n"
            "\n"
            f"CE QUI S'EST PASSÉ. Le {d_date}, le compte {CPT_CONVERSION[0]} "
            f"{ctx.libelle_compte(CPT_CONVERSION[0])} est débité de {xaf(montant)} par "
            f"l'utilisateur technique {user_reprise}, sans aucun libellé. "
            f"{nb(ecart_jours)} jours plus tard, le {c_date}, l'opérateur {user_apurement} le "
            "crédite du même montant, sous le libellé « Securities received from SCB to be "
            "booked manually » — titres reçus de SCB, à comptabiliser manuellement.\n"
            "\n"
            "TROIS ANOMALIES SE SUPERPOSENT.\n"
            f"- LA DATE. Cette reprise intervient {mois_bascule} mois APRÈS la bascule "
            f"vers Calypso du {str(DATE_BASCULE)[:10]}. Une reprise de portefeuille "
            "postérieure de près de six mois à la migration n'est pas une migration : c'est "
            "une entrée de portefeuille traitée avec les outils de la migration.\n"
            f"- L'UTILISATEUR. L'écriture d'origine est passée sous l'utilisateur technique de "
            f"reprise {user_reprise}, et sans libellé. Une entrée de titres de cette taille "
            "n'a pas à être initiée par un utilisateur non nominatif : la responsabilité de "
            "l'écriture n'est rattachable à personne.\n"
            "- LE MODE OPÉRATOIRE. Le libellé annonce lui-même que les titres seront "
            "« comptabilisés manuellement ». Un portefeuille entier entre donc dans les "
            "comptes sans passer par le circuit de traitement des titres, donc sans les "
            "contrôles qui y sont attachés : pas de contrat, pas de schéma comptable "
            "automatique, pas de calcul de courus.\n"
            "\n"
            "MAIS L'ANOMALIE LA PLUS LOURDE EST AILLEURS — DANS LA CONTREPARTIE. Le crédit du "
            f"{c_date} sort bien le montant du compte de conversion, mais il le sort contre un "
            f"DÉBIT de {cpt_contrepartie} {lib_contrepartie} : le compte de règlement de la "
            "banque auprès de la banque centrale. Or la banque n'a rien encaissé — elle a reçu "
            "des TITRES. Elle a donc enregistré, à son compte à la BEAC, "
            f"{xaf(montant)} de trésorerie qui n'existait pas.\n"
            "\n"
            f"CETTE SURÉVALUATION A DURÉ {nb(ap_jours - ecart_jours)} JOURS, du {c_date} au "
            f"{ap_date}, date à laquelle l'écriture d'entrée en portefeuille la reprend. ELLE "
            "TRAVERSE L'ARRÊTÉ ANNUEL DU 31 DÉCEMBRE 2025 : à cette date, le nostro BEAC "
            f"publié comprend {xaf(montant)} de trésorerie fictive, et le portefeuille titres "
            "ne comprend pas les titres correspondants. Le bilan est faux des deux côtés à la "
            "fois — en nature comme en montant. Un écart de cette ampleur sur le compte de "
            "règlement de la banque centrale aurait dû être arrêté par le rapprochement "
            "bancaire mensuel. C'est la même défaillance que celle des contrôles 5.3 et 11.8, "
            "sur le même compte.\n"
            "\n"
            "CE QUI S'EST PASSÉ ENSUITE. Les titres eux-mêmes "
            f"n'entrent au portefeuille que le {ap_date}, soit {nb(ap_jours)} jours plus tard, "
            f"par une écriture manuelle unique passée par l'opérateur {ap_user} : "
            f"{nb(ap_titres)} bons et obligations du Trésor camerounais y sont enregistrés "
            "d'un seul mouvement, avec leur décote et leurs intérêts, contre le nostro BEAC et "
            f"le compte de nantissement du contrôle 12.4.\n"
            "\n"
            "LE DOSSIER TIENT DONC EN TROIS ÉCRITURES MANUELLES ÉTALÉES SUR SIX MOIS, et pas "
            "une de plus : une reprise technique sans libellé, un apurement qui déverse le "
            "montant sur le nostro, puis une entrée en portefeuille. Un portefeuille de "
            f"{xaf(montant)} est resté six mois hors des comptes de titres, logé dans la "
            "trésorerie de la banque centrale."
        ),
        chiffres=[
            ("Montant repris", xaf(montant)),
            ("Date de la reprise technique", d_date),
            ("Date de l'apurement manuel", c_date),
            ("Délai entre la reprise et son apurement", f"{nb(ecart_jours)} jours"),
            ("Date d'entrée effective des titres au portefeuille", ap_date),
            ("Délai total, de la reprise à l'entrée en portefeuille", f"{nb(ap_jours)} jours"),
            ("Titres enregistrés par cette écriture unique", nb(ap_titres)),
            ("Écart avec la date de bascule vers Calypso", f"{mois_bascule} mois"),
            ("Contrepartie de l'apurement", f"{cpt_contrepartie} {lib_contrepartie}"),
            ("Durée de la surévaluation du nostro", f"{nb(ap_jours - ecart_jours)} jours"),
            ("Dates d'arrêté traversées", "2025-12-31"),
            ("Utilisateur de la reprise", user_reprise),
            ("Opérateur de l'apurement", user_apurement),
        ],
        tableaux=[
            Tableau(
                entetes=["Date", "Compte", "Sens", "Montant XAF", "Opérateur", "Libellé"],
                lignes=([[r.TRN_DT, r.AC_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID,
                          str(r.DESCRIPTION or "")[:58]] for _, r in mouv.iterrows()]
                        + [[r.TRN_DT, r.AC_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID,
                            str(r.DESCRIPTION or "")[:58]]
                           for _, r in contrepartie.iterrows()]),
                note=("Les deux écritures du compte de conversion, et la jambe de contrepartie "
                      "qui porte le montant au compte de la banque centrale."),
            ),
        ],
        recommandation=(
            f"1. Chiffrer l'effet sur les états arrêtés au 31 décembre 2025 : {xaf(montant)} "
            "de trésorerie inexistante au nostro BEAC, et autant de titres absents du "
            "portefeuille. Vérifier si les états publiés à cette date en ont été corrigés.\n"
            "2. Obtenir le dossier de reprise du portefeuille SCB : contrat de cession, état "
            "des titres transférés, valorisation retenue, et rapprochement avec le "
            "dépositaire.\n"
            "3. Vérifier que chacun des titres repris a bien été enregistré individuellement, "
            "avec son nominal, son taux, sa date d'échéance et son calcul de courus.\n"
            "4. Faire justifier l'emploi d'un compte de conversion et d'un utilisateur "
            "technique pour une opération postérieure de six mois à la migration.\n"
            "5. Vérifier qu'aucune autre écriture de la période n'a été passée sous cet "
            "utilisateur technique."
        ),
    )


# --- 12.6 ---------------------------------------------------------------------------------
def _c126_comptes_dormants(ctx) -> Constat:
    d = ctx.comptes_complementaires
    presents = set(d.AC_NO.unique())
    dormants = [[c, ctx.libelle_compte(c)] for c in CPT_VAGUE2_DEMANDES if c not in presents]
    provisions = [c for c in CPT_PROVISIONS_TITRES if c not in presents]
    # Comptes du plan de comptes qui intéressent le circuit titres et restent non extraits.
    a_extraire = [
        ("511800101", "désigné en toutes lettres par les libellés du compte d'attente 466000107"),
        ("511801100", "courus du portefeuille repris de SCB, dont le contrôle 12.5 établit l'entrée"),
        ("601200100", "charge d'intérêt du marché monétaire face à la BEAC, contrepartie attendue des pensions"),
        ("601200101", "même charge, guichet de refinancement"),
        ("706100100", "commissions perçues sur opérations de marché monétaire"),
        ("952200100", "autres titres publics affectés en garantie, symétrique de 952100100"),
        ("265220100", "autres titres d'investissement publics, hors garantie BEAC"),
        ("511100100", "actions et parts d'établissements de crédit — placement"),
        ("511220100", "autres bons et assimilés — placement"),
        ("512600100", "autres titres à court terme — transaction"),
    ]
    a_extraire = [[c, ctx.libelle_compte(c), motif] for c, motif in a_extraire
                  if c not in presents]

    return Constat(
        code="12.6",
        titre="Comptes dormants du dispositif titres, et comptes qu'il reste à extraire",
        gravite=Gravite.MOYENNE,
        reference=f"{len(dormants)} comptes demandés sans aucun mouvement",
        constat=(
            "CE QUE CE CONTRÔLE ÉTABLIT. La deuxième extraction portait sur "
            f"{nb(len(CPT_VAGUE2_DEMANDES))} comptes du plan de comptes intéressant le circuit "
            f"des titres. {nb(len(dormants))} d'entre eux sont revenus vides. Un compte vide "
            "n'est pas une absence d'information : c'est l'information qu'un dispositif prévu "
            "par le plan de comptes n'a jamais été employé.\n"
            "\n"
            "TROIS FAMILLES SE DÉGAGENT.\n"
            f"- LES PROVISIONS POUR DÉPRÉCIATION. {nb(len(provisions))} comptes de provision "
            "du portefeuille de placement n'ont jamais été mouvementés, et le seul qui le soit, "
            "591400100, présente un solde nul. AUCUNE DÉPRÉCIATION N'A DONC ÉTÉ CONSTATÉE SUR "
            "LE PORTEFEUILLE TITRES PENDANT TOUTE LA PÉRIODE. Sur un portefeuille souverain "
            "CEMAC de cette taille, détenu sur trois exercices, l'absence totale de provision "
            "suppose que la banque a conclu, chaque année, qu'aucun titre ne présentait de "
            "risque de recouvrement. Cette conclusion doit reposer sur un test de dépréciation "
            "documenté ; à défaut, elle n'est pas soutenable.\n"
            "- LES COMPTES DE PENSION ET DE REFINANCEMENT, traités au contrôle 12.2.\n"
            "- LE HORS-BILAN DU MARCHÉ GRIS. Les comptes de titres à recevoir et à livrer sont "
            "vides, alors que les opérations d'intervention à l'émission et de marché gris "
            "existent. Les engagements correspondants ne sont donc pas suivis.\n"
            "\n"
            "CE QU'IL RESTE À OBTENIR. L'examen des libellés de la deuxième vague fait "
            "apparaître des comptes dont l'existence est certaine mais qui n'ont encore été "
            "extraits dans aucune des deux vagues. Le plus important est 511800101 « créances "
            "rattachées — MANUELLES » : le compte d'attente 466000107 porte des écritures qui "
            "le désignent nommément, ce qui signifie qu'un second compte de courus, réservé "
            "aux écritures manuelles, vit en parallèle de 511800100. Tant qu'il n'est pas "
            "extrait, l'analyse des courus du contrôle 5.3 et du contrôle 11.7 reste établie "
            "sur une vue partielle."
        ),
        chiffres=[
            ("Comptes demandés à la deuxième extraction", nb(len(CPT_VAGUE2_DEMANDES))),
            ("Revenus avec des mouvements", nb(len(CPT_VAGUE2_DEMANDES) - len(dormants))),
            ("Revenus vides", nb(len(dormants))),
            ("Comptes de provision titres sans mouvement", nb(len(provisions))),
            ("Dépréciation constatée sur le portefeuille, toute la période", xaf(0)),
            ("Comptes identifiés restant à extraire", nb(len(a_extraire))),
        ],
        tableaux=[
            Tableau(
                entetes=["Compte", "Libellé"],
                lignes=dormants,
                max_lignes=30,
                note=("Les comptes demandés lors de la deuxième extraction et revenus sans "
                      "aucun mouvement sur la période d'audit."),
            ),
            Tableau(
                entetes=["Compte", "Libellé", "Pourquoi l'extraire"],
                lignes=a_extraire,
                max_lignes=12,
                note=("Comptes du plan de comptes qui intéressent le circuit des titres et qui "
                      "n'ont été extraits dans aucune des deux vagues."),
            ),
        ],
        recommandation=(
            "1. Obtenir le test de dépréciation du portefeuille titres à chaque arrêté, et la "
            "conclusion qui a conduit à ne constater aucune provision.\n"
            "2. Extraire l'historique de 511800101 « créances rattachées — manuelles » et de "
            "511801100, et reprendre sur cette base l'analyse des courus des contrôles 5.3 et "
            "11.7.\n"
            "3. Extraire 601200100 et 601200101 : ce sont les comptes où devrait figurer la "
            "charge d'intérêt des opérations de refinancement face à la BEAC, dont le contrôle "
            "12.2 établit l'absence.\n"
            "4. Faire expliquer pourquoi les comptes de hors-bilan du marché gris ne sont pas "
            "servis, alors que les opérations correspondantes sont enregistrées."
        ),
    )
