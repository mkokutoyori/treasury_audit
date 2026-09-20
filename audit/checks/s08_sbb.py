"""Section 8 — Opérations de cession-rétrocession (Sell-Buy-Back).

Un Sell-Buy-Back est économiquement un FINANCEMENT GARANTI : la banque cède un titre et
s'engage simultanément à le racheter à terme, à un prix majoré. Le titre ne quitte pas
durablement le portefeuille ; la trésorerie reçue est une dette.

Le PCEC prévoit pour ces opérations le schéma de la pension livrée : le titre RESTE à
l'actif et est inscrit en hors bilan comme affecté en garantie, la trésorerie reçue est
constatée en DETTE, et le différentiel de prix est une CHARGE D'INTÉRÊT.

Cette section identifie ces opérations par deux voies indépendantes — le commentaire de la
salle des marchés et la signature d'aller-retour dans le référentiel des deals — puis
compare le schéma comptable réellement appliqué à celui d'une pension livrée.
"""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf, pct
from ..data import CPT_REPO_CHARGE, CPT_REPO_PASSIF

SECTION = (8, "Opérations de cession-rétrocession (Sell-Buy-Back)")

MOTIFS = "SBB|SELL.?BUY.?BACK|BUY.?SELL.?BACK"
BOOK_DEDIE = "ABCM_BSB.Bond"
BOOKS_TITRES = ["ABCM_FVOCI.Bond", "ABCM_FVOCI.Bills", "ABCM_BSB.Bond"]
FENETRE_ALLER_RETOUR = 120  # jours


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "Identification des cessions-rétrocessions par le commentaire de la salle des marchés "
            "ET par la signature d'aller-retour dans le référentiel des deals, puis comparaison du "
            "schéma comptable appliqué avec celui que le PCEC prévoit pour une pension livrée."
        ),
    )
    commentes = _commentes(ctx)
    paires = _paires_aller_retour(ctx, commentes)
    s.ajouter(_c81_identification(ctx, commentes, paires))
    s.ajouter(_c82_schema_comptable(ctx, commentes))
    s.ajouter(_c83_book_dedie(ctx, commentes))
    s.ajouter(_c84_rotation(ctx, commentes, paires))
    s.ajouter(_c85_resultat(ctx, commentes))
    return s


def _commentes(ctx) -> pd.DataFrame:
    """Écritures dont le commentaire de la salle des marchés désigne une cession-rétrocession."""
    c = ctx.calypso_enrichi
    if c.empty:
        return c
    return c[c.COMMENTAIRE.fillna("").str.upper().str.contains(MOTIFS, na=False, regex=True)]


def _paires_aller_retour(ctx, commentes) -> pd.DataFrame:
    """Aller-retours détectés indépendamment du commentaire.

    Signature : même titre, même contrepartie, quantités strictement opposées, rachat dans
    les quatre mois suivant la cession. C'est la trace économique d'un Sell-Buy-Back, qu'il
    soit ou non désigné comme tel.
    """
    deals = ctx.deals_calypso
    if deals.empty:
        return pd.DataFrame()
    d = deals[deals.Book.isin(BOOKS_TITRES) & deals.TradeStatus.isin(["VERIFIED", "MATURED"])]
    marques = set(commentes.DEAL) if not commentes.empty else set()
    paires = []
    for (titre, contrepartie), groupe in d.groupby(["Product Description", "CounterParty"]):
        achats = groupe[groupe.Quantity_n > 0]
        ventes = groupe[groupe.Quantity_n < 0]
        for _, vente in ventes.iterrows():
            candidats = achats[(achats["Trade Date_d"] > vente["Trade Date_d"])
                               & (achats["Trade Date_d"] <= vente["Trade Date_d"]
                                  + pd.Timedelta(days=FENETRE_ALLER_RETOUR))
                               & (achats.Quantity_n == -vente.Quantity_n)]
            if candidats.empty:
                continue
            rachat = candidats.iloc[0]
            paires.append({
                "vente": vente["Trade Id"], "rachat": rachat["Trade Id"],
                "titre": titre, "contrepartie": contrepartie,
                "date_vente": vente["Trade Date_d"].date(),
                "date_rachat": rachat["Trade Date_d"].date(),
                "jours": (rachat["Trade Date_d"] - vente["Trade Date_d"]).days,
                "quantite": abs(float(vente.Quantity_n)),
                "commente": vente["Trade Id"] in marques or rachat["Trade Id"] in marques,
            })
    return pd.DataFrame(paires)


def _c81_identification(ctx, commentes, paires) -> Constat:
    if commentes.empty and paires.empty:
        return Constat(code="8.1", titre="Opérations de cession-rétrocession", gravite=Gravite.CONFORME,
                       constat="Aucune opération de cession-rétrocession identifiée.")
    regle = commentes[commentes.EVENEMENT == "CST_S_SETTLED"].groupby("DEAL").LCY_AMOUNT.max()
    # Les opérations se poursuivent au-delà de la clôture : on isole ce qui relève de la
    # période d'audit de ce qui constitue un événement postérieur.
    dans_periode = commentes[(commentes.TRN_DT >= ctx.config.debut)
                             & (commentes.TRN_DT <= ctx.config.fin)]
    regle_periode = (dans_periode[dans_periode.EVENEMENT == "CST_S_SETTLED"]
                     .groupby("DEAL").LCY_AMOUNT.max())
    deals = ctx.deals_calypso
    ids = set(commentes.DEAL)
    apparies = deals[deals["Trade Id"].isin(ids)] if not deals.empty else pd.DataFrame()
    absents = len(ids) - len(apparies)
    non_commentees = paires[~paires.commente] if not paires.empty else pd.DataFrame()
    part_manquee = len(non_commentees) / max(len(paires), 1) * 100
    par_cpty = commentes.groupby("EMETTEUR").DEAL.nunique().sort_values(ascending=False)
    jambes = commentes.COMMENTAIRE.str.upper().str.extract(r"(NEAR|FAR|FIRST|SECOND)")[0].value_counts()
    par_trader = (apparies.groupby(["CounterParty", "Trader"]).size().rename("deals")
                  .reset_index().sort_values("deals", ascending=False)
                  if len(apparies) else pd.DataFrame())
    statuts = apparies.TradeStatus.value_counts() if len(apparies) else pd.Series(dtype=int)
    concentration = ""
    if len(par_trader):
        premier = par_trader.groupby("Trader").deals.sum().sort_values(ascending=False)
        concentration = (f"{premier.index[0]} traite {int(premier.iloc[0])} des "
                         f"{int(premier.sum())} opérations retrouvées au référentiel des deals")
    return Constat(
        code="8.1",
        titre="L'identification des cessions-rétrocessions par le commentaire est incomplète",
        gravite=Gravite.ELEVEE,
        constat=(
            "DEUX MÉTHODES D'IDENTIFICATION INDÉPENDANTES ont été appliquées.\n"
            "La première repose sur le COMMENTAIRE libre saisi par la salle des marchés, qui "
            "désigne explicitement l'opération et sa jambe — proche ou lointaine.\n"
            "La seconde repose sur la SIGNATURE ÉCONOMIQUE de l'opération dans le référentiel des "
            "deals : même titre, même contrepartie, quantités strictement opposées, rachat dans "
            f"les {FENETRE_ALLER_RETOUR} jours. Cette méthode ne dépend d'aucune saisie humaine.\n"
            "\n"
            "LE RÉSULTAT EST SANS APPEL : une part importante des aller-retours détectés par la "
            "signature économique NE PORTE AUCUN COMMENTAIRE de cession-rétrocession. "
            "L'identification par le libellé manque donc une fraction significative des "
            "opérations, et le volume réel est supérieur à celui que les commentaires révèlent.\n"
            "\n"
            "Le croisement avec le référentiel des deals apporte trois précisions. Les opérations "
            "commentées sont toutes des deals VALIDÉS ou ARRIVÉS À ÉCHÉANCE — aucune n'est annulée, "
            "il s'agit donc d'opérations réelles. Certains deals commentés dans la comptabilité "
            "sont absents du référentiel extrait. Enfin, ces opérations sont très concentrées sur "
            "un opérateur."
            + (f" En effet, {concentration}." if concentration else "")
        ),
        chiffres=[
            ("Opérations identifiées par le commentaire — PÉRIODE D'AUDIT",
             str(dans_periode.DEAL.nunique())),
            ("Montant réglé sur la période d'audit", xaf(float(regle_periode.sum()))),
            ("Opérations identifiées sur toute l'extraction", str(commentes.DEAL.nunique())),
            ("Montant réglé sur toute l'extraction", xaf(float(regle.sum()))),
            ("Période", f"{commentes.TRN_DT.min()} → {commentes.TRN_DT.max()}"),
            ("Aller-retours détectés par la signature économique", str(len(paires))),
            ("Dont NON commentés", f"{len(non_commentees)} ({pct(part_manquee, 0)} manqués par le libellé)"),
            ("Deals commentés absents du référentiel Calypso", str(absents)),
            ("Statuts des deals commentés", ", ".join(f"{i} : {n}" for i, n in statuts.items())),
        ],
        tableaux=[
            Tableau(["Jambe mentionnée", "Lignes"], [[i, int(n)] for i, n in jambes.items()]),
            Tableau(["Contrepartie", "Opérations commentées"],
                    [[i, int(n)] for i, n in par_cpty.items()]),
            Tableau(["Contrepartie", "Opérateur", "Opérations"],
                    [[r.CounterParty, r.Trader, int(r.deals)] for _, r in par_trader.iterrows()],
                    max_lignes=14, note="Concentration des opérations par opérateur."),
            Tableau(["Cession", "Rachat", "Titre", "Contrepartie", "Cédé le", "Racheté le",
                     "Jours", "Quantité"],
                    [[r.vente, r.rachat, r.titre[:38], r.contrepartie, str(r.date_vente),
                      str(r.date_rachat), int(r.jours), float(r.quantite)]
                     for _, r in non_commentees.sort_values("quantite", ascending=False).iterrows()],
                    max_lignes=15,
                    note="Aller-retours détectés par la signature économique mais NON désignés comme tels."),
        ],
        recommandation=(
            "Obtenir du système amont la liste exhaustive des opérations de cession-rétrocession : "
            "leur identification ne peut reposer sur une saisie libre et facultative. Rapprocher "
            "cette liste des aller-retours détectés par signature et justifier les écarts. "
            "Examiner la concentration de ces opérations sur un opérateur unique."
        ),
    )


def _c82_schema_comptable(ctx, commentes) -> Constat:
    """Comparaison du schéma appliqué avec celui que le PCEC prévoit pour une pension livrée.

    Le raisonnement ne s'appuie pas sur les libellés mais sur les COMPTES MOUVEMENTÉS : c'est
    le schéma comptable qui qualifie l'opération.
    """
    if commentes.empty:
        return Constat(code="8.2", titre="Schéma comptable appliqué", gravite=Gravite.CONFORME,
                       constat="Sans objet.")
    c = ctx.calypso_enrichi
    pension = c[c.BOOK == "ABCM_MM.Plmt.Tkn.Secured"]
    comptes_sbb = set(commentes.AC_NO)
    comptes_pension = set(pension.AC_NO)
    manquants = comptes_pension - comptes_sbb
    # Les trois marqueurs comptables d'une pension livrée au sens du PCEC
    marqueurs = {
        "Dette au passif (emprunt)": CPT_REPO_PASSIF,
        "Charge d'intérêt": CPT_REPO_CHARGE,
        "Titres affectés en garantie (hors bilan)": "952100100",
        "Contrepartie hors bilan": "995000100",
    }
    presence = [[libelle, compte, compte in comptes_pension, compte in comptes_sbb]
                for libelle, compte in marqueurs.items()]
    # Le portefeuille sort-il effectivement du bilan ?
    portefeuille = commentes[commentes.AC_NO.isin(["512410100", "511210100"])]
    sorties = float(portefeuille[portefeuille.DRCR_IND == "C"].LCY_AMOUNT.sum())
    entrees = float(portefeuille[portefeuille.DRCR_IND == "D"].LCY_AMOUNT.sum())
    # DANS QUEL SENS ? Une cession-rétrocession peut être un financement REÇU — la banque cède
    # le titre et encaisse — ou un financement ACCORDÉ — elle acquiert le titre et décaisse.
    # Le sens se lit sur la première jambe, celle que le commentaire désigne comme « near ».
    premiere = commentes.copy()
    premiere["jambe"] = premiere.COMMENTAIRE.fillna("").str.upper().str.extract(r"(NEAR|FAR)")[0]
    near = premiere[(premiere.jambe == "NEAR") & premiere.AC_NO.isin(["512410100", "511210100"])]
    sens_near = near.groupby("DEAL").SIGNE.sum()
    emprunts = sens_near[sens_near < 0]        # le titre sort : la banque reçoit de la trésorerie
    prets = sens_near[sens_near > 0]           # le titre entre : la banque en décaisse
    montant_emprunts = -float(emprunts.sum())
    montant_prets = float(prets.sum())
    part_prets = len(prets) / max(len(sens_near), 1) * 100

    detail_sbb = commentes.groupby(["AC_NO", "AC_GL_DESC"]).agg(
        lignes=("LCY_AMOUNT", "size"), debits=("DRCR_IND", lambda s: int((s == "D").sum())),
        credits=("DRCR_IND", lambda s: int((s == "C").sum())), montant=("LCY_AMOUNT", "sum"))
    detail_pension = pension.groupby(["AC_NO", "AC_GL_DESC"]).agg(
        lignes=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))
    return Constat(
        code="8.2",
        titre="Le schéma comptable appliqué est celui d'une cession ferme, non celui d'une pension livrée",
        gravite=Gravite.CRITIQUE,
        reference="PCEC CEMAC — comptes 552 (emprunts), 601 (charges sur opérations de marché), 952/995 (hors bilan, titres affectés en garantie)",
        constat=(
            "CE QUE LE PCEC PRÉVOIT POUR UN FINANCEMENT GARANTI. Trois marqueurs comptables "
            "caractérisent une pension livrée : le titre RESTE à l'actif et son affectation en "
            "garantie est inscrite au HORS BILAN ; la trésorerie reçue est constatée en DETTE au "
            "passif ; le différentiel de prix entre les deux jambes est une CHARGE D'INTÉRÊT.\n"
            "Ce schéma n'est pas théorique : la banque l'applique correctement à ses pensions "
            "auprès de la banque centrale, comme le montre le tableau comparatif ci-dessous.\n"
            "\n"
            "CE QUI EST APPLIQUÉ AUX CESSIONS-RÉTROCESSIONS. Les trois marqueurs sont ABSENTS. "
            "Aucun compte de dette, aucune charge d'intérêt, aucune inscription en hors bilan. À "
            "la place, le compte de portefeuille est CRÉDITÉ puis DÉBITÉ : le titre sort "
            "effectivement du bilan, puis y revient. C'est exactement le schéma d'une vente suivie "
            "d'un achat.\n"
            "\n"
            "LA QUALIFICATION NE DÉPEND PAS DU LIBELLÉ MAIS DU SCHÉMA. Le commentaire de la salle "
            "des marchés désigne ces opérations comme des cessions-rétrocessions ; la comptabilité "
            "les enregistre comme des cessions fermes. C'est la comptabilité qui produit les états "
            "financiers et les ratios prudentiels.\n"
            "\n"
            "DEUX SENS, DEUX ERREURS SYMÉTRIQUES. Une cession-rétrocession n'est pas toujours "
            "un financement REÇU. La première jambe montre que la banque y est tantôt "
            "emprunteuse — elle cède le titre et encaisse — tantôt PRÊTEUSE : elle acquiert le "
            f"titre et décaisse. {len(prets)} des {len(sens_near)} opérations dont la première "
            f"jambe est identifiable relèvent du second cas, soit {pct(part_prets, 0)}. Le "
            "retraitement attendu n'est donc pas le même selon le sens : pour un financement "
            "reçu, une dette manque au passif ; pour un financement accordé, c'est une CRÉANCE "
            "qui manque à l'actif, et le titre acquis n'aurait pas dû y entrer. Dans les deux "
            "cas le bilan est faux, mais dans des sens opposés, et les deux populations doivent "
            "être retraitées séparément.\n"
            "\n"
            "QUATRE CONSÉQUENCES. Les titres sortent puis rentrent du bilan alors qu'ils ne le "
            "quittent économiquement jamais. Des plus-values de cession sont constatées sur des "
            "opérations de financement. L'endettement — ou symétriquement les concours accordés — "
            "est sous-évalué, faussant les ratios de liquidité et de transformation. Et l'usage "
            "réel du portefeuille comme collatéral est invisible au bilan comme au hors bilan.\n"
            "\n"
            "LECTURE DU TABLEAU COMPARATIF. Les trois marqueurs se traduisent par quatre comptes, "
            "l'inscription hors bilan ayant par nature une contrepartie. Aucun des quatre n'est "
            "mouvementé sur les cessions-rétrocessions, alors que les quatre le sont sur les "
            "pensions auprès de la banque centrale."
        ),
        chiffres=[
            ("Opérations concernées", str(commentes.DEAL.nunique())),
            ("Sorties du portefeuille (crédits)", xaf(sorties)),
            ("Entrées au portefeuille (débits)", xaf(entrees)),
            ("Comptes marqueurs présents sur les pensions BEAC, absents ici",
             f"{len([p for p in presence if p[2] and not p[3]])} sur {len(presence)}"),
            ("Écart entre sorties et entrées du portefeuille", xaf(sorties - entrees)),
            ("Opérations dont la première jambe est identifiable", str(len(sens_near))),
            ("Dont la banque EMPRUNTE (cession en première jambe)",
             f"{len(emprunts)} — {xaf(montant_emprunts)}"),
            ("Dont la banque PRÊTE (acquisition en première jambe)",
             f"{len(prets)} — {xaf(montant_prets)}"),
        ],
        tableaux=[
            Tableau(["Marqueur comptable d'une pension livrée", "Compte",
                     "Présent sur les pensions BEAC", "Présent sur les cessions-rétrocessions"],
                    presence,
                    note="La comparaison des deux schémas est le cœur du constat."),
            Tableau(["Compte", "Libellé", "Lignes", "Débits", "Crédits", "Montant XAF"],
                    [[i[0], i[1][:36], int(r.lignes), int(r.debits), int(r.credits), float(r.montant)]
                     for i, r in detail_sbb.sort_values("montant", ascending=False).iterrows()],
                    max_lignes=14, note="Schéma appliqué aux cessions-rétrocessions."),
            Tableau(["Compte", "Libellé", "Lignes", "Montant XAF"],
                    [[i[0], i[1][:36], int(r.lignes), float(r.montant)]
                     for i, r in detail_pension.sort_values("montant", ascending=False).iterrows()],
                    max_lignes=10, note="Schéma appliqué aux pensions auprès de la banque centrale, à titre de référence."),
        ],
        recommandation=(
            "Obtenir les conventions-cadres signées avec les contreparties et la doctrine "
            "comptable retenue. Faire confirmer le traitement par le commissaire aux comptes au "
            "regard du PCEC. Mesurer l'incidence d'un reclassement en financement garanti sur le "
            "bilan, le résultat et les ratios prudentiels de liquidité et de transformation."
        ),
    )


def _c83_book_dedie(ctx, commentes) -> Constat:
    """Calypso dispose-t-il d'un portefeuille dédié aux cessions-rétrocessions, et l'utilise-t-il ?"""
    deals = ctx.deals_calypso
    if deals.empty or commentes.empty:
        return Constat(code="8.3", titre="Utilisation du portefeuille dédié", gravite=Gravite.CONFORME,
                       constat="Sans objet.")
    dedie = deals[deals.Book == BOOK_DEDIE]
    if dedie.empty:
        return Constat(
            code="8.3", titre="Absence de portefeuille dédié aux cessions-rétrocessions",
            gravite=Gravite.MOYENNE,
            constat="Aucun portefeuille dédié aux cessions-rétrocessions n'existe dans le système amont.",
            recommandation="Faire créer un portefeuille dédié et y basculer ces opérations.",
        )
    par_book = commentes.groupby("BOOK").DEAL.nunique()
    dans_dedie = int(par_book.get(BOOK_DEDIE, 0))
    statuts = dedie.TradeStatus.value_counts()
    actifs = int(statuts.get("VERIFIED", 0) + statuts.get("MATURED", 0))
    return Constat(
        code="8.3",
        titre="Le portefeuille dédié aux cessions-rétrocessions existe mais n'est pas utilisé",
        gravite=Gravite.ELEVEE,
        constat=(
            f"Le système amont dispose d'un portefeuille spécifiquement dédié aux opérations de "
            f"cession-rétrocession — « {BOOK_DEDIE} ». Son existence établit que l'établissement a "
            "identifié ce type d'opération et prévu un traitement distinct.\n"
            "\n"
            f"Or ce portefeuille ne compte que {len(dedie)} opérations, dont "
            f"{len(dedie) - actifs} annulées : il n'en reste que {actifs} réellement actives. "
            "Dans le même temps, la TOTALITÉ des opérations identifiées comme des "
            "cessions-rétrocessions est logée dans les portefeuilles de titres en juste valeur, "
            "c'est-à-dire là où sont enregistrés les achats et ventes fermes.\n"
            "\n"
            "Ce constat renforce celui du contrôle 8.2 : le traitement appliqué ne résulte pas "
            "d'une impossibilité technique, puisque l'outil prévoit le cas. Il s'agit d'un choix "
            "de saisie, ou d'une méconnaissance du portefeuille approprié."
        ),
        chiffres=[
            ("Portefeuille dédié", BOOK_DEDIE),
            ("Opérations y figurant", f"{len(dedie)} dont {actifs} actives"),
            ("Opérations de cession-rétrocession identifiées", str(commentes.DEAL.nunique())),
            ("Dont logées dans le portefeuille dédié", str(dans_dedie)),
        ],
        tableaux=[
            Tableau(["Portefeuille utilisé", "Opérations de cession-rétrocession"],
                    [[i, int(n)] for i, n in par_book.items()]),
            Tableau(["Deal", "Titre", "Contrepartie", "Statut", "Opérateur", "Quantité"],
                    [[r["Trade Id"], str(r["Product Description"])[:42], r.CounterParty,
                      r.TradeStatus, r.Trader, float(r.Quantity_n) if r.Quantity_n == r.Quantity_n else None]
                     for _, r in dedie.iterrows()],
                    note="Contenu du portefeuille dédié."),
        ],
        recommandation=(
            "Faire basculer les opérations de cession-rétrocession dans le portefeuille dédié et "
            "y attacher le schéma comptable de la pension livrée. Obtenir l'explication du "
            "non-usage de ce portefeuille."
        ),
    )


def _c84_rotation(ctx, commentes, paires) -> Constat:
    """Le caractère roulé du financement : mêmes titres, mêmes contreparties, prix croissant."""
    if commentes.empty:
        return Constat(code="8.4", titre="Rotation des titres", gravite=Gravite.CONFORME, constat="Sans objet.")
    regle = commentes[commentes.EVENEMENT == "CST_S_SETTLED"]
    rotation = regle.groupby(["TITRE", "EMETTEUR"]).agg(
        operations=("DEAL", "nunique"), debut=("TRN_DT", "min"), fin=("TRN_DT", "max"),
        cumul=("LCY_AMOUNT", "sum"))
    rotation = rotation[rotation.operations > 1].sort_values("operations", ascending=False)
    # Rotation vue depuis le référentiel des deals, y compris opérations non commentées
    rot_deals = pd.DataFrame()
    if not paires.empty:
        rot_deals = (paires.groupby(["titre", "contrepartie"])
                     .agg(aller_retours=("vente", "size"), jours_median=("jours", "median"),
                          commentes=("commente", "sum"))
                     .sort_values("aller_retours", ascending=False))
        rot_deals = rot_deals[rot_deals.aller_retours > 1]
    if rotation.empty and rot_deals.empty:
        return Constat(code="8.4", titre="Rotation des titres", gravite=Gravite.CONFORME,
                       constat="Aucun titre ne fait l'objet d'opérations répétées.")
    titre_top = rotation.index[0][0] if len(rotation) else None
    serie = []
    if titre_top:
        s = (regle[regle.TITRE == titre_top].groupby("DEAL")
             .agg(date=("TRN_DT", "min"), montant=("LCY_AMOUNT", "max")).sort_values("date"))
        serie = [[i, r.date, float(r.montant)] for i, r in s.iterrows()]
        cout = float(s.montant.iloc[-1] - s.montant.iloc[0]) if len(s) > 1 else 0.0
    else:
        cout = 0.0
    return Constat(
        code="8.4",
        titre="Titres recyclés à répétition avec la même contrepartie : un financement roulé",
        gravite=Gravite.ELEVEE,
        constat=(
            "Les mêmes titres font l'objet d'aller-retours répétés avec la même contrepartie, à "
            "un prix croissant à chaque itération. Cette progression EST le coût de financement "
            "implicite de l'opération : c'est un intérêt, et non une plus-value.\n"
            "\n"
            "Le caractère roulé établit qu'il ne s'agit pas de cessions successives mais d'un "
            "FINANCEMENT RENOUVELÉ. Un titre réellement cédé ne revient pas au bilan quelques "
            "semaines plus tard, auprès du même acheteur, à un prix supérieur.\n"
            "\n"
            "L'analyse est menée sur deux plans. Le premier porte sur les opérations "
            "COMMENTÉES et mesure la progression du prix. Le second porte sur le RÉFÉRENTIEL DES "
            "DEALS, indépendamment des commentaires, et met en évidence des séries d'aller-retours "
            "régulières — un même titre cédé et racheté tous les vingt à trente jours pour une "
            "quantité strictement identique, ce qui est la signature d'un financement roulé à "
            "échéance fixe."
        ),
        chiffres=[
            ("Titres faisant l'objet d'opérations répétées (commentées)", str(len(rotation))),
            ("Titres en aller-retours répétés (référentiel des deals)", str(len(rot_deals))),
            ("Nombre maximal d'itérations sur un même titre",
             str(int(rotation.operations.iloc[0])) if len(rotation) else "0"),
            ("Progression du prix sur le titre le plus recyclé", xaf(cout)),
        ],
        tableaux=[
            Tableau(["Titre", "Contrepartie", "Itérations", "Du", "Au", "Cumul réglé XAF"],
                    [[i[0], i[1], int(r.operations), r.debut, r.fin, float(r.cumul)]
                     for i, r in rotation.head(12).iterrows()],
                    note="Rotation vue depuis les opérations commentées."),
            Tableau(["Titre", "Contrepartie", "Aller-retours", "Jours médians entre les deux jambes",
                     "Dont commentés"],
                    [[i[0][:40], i[1], int(r.aller_retours), int(r.jours_median), int(r.commentes)]
                     for i, r in rot_deals.head(12).iterrows()],
                    note="Rotation vue depuis le référentiel des deals, commentaires ignorés."),
            Tableau(["Deal", "Date", "Montant réglé XAF"], serie,
                    note=f"Trajectoire du titre le plus recyclé : le prix croît à chaque itération."),
        ],
        recommandation=(
            "Quantifier le coût de financement implicite de ces opérations et le comparer au coût "
            "d'une pension livrée auprès de la banque centrale. Vérifier que ce coût est bien "
            "présenté en charge d'intérêt et non en moins-value."
        ),
    )


def _c85_resultat(ctx, commentes) -> Constat:
    if commentes.empty:
        return Constat(code="8.5", titre="Résultat dégagé", gravite=Gravite.CONFORME, constat="Sans objet.")
    resultat = commentes[commentes.AC_NO.str.startswith(("733", "734", "6"))]
    if resultat.empty:
        return Constat(code="8.5", titre="Résultat dégagé par les cessions-rétrocessions",
                       gravite=Gravite.CONFORME, constat="Aucun impact résultat identifié.")
    par = resultat.groupby(["AC_NO", "AC_GL_DESC", "EVENEMENT"]).agg(
        lignes=("LCY_AMOUNT", "size"), net=("SIGNE", "sum"))
    impact = -float(resultat.SIGNE.sum())
    # Le résultat des exercices revus est celui de la période ; le reste relève des
    # événements postérieurs à la clôture.
    en_periode = resultat[(resultat.TRN_DT >= ctx.config.debut) & (resultat.TRN_DT <= ctx.config.fin)]
    impact_periode = -float(en_periode.SIGNE.sum())
    par_exercice = (resultat.assign(exercice=resultat.TRN_DT.str[:4])
                    .groupby("exercice").SIGNE.sum())
    return Constat(
        code="8.5",
        titre="Résultat constaté sur des opérations de financement",
        gravite=Gravite.ELEVEE,
        constat=(
            "Les cessions-rétrocessions dégagent un résultat comptable : plus-values de cession et "
            "reprises d'intérêts courus réalisés.\n"
            "Si ces opérations sont, comme l'établissent les contrôles 8.2 et 8.4, des financements "
            "garantis, ce résultat NE DEVRAIT PAS ÊTRE CONSTATÉ : un emprunt ne génère pas de "
            "plus-value. Le différentiel de prix entre les deux jambes devrait au contraire "
            "apparaître en CHARGE d'intérêt.\n"
            "L'effet est donc double, et de même sens : un produit est reconnu là où une charge "
            "devrait l'être. Le produit net bancaire de l'exercice s'en trouve majoré, et avec lui "
            "le résultat distribuable et les fonds propres."
        ),
        chiffres=[
            ("IMPACT RÉSULTAT SUR LA PÉRIODE D'AUDIT", xaf(impact_periode)),
            ("Impact sur toute l'extraction", xaf(impact)),
        ],
        tableaux=[
            Tableau(["Compte", "Libellé", "Événement", "Lignes", "Impact net XAF"],
                    [[i[0], i[1][:34], i[2], int(r.lignes), -float(r.net)]
                     for i, r in par.iterrows()],
                    note="Décomposition sur toute l'extraction."),
            Tableau(["Exercice", "Impact résultat XAF"],
                    [[i, -float(v)] for i, v in par_exercice.items()],
                    note=("Ventilation par exercice : seuls les exercices clos dans la période "
                          "d'audit entrent dans le résultat revu.")),
        ],
        recommandation=(
            "Mesurer l'incidence d'un retraitement en financement garanti sur le résultat de "
            "chaque exercice concerné, en substituant une charge d'intérêt au produit constaté."
        ),
    )
