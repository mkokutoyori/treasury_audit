"""Section 12 — Comptes de régularisation, comptes d'attente et comptes dormants.

Cette section repose sur la deuxième vague d'extractions : les comptes du plan de comptes
qui intéressent l'activité titres mais qui ne figuraient pas dans la liste initiale des
41 comptes clés. Elle produit deux natures de constat, également instructives :
ce que ces comptes CONTIENNENT, et ce qu'ils ne contiennent PAS.
"""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf, nb, pct, fois
from ..data import (DATE_BASCULE, CPT_ATTENTE, CPT_COURUS_MANUELS, CPT_INTERET_BEAC, CPT_COLLATERAL, CPT_REPO_CHARGE,
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
    s.ajouter(_c127_courus_manuels(ctx))
    return s


def _periode(ctx, compte: str) -> pd.DataFrame:
    return ctx.historique_compte(compte, dans_periode=True)


# --- 12.1 ---------------------------------------------------------------------------------
# Emplois que le PCEC assigne au compte de commissions et frais sur titres. Tout le reste y
# est étranger. Le CRCT — Cellule de Règlement et de Conservation des Titres — est le
# dépositaire central de la CEMAC : ses prélèvements sont des frais de conservation, donc un
# emploi prévu.
USAGES_PREVUS = ("A. droit de garde", "B. commission du dépositaire CRCT",
                 "C. commission d'intermédiation")


def _classer(libelle: str) -> str:
    """Rattache une écriture de 622000100 à la nature d'opération qu'elle traduit."""
    t = "" if libelle is None or pd.isna(libelle) else str(libelle).upper()
    if "GARDE" in t or "CONSERVATION" in t:
        return "A. droit de garde"
    if "CRCT" in t:
        return "B. commission du dépositaire CRCT"
    if "COMMIS" in t or "COURTAGE" in t or "BROKERAGE" in t:
        return "C. commission d'intermédiation"
    if "DISCOUNT" in t or "DECOTE" in t or "DÉCOTE" in t:
        return "D. décote ou prime sur titre"
    if "INTEREST" in t or "INTERET" in t or "INTÉRÊT" in t or "COUPON" in t:
        return "E. intérêt ou régularisation d'intérêt"
    if "DIFF" in t or "REGUL" in t or "RECLASS" in t or "RCLSS" in t or "ZERORI" in t:
        return "F. écart ou reclassement"
    return "G. résidu sur opération, sans qualification"


def _c121_commissions_fourre_tout(ctx) -> Constat:
    brut = ctx.historique_compte(CPT_COMM_TITRES, dans_periode=True)
    libelle = ctx.libelle_compte(CPT_COMM_TITRES) or "COMM ET FRAIS SUR TITRES"
    if brut.empty:
        return Constat(code="12.1", titre=f"Compte {CPT_COMM_TITRES} non mouvementé",
                       gravite=Gravite.CONFORME, constat="Aucun mouvement sur la période.")
    # Les écritures de clôture annuelle soldent le compte contre le résultat : c'est le
    # fonctionnement normal d'un compte de charge, et non une écriture d'exploitation.
    cloture = brut[(brut.MODULE == "GL") | brut.TRN_REF_NO.str.contains("ZYND", na=False)]
    d = brut[~brut.index.isin(cloture.index)].copy()
    d["nature"] = d.DESCRIPTION.map(_classer)
    agg = (d.groupby("nature")
             .agg(lignes=("LCY_AMOUNT", "size"),
                  debit=("SIGNE", lambda x: float(x[x > 0].sum())),
                  credit=("SIGNE", lambda x: float(-x[x < 0].sum())),
                  net=("SIGNE", "sum"))
             .reset_index().sort_values("nature"))
    prevu = agg[agg.nature.isin(USAGES_PREVUS)]
    devoye = agg[~agg.nature.isin(USAGES_PREVUS)]
    n_prevu, n_devoye = int(prevu.lignes.sum()), int(devoye.lignes.sum())
    net_prevu, net_devoye = float(prevu.net.sum()), float(devoye.net.sum())

    # LES CRÉDITS — mesure honnête. Un crédit apparié à un débit du même montant est une
    # correction, pas un produit logé en charge. Seuls les crédits non appariés le sont.
    from collections import Counter
    debits = Counter(d[d.SIGNE > 0].LCY_AMOUNT.round(0))
    non_apparies = []
    for _, r in d[d.SIGNE < 0].iterrows():
        k = round(float(r.LCY_AMOUNT))
        if debits[k] > 0:
            debits[k] -= 1
        else:
            non_apparies.append(r)
    compensation = pd.DataFrame(non_apparies)
    montant_compensation = float(compensation.LCY_AMOUNT.sum()) if len(compensation) else 0.0
    credits_total = float(d[d.SIGNE < 0].LCY_AMOUNT.sum())
    corrections = credits_total - montant_compensation

    # LA PREUVE INTERNE : la banque a elle-même reclassé une décote vers le compte de revenus.
    a = ctx.toutes_ecritures
    dec = d[d.nature.str.startswith("D.")]
    reclass = dec[dec.DESCRIPTION.fillna("").str.upper().str.contains("RECLASS")]
    montant_reclass = float(reclass.LCY_AMOUNT.max()) if not reclass.empty else 0.0
    date_reclass = str(reclass.TRN_DT.iloc[0]) if not reclass.empty else ""
    cible = ""
    if not reclass.empty:
        # La jambe de contrepartie est celle qui porte le MÊME montant en sens inverse : une
        # écriture peut en contenir d'autres, sans rapport avec le reclassement.
        ligne = reclass.nlargest(1, "LCY_AMOUNT").iloc[0]
        sens_oppose = "D" if str(ligne.DRCR_IND) == "C" else "C"
        autres = a[(a.TRN_REF_NO == ligne.TRN_REF_NO) & (a.AC_NO != CPT_COMM_TITRES)
                   & (a.DRCR_IND == sens_oppose)
                   & ((a.LCY_AMOUNT - float(ligne.LCY_AMOUNT)).abs() < 1)]
        if not autres.empty:
            cpt = str(autres.AC_NO.iloc[0])
            cible = f"{cpt} {ctx.libelle_compte(cpt)}"

    residus = d[d.nature.str.startswith("G.")]
    petits = d[d.LCY_AMOUNT <= 100]
    interets = float(agg.loc[agg.nature.str.startswith("E."), "net"].sum())
    decotes = float(agg.loc[agg.nature.str.startswith("D."), "net"].sum())

    return Constat(
        code="12.1",
        titre=("Le compte de charge 622000100 porte 616 millions d'imputations qui ne relèvent "
               "pas de son objet"),
        gravite=Gravite.ELEVEE,
        reference=f"Compte {CPT_COMM_TITRES} {libelle} — {nb(len(brut))} écritures sur la période",
        constat=(
            "I. CE QUE LE PCEC RÉSERVE À CE COMPTE\n"
            "\n"
            f"{CPT_COMM_TITRES} {libelle} est un compte de CHARGE d'exploitation. Le PCEC lui "
            "assigne des emplois précis : les commissions d'intermédiation versées lors de "
            "l'achat et de la vente de titres, et les frais de conservation — droits de garde "
            "du dépositaire, prélèvements du CRCT, la cellule de règlement et de conservation "
            "des titres de la CEMAC. Rien d'autre.\n"
            "\n"
            "II. CE QU'IL PORTE RÉELLEMENT\n"
            "\n"
            f"Le compte porte {nb(len(brut))} écritures sur la période, dont "
            f"{nb(len(cloture))} sont les écritures de clôture annuelle qui le soldent contre "
            "le résultat — fonctionnement normal d'un compte de charge, écarté de l'analyse. "
            f"Restent {nb(len(d))} écritures d'exploitation.\n"
            f"Sur celles-ci, {nb(n_prevu)} relèvent des emplois prévus, pour {xaf(net_prevu)}. "
            f"Les {nb(n_devoye)} autres — {pct(n_devoye / max(len(d), 1) * 100)} des lignes — "
            f"portent {xaf(net_devoye)}, soit "
            f"{pct(abs(net_devoye) / max(abs(net_prevu + net_devoye), 1) * 100)} de la charge "
            "nette du compte. Le détail figure au tableau ci-dessous.\n"
            "\n"
            "III. UNE MESURE QUE JE CORRIGE\n"
            "\n"
            "Une version antérieure de ce contrôle annonçait que des produits avaient été "
            f"logés en diminution de cette charge pour {xaf(credits_total + float(cloture.LCY_AMOUNT.sum()))}. "
            "Ce chiffre était faux, et il convient de le dire. Il additionnait trois choses "
            "qui n'ont rien à voir :\n"
            f"- {xaf(float(cloture.LCY_AMOUNT.sum()))} d'écritures de CLÔTURE ANNUELLE, qui "
            "soldent normalement un compte de charge contre le résultat ;\n"
            f"- {xaf(corrections)} de CRÉDITS APPARIÉS à un débit du même montant sur le même "
            "compte : ce sont des contre-passations, donc des corrections ;\n"
            f"- et seulement {xaf(montant_compensation)} de crédits réellement non appariés.\n"
            "\n"
            f"CE DERNIER MONTANT RESTE UNE ANOMALIE, MAIS IL FAUT LE DIRE À SA MESURE. Les "
            f"{nb(len(compensation))} lignes qui le composent sont, pour l'essentiel, des "
            "commissions de courtage FACTURÉES À DES CLIENTS nommément désignés dans le "
            "libellé. Un produit facturé au client ne se présente pas en diminution d'une "
            "charge : le PCEC prohibe la compensation entre charges et produits, qui doivent "
            "figurer pour leur montant brut.\n"
            "\n"
            "IV. LE POINT LE PLUS LOURD — LES DÉCOTES\n"
            "\n"
            f"{xaf(decotes)} de décotes et primes sur titres sont imputées à ce compte de "
            "commissions. Une décote n'est pas un frais : c'est un élément du prix de revient "
            "du titre ou du résultat de cession, selon le cas. Elle relève des comptes de "
            "revenus et résultats sur titres, ou des comptes de produits comptabilisés "
            "d'avance.\n"
            + (f"\nET LA BANQUE LE SAIT, CAR ELLE L'A FAIT. Le {date_reclass}, elle a "
               f"elle-même reclassé {xaf(montant_reclass)} de décote hors de ce compte, vers "
               f"{cible}. L'écriture porte le mot RECLASS dans son libellé, et le compte de "
               "revenus est DÉBITÉ : la décote consentie à la vente vient en diminution du "
               "revenu du titre, et non en charge de commission. Le traitement correct est "
               "donc connu, et appliqué — mais une fois seulement.\n"
               if montant_reclass else "")
            + "\n"
            "V. LES INTÉRÊTS ET LES RÉSIDUS\n"
            "\n"
            f"- {nb(int(agg.loc[agg.nature.str.startswith('E.'), 'lignes'].sum()))} écritures "
            f"de régularisation d'intérêts, pour un effet net de {xaf(abs(interets))} "
            + ("au CRÉDIT — des produits d'intérêt venant, là encore, en diminution d'une "
               "charge.\n" if interets < 0 else "au débit.\n")
            + f"- {nb(len(residus))} écritures pour {xaf(float(residus.SIGNE.sum()))} ne "
            "portent aucune qualification : leur libellé se borne à désigner une opération "
            "sur titre — « SALES security », « Purchase of the security » — sans dire quelle "
            f"charge elles constituent. La plus lourde atteint "
            f"{xaf(float(residus.LCY_AMOUNT.max()))}.\n"
            f"- {nb(len(petits))} écritures portent sur {xaf(float(petits.LCY_AMOUNT.sum()))} "
            "au total, soit quelques francs chacune. Des écritures d'un ou deux francs sur un "
            "compte de charge sont la trace d'un rapprochement forcé : plutôt que d'expliquer "
            "un écart, on l'éteint. Le contrôle 5.3 en donne l'illustration la plus nette — le "
            "reliquat de la correction d'apurement de la migration y a été passé en charge.\n"
            "\n"
            "VI. POURQUOI CELA COMPTE\n"
            "\n"
            "Ce constat n'est pas un constat de perte : les montants sont bien enregistrés, et "
            "le résultat de la banque n'en est pas faussé globalement. C'est un constat de "
            "PRÉSENTATION, et il a deux effets concrets.\n"
            "Le premier est que la ligne « commissions et frais sur titres » du compte de "
            f"résultat est surévaluée de l'ordre de {xaf(net_devoye)}, et que les postes qui "
            "auraient dû porter ces montants — revenus sur titres, produits comptabilisés "
            "d'avance — sont sous-évalués d'autant.\n"
            "Le second est qu'aucune revue analytique n'est possible : il devient impossible de "
            "dire ce que la banque a réellement payé en commissions et en droits de garde, ni "
            "de rapprocher ce coût des relevés du dépositaire et des intermédiaires."
        ),
        chiffres=[
            ("Écritures sur la période", nb(len(brut))),
            ("Dont écritures de clôture annuelle, écartées", nb(len(cloture))),
            ("Écritures d'exploitation analysées", nb(len(d))),
            ("Relevant des emplois prévus par le PCEC", f"{nb(n_prevu)} — {xaf(net_prevu)}"),
            ("Étrangères à l'objet du compte", f"{nb(n_devoye)} — {xaf(net_devoye)}"),
            ("Décotes et primes imputées à tort", xaf(decotes)),
            ("Régularisations d'intérêts", xaf(abs(interets)) + (" au crédit" if interets < 0 else " au débit")),
            ("Résidus sans qualification", f"{nb(len(residus))} — {xaf(float(residus.SIGNE.sum()))}"),
            ("Écritures de 100 XAF ou moins", f"{nb(len(petits))} — {xaf(float(petits.LCY_AMOUNT.sum()))}"),
            ("Crédits totaux hors clôture", xaf(credits_total)),
            ("Dont contre-passations appariées", xaf(corrections)),
            ("Dont produits réellement logés en charge", xaf(montant_compensation)),
            ("Décote reclassée par la banque elle-même", xaf(montant_reclass)),
            ("Opérateurs distincts", nb(d.USER_ID.nunique())),
        ],
        tableaux=[
            Tableau(
                entetes=["Nature de l'opération", "Lignes", "Débits XAF", "Crédits XAF",
                         "Net XAF", "Emploi prévu"],
                lignes=[[r.nature, int(r.lignes), r.debit, r.credit, r.net,
                         "oui" if r.nature in USAGES_PREVUS else "NON"]
                        for _, r in agg.iterrows()],
                note=("Décomposition du compte par la nature de l'opération, lue dans le "
                      "libellé de chaque écriture, hors écritures de clôture annuelle. Les "
                      "trois premières lignes sont les seuls emplois que le PCEC autorise."),
            ),
            Tableau(
                entetes=["Date", "Référence", "Sens", "Montant XAF", "Opérateur", "Libellé"],
                lignes=[[r.TRN_DT, r.TRN_REF_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID,
                         str(r.DESCRIPTION or "")[:60]]
                        for _, r in d.nlargest(10, "LCY_AMOUNT").iterrows()],
                note="Les dix plus gros mouvements d'exploitation du compte sur la période.",
            ),
            Tableau(
                entetes=["Date", "Sens", "Montant XAF", "Libellé"],
                lignes=[[r.TRN_DT, r.DRCR_IND, float(r.LCY_AMOUNT),
                         str(r.DESCRIPTION or "")[:74]]
                        for _, r in residus.nlargest(8, "LCY_AMOUNT").iterrows()],
                note=("Les résidus sans qualification : leur libellé désigne une opération sur "
                      "titre sans dire quelle charge elle constitue."),
            ),
        ],
        recommandation=(
            f"1. Faire reclasser les {xaf(decotes)} de décotes et primes vers les comptes de "
            "revenus et résultats sur titres ou de produits comptabilisés d'avance, selon le "
            + (f"cas — la banque a montré la voie en reclassant {xaf(montant_reclass)} le "
               f"{date_reclass}.\n" if montant_reclass else "cas.\n")
            + "2. Interdire les écritures au crédit de ce compte : une commission facturée à "
            "un client est un produit et s'enregistre comme tel, sans compensation avec la "
            "charge.\n"
            f"3. Faire justifier les {nb(len(residus))} résidus sans qualification, et en "
            f"premier lieu celui de {xaf(float(residus.LCY_AMOUNT.max()))} : quelle charge "
            "constituent-ils ?\n"
            "4. Instaurer une règle de justification : toute écriture sur un compte de charge "
            "titres porte la référence du contrat et la nature de la charge. Un libellé qui se "
            "borne à « SALES security » ne permet aucun contrôle.\n"
            "5. Rapprocher le montant des commissions et droits de garde réellement dus des "
            "relevés du CRCT, du dépositaire et des intermédiaires — ce que la comptabilité ne "
            "permet pas aujourd'hui."
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
# Un libellé se rapporte au circuit titres s'il porte une référence de contrat Flexcube
# (099XXXX suivi de neuf chiffres) ou un code de titre CEMAC. Les motifs plus lâches —
# « CM1 », « CM2 » employés comme fragments — produisent trop de faux positifs.
MOTIF_CONTRAT = r"099[A-Z]{4}\d{9}"
MOTIF_ISIN = r"\b(?:CM|CG|GA|GQ|TD|CF)[0-9][A-Z0-9]{8}\b"


def _c123_compte_attente(ctx) -> Constat:
    """Le compte d'attente de la direction financière, et ce que le circuit titres y a fait.

    Deux choses sont à séparer, et la version antérieure de ce contrôle les confondait : ce
    compte n'est PAS un compte de passage du circuit titres — il sert à la direction
    financière pour toutes ses régularisations. Mais le circuit titres y a fait, une fois,
    une incursion massive.
    """
    compte = CPT_ATTENTE[0]
    d = _periode(ctx, compte)
    complet = ctx.historique_compte(compte, dans_periode=False)
    libelle = ctx.libelle_compte(compte)
    if d.empty:
        return Constat(code="12.3", titre=f"Compte {compte} non mouvementé",
                       gravite=Gravite.CONFORME, constat="Aucun mouvement sur la période.")

    texte = d.DESCRIPTION.fillna("").str.upper()
    titres = d[texte.str.contains(MOTIF_CONTRAT, regex=True)
               | texte.str.contains(MOTIF_ISIN, regex=True)]
    jours_titres = sorted(set(titres.TRN_DT))
    campagne = d[d.TRN_DT.isin(jours_titres)]
    hors_campagne_titres = len(titres[~titres.TRN_DT.isin(jours_titres)])

    lib_camp = campagne.DESCRIPTION.fillna("").str.upper()
    reversals = campagne[lib_camp.str.contains("REVERSAL|RVSL", regex=True)]
    contrats = int(lib_camp.str.extract(f"({MOTIF_CONTRAT})")[0].nunique())
    jour_pic = campagne.groupby("TRN_DT").size().idxmax()
    n_pic = int(campagne.groupby("TRN_DT").size().max())
    # Le jour où le compte s'écarte le plus de zéro, et dans quel sens.
    soldes_camp = {j: ctx.solde_a(compte, j) for j in sorted(set(campagne.TRN_DT))}
    pire_jour = min(soldes_camp, key=lambda j: soldes_camp[j])
    pire_solde = soldes_camp[pire_jour]

    # Le lien avec le compte de courus MANUELS du contrôle 12.7.
    vague = ctx.comptes_complementaires
    manuel = vague[vague.AC_NO == CPT_COURUS_MANUELS]
    refs_attente = set(campagne.TRN_REF_NO)
    refs_manuel = set(manuel[manuel.TRN_DT.isin(jours_titres)].TRN_REF_NO)
    communes = refs_attente & refs_manuel
    veille = min(jours_titres)
    avant = float(manuel[manuel.TRN_DT < veille].SIGNE.sum())
    apres = float(manuel[manuel.TRN_DT <= max(jours_titres)].SIGNE.sum())

    # Le solde qui reste, et ce qu'il est réellement.
    soldes = [[a, ctx.solde_a(compte, a)] for a in ctx.arretes]
    fin_periode = ctx.solde_a(compte, ctx.config.fin)
    gros = d.nlargest(1, "LCY_AMOUNT")
    gros_montant = float(gros.LCY_AMOUNT.iloc[0]) if len(gros) else 0.0
    gros_date = str(gros.TRN_DT.iloc[0]) if len(gros) else ""
    # L'apurement, postérieur à la période : c'est lui qui dit ce qu'était ce solde.
    apur = complet[complet.DESCRIPTION.fillna("").str.contains(
        "Regularization suspense", case=False)]
    apur_scb = apur[apur.DESCRIPTION.fillna("").str.upper().str.contains("SCB")]
    apur_date = str(apur_scb.TRN_DT.max()) if not apur_scb.empty else ""
    apur_lib = str(apur_scb.DESCRIPTION.iloc[0]) if not apur_scb.empty else ""
    jours_solde = ((pd.Timestamp(apur_date) - pd.Timestamp(gros_date)).days
                   if apur_date and gros_date else 0)
    autre = ctx.solde_a(CPT_ATTENTE[1], ctx.config.fin)

    return Constat(
        code="12.3",
        titre=("Le compte d'attente de la direction financière : une reprise massive d'intérêts "
               "sur titres en quatre jours, et le résidu de la fusion SCB à la clôture"),
        gravite=Gravite.ELEVEE,
        reference=f"Compte {compte} {libelle}",
        constat=(
            "I. CE QU'EST CE COMPTE — ET CE QU'IL N'EST PAS\n"
            "\n"
            f"{compte} {libelle} est le compte d'attente de la DIRECTION FINANCIÈRE. Son "
            "contenu ordinaire n'a rien de bancaire au sens du marché : factures "
            "informatiques en attente de rattachement, reprises de paie, écritures "
            "inter-agences. Ce n'est pas un compte de trésorerie, et la version antérieure de "
            "ce contrôle le présentait à tort comme « un compte de passage du circuit "
            "titres ». Il ne l'est pas.\n"
            "\n"
            "II. MAIS LE CIRCUIT TITRES Y A FAIT UNE INCURSION, ET ELLE EST MASSIVE\n"
            "\n"
            f"Sur les {nb(len(d))} lignes de la période, {nb(len(titres))} portent une "
            "référence de contrat de marché monétaire ou un code de titre CEMAC. Le fait "
            "marquant n'est pas leur nombre, c'est leur DATE : elles se concentrent toutes "
            f"sur {nb(len(jours_titres))} JOURS — {', '.join(jours_titres)}. "
            + ("En dehors de ces quelques jours, le compte ne porte PAS UNE SEULE écriture "
               "se rapportant à un titre.\n"
               if hors_campagne_titres == 0 else
               f"En dehors de ces jours, il en porte {nb(hors_campagne_titres)}.\n")
            + "\n"
            "III. CE QUE CETTE CAMPAGNE A FAIT\n"
            "\n"
            f"Sur ces {nb(len(jours_titres))} jours, {nb(len(campagne))} lignes ont transité "
            f"par le compte, en {nb(campagne.TRN_REF_NO.nunique())} écritures manuelles "
            f"saisies par {nb(campagne.USER_ID.nunique())} opérateurs, pour "
            f"{xaf(float(campagne.LCY_AMOUNT.sum()))} de mouvements bruts. "
            f"{nb(len(reversals))} de ces lignes sont des ANNULATIONS, pour "
            f"{xaf(float(reversals.LCY_AMOUNT.sum()))}, et elles touchent {nb(contrats)} "
            f"contrats distincts. La seule journée du {jour_pic} en porte {nb(n_pic)}.\n"
            "\n"
            "CE QUI ÉTAIT VISÉ EST IDENTIFIABLE, ET C'EST IMPORTANT. Les libellés le disent : "
            f"« Reversal of {CPT_COURUS_MANUELS} in {compte} ». "
            f"{nb(len(communes))} écritures de la campagne mouvementent SIMULTANÉMENT ce "
            f"compte d'attente et {CPT_COURUS_MANUELS} "
            f"{ctx.libelle_compte(CPT_COURUS_MANUELS)} — le second compte de courus, servi à "
            "la main, dont le contrôle 12.7 retrace l'histoire.\n"
            f"L'effet est mesurable : le solde de {CPT_COURUS_MANUELS} passe de "
            f"{xaf(avant)} la veille de la campagne à {xaf(apres)} au lendemain, soit "
            f"{xaf(avant - apres)} de moins.\n"
            "\n"
            "AUTREMENT DIT, CETTE CAMPAGNE ÉTAIT UNE TENTATIVE D'APUREMENT DU COMPTE DE COURUS "
            "MANUELS. Elle n'a pas abouti : le contrôle 12.7 établit que le solde résiduel de "
            "ce compte a fini, deux ans plus tard, en PERTE OPÉRATIONNELLE. Les deux constats "
            "décrivent le même dossier à deux moments : la tentative de nettoyage, puis "
            "l'abandon.\n"
            "\n"
            "IV. CE QUE LA CAMPAGNE LAISSE COMME PROBLÈME DE PISTE D'AUDIT\n"
            "\n"
            f"{xaf(float(reversals.LCY_AMOUNT.sum()))} de produits sur titres ont été défaits "
            "puis refaits par écritures manuelles, en dehors de tout traitement automatique, "
            "sans qu'aucune pièce ne rattache l'ensemble à une décision de correction "
            f"identifiée. Le {jour_pic} — une fin de trimestre — le compte d'attente porte "
            f"encore {xaf(ctx.solde_a(compte, jour_pic))} en fin de journée.\n"
            + (f"\nPLUS RÉVÉLATEUR ENCORE : le {pire_jour}, en cours de campagne, le compte "
               f"se présente à {xaf(pire_solde)}, c'est-à-dire CRÉDITEUR — sur un compte que "
               "son intitulé même désigne comme débiteur. Un compte d'attente qui bascule de "
               "plus d'un milliard dans le sens opposé à sa nature signale que les deux jambes "
               "d'une même correction ont été passées à plusieurs jours d'intervalle.\n"
               if pire_solde < -1 else "")
            + "\n"
            "V. LE SOLDE QUI RESTE À LA CLÔTURE — ET CE QU'IL EST RÉELLEMENT\n"
            "\n"
            f"Au {ctx.config.fin}, le compte porte {xaf(fin_periode)} au DÉBIT. L'essentiel "
            f"tient à une écriture unique, passée le {gros_date} — le jour de l'arrêté "
            f"annuel — pour {xaf(gros_montant)}, sous le libellé laconique « Rclss COMPTE "
            "INTER BRANCHES ».\n"
            + (f"\nCE QU'IL Y AVAIT DERRIÈRE, LA BANQUE LE DIT ELLE-MÊME — MAIS SEULEMENT LE "
               f"{apur_date}, en apurant le compte par l'écriture exactement inverse. Le "
               f"libellé est alors explicite : « {apur_lib} ». Il ne s'agissait donc pas d'un "
               "problème inter-agences ordinaire, mais du RÉSIDU NON AFFECTÉ DE LA MIGRATION "
               "DE FUSION DE STANDARD CHARTERED — le même dossier que le contrôle 12.5 — "
               "comprenant notamment un découvert du compte de Standard Chartered à New York.\n"
               f"\nCE RÉSIDU EST RESTÉ {nb(jours_solde)} JOURS DANS UN COMPTE D'ATTENTE, et "
               "il a figuré comme tel à l'actif du bilan à l'arrêté du 31 décembre 2025 et à "
               "celui du 30 juin 2026. Porter au bilan, sous un libellé qui n'en dit rien, un "
               "milliard dont on sait qu'il provient d'une fusion non soldée, n'est pas une "
               "imputation : c'est un report.\n" if apur_date else "")
            + "\n"
            "VI. À TITRE DE COMPARAISON\n"
            "\n"
            f"Le compte d'attente symétrique {CPT_ATTENTE[1]} "
            f"{ctx.libelle_compte(CPT_ATTENTE[1])} se présente à {xaf(autre)} à la clôture : "
            "lui est correctement apuré. La défaillance porte sur un compte, pas sur le "
            "dispositif."
        ),
        chiffres=[
            ("Nature du compte", "attente de la direction financière, hors périmètre trésorerie"),
            ("Écritures sur la période", nb(len(d))),
            ("Dont portant une référence de titre", nb(len(titres))),
            ("Jours où le circuit titres a employé ce compte", nb(len(jours_titres))),
            ("Écritures titres en dehors de ces jours", nb(hors_campagne_titres)),
            ("Campagne — lignes", nb(len(campagne))),
            ("Campagne — écritures manuelles", nb(campagne.TRN_REF_NO.nunique())),
            ("Campagne — opérateurs", nb(campagne.USER_ID.nunique())),
            ("Campagne — mouvements bruts", xaf(float(campagne.LCY_AMOUNT.sum()))),
            ("Campagne — annulations", f"{nb(len(reversals))} — {xaf(float(reversals.LCY_AMOUNT.sum()))}"),
            ("Campagne — contrats touchés", nb(contrats)),
            (f"Écritures touchant aussi {CPT_COURUS_MANUELS}", nb(len(communes))),
            (f"Solde de {CPT_COURUS_MANUELS} avant la campagne", xaf(avant)),
            (f"Solde de {CPT_COURUS_MANUELS} après la campagne", xaf(apres)),
            ("Réduction obtenue", xaf(avant - apres)),
            (f"Solde du compte d'attente au {ctx.config.fin}", xaf(fin_periode)),
            ("Dont résidu de la fusion SCB", xaf(gros_montant)),
            ("Durée du séjour de ce résidu", f"{nb(jours_solde)} jours" if jours_solde else "n/d"),
            ("Date d'apurement, postérieure à la période", apur_date or "non apuré"),
        ],
        tableaux=[
            Tableau(
                entetes=["Jour de la campagne", "Lignes", "Mouvements bruts XAF",
                         "Solde du compte en fin de journée XAF"],
                lignes=[[j, int((campagne.TRN_DT == j).sum()),
                         float(campagne[campagne.TRN_DT == j].LCY_AMOUNT.sum()),
                         ctx.solde_a(compte, j)] for j in jours_titres],
                note=("La campagne de reprise, jour par jour. Elle tient en quelques journées, "
                      "dont une fin de trimestre."),
            ),
            Tableau(
                entetes=["Date d'arrêté", "Solde XAF"],
                lignes=soldes,
                note=("Le solde du compte d'attente à chaque date d'arrêté. Un compte "
                      "d'attente doit s'y présenter à zéro."),
            ),
            Tableau(
                entetes=["Date", "Référence", "Sens", "Montant XAF", "Opérateur", "Libellé"],
                lignes=[[r.TRN_DT, r.TRN_REF_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID,
                         str(r.DESCRIPTION or "")[:56]]
                        for _, r in pd.concat([d.nlargest(6, "LCY_AMOUNT"), apur_scb]).iterrows()],
                max_lignes=12,
                note=("Les plus gros mouvements de la période, et l'écriture d'apurement "
                      "postérieure qui révèle la nature du solde porté à la clôture."),
            ),
        ],
        recommandation=(
            "1. Obtenir la note de correction qui fonde la campagne de reprise : qui l'a "
            "décidée, sur quel diagnostic, et pourquoi elle a été exécutée par écritures "
            "manuelles plutôt que par reprise du traitement. Elle touche "
            f"{nb(contrats)} contrats et {xaf(float(reversals.LCY_AMOUNT.sum()))}.\n"
            "2. La rapprocher du contrôle 12.7 : la campagne visait le compte de courus "
            "manuels, et n'a pas suffi à l'apurer. Comprendre pourquoi permet de savoir ce "
            "que la perte opérationnelle finale recouvrait réellement.\n"
            f"3. Faire justifier le maintien de {xaf(gros_montant)} de résidus de la fusion "
            "Standard Chartered dans un compte d'attente à la date d'arrêté annuel, sous un "
            "libellé qui n'en indique pas la nature, et obtenir l'analyse détaillée qui a "
            "permis de les apurer en août 2026.\n"
            "4. Instaurer une règle d'apurement : tout solde d'un compte d'attente de plus de "
            "trente jours fait l'objet d'un état nominatif présenté au comité d'audit, avec "
            "l'origine de chaque ligne."
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
    """La reprise du portefeuille de Standard Chartered lors de la fusion.

    ATTENTION AU CONTEXTE : la période porte DEUX migrations distinctes. Celle de juin 2025
    est un changement de plateforme — Flexcube vers Calypso. Celle de décembre 2025 est la
    reprise des données de Standard Chartered Bank Cameroun dans Access Bank Cameroun, à la
    suite de l'acquisition de la filiale. L'emploi d'un utilisateur technique et de comptes
    de conversion y est donc normal, et n'appelle aucune observation. Le constat porte sur un
    point précis : la contrepartie retenue pour apurer le compte de conversion.
    """
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

    a = ctx.toutes_ecritures
    # L'ampleur réelle de la migration de fusion, mesurée sur l'utilisateur technique. Le
    # compte de conversion ne vit que dans la deuxième vague : on réunit les deux sources.
    tout = pd.concat([a, d], ignore_index=True) if not d.empty else a
    tech = tout[tout.USER_ID == user_reprise]
    nb_refs = int(tech.TRN_REF_NO.nunique())
    nb_lignes = int(len(tech))
    comptes_fusion = sorted(set(tech.AC_NO.dropna()))
    dates_fusion = sorted(set(tech.TRN_DT.dropna()))

    # La contrepartie de l'apurement du compte de conversion.
    ref_apurement = str(credits.TRN_REF_NO.iloc[0]) if len(credits) else ""
    contrepartie = a[(a.TRN_REF_NO == ref_apurement) & (~a.AC_NO.isin(CPT_CONVERSION))]
    cpt_contrepartie = str(contrepartie.AC_NO.iloc[0]) if not contrepartie.empty else ""
    lib_contrepartie = ctx.libelle_compte(cpt_contrepartie) if cpt_contrepartie else ""

    # L'écriture de régularisation, six mois plus tard.
    regul = a[a.TRN_REF_NO == "0990023261670001"].drop_duplicates(
        subset=["AC_NO", "DRCR_IND", "LCY_AMOUNT", "DESCRIPTION"])
    ap_date = str(regul.TRN_DT.iloc[0]) if not regul.empty else ""
    ap_user = str(regul.USER_ID.iloc[0]) if not regul.empty else ""
    jours = (pd.Timestamp(ap_date) - pd.Timestamp(c_date)).days if ap_date and c_date else 0
    titres = sorted(set(regul.DESCRIPTION.fillna("").str.extract(
        r"(CM[0-9][A-Z0-9]{8})")[0].dropna())) if not regul.empty else []

    # L'EFFET SUR L'ARRÊTÉ — le chiffre qui porte le constat.
    def solde(compte, date):
        b = a[(a.AC_NO == compte) & (a.TRN_DT <= date)].drop_duplicates(
            subset=["TRN_REF_NO", "DRCR_IND", "LCY_AMOUNT", "STMT_DT", "DESCRIPTION"])
        return float(b.SIGNE.sum())
    arrete = "2025-12-31"
    nostro_affiche = solde(cpt_contrepartie, arrete) if cpt_contrepartie else 0.0
    nostro_corrige = nostro_affiche - montant
    cpt_titres = "511210100"
    titres_affiche = solde(cpt_titres, arrete)

    return Constat(
        code="12.5",
        titre=("Le portefeuille repris de Standard Chartered est resté six mois au compte de la "
               "banque centrale au lieu du portefeuille titres"),
        gravite=Gravite.CRITIQUE,
        reference=(f"Migration de fusion SCB — écritures des {d_date}, {c_date} et {ap_date}"),
        constat=(
            "I. LE CONTEXTE — DEUX MIGRATIONS DISTINCTES, À NE PAS CONFONDRE\n"
            "\n"
            "La période d'audit porte deux migrations sans rapport l'une avec l'autre.\n"
            f"- Celle du {str(DATE_BASCULE)[:10]} est un CHANGEMENT DE PLATEFORME : la gestion "
            "des titres quitte le module Money Market de Flexcube pour Calypso. C'est elle que "
            "traite la section 5.\n"
            f"- Celle du {d_date} est tout autre chose : c'est la REPRISE DES DONNÉES DE "
            "STANDARD CHARTERED BANK CAMEROUN dans Access Bank Cameroun, à la suite de "
            "l'acquisition de la filiale. Une migration de fusion.\n"
            "\n"
            "LES ÉCRITURES LE CONFIRMENT SANS AMBIGUÏTÉ. Ce jour-là, l'utilisateur technique "
            f"{user_reprise} passe {nb(nb_lignes)} lignes en {nb(nb_refs)} écritures, sur "
            f"{nb(len(comptes_fusion))} comptes — et parmi eux les nostri PROPRES de Standard "
            "Chartered, 007ACB00033 SCB NEW-YORK et 007ACB00034 SCB FRANKFURT, ainsi que "
            "l'intégralité du dispositif de position de change, comptes de position et "
            "comptes de contre-valeur. Les références d'écriture portent les préfixes des "
            "agences reprises. Il ne s'agit donc pas d'une reprise tardive de la bascule de "
            "juin, mais d'une opération de fusion, datée et distincte.\n"
            "\n"
            "II. CE QUI EST NORMAL, ET QUE LE CONSTAT NE VISE PAS\n"
            "\n"
            "L'emploi d'un utilisateur technique de reprise, l'emploi d'un compte de "
            "conversion, et la comptabilisation manuelle des positions reprises sont les "
            "procédés ordinaires d'une migration de fusion. Le compte de conversion est même "
            "fait pour cela : accueillir un solde le temps qu'il soit affecté. Rien de tout "
            "cela n'appelle d'observation, et une version antérieure du présent rapport les "
            "présentait à tort comme des anomalies.\n"
            "\n"
            "III. LE POINT QUI N'EST PAS NORMAL — LA CONTREPARTIE DE L'APUREMENT\n"
            "\n"
            f"Le {d_date}, {user_reprise} débite le compte de conversion "
            f"{CPT_CONVERSION[0]} {ctx.libelle_compte(CPT_CONVERSION[0])} de {xaf(montant)} : "
            "les bons du Trésor repris de Standard Chartered. Correct.\n"
            f"Le {c_date}, l'opérateur {user_apurement} apure ce compte de conversion. Il "
            f"aurait dû le faire en DÉBITANT le portefeuille titres. Il le fait en débitant "
            f"{cpt_contrepartie} {lib_contrepartie} — le compte de règlement de la banque "
            "auprès de la banque centrale.\n"
            "\n"
            "Autrement dit, la banque enregistre avoir reçu de la TRÉSORERIE à la banque "
            "centrale, alors qu'elle a reçu des TITRES. Le libellé de l'écriture le dit "
            "lui-même : « Securities received from SCB to be booked manually ». Des titres, "
            "à comptabiliser manuellement — et en attendant, ils sont logés dans la "
            "trésorerie.\n"
            "\n"
            "IV. LA PREUVE QU'IL S'AGIT D'UNE ERREUR, ET NON D'UN CHOIX DE PRÉSENTATION\n"
            "\n"
            f"C'est la banque elle-même qui la fournit. Le {ap_date}, l'opérateur {ap_user} "
            f"passe l'écriture de régularisation : elle CRÉDITE {cpt_contrepartie} de "
            f"{xaf(montant)} et DÉBITE {cpt_titres} {ctx.libelle_compte(cpt_titres)} du même "
            "montant, sous le libellé « Clearing Securities received from SCB to be booked "
            "manually during transition ». Le montant sort de la trésorerie et entre au "
            "portefeuille.\n"
            "Si le débit de décembre avait correspondu à une reprise réelle de trésorerie, il "
            f"n'y aurait rien eu à contre-passer. {nb(jours)} JOURS SE SONT ÉCOULÉS ENTRE "
            "L'ERREUR ET SA CORRECTION.\n"
            "\n"
            "V. L'EFFET SUR L'ARRÊTÉ ANNUEL DU 31 DÉCEMBRE 2025\n"
            "\n"
            "C'est ici que le constat prend sa mesure, et il ne se lit pas en pourcentage mais "
            "en changement de nature.\n"
            f"- Le compte de règlement auprès de la banque centrale affiche {xaf(nostro_affiche)} "
            "à cette date.\n"
            f"- Il contient {xaf(montant)} qui ne sont pas de la trésorerie.\n"
            f"- CORRIGÉ, IL RESSORT À {xaf(nostro_corrige)} — c'est-à-dire en position "
            "CRÉDITRICE.\n"
            "\n"
            "L'écriture ne surévalue donc pas seulement la trésorerie : ELLE INVERSE LE SENS "
            "DE LA POSITION DE LA BANQUE AUPRÈS DE SON INSTITUT D'ÉMISSION à la date "
            "d'arrêté. Les états présentent un AVOIR à la banque centrale là où la position "
            "corrigée fait apparaître un DÉCOUVERT. C'est une information qui intéresse "
            "directement le suivi des réserves obligatoires et le ratio de liquidité.\n"
            "\n"
            f"Symétriquement, le compte {cpt_titres} affiche {xaf(titres_affiche)} au "
            f"31 décembre 2025, alors qu'il aurait dû porter {xaf(titres_affiche + montant)} : "
            "le portefeuille de bons du Trésor est présenté pour moins de la moitié de sa "
            "consistance réelle.\n"
            "\n"
            "VI. CE QUE LES SIX MOIS ONT EMPORTÉ AU PASSAGE\n"
            "\n"
            f"L'écriture du {ap_date} ne fait pas qu'entrer les titres : elle les entre ET les "
            f"sort. Elle nomme {nb(len(titres))} lignes de titres repris de Standard "
            "Chartered — dont les échéances s'échelonnent d'avril à octobre 2026 — et "
            "comptabilise dans le même mouvement leur dénouement, leur décote et leurs "
            "intérêts. Plusieurs de ces titres sont donc arrivés à échéance PENDANT qu'ils "
            "étaient logés dans la trésorerie.\n"
            "Il en résulte que, sur toute la période, le portefeuille n'a jamais porté ces "
            "titres, qu'aucun intérêt couru n'a été constaté sur eux dans les comptes de "
            "rattachement, et que leur produit n'est pas identifiable exercice par exercice."
        ),
        chiffres=[
            ("Nature de l'opération", "migration de fusion Standard Chartered → Access Bank"),
            ("Date de la reprise technique", d_date),
            ("Utilisateur technique de reprise", user_reprise),
            ("Écritures passées ce jour-là", f"{nb(nb_lignes)} lignes en {nb(nb_refs)} écritures"),
            ("Montant des titres repris", xaf(montant)),
            ("Date d'apurement du compte de conversion", c_date),
            ("Contrepartie retenue à l'apurement", f"{cpt_contrepartie} {lib_contrepartie}"),
            ("Contrepartie qui aurait dû l'être", f"{cpt_titres} {ctx.libelle_compte(cpt_titres)}"),
            ("Date de la régularisation", ap_date),
            ("Durée de l'anomalie", f"{nb(jours)} jours"),
            ("Dates d'arrêté traversées", arrete),
            (f"Compte de règlement affiché au {arrete}", xaf(nostro_affiche)),
            (f"Compte de règlement corrigé au {arrete}", xaf(nostro_corrige)),
            ("Sens de la position après correction", "CRÉDITEUR" if nostro_corrige < 0 else "débiteur"),
            (f"Portefeuille {cpt_titres} affiché au {arrete}", xaf(titres_affiche)),
            (f"Portefeuille {cpt_titres} corrigé au {arrete}", xaf(titres_affiche + montant)),
        ],
        tableaux=[
            Tableau(
                entetes=["Date", "Compte", "Sens", "Montant XAF", "Opérateur", "Libellé"],
                lignes=([[r.TRN_DT, r.AC_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID,
                          str(r.DESCRIPTION or "")[:52]] for _, r in mouv.iterrows()]
                        + [[r.TRN_DT, r.AC_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID,
                            str(r.DESCRIPTION or "")[:52]]
                           for _, r in contrepartie.iterrows()]
                        + [[r.TRN_DT, r.AC_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID,
                            str(r.DESCRIPTION or "")[:52]]
                           for _, r in regul[regul.DESCRIPTION.fillna("").str.contains(
                               "during transition")].iterrows()]),
                note=("Les trois écritures qui font le dossier : la reprise technique au compte "
                      "de conversion, son apurement sur le compte de la banque centrale, et la "
                      "régularisation six mois plus tard vers le portefeuille titres."),
            ),
            Tableau(
                entetes=["Compte", "Libellé", "Rôle dans la migration de fusion"],
                lignes=[[x, ctx.libelle_compte(x) or "—",
                         "nostro repris de Standard Chartered" if x.startswith("007")
                         else ("compte de conversion des titres" if x in CPT_CONVERSION
                               else "position de change et contre-valeur")]
                        for x in comptes_fusion],
                max_lignes=12,
                note=("Les comptes mouvementés par l'utilisateur technique le jour de la "
                      "migration de fusion. La présence des nostri propres de Standard "
                      "Chartered établit la nature de l'opération."),
            ),
        ],
        recommandation=(
            f"1. Chiffrer l'effet sur les états arrêtés au {arrete} et vérifier s'ils ont été "
            f"corrigés : {xaf(montant)} de trésorerie inexistante au compte de la banque "
            "centrale, autant de titres absents du portefeuille, et une position auprès de "
            "l'institut d'émission présentée en sens inverse de sa réalité.\n"
            "2. Vérifier l'incidence sur les réserves obligatoires et sur le ratio de "
            "liquidité déclarés à cette date, que le rapprochement bancaire du compte de la "
            "banque centrale aurait dû faire apparaître dès décembre.\n"
            "3. Obtenir le dossier de reprise du portefeuille Standard Chartered : état des "
            "titres transférés, valorisation retenue, et rapprochement avec le dépositaire.\n"
            f"4. Faire expliquer pourquoi l'apurement du compte de conversion a été imputé au "
            f"compte {cpt_contrepartie} plutôt qu'au portefeuille titres, et pourquoi la "
            f"correction a demandé {nb(jours)} jours.\n"
            "5. Reconstituer les intérêts courus sur ces titres entre la reprise et leur "
            "comptabilisation effective : ils n'ont été constatés dans aucun compte de "
            "rattachement pendant cette période.\n"
            "6. Vérifier que les autres volets de la migration de fusion — position de change, "
            "nostri repris — ont bien été imputés à leur compte définitif, et qu'aucun autre "
            "solde n'est resté logé dans un compte de passage."
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
        ("511801100", "courus du portefeuille repris de SCB, dont le contrôle 12.5 établit l'entrée"),
        ("601200101", "charge d'intérêt du guichet de refinancement BEAC"),
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
            "CE QUE LA TROISIÈME VAGUE A APPORTÉ. Le compte 511800101 « créances rattachées — "
            "MANUELLES », que ce contrôle signalait comme manquant, a depuis été extrait : il "
            "fait l'objet du contrôle 12.7, et ce qu'il révèle est le constat le plus lourd de "
            "la section. Le compte 601200100 l'a été également — il ne porte que quatre "
            "écritures, étrangères aux pensions, ce qui confirme le contrôle 12.2.\n"
            "\n"
            "CE QU'IL RESTE À OBTENIR. Deux comptes que les libellés désignent n'ont encore été "
            "extraits dans aucune vague, dont 511801100, qui porte les courus du portefeuille "
            "repris de SCB au contrôle 12.5. Tant qu'il n'est pas extrait, l'analyse des "
            "courus reste établie sur une vue partielle."
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


# --- 12.7 ---------------------------------------------------------------------------------
def _c127_courus_manuels(ctx) -> Constat:
    """Le second compte de courus, réservé aux écritures manuelles.

    Il vit en parallèle de 511800100 sans qu'aucun contrôle antérieur l'ait vu, parce qu'il ne
    figurait dans aucune extraction. Son historique complet change la lecture de la migration.
    """
    d = ctx.historique_compte(CPT_COURUS_MANUELS, dans_periode=False)
    if d.empty:
        return Constat(code="12.7", titre=f"Compte {CPT_COURUS_MANUELS} non extrait",
                       gravite=Gravite.CONFORME, constat="Sans objet.")
    libelle = ctx.libelle_compte(CPT_COURUS_MANUELS)
    periode = d[(d.TRN_DT >= ctx.config.debut) & (d.TRN_DT <= ctx.config.fin)]
    soldes = [[a, ctx.solde_a(CPT_COURUS_MANUELS, a)] for a in ctx.arretes]
    bascule = str(DATE_BASCULE)[:10]
    apres = d[d.TRN_DT > bascule]
    dernier = apres.iloc[-1] if not apres.empty else None
    solde_bascule = ctx.solde_a(CPT_COURUS_MANUELS, bascule)
    solde_fin = ctx.solde_a(CPT_COURUS_MANUELS, ctx.config.fin)
    par_an = (d.groupby(d.TRN_DT.str[:4])
              .agg(lignes=("LCY_AMOUNT", "size"), brut=("LCY_AMOUNT", "sum"),
                   net=("SIGNE", "sum")).reset_index())
    lib_ecriture = str(dernier.DESCRIPTION or "") if dernier is not None else ""
    date_ecriture = str(dernier.TRN_DT) if dernier is not None else ""
    montant_ecriture = float(dernier.LCY_AMOUNT) if dernier is not None else 0.0

    return Constat(
        code="12.7",
        titre="Un second compte de courus, jamais apuré à la migration, soldé en perte opérationnelle APRÈS la clôture de la période",
        gravite=Gravite.CRITIQUE,
        reference=f"Compte {CPT_COURUS_MANUELS} {libelle} — écriture de solde du {date_ecriture}",
        constat=(
            f"CE COMPTE N'AVAIT JAMAIS ÉTÉ VU. {CPT_COURUS_MANUELS} {libelle} porte les "
            "intérêts courus enregistrés PAR ÉCRITURE MANUELLE, en parallèle du compte "
            "automatique 511800100. Il ne figurait dans aucune des extractions précédentes ; "
            "seuls les libellés du compte d'attente 466000107 le désignaient (contrôle 12.3). "
            "Son historique complet change la lecture de plusieurs constats antérieurs.\n"
            "\n"
            f"CE QU'IL PORTE. {nb(len(periode))} écritures sur la période d'audit, pour "
            f"{xaf(float(periode.LCY_AMOUNT.sum()))} de mouvements bruts. L'année 2024 à elle "
            "seule en compte plus de treize cents. Un volume de cette ampleur sur un compte "
            "servi exclusivement à la main, en doublure d'un compte alimenté automatiquement, "
            "n'est pas une exception de traitement : c'est un second circuit.\n"
            "\n"
            f"IL S'ARRÊTE À LA BASCULE — ET N'EST PAS APURÉ. Le dernier mouvement d'exploitation "
            f"est daté du 2025-06-12, quatre jours avant la bascule vers Calypso du {bascule}. "
            f"Le compte reste alors à {xaf(solde_bascule)} au DÉBIT. L'écriture d'apurement des "
            "courus passée à la migration, que le contrôle 5.3 décompose, ne portait QUE sur "
            f"511800100. {CPT_COURUS_MANUELS} n'a pas été touché. Son solde est resté "
            "IDENTIQUE, au franc près, pendant plus d'un an — à la clôture annuelle du "
            f"31 décembre 2025 comme à la clôture de la période auditée.\n"
            "\n"
            "CE QUE LA BANQUE EN A FAIT. Une seule écriture est passée après la bascule, et "
            f"elle est datée du {date_ecriture} — soit APRÈS la fin de la période auditée. "
            f"Elle solde le compte par un CRÉDIT de {xaf(montant_ecriture)} sous le libellé "
            f"« {lib_ecriture} ».\n"
            "\n"
            "CE QUE CE LIBELLÉ ÉTABLIT, ET IL EST SANS AMBIGUÏTÉ.\n"
            "- La banque a elle-même qualifié ce solde de PERTE OPÉRATIONNELLE. Ce n'était donc "
            "pas une créance recouvrable.\n"
            "- La période couverte, de mai 2022 à juin 2025, correspond à plus de trois "
            "exercices. Il ne s'agit pas d'un incident ponctuel mais d'une accumulation.\n"
            "- L'écriture est passée APRÈS la clôture de la période auditée. Il en résulte que "
            "les états arrêtés au 31 décembre 2023, au 31 décembre 2024, au 30 juin 2025 et au "
            f"31 décembre 2025 portent tous à l'ACTIF, au minimum, les {xaf(montant_ecriture)} "
            "que la banque a ensuite reconnus comme perdus — les soldes antérieurs étant même "
            "plus élevés, ainsi que le montre le tableau des arrêtés.\n"
            "\n"
            "LE LIEN AVEC LE CONTRÔLE 12.6 EST DIRECT. Celui-ci établit qu'AUCUNE dépréciation "
            "n'a jamais été constatée sur le portefeuille titres. On en a ici la contrepartie "
            "concrète : plutôt que de déprécier progressivement une créance devenue douteuse, "
            "la banque l'a maintenue à sa valeur nominale pendant trois ans, puis l'a passée "
            "en perte en une seule écriture, hors période.\n"
            "\n"
            f"ENFIN, CE CONSTAT COMPLÈTE LES CONTRÔLES 5.2 ET 5.3. La migration a sur-apuré le "
            f"compte automatique de {xaf(1_205_231_891)} et laissé le compte manuel intact à "
            f"{xaf(solde_bascule)}. Les deux erreurs vont dans le même sens : les courus repris "
            "à la bascule ne reflétaient pas la réalité des créances."
        ),
        chiffres=[
            ("Écritures sur la période d'audit", nb(len(periode))),
            ("Mouvements bruts cumulés", xaf(float(periode.LCY_AMOUNT.sum()))),
            ("Dernier mouvement d'exploitation", "2025-06-12"),
            (f"Solde au jour de la bascule ({bascule})", xaf(solde_bascule)),
            ("Solde à la clôture de la période auditée", xaf(solde_fin)),
            ("Date de l'écriture de solde", date_ecriture),
            ("Nature retenue par la banque", "perte opérationnelle"),
            ("Période couverte par la perte", "mai 2022 à juin 2025"),
            ("Montant passé en perte", xaf(montant_ecriture)),
            ("Dépréciation constatée avant cette écriture", xaf(0)),
        ],
        tableaux=[
            Tableau(
                entetes=["Date d'arrêté", "Solde du compte XAF"],
                lignes=soldes,
                note=("Le solde du compte à chaque date d'arrêté. Il figure à l'ACTIF du bilan "
                      "à chacune d'elles, et la banque l'a ensuite reconnu comme perdu."),
            ),
            Tableau(
                entetes=["Année", "Écritures", "Mouvements bruts XAF", "Variation nette XAF"],
                lignes=[[r.TRN_DT, int(r.lignes), float(r.brut), float(r.net)]
                        for _, r in par_an.iterrows()],
                note=("L'activité du compte année par année. Elle cesse en 2025, et la seule "
                      "écriture de 2026 est celle qui le solde en perte."),
            ),
            Tableau(
                entetes=["Date", "Référence", "Sens", "Montant XAF", "Opérateur", "Libellé"],
                lignes=[[r.TRN_DT, r.TRN_REF_NO, r.DRCR_IND, float(r.LCY_AMOUNT), r.USER_ID,
                         str(r.DESCRIPTION or "")[:60]]
                        for _, r in d.nlargest(8, "LCY_AMOUNT").iterrows()],
                note="Les huit plus gros mouvements de l'histoire du compte.",
            ),
        ],
        recommandation=(
            f"1. Obtenir le dossier justifiant la perte opérationnelle de {xaf(montant_ecriture)} "
            "passée le 31 juillet 2026 : quelles créances la composent, sur quels contrats, et "
            "à partir de quelle date étaient-elles compromises ?\n"
            "2. En déduire l'exercice de RATTACHEMENT de la perte. Si elle était acquise avant "
            "le 31 décembre 2025 — ce que le libellé « mai 2022 - juin 2025 » suggère — les "
            "états de cet exercice et des précédents sont surévalués à l'actif, et la question "
            "d'une correction d'erreur se pose.\n"
            "3. Faire expliquer pourquoi l'écriture d'apurement des courus de la migration "
            f"(contrôle 5.3) a porté sur 511800100 et pas sur {CPT_COURUS_MANUELS}, alors que "
            "les deux comptes portaient des intérêts courus sur le même portefeuille.\n"
            "4. Faire justifier l'existence même d'un second circuit de courus servi à la "
            f"main : {nb(len(periode))} écritures manuelles sur la période, c'est un dispositif "
            "permanent, non une exception.\n"
            "5. Rapprocher ce constat du contrôle 12.6 : l'absence totale de dépréciation sur "
            "le portefeuille et une perte de cette taille passée en une fois ne peuvent pas "
            "coexister sans explication."
        ),
    )
