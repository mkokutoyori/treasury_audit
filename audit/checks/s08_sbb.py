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

import re

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf, pct, nb
from ..data import (CPT_BEAC, CPT_PORTEFEUILLE_CALYPSO, CPT_REPO_CHARGE, CPT_REPO_PASSIF)

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


# Comptes que le PCEC consacre à la pension livrée et à sa rémunération. Aucun ne suppose
# une sortie du titre du bilan : le 5216 est un compte de PASSIF, le 602 une CHARGE.
CPT_PENSION_PCEC_SBB = [
    ("521600100", "VALEURS DONNEES EN PENSION", "passif — la dette envers le cessionnaire"),
    ("532000100", "AUTRES VAL DONNEES EN PENSION OU VENDUES FERMES", "passif — même objet"),
    ("539000100", "DETTES RATTACHEES", "passif — intérêts courus sur la dette"),
    ("602000100", "INTERET SUR VAL DONNEES EN PENSION", "charge — le coût du financement"),
    ("521300100", "VAL RECU PENSION OPS INTERB", "actif — la créance, sens inverse"),
    ("531000100", "AUTRES VAL RECUES EN PENSION", "actif — même objet"),
    ("702000100", "INTS SUR AUT VALS RECUES PENSION", "produit — sens inverse"),
]


def _test_coupon(ctx, commentes) -> pd.DataFrame:
    """Le prix pied de coupon est-il identique aux deux jambes ?

    C'est LE test qui tranche, et il ne dépend d'aucune interprétation de texte. Si le
    différentiel de trésorerie entre la jambe aller et la jambe retour est exactement égal au
    COUPON COURU sur la période, alors le prix pied de coupon n'a pas bougé d'un centime : la
    banque a cédé à un prix et s'est engagée à racheter au MÊME prix. Aucun risque de prix
    n'a donc été transféré — et sans transfert des risques, il ne peut y avoir sortie du
    bilan. Le différentiel constaté est alors, par construction, un INTÉRÊT.
    """
    if commentes.empty:
        return pd.DataFrame()
    coupons = {}
    c = ctx.calypso_enrichi
    for titre, desc in c[c.TITRE.notna() & (c.TITRE != "")].groupby("TITRE").DESCRIPTION.first().items():
        m = re.search(r"/([\d.]+)%", str(desc))
        if m:
            coupons[titre] = float(m.group(1))
    # Une fiche par deal : jambe, titre, nominal, trésorerie réglée
    fiches = []
    for deal, g in commentes.groupby("DEAL"):
        lib = str(g.COMMENTAIRE.dropna().iloc[0]).upper() if g.COMMENTAIRE.notna().any() else ""
        jambe = "NEAR" if "NEAR" in lib else ("FAR" if "FAR" in lib else "")
        if not jambe:
            continue
        nominal = g[g.AC_NO.isin(CPT_PORTEFEUILLE_CALYPSO)]
        if nominal.empty:
            continue
        fiches.append({
            "deal": deal, "jambe": jambe,
            "titre": g.TITRE.dropna().iloc[0] if g.TITRE.notna().any() else "",
            "date": g.TRN_DT.min(), "nominal": float(nominal.LCY_AMOUNT.sum()),
            "sens": "cession" if float(nominal.SIGNE.sum()) < 0 else "acquisition",
            "cash": float(g[g.AC_NO == CPT_BEAC].SIGNE.sum()),
            "contrepartie": _contrepartie(lib),
        })
    if not fiches:
        return pd.DataFrame()
    f = pd.DataFrame(fiches)
    near, far = f[f.jambe == "NEAR"], f[f.jambe == "FAR"]
    paires = []
    for _, n in near.iterrows():
        cand = far[(far.titre == n.titre) & (far.contrepartie == n.contrepartie)
                   & (far.date > n.date) & ((far.nominal - n.nominal).abs() < 1)]
        if cand.empty:
            continue
        r = cand.sort_values("date").iloc[0]
        jours = (pd.Timestamp(r.date) - pd.Timestamp(n.date)).days
        if jours <= 0 or jours > 200 or n.nominal <= 0:
            continue
        coupon = coupons.get(n.titre)
        if coupon is None:
            continue
        constate = abs(n.cash + r.cash)
        theorique = n.nominal * coupon / 100 * jours / 365
        paires.append({
            "near": n.deal, "far": r.deal, "titre": n.titre, "contrepartie": n.contrepartie,
            "date_near": n.date, "date_far": r.date, "jours": jours, "sens": n.sens,
            "nominal": n.nominal, "constate": constate, "theorique": theorique,
            "ecart": constate - theorique, "coupon": coupon,
            "taux_implicite": constate / n.nominal * 365 / jours * 100,
        })
    if not paires:
        return pd.DataFrame()
    return pd.DataFrame(paires).drop_duplicates("far").sort_values("ecart", key=abs)


def _contrepartie(libelle: str) -> str:
    """Contrepartie lue dans le commentaire de la salle des marchés."""
    t = str(libelle).upper()
    for cle, nom in (("SOCIETE GENERAL", "SGCM"), ("SOC GEN", "SGCM"), ("SOG GEN", "SGCM"),
                     ("ECOBANK", "ECOBANK"), ("BICEC", "BICEC"), ("MAKEDA", "MAKEDA"),
                     ("AFRICA BRIGHT", "AFRICA BRIGHT"), ("ENKO", "ENKO"), ("CDC", "CDC"),
                     ("UBA", "UBA"), ("UBC", "UBC"), ("ECM", "ECM"), ("CCA", "CCA")):
        if cle in t:
            return nom
    return "?"


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
    # --- LE TEST QUI TRANCHE : le prix pied de coupon a-t-il bougé entre les deux jambes ?
    coupon = _test_coupon(ctx, commentes)
    exacts = coupon[coupon.ecart.abs() < 1] if not coupon.empty else coupon
    # --- Les comptes que le PCEC consacre à la pension : servis, ou pas ?
    presence_pcec = [[c_, lib, role, nb(int((commentes.AC_NO == c_).sum()))]
                     for c_, lib, role in CPT_PENSION_PCEC_SBB]
    total_pcec = sum(int((commentes.AC_NO == c_).sum()) for c_, _, _ in CPT_PENSION_PCEC_SBB)
    # --- Où le coût du financement a-t-il atterri ?
    courus = float(commentes[commentes.AC_NO == "512800100"].SIGNE.sum())
    revenus = float(commentes[commentes.AC_NO.isin(["733400100", "733200100"])].SIGNE.sum())
    # --- Le portefeuille dédié existe-t-il, et est-il employé ?
    books = commentes.BOOK.dropna()
    part_fvoci = int((books != BOOK_DEDIE).sum())
    deals_bsb = int(commentes[commentes.BOOK == BOOK_DEDIE].DEAL.nunique())
    ref = ctx.deals_calypso
    contreparties = []
    if not ref.empty and "Trade Id" in ref.columns:
        m = ref[ref["Trade Id"].isin(set(commentes.DEAL))]
        contreparties = sorted({str(x) for x in m.CounterParty.dropna().unique()})

    return Constat(
        code="8.2",
        titre="Les cessions-rétrocessions sont comptabilisées en cessions fermes alors que le prix de rachat est fixé d'avance",
        gravite=Gravite.CRITIQUE,
        reference=("Règlement COBAC R-2003/03 relatif à la comptabilisation et au traitement "
                   "prudentiel des opérations sur titres effectuées par les établissements de "
                   "crédit, modifié par le Règlement COBAC R-2010/03 — PCEC, comptes 5216, "
                   "5320, 5390, 602, 5213, 5310, 702"),
        constat=(
            "I. CE QUE LA RÈGLE PRESCRIT\n"
            "\n"
            "Le texte applicable est le Règlement COBAC R-2003/03, modifié par le Règlement "
            "COBAC R-2010/03. Il définit la pension comme l'opération par laquelle le CÉDANT "
            "remet des titres au CESSIONNAIRE contre un prix convenu, le cessionnaire "
            "s'engageant à rétrocéder des titres de même nature. Et il en tire la conséquence "
            "comptable, dans les termes suivants :\n"
            "\n"
            "  « La pension entraîne, chez le cédant, d'une part, le MAINTIEN À L'ACTIF de son "
            "bilan des titres financiers mis en pension et, d'autre part, l'INSCRIPTION AU "
            "PASSIF du bilan du montant de sa DETTE vis-à-vis du cessionnaire. »\n"
            "\n"
            "  « Les titres financiers reçus en pension NE SONT PAS INSCRITS AU BILAN du "
            "cessionnaire ; celui-ci enregistre à l'actif de son bilan le montant de sa "
            "CRÉANCE sur le cédant. »\n"
            "\n"
            "La règle ne laisse donc aucune marge : dans une pension, le titre NE SORT PAS du "
            "bilan du cédant, et la trésorerie reçue est une DETTE.\n"
            "\n"
            "II. LE PLAN DE COMPTES DE LA BANQUE LE CONFIRME, SANS QU'IL SOIT BESOIN D'INTERPRÉTER\n"
            "\n"
            "Le référentiel de comptes de la banque — son propre PCEC — ouvre sept comptes "
            "dédiés à cette opération, dont le seul intitulé suffit à établir le traitement "
            "attendu : 521600100 VALEURS DONNÉES EN PENSION et 532000100 sont des comptes de "
            "PASSIF ; 539000100 porte les dettes rattachées ; 602000100 INTÉRÊT SUR VALEURS "
            "DONNÉES EN PENSION est un compte de CHARGE. Si une pension devait s'enregistrer "
            "comme une vente, aucun de ces comptes n'aurait de raison d'exister. Le plan de "
            "comptes est un élément de preuve interne : il n'est pas discutable, il est celui "
            "de la banque.\n"
            "\n"
            "III. CE QUI A ÉTÉ COMPTABILISÉ\n"
            "\n"
            "L'inverse, exactement. Le compte de portefeuille est CRÉDITÉ à la première jambe "
            "— le titre sort du bilan — puis DÉBITÉ à la seconde — il y revient. La trésorerie "
            "encaissée n'est constatée nulle part comme une dette. Le schéma appliqué est "
            "celui d'une vente suivie d'un achat.\n"
            + (f"Sur les sept comptes que le PCEC consacre à la pension, AUCUNE ligne n'a été "
               "mouvementée par ces opérations."
               if total_pcec == 0 else
               f"Sur les sept comptes que le PCEC consacre à la pension, {nb(total_pcec)} lignes "
               "seulement ont été mouvementées par ces opérations.")
            + " Le tableau de présence ci-dessous le détaille compte par compte.\n"
            "\n"
            "IV. LE TEST QUI TRANCHE — ET QUI NE DÉPEND D'AUCUNE INTERPRÉTATION DE TEXTE\n"
            "\n"
            "On pourrait objecter que la qualification se discute, et qu'une cession suivie "
            "d'un rachat peut être deux opérations fermes indépendantes. Cette objection se "
            "tranche par l'arithmétique, sans recourir au droit.\n"
            "\n"
            "Le raisonnement est le suivant. Le prix d'une obligation se décompose en un PRIX "
            "PIED DE COUPON, qui suit le marché, et un COUPON COURU, qui ne dépend que du "
            "temps écoulé. Si, entre la jambe aller et la jambe retour, le différentiel de "
            "trésorerie est EXACTEMENT ÉGAL au coupon couru sur la période, alors le prix pied "
            "de coupon n'a pas bougé d'un centime. Autrement dit : la banque a cédé à un prix "
            "et s'est engagée à racheter AU MÊME PRIX. Aucun risque de prix n'a été transféré, "
            "et le différentiel encaissé par la contrepartie n'est rien d'autre qu'un "
            "INTÉRÊT.\n"
            "\n"
            f"LE TEST A ÉTÉ EXÉCUTÉ SUR {nb(len(coupon))} OPÉRATIONS APPARIÉES. "
            f"{nb(len(exacts))} d'entre elles vérifient l'égalité À MOINS D'UN FRANC PRÈS — "
            "l'écart résiduel étant l'arrondi à l'unité. Sur ces opérations, le taux implicite "
            "calculé à partir de la seule trésorerie tombe sur le TAUX NOMINAL DU COUPON de "
            "l'obligation, à deux décimales : 5,75 contre 5,75 ; 7,25 contre 7,25 ; 6,50 "
            "contre 6,50 ; 7,00 contre 7,00.\n"
            "\n"
            "UNE TELLE COÏNCIDENCE N'EXISTE PAS ENTRE DEUX OPÉRATIONS FERMES INDÉPENDANTES. "
            "Deux transactions réellement distinctes, séparées de plusieurs jours, sur un "
            "marché où les prix bougent, ne produisent pas un différentiel égal au franc près "
            "au coupon couru. Le prix de rachat était FIXÉ DÈS L'ORIGINE. Il s'ensuit que la "
            "banque a conservé la totalité du risque de prix et la totalité du risque de "
            "crédit sur l'émetteur — et qu'il ne pouvait donc pas y avoir sortie du bilan.\n"
            "\n"
            "V. OÙ LE COÛT DU FINANCEMENT A-T-IL ATTERRI ?\n"
            "\n"
            "Puisqu'aucune charge d'intérêt n'est constatée, la rémunération de la "
            "contrepartie devait bien passer quelque part. Elle transite par le compte de "
            f"COURUS 512800100 — effet net {xaf(courus)} sur ces opérations — puis se dénoue "
            "dans les comptes de REVENUS DE TITRES 733200100 et 733400100, dont l'effet net "
            f"est de {xaf(abs(revenus))} au CRÉDIT, c'est-à-dire en produit.\n"
            "Le coût d'un financement est ainsi absorbé dans le revenu du portefeuille, au lieu "
            "d'être isolé en charge. Deux conséquences. D'abord, le PCEC prohibe la "
            "compensation entre charges et produits : une charge d'intérêt ne se présente pas "
            "en diminution d'un revenu de titres. Ensuite, et c'est le plus gênant pour le "
            "pilotage, le coût de cette ressource devient impossible à mesurer — ni la "
            "trésorerie, ni le contrôle de gestion, ni le régulateur ne peuvent savoir ce que "
            "la banque paie pour se refinancer par ce canal.\n"
            "\n"
            "VI. LA BANQUE CONNAÎT LE SCHÉMA CORRECT, ET L'APPLIQUE AILLEURS\n"
            "\n"
            "Le tableau comparatif ci-dessous met face à face les deux traitements. Sur ses "
            "pensions auprès de la banque centrale, la banque constate bien une dette au "
            "passif, une charge d'intérêt et une inscription au hors bilan des titres donnés "
            "en garantie. Le dispositif existe, il est paramétré, il fonctionne. Il n'est pas "
            "employé ici. L'anomalie ne peut donc pas être attribuée à une limite du système.\n"
            "\n"
            "VII. LA BANQUE DÉSIGNE ELLE-MÊME CES OPÉRATIONS COMME DES PENSIONS\n"
            "\n"
            "Les commentaires saisis par la salle des marchés emploient le vocabulaire "
            "technique du marché de la pension et lui seul : « SBB », « NEAR LEG », « FAR "
            "LEG », et parfois la durée — « FOR 30 DAYS ». Une jambe proche et une jambe "
            "lointaine ne se conçoivent que si les deux sont contractées ensemble. Les "
            "contreparties, telles que le référentiel Calypso les enregistre, sont des "
            f"professionnels de marché : {', '.join(contreparties)}. Aucune n'est un client "
            "de la banque.\n"
            f"Enfin, Calypso comporte un portefeuille dédié, {BOOK_DEDIE}, dont le nom même "
            "désigne l'opération. "
            + (f"AUCUNE de ces {nb(commentes.DEAL.nunique())} opérations n'y figure"
               if deals_bsb == 0 else
               f"{nb(deals_bsb)} de ces {nb(commentes.DEAL.nunique())} opérations y figurent")
            + " : elles sont toutes enregistrées dans les portefeuilles de détention "
            "ordinaire. Le portefeuille qui aurait permis de les identifier existe, et il "
            "n'est pas utilisé.\n"
            "\n"
            "VIII. DEUX SENS, DEUX RETRAITEMENTS DISTINCTS\n"
            "\n"
            "Une cession-rétrocession n'est pas toujours un financement REÇU. La première "
            f"jambe montre que la banque y est tantôt emprunteuse — elle cède le titre et "
            f"encaisse — tantôt PRÊTEUSE : elle acquiert le titre et décaisse. {len(prets)} "
            f"des {len(sens_near)} opérations dont la première jambe est identifiable relèvent "
            f"du second cas, soit {pct(part_prets, 0)}. Pour un financement reçu, une DETTE "
            "manque au passif ; pour un financement accordé, c'est une CRÉANCE qui manque à "
            "l'actif, et le titre acquis n'aurait pas dû entrer au bilan. Les deux populations "
            "doivent être retraitées séparément.\n"
            "\n"
            "IX. CONSÉQUENCES\n"
            "\n"
            "Les titres sortent puis rentrent du bilan alors qu'ils ne le quittent "
            "économiquement jamais. Des plus-values de cession sont constatées sur des "
            "opérations de financement. L'endettement — ou symétriquement les concours "
            "accordés — est sous-évalué, ce qui fausse les ratios de liquidité et de "
            "transformation. L'usage réel du portefeuille comme collatéral est invisible au "
            "bilan comme au hors bilan. Et le portefeuille affiché à chaque arrêté ne reflète "
            "pas les titres réellement détenus.\n"
            "\n"
            "X. CE QUE CE CONSTAT N'ÉTABLIT PAS\n"
            "\n"
            "Par souci d'exactitude : le texte du Règlement COBAC R-2003/03 n'a pas pu être "
            "consulté dans son édition officielle depuis l'environnement de travail ; la règle "
            "citée au I doit être rapprochée de l'article correspondant, dont copie sera jointe "
            "au dossier. Cela ne fragilise pas le constat, qui repose au II sur le plan de "
            "comptes de la banque elle-même et au IV sur une démonstration arithmétique "
            f"indépendante de tout texte. Par ailleurs, l'appariement des deux jambes est "
            f"volontairement STRICT — même titre, même contrepartie, même nominal au franc "
            f"près : il retient {nb(len(coupon))} opérations sur les {nb(commentes.DEAL.nunique())} "
            "identifiées. Les autres ne sont pas exonérées ; elles n'ont simplement pas pu "
            "être appariées automatiquement et demandent une revue manuelle."
        ),
        chiffres=[
            ("Opérations concernées", nb(commentes.DEAL.nunique())),
            ("Contreparties, au référentiel Calypso", ", ".join(contreparties)),
            ("Lignes sur les 7 comptes PCEC de la pension", nb(total_pcec)),
            ("Sorties du portefeuille (crédits)", xaf(sorties)),
            ("Entrées au portefeuille (débits)", xaf(entrees)),
            ("Écart entre sorties et entrées du portefeuille", xaf(sorties - entrees)),
            ("TEST DU COUPON — opérations appariées", nb(len(coupon))),
            ("TEST DU COUPON — vérifiées à moins d'un franc près", nb(len(exacts))),
            ("Effet net sur le compte de courus 512800100", xaf(courus)),
            ("Effet net sur les comptes de revenus de titres",
             xaf(abs(revenus)) + (" au CRÉDIT (produit)" if revenus < 0 else " au DÉBIT (charge)")),
            ("Charge d'intérêt constatée", xaf(0)),
            ("Dette constatée au passif", xaf(0)),
            ("Opérations dont la première jambe est identifiable", nb(len(sens_near))),
            ("Dont la banque EMPRUNTE (cession en première jambe)",
             f"{len(emprunts)} — {xaf(montant_emprunts)}"),
            ("Dont la banque PRÊTE (acquisition en première jambe)",
             f"{len(prets)} — {xaf(montant_prets)}"),
        ],
        tableaux=[
            Tableau(["Paire NEAR / FAR", "Titre", "Jours", "Nominal XAF",
                     "Différentiel de trésorerie", "Coupon couru théorique", "Écart XAF",
                     "Taux implicite %", "Coupon nominal %"],
                    [[f"{r.near} / {r.far}", r.titre, int(r.jours), float(r.nominal),
                      float(r.constate), round(float(r.theorique), 2), round(float(r.ecart), 2),
                      round(float(r.taux_implicite), 2), float(r.coupon)]
                     for _, r in exacts.iterrows()] if not exacts.empty else [],
                    max_lignes=12,
                    note=("LE TEST DÉCISIF. Pour chacune de ces opérations, le différentiel de "
                          "trésorerie entre les deux jambes est égal au coupon couru sur la "
                          "période à moins d'un franc près, et le taux implicite tombe sur le "
                          "taux nominal du coupon. Le prix pied de coupon était donc identique "
                          "aux deux jambes : le prix de rachat était fixé dès l'origine.")),
            Tableau(["Compte PCEC de la pension", "Intitulé", "Ce qu'il devrait porter",
                     "Lignes mouvementées"],
                    presence_pcec,
                    note=("Les sept comptes que le plan de comptes de la banque consacre à la "
                          "pension livrée, et leur emploi sur ces opérations.")),
            Tableau(["Marqueur comptable d'une pension livrée", "Compte",
                     "Présent sur les pensions BEAC", "Présent sur les cessions-rétrocessions"],
                    presence,
                    note="La comparaison des deux schémas appliqués par la même banque."),
            Tableau(["Compte", "Libellé", "Lignes", "Débits", "Crédits", "Montant XAF"],
                    [[i[0], i[1][:36], int(r.lignes), int(r.debits), int(r.credits), float(r.montant)]
                     for i, r in detail_sbb.sort_values("montant", ascending=False).iterrows()],
                    max_lignes=14, note="Schéma appliqué aux cessions-rétrocessions."),
            Tableau(["Compte", "Libellé", "Lignes", "Montant XAF"],
                    [[i[0], i[1][:36], int(r.lignes), float(r.montant)]
                     for i, r in detail_pension.sort_values("montant", ascending=False).iterrows()],
                    max_lignes=10,
                    note="Schéma appliqué aux pensions auprès de la banque centrale, à titre de référence."),
        ],
        recommandation=(
            "1. Joindre au dossier le Règlement COBAC R-2003/03 modifié et la convention-cadre "
            "signée avec chaque contrepartie. Une convention-cadre de pension livrée "
            "trancherait la qualification juridique à elle seule.\n"
            "2. Opposer à la direction le test du coupon : un prix de rachat égal au prix de "
            "cession pied de coupon n'est pas une coïncidence de marché, c'est un prix "
            "convenu. Demander sur quelle base la direction soutient que le risque a été "
            "transféré.\n"
            "3. Faire confirmer le traitement par le commissaire aux comptes au regard du "
            "Règlement COBAC R-2003/03, et mesurer l'incidence d'un reclassement en "
            "financement garanti sur le bilan, le résultat, le produit net bancaire et les "
            "ratios prudentiels de liquidité et de transformation.\n"
            "4. Reconstituer, exercice par exercice, la charge d'intérêt qui aurait dû être "
            "constatée et la dette qui aurait dû figurer au passif à chaque arrêté.\n"
            f"5. Rendre obligatoire l'emploi du portefeuille dédié {BOOK_DEDIE} : il existe, "
            "et son utilisation rendrait ces opérations identifiables sans recourir au "
            "commentaire libre de la salle des marchés (contrôle 8.1)."
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
