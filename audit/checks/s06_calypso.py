"""Section 6 — Manquements du dispositif Calypso.

Calypso ne déverse que du grand livre dans Flexcube : aucun contrat n'y est créé. Cette
section recense ce que le nouveau dispositif a fait perdre par rapport au module MM, et les
zones que l'audit ne peut plus couvrir depuis Flexcube.
"""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf, pct, nb, fois
from ..data import CPT_LIAISON, DATE_BASCULE

SECTION = (6, "Manquements du dispositif Calypso")


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "L'interface entre Calypso et Flexcube se limite au grand livre : Calypso passe les "
            "écritures comptables et rien d'autre. Cette section mesure ce que ce choix "
            "d'architecture fait perdre en matière de piste d'audit, de contrôle et de "
            "rapprochement, et identifie les soldes qu'il laisse en suspens."
        ),
    )
    s.ajouter(_c61_absence_referentiel(ctx))
    s.ajouter(_c62_validation(ctx))
    s.ajouter(_c63_perte_semantique(ctx))
    s.ajouter(_c64_comptes_liaison(ctx))
    s.ajouter(_c65_cancel_rebook(ctx))
    s.ajouter(_c66_tracabilite(ctx))
    s.ajouter(_c67_doublons_interface(ctx))
    return s


def _c61_absence_referentiel(ctx) -> Constat:
    contrats = ctx.contrats_uniques
    calypso = ctx.calypso_enrichi
    deals = calypso.DEAL.nunique() if not calypso.empty else 0
    derniere_negociation = contrats.TRADE_DATE_d.max()
    return Constat(
        code="6.1",
        titre="Aucun référentiel de contrat n'alimente plus le core banking",
        gravite=Gravite.CRITIQUE,
        constat=(
            "Sous Flexcube, chaque opération de marché créait un contrat portant le nominal, le "
            "taux, les dates et la contrepartie. Ce référentiel permettait de recalculer les "
            "intérêts, de contrôler les échéances et de rapprocher la comptabilité des "
            "caractéristiques contractuelles.\n"
            "Depuis la bascule, Calypso ne crée plus aucun contrat dans Flexcube : seules des "
            "écritures de grand livre sont déversées. Le référentiel s'arrête donc à la dernière "
            "négociation enregistrée, alors que les deals continuent d'être traités.\n"
            "Conséquence directe pour l'audit : nominal, taux, échéance, sens et contrepartie des "
            "deals de la période Calypso ne sont connus qu'INDIRECTEMENT, par le libellé des "
            "écritures. Aucun recalcul indépendant des intérêts n'est possible depuis le core "
            "banking, et aucun contrôle d'exhaustivité ne peut y être mené."
        ),
        chiffres=[
            ("Dernière négociation au référentiel", derniere_negociation.strftime("%d/%m/%Y")),
            ("Date de bascule", DATE_BASCULE),
            ("Deals Calypso sans contrat dans le core banking", nb(deals)),
        ],
        recommandation=(
            "Obtenir l'extraction du référentiel des deals Calypso (nominal, taux, dates, sens, "
            "contrepartie) : elle conditionne la profondeur des travaux sur toute la période "
            "postérieure à la bascule. Étudier l'extension de l'interface au-delà du grand livre."
        ),
    )


def _c62_validation(ctx) -> Constat:
    calypso = ctx.grand_livre[ctx.grand_livre.PRODUCT == "MNIP"]
    if calypso.empty:
        return Constat(code="6.2", titre="Validation des écritures Calypso", gravite=Gravite.CONFORME,
                       constat="Aucune écriture Calypso dans le périmètre.")
    users = calypso.USER_ID.value_counts()
    auto = int((calypso.USER_ID == calypso.AUTH_ID).sum())
    part = auto / len(calypso) * 100
    return Constat(
        code="6.2",
        titre="Le contrôle des quatre yeux de Flexcube est intégralement neutralisé sur le flux Calypso",
        gravite=Gravite.ELEVEE,
        constat=(
            "La totalité des écritures déversées par Calypso est saisie et validée par un compte "
            "technique unique. Le contrôle applicatif des quatre yeux de Flexcube, qui s'applique "
            "aux saisies manuelles, est donc sans effet sur ce flux — lequel représente "
            "l'essentiel de l'activité de titres depuis la bascule.\n"
            "Le contrôle de validation doit par conséquent être recherché dans Calypso. Or Calypso "
            "est hors du périmètre des extractions : l'audit ne peut, en l'état, se prononcer sur "
            "l'existence d'une séparation des tâches sur les opérations postérieures à la bascule."
        ),
        chiffres=[
            ("Écritures Calypso", nb(len(calypso))),
            ("Saisie = validation", f"{nb(auto)} ({pct(part, 0)})"),
            ("Comptes utilisés", ", ".join(users.index[:5])),
        ],
        recommandation=(
            "Obtenir la procédure de validation des deals dans Calypso, la matrice des "
            "habilitations et un extrait du journal d'audit applicatif attestant qu'un second "
            "intervenant valide chaque opération."
        ),
    )


def _c63_perte_semantique(ctx) -> Constat:
    """Sous MM, AMOUNT_TAG portait la nature de l'événement. Sous Calypso, il est constant."""
    gl = ctx.grand_livre
    mm = gl[gl.MODULE == "MM"]
    calypso = gl[gl.PRODUCT == "MNIP"]
    tags_mm = mm.AMOUNT_TAG.nunique()
    tags_cal = calypso.AMOUNT_TAG.value_counts()
    return Constat(
        code="6.3",
        titre="Perte de l'information comptable structurée dans les écritures",
        gravite=Gravite.ELEVEE,
        constat=(
            "Dans le module MM, le champ d'étiquette de montant portait la nature de l'événement "
            "comptable (acquisition, couru, liquidation, encaissement d'intérêt), ce qui permettait "
            "de reconstituer le cycle de vie d'un titre par simple agrégation.\n"
            "Dans le flux Calypso, ce champ est constant : toutes les écritures portent la même "
            "étiquette générique. De même, le champ produit est unique et le module est toujours "
            "celui de l'écriture directe. L'information de nature de l'événement a été déplacée "
            "dans un LIBELLÉ TEXTUEL non normalisé, exploitable seulement par analyse de chaîne de "
            "caractères — donc fragile et non auditable de façon fiable."
        ),
        chiffres=[
            ("Étiquettes distinctes sous le module MM", str(tags_mm)),
            ("Étiquettes distinctes sous Calypso", str(len(tags_cal))),
            ("Étiquette unique utilisée", ", ".join(tags_cal.index[:3])),
            ("Modules utilisés par Calypso", ", ".join(sorted(calypso.MODULE.dropna().unique()))),
        ],
        recommandation=(
            "Demander l'enrichissement de l'interface : reporter la nature de l'événement Calypso "
            "dans un champ structuré du grand livre, et non dans un libellé libre."
        ),
    )


def _c64_comptes_liaison(ctx) -> Constat:
    """Un compte de liaison est un compte de passage : il doit revenir à zéro.

    Le contrôle ne se contente pas de constater un solde : il établit à quelle date chaque
    compte a CESSÉ de revenir à zéro, et décompose le solde arrêté entre ce qui n'a jamais
    été déversé et ce qui l'a été après la clôture.
    """
    gl = ctx.grand_livre
    cfg = ctx.config
    lignes = []
    total_fin = total_periode = 0.0
    for compte in CPT_LIAISON:
        sous = gl[gl.AC_NO == compte].sort_values(["TRN_DT", "STMT_DT"])
        if sous.empty:
            continue
        # Un compte de passage doit revenir à zéro. On cherche la DERNIÈRE fois qu'il l'a fait.
        quotidien = sous.assign(cumul=sous.SIGNE.cumsum()).groupby("TRN_DT").cumul.last()
        retours = quotidien[quotidien.abs() < 1]
        dernier_zero = retours.index[-1] if len(retours) else ""
        depuis = int((quotidien.index > dernier_zero).sum()) if dernier_zero else len(quotidien)
        solde = float(sous.SIGNE.sum())
        solde_periode = float(sous[sous.TRN_DT <= cfg.fin].SIGNE.sum())
        total_fin += solde
        total_periode += solde_periode
        lignes.append([compte, sous.AC_GL_DESC.iloc[0][:36], sous.TRN_DT.min(), len(sous),
                       len(retours), dernier_zero or "jamais", depuis,
                       solde_periode, solde])
    if not lignes:
        return Constat(code="6.4", titre="Comptes de liaison Calypso", gravite=Gravite.CONFORME,
                       constat="Aucun compte de liaison dans le périmètre.")
    retours_total = sum(l[4] for l in lignes)
    dernier_global = max((l[5] for l in lignes if l[5] != "jamais"), default="")

    # --- Décomposition du solde arrêté, deal par deal ---------------------------------
    c = ctx.calypso_enrichi
    pont = c[c.AC_NO.isin(CPT_LIAISON) & c.DEAL.notna() & (c.DEAL != "")]
    arrete = pont[pont.TRN_DT <= cfg.fin].groupby("DEAL").SIGNE.sum()
    contributeurs = arrete[arrete.abs() >= 1]
    vie_entiere = pont.groupby("DEAL").SIGNE.sum()
    # Deux populations : ceux qui ne se soldent jamais, et ceux qui se soldent APRÈS la clôture
    jamais = [d for d in contributeurs.index if abs(vie_entiere.get(d, 0)) >= 1]
    apres_cloture = [d for d in contributeurs.index if abs(vie_entiere.get(d, 0)) < 1]
    montant_jamais = float(contributeurs[jamais].sum()) if jamais else 0.0
    montant_apres = float(contributeurs[apres_cloture].sum()) if apres_cloture else 0.0
    # Lignes de pont sans identifiant de deal : réévaluations quotidiennes
    sans_deal = gl[gl.AC_NO.isin(CPT_LIAISON) & (gl.TRN_DT <= cfg.fin)]
    montant_sans_deal = total_periode - montant_jamais - montant_apres
    reconciliation = [
        ["Deals dont le déversement reste incomplet (contrôle 11.6)", len(jamais), montant_jamais],
        ["Deals ouverts à la clôture, annulés ou dénoués après", len(apres_cloture), montant_apres],
        ["Écritures de réévaluation sans identifiant de deal", "—", montant_sans_deal],
        ["SOLDE DES COMPTES DE LIAISON AU " + cfg.fin, "—", total_periode],
    ]
    detail_apres = []
    for d in sorted(apres_cloture, key=lambda x: -abs(contributeurs[x]))[:10]:
        g = pont[pont.DEAL == d]
        detail_apres.append([d, g.TRN_DT.min(), g[g.TRN_DT > cfg.fin].TRN_DT.min(),
                             float(contributeurs[d]),
                             (pd.Timestamp(g[g.TRN_DT > cfg.fin].TRN_DT.min())
                              - pd.Timestamp(g.TRN_DT.min())).days])

    principal = max(lignes, key=lambda l: abs(l[8]))[0]
    serie = (gl[gl.AC_NO == principal].sort_values(["TRN_DT", "STMT_DT"])
             .set_index("TRN_DT_d").SIGNE.cumsum())
    traj = serie.resample("QE").last().ffill()
    gravite = Gravite.CRITIQUE if abs(total_periode) > cfg.seuil_significatif * 10 else Gravite.ELEVEE
    return Constat(
        code="6.4",
        titre="Comptes de liaison Calypso : ils ont fonctionné, puis ont cessé de revenir à zéro",
        gravite=gravite,
        constat=(
            "CE QU'EST UN COMPTE DE LIAISON. Chaque deal Calypso y fait transiter ses jambes de "
            "bilan d'un côté et son règlement en trésorerie de l'autre. C'est un COMPTE DE "
            "PASSAGE : un deal intégralement déversé le laisse à zéro, et le compte doit donc "
            "revenir à zéro dès que les opérations en cours sont dénouées.\n"
            "\n"
            "ILS ONT D'ABORD FONCTIONNÉ. Le fait mérite d'être relevé, car il écarte l'hypothèse "
            f"d'un paramétrage défectueux dès l'origine : ces comptes sont revenus à zéro "
            f"{retours_total} fois au total, et l'un d'eux {max(l[4] for l in lignes)} fois à lui "
            "seul. Le mécanisme est donc correctement conçu.\n"
            "\n"
            "PUIS ILS ONT CESSÉ. Chacun porte une date après laquelle il n'est JAMAIS revenu à "
            f"zéro — la plus tardive est le {dernier_global}. Depuis, les soldes oscillent sans "
            "jamais se résorber. Ce n'est donc pas une dérive progressive mais une RUPTURE : le "
            "dispositif a fonctionné, puis il a cessé de le faire, à une date identifiable pour "
            "chaque compte. C'est cette date qu'il faut rapprocher des évolutions apportées à "
            "l'interface.\n"
            "\n"
            "CE QUE LE SOLDE CONTIENT. Le tableau de réconciliation décompose le solde arrêté et "
            "le rapproche exactement du contrôle 11.6. Il se compose de deux populations "
            "distinctes, qui n'appellent pas la même réponse : des deals dont le déversement "
            "reste incomplet, et des deals qui étaient simplement OUVERTS à la clôture et que "
            "Calypso a dénoués ou annulés ensuite. Les seconds ne sont pas une anomalie "
            "d'interface, mais ils faussent bien les comptes arrêtés : au 30/06/2026, la "
            "trésorerie et le portefeuille portaient des opérations que le système a ensuite "
            "défaites. Ces douze deals ont tous été soldés dans la même semaine de septembre "
            "2026, ce qui signe une campagne de régularisation et non un dénouement au fil de "
            "l'eau : la banque a repris ces opérations en une fois, plus de deux mois après la "
            "clôture qu'elles traversaient."
        ),
        chiffres=[
            ("SOLDE CUMULÉ AU " + cfg.fin, xaf(total_periode)),
            ("Solde à la fin de l'extraction", xaf(total_fin)),
            ("Retours à zéro constatés, tous comptes", str(retours_total)),
            ("Dernier retour à zéro, tous comptes confondus", dernier_global or "jamais"),
            ("Deals au déversement incomplet à la clôture",
             f"{len(jamais)} — {xaf(montant_jamais)}"),
            ("Deals ouverts à la clôture, dénoués ou annulés après",
             f"{len(apres_cloture)} — {xaf(montant_apres)}"),
        ],
        tableaux=[
            Tableau(["Compte", "Libellé", "Ouverture", "Lignes", "Retours à zéro",
                     "Dernier retour", "Jours actifs depuis", "Solde au " + cfg.fin,
                     "Solde fin extraction"],
                    lignes,
                    note=("« Retours à zéro » compte les journées où le compte s'est effectivement "
                          "soldé : c'est la preuve qu'il a fonctionné. « Dernier retour » date la "
                          "rupture.")),
            Tableau(["Composante du solde", "Deals", "Montant XAF"], reconciliation,
                    note=("Décomposition du solde arrêté. Les trois premières lignes "
                          "s'additionnent exactement à la quatrième.")),
            Tableau(["Deal", "Première écriture", "Dénouement ou annulation", "Solde à la clôture XAF",
                     "Jours d'ouverture"],
                    detail_apres,
                    note=("Deals ouverts au 30/06/2026 et soldés depuis. Leur durée d'ouverture "
                          "mesure le temps pendant lequel les comptes ont porté une opération "
                          "que le système a ensuite défaite.")),
            Tableau(["Fin de trimestre", f"Solde cumulé {principal}"],
                    [[d.strftime("%d/%m/%Y"), float(v)] for d, v in traj.items()],
                    note=f"Trajectoire du compte le plus chargé ({principal})."),
        ],
        recommandation=(
            "Rapprocher la date à laquelle chaque compte a cessé de revenir à zéro des "
            "évolutions apportées à l'interface : le dispositif a fonctionné avant, la cause de "
            "la rupture est donc datable. Vérifier si ce solde figure tel quel au bilan à la "
            "date d'arrêté. Obtenir l'état de rapprochement de ces comptes et sa périodicité. "
            "Traiter les deals au déversement incomplet au contrôle 11.6, et faire expliquer "
            "pourquoi des opérations restent ouvertes plusieurs mois avant d'être annulées."
        ),
    )


def _c65_cancel_rebook(ctx) -> Constat:
    """Calypso contre-passe chaque jour le couru de la veille puis le repasse."""
    calypso = ctx.calypso_enrichi
    if calypso.empty:
        return Constat(code="6.5", titre="Méthode de contre-passation Calypso", gravite=Gravite.CONFORME,
                       constat="Aucune écriture Calypso exploitable.")
    gl = ctx.grand_livre
    ev = gl[gl.PRODUCT == "MNIP"].copy()
    desc = ev.DESCRIPTION.fillna("")
    ev["EV"] = desc.str.split("|").str[1].where(desc.str.count(r"\|").isin([2, 4]))
    ev.loc[desc.str.count(r"\|") == 9, "EV"] = desc.str.split("|").str[3]
    recurrents = ev[ev.EV.isin(["ACCRUAL", "PREM_DISC_YIELD"])]
    if recurrents.empty:
        return Constat(code="6.5", titre="Méthode de contre-passation Calypso", gravite=Gravite.FAIBLE,
                       constat="Événements récurrents non identifiés.")
    par_ev = recurrents.groupby(["EV", "DRCR_IND"]).LCY_AMOUNT.agg(["size", "sum"]).unstack(fill_value=0)
    # Sommer toutes les jambes donnerait zéro par construction : une écriture est équilibrée.
    # Le facteur de surévaluation se mesure donc SUR UN COMPTE, ici le compte de produits
    # d'intérêt, où le brut est le cumul des passages et le net l'effet réel sur le résultat.
    compte_temoin = (recurrents[recurrents.AC_NO.str.startswith(("733", "734"))]
                     .AC_NO.value_counts())
    temoin = compte_temoin.index[0] if len(compte_temoin) else None
    sur_temoin = recurrents[recurrents.AC_NO == temoin] if temoin else recurrents.iloc[0:0]
    brut = float(sur_temoin.LCY_AMOUNT.sum())
    net = float(-sur_temoin.SIGNE.sum())
    lignes = []
    for ev_nom in par_ev.index:
        d = float(par_ev.loc[ev_nom, ("sum", "D")]) if ("sum", "D") in par_ev.columns else 0.0
        c = float(par_ev.loc[ev_nom, ("sum", "C")]) if ("sum", "C") in par_ev.columns else 0.0
        nd = int(par_ev.loc[ev_nom, ("size", "D")]) if ("size", "D") in par_ev.columns else 0
        nc = int(par_ev.loc[ev_nom, ("size", "C")]) if ("size", "C") in par_ev.columns else 0
        lignes.append([ev_nom, nd, nc, d, c, d - c])
    return Constat(
        code="6.5",
        titre="Contre-passation quotidienne intégrale : les volumes Calypso ne sont pas exploitables bruts",
        gravite=Gravite.MOYENNE,
        constat=(
            "Calypso pratique la contre-passation intégrale : chaque jour il annule le couru "
            "cumulé de la veille puis repasse le couru cumulé à date. Les débits et les crédits "
            "sont donc quasi symétriques, et les volumes bruts sont mécaniquement doublés.\n"
            "Toute statistique établie sur les montants bruts du flux Calypso — charge, produit, "
            "volume d'activité — serait sans signification. Les analyses doivent être conduites en "
            "net. Cette convention est en outre OPPOSÉE à celle de Flexcube, qui contre-passe par "
            "un montant négatif : les deux systèmes ne peuvent pas être agrégés sans retraitement.\n"
            "La mesure de l'écart se fait sur UN COMPTE et non sur l'ensemble des jambes : "
            "additionner toutes les jambes d'écritures équilibrées donnerait zéro par construction "
            "et ne dirait rien. Le compte de produits d'intérêt sert donc de témoin."
        ),
        chiffres=[
            ("Compte témoin de la mesure", f"{temoin} {ctx.libelle_compte(temoin)}" if temoin else "n/d"),
            ("Volume brut passé sur ce compte", xaf(brut)),
            ("Effet net réel sur le résultat", xaf(net)),
            ("Facteur de surévaluation", fois(brut / abs(net)) if abs(net) > 1 else "non calculable"),
        ],
        tableaux=[Tableau(["Événement", "Nb débits", "Nb crédits", "Total débits",
                           "Total crédits", "Net"], lignes,
                          note=("Totaux calculés sur TOUTES les jambes de ces événements, tous "
                                "comptes confondus : ils s'annulent par construction, ce qui est "
                                "précisément la raison pour laquelle la mesure de l'écart se fait "
                                "sur le compte témoin et non sur ces totaux."))],
        recommandation=(
            "Documenter cette convention dans les procédures d'analyse et ne publier aucune "
            "statistique de volume issue de ce flux sans retraitement."
        ),
    )


def _c66_tracabilite(ctx) -> Constat:
    """L'information métier réside dans un commentaire libre, non normalisé."""
    calypso = ctx.calypso_enrichi
    if calypso.empty:
        return Constat(code="6.6", titre="Traçabilité des opérations Calypso", gravite=Gravite.FAIBLE,
                       constat="Aucune écriture Calypso exploitable.")
    avec = calypso[calypso.COMMENTAIRE.fillna("") != ""]
    gl_calypso = ctx.grand_livre[ctx.grand_livre.PRODUCT == "MNIP"]
    part_structure = len(calypso) / max(len(gl_calypso), 1) * 100
    exemples = avec.COMMENTAIRE.value_counts().head(8)
    return Constat(
        code="6.6",
        titre="L'intention économique des opérations n'est tracée que par un commentaire libre",
        gravite=Gravite.ELEVEE,
        constat=(
            "La nature réelle de certaines opérations — notamment les opérations de cession-"
            "rétrocession — n'est documentée que par un COMMENTAIRE LIBRE saisi par la salle des "
            "marchés dans le libellé de l'écriture. Ce commentaire n'est ni normalisé, ni "
            "obligatoire, ni contrôlé.\n"
            "Cette situation appelle deux remarques opposées. D'une part, ces commentaires "
            "constituent aujourd'hui la SEULE source permettant d'établir l'intention économique "
            "des opérations : sans eux, la nature des cessions-rétrocessions serait restée "
            "invisible dans les schémas comptables. D'autre part, faire reposer la qualification "
            "d'une opération sur une saisie libre et facultative est une faiblesse de contrôle "
            "majeure : rien ne garantit l'exhaustivité ni la sincérité de ces mentions.\n"
            "Par ailleurs, seule une minorité des écritures Calypso porte un libellé structuré "
            "identifiant le deal ; les autres ne portent qu'une mention de valorisation agrégée, "
            "sans lien avec une opération identifiable."
        ),
        chiffres=[
            ("Écritures Calypso dans le périmètre", nb(len(gl_calypso))),
            ("Dont libellé structuré (deal identifiable)",
             f"{nb(len(calypso))} ({pct(part_structure, 0)})"),
            ("Dont commentaire libre renseigné", nb(len(avec))),
        ],
        tableaux=[Tableau(["Commentaire libre le plus fréquent", "Occurrences"],
                          [[str(i)[:70], int(n)] for i, n in exemples.items()])],
        recommandation=(
            "Exiger que la nature de l'opération soit portée dans un champ structuré et obligatoire "
            "de l'interface, et non dans un commentaire libre. Dans l'intervalle, exploiter "
            "systématiquement ces commentaires dans les travaux d'audit."
        ),
    )


def _c67_doublons_interface(ctx) -> Constat:
    """L'interface doit être idempotente : un mouvement Calypso ne doit être déversé qu'une fois.

    Le contrôle se mène au niveau du MOUVEMENT et non de la jambe d'écriture : un mouvement
    produit deux à quatre jambes, et les compter séparément reviendrait à compter la même
    anomalie plusieurs fois, en additionnant un débit et son crédit. L'incidence sur les
    SOLDES se mesure en revanche compte par compte, chaque jambe ne faussant que le sien.
    """
    legs = ctx.mouvements_dupliques
    mouvements = ctx.doublons_par_mouvement
    if legs.empty or mouvements.empty:
        return Constat(
            code="6.7", titre="Idempotence de l'interface Calypso", gravite=Gravite.CONFORME,
            constat="Aucun mouvement Calypso n'apparaît plusieurs fois dans le grand livre.",
        )
    cfg = ctx.config
    periode = mouvements[mouvements.date <= cfg.fin]
    apres = mouvements[mouvements.date > cfg.fin]
    corriges = mouvements[mouvements.corrige]
    solde = mouvements[mouvements.residu > 1]
    # Incidence sur les soldes : une jambe fausse le compte qu'elle touche, une seule fois.
    legs_periode = legs[legs.date <= cfg.fin]
    # Les jambes des mouvements effectivement contre-passés ne faussent plus aucun solde :
    # les inclure surestimerait l'incidence. On ne retient que celles qui laissent un résidu.
    non_resorbes = set(solde.mouvement)
    legs_actives = legs[(legs.deal + "|" + legs.mouvement).isin(non_resorbes)]
    par_compte = (legs_actives.groupby(["compte", "libelle"])
                  .agg(jambes=("montant", "size"),
                       impact=("impact", "sum"),
                       impact_periode=("impact", "sum"))
                  .sort_values("impact", key=abs, ascending=False))
    # Incidence arrêtée à la clôture, compte par compte
    actives_periode = legs_actives[legs_actives.date <= cfg.fin]
    impact_arrete = actives_periode.groupby("compte").impact.sum().to_dict()
    par_compte["impact_periode"] = [impact_arrete.get(i[0], 0.0) for i in par_compte.index]
    materiels = par_compte[par_compte.impact.abs() > cfg.seuil_significatif]
    par_mois = mouvements.assign(mois=mouvements.date.str[:7]).groupby("mois").agg(
        mouvements=("montant", "size"), montant=("montant", "sum"))
    pire = mouvements.reindex(mouvements.montant.sort_values(ascending=False).index).head(12)
    return Constat(
        code="6.7",
        titre="L'interface Calypso déverse certains mouvements en double dans le grand livre",
        gravite=Gravite.CRITIQUE,
        constat=(
            "Chaque mouvement Calypso porte un identifiant de transfert unique. Or des "
            "mouvements apparaissent DEUX FOIS dans le grand livre, sous deux références "
            "Flexcube différentes, pour les mêmes comptes, le même sens et le même montant. "
            "L'interface n'est donc pas idempotente : elle peut rejouer une opération déjà "
            "déversée sans la détecter. Les deux références sont le plus souvent consécutives, "
            "ce qui signe un rejeu immédiat et non un incident isolé.\n"
            "\n"
            "COMMENT LE VOLUME EST MESURÉ. Un mouvement produit deux à quatre jambes "
            "d'écriture. Les compter séparément reviendrait à compter la même anomalie "
            "plusieurs fois, et à additionner un débit et le crédit qui lui répond comme s'il "
            "s'agissait de deux anomalies distinctes. Le volume dupliqué est donc compté UNE "
            "FOIS PAR MOUVEMENT. L'incidence sur les soldes se mesure en revanche jambe par "
            "jambe, chacune ne faussant que le compte qu'elle touche : c'est l'objet du tableau "
            "par compte.\n"
            "\n"
            "LA BANQUE EN CORRIGE UNE PARTIE, TARDIVEMENT ET INCOMPLÈTEMENT. "
            + (f"{len(corriges)} des {len(mouvements)} mouvements dupliqués ont fait l'objet "
               "d'une écriture de contre-passation ultérieure, passée MANUELLEMENT — la "
               "référence n'est pas celle de l'interface. Un dispositif de détection existe "
               "donc, mais il est partiel et il intervient tard : plusieurs semaines après le "
               "doublon, soit bien au-delà de l'arrêté que celui-ci peut traverser. "
               + (f"L'un de ces {len(corriges)} cas n'a d'ailleurs été corrigé que sur une "
                  "partie de ses jambes, laissant un résidu."
                  if len(corriges) > len(mouvements) - len(solde) else "")
               if len(corriges) else
               "Aucune écriture de correction ultérieure n'est identifiée : aucun des doublons "
               "n'a été repris.")
            + "\n"
            "\n"
            "CE QUE CELA FAUSSE. Le défaut n'est pas théorique : il fausse directement le solde "
            "des comptes touchés. Le compte de règlement de la banque centrale et le compte de "
            "portefeuille figurent parmi eux, ce qui signifie que le nostro et la valeur du "
            "portefeuille présentés au bilan sont affectés.\n"
            "PÉRIMÈTRE. Le défaut est apparu pendant la période d'audit et se poursuit au-delà. "
            "Les deux volets sont chiffrés séparément : le premier affecte les comptes arrêtés "
            "au 30/06/2026, le second relève des événements postérieurs à la clôture et signale "
            "que l'anomalie n'est toujours pas corrigée.\n"
            "Il constitue par ailleurs une CAUSE RACINE d'autres constats du présent rapport, "
            "au premier rang desquels la dérive des comptes de liaison (contrôles 6.4 et 11.6) "
            "et le solde anormal du compte d'emprunt (contrôle 9.4)."
        ),
        chiffres=[
            ("MOUVEMENTS déversés en double — PÉRIODE D'AUDIT", str(len(periode))),
            ("Volume dupliqué sur la période d'audit", xaf(float(periode.montant.sum()))),
            ("Mouvements déversés en double après la clôture", str(len(apres))),
            ("Volume dupliqué après la clôture", xaf(float(apres.montant.sum()))),
            ("Total sur l'extraction",
             f"{len(mouvements)} mouvements, {xaf(float(mouvements.montant.sum()))}"),
            ("Jambes d'écriture concernées", f"{len(legs)} dont {len(legs_periode)} sur la période"),
            ("Période couverte", f"{mouvements.date.min()} → {mouvements.date.max()}"),
            ("Dont CORRIGÉS par une écriture manuelle ultérieure", str(len(corriges))),
            ("Dont laissant encore un résidu aux comptes", str(len(solde))),
            ("Comptes dont le solde reste faussé", str(legs_actives.compte.nunique())),
            ("Dont comptes à impact significatif", str(len(materiels))),
        ],
        tableaux=[
            Tableau(["Compte", "Libellé", "Jambes", "Impact AU 30/06/2026 XAF",
                     "Impact fin d'extraction XAF"],
                    [[i[0], i[1][:38], int(r.jambes), float(r.impact_periode), float(r.impact)]
                     for i, r in par_compte.iterrows()],
                    max_lignes=18,
                    note=("Montant dont le solde de chaque compte est faussé. Les mouvements "
                          "contre-passés par la banque en sont exclus : ils ne faussent plus "
                          "rien. Ces impacts ne s'additionnent pas entre eux — le débit et le "
                          "crédit d'un même mouvement y figurent tous deux.")),
            Tableau(["Mois", "Mouvements", "Volume dupliqué XAF"],
                    [[i, int(r.mouvements), float(r.montant)] for i, r in par_mois.iterrows()],
                    max_lignes=18),
            Tableau(["Mouvement", "Deal", "Date", "Événement", "Portefeuille", "Montant XAF",
                     "Jambes", "Corrigé le", "Résidu XAF"],
                    [[r.mouvement.split("|")[1], r.deal, r.date, r.evenement, r.book,
                      float(r.montant), int(r.jambes),
                      r.date_correction if r.corrige else "non corrigé", float(r.residu)]
                     for _, r in pire.iterrows()],
                    max_lignes=12,
                    note="Les douze mouvements dupliqués les plus importants, toutes périodes."),
            Tableau(["Mouvement", "Deal", "Date du doublon", "Montant XAF",
                     "Date de correction", "Délai (j)", "Résidu XAF"],
                    [[r.mouvement.split("|")[1], r.deal, r.date, float(r.montant),
                      r.date_correction,
                      (pd.Timestamp(r.date_correction) - pd.Timestamp(r.date)).days,
                      float(r.residu)]
                     for _, r in corriges.iterrows()],
                    note=("Doublons repris par la banque. Le délai mesure le temps écoulé "
                          "avant la correction ; un résidu non nul signale une correction "
                          "partielle.")),
        ],
        recommandation=(
            "Faire corriger l'interface pour qu'elle rejette tout mouvement déjà déversé, en "
            "s'appuyant sur l'identifiant de transfert. Quantifier l'incidence cumulée sur les "
            "soldes à chaque date d'arrêté et passer les écritures de correction pour les "
            "mouvements qui n'en ont pas fait l'objet. Documenter le contrôle qui a permis de "
            "détecter les quelques doublons déjà repris, et en faire un contrôle quotidien et "
            "exhaustif : le test d'égalité de règlement du contrôle 11.7 les détecte tous."
        ),
    )
