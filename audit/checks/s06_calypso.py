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
    """Un compte de liaison est un compte de passage : il doit revenir à zéro."""
    gl = ctx.grand_livre
    cfg = ctx.config
    lignes, total_fin, total_periode = [], 0.0, 0.0
    for compte in CPT_LIAISON:
        sous = gl[gl.AC_NO == compte]
        if sous.empty:
            continue
        premier = sous.TRN_DT.min()
        solde = float(sous.SIGNE.sum())
        solde_periode = float(sous[sous.TRN_DT <= cfg.fin].SIGNE.sum())
        total_fin += solde
        total_periode += solde_periode
        lignes.append([compte, sous.AC_GL_DESC.iloc[0][:38], premier, len(sous), solde_periode, solde])
    if not lignes:
        return Constat(code="6.4", titre="Comptes de liaison Calypso", gravite=Gravite.CONFORME,
                       constat="Aucun compte de liaison dans le périmètre.")
    # Trajectoire trimestrielle du compte le plus chargé
    principal = max(lignes, key=lambda l: abs(l[5]))[0]
    serie = gl[gl.AC_NO == principal].sort_values(["TRN_DT", "STMT_DT"]).set_index("TRN_DT_d").SIGNE.cumsum()
    traj = serie.resample("QE").last().ffill()
    gravite = Gravite.CRITIQUE if abs(total_periode) > cfg.seuil_significatif * 10 else Gravite.ELEVEE
    # Durée écoulée entre l'ouverture des comptes et la clôture, exprimée en mois entiers :
    # écrire « quinze mois » en dur reviendrait à décrire une extraction et non la période.
    ouverture = min(l[2] for l in lignes)
    mois = ((pd.Timestamp(cfg.fin).year - pd.Timestamp(ouverture).year) * 12
            + pd.Timestamp(cfg.fin).month - pd.Timestamp(ouverture).month)
    return Constat(
        code="6.4",
        titre="Comptes de liaison Calypso non apurés, en dérive continue",
        gravite=gravite,
        constat=(
            "Les comptes de liaison ouverts pour l'interface Calypso ont leur première écriture au "
            "jour de la bascule : leur solde d'ouverture est donc nul et le cumul des mouvements "
            "constitue leur solde exact.\n"
            "Or un compte de liaison est, par construction, un COMPTE DE PASSAGE : il est "
            "mouvementé dans un sens à l'initiation de l'opération et dans l'autre à son "
            "dénouement, et doit revenir à zéro. Un solde qui ne fait que croître établit que le "
            "dénouement ne suit pas l'initiation.\n"
            "Le solde cumulé atteint à la fin de la période d'audit un montant considérable, sans "
            f"qu'aucun retour à zéro ne soit constaté depuis l'ouverture de ces comptes, soit "
            f"{mois} mois."
        ),
        chiffres=[
            ("SOLDE CUMULÉ À LA FIN DE LA PÉRIODE D'AUDIT", xaf(total_periode)),
            ("Solde à la fin de l'extraction", xaf(total_fin)),
        ],
        tableaux=[
            Tableau(["Compte", "Libellé", "1re écriture", "Lignes", "Solde fin période", "Solde fin extraction"], lignes),
            Tableau(["Fin de trimestre", f"Solde cumulé {principal}"],
                    [[d.strftime("%d/%m/%Y"), float(v)] for d, v in traj.items()],
                    note=f"Trajectoire du compte le plus chargé ({principal}).", max_lignes=20),
        ],
        recommandation=(
            "Vérifier si ce solde figure tel quel au bilan à la date d'arrêté. Obtenir l'état de "
            "rapprochement de ces comptes et sa périodicité. Déterminer s'il s'agit d'opérations "
            "non dénouées, d'un paramétrage d'interface asymétrique — une jambe déversée, l'autre "
            "non — ou d'un décalage de dates de valeur."
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
    """L'interface doit être idempotente : un mouvement Calypso ne doit être déversé qu'une fois."""
    doublons = ctx.mouvements_dupliques
    if doublons.empty:
        return Constat(
            code="6.7", titre="Idempotence de l'interface Calypso", gravite=Gravite.CONFORME,
            constat="Aucun mouvement Calypso n'apparaît plusieurs fois dans le grand livre.",
        )
    # Les doublons débordent la période d'audit : on distingue ce qui la concerne de ce qui
    # relève des événements postérieurs, faute de quoi le chiffre annoncé serait dominé par
    # des mois hors périmètre.
    dans_periode = doublons[(doublons.date >= ctx.config.debut) & (doublons.date <= ctx.config.fin)]
    hors_periode = doublons[doublons.date > ctx.config.fin]
    par_compte = (doublons.groupby(["compte", "libelle"])
                  .agg(mouvements=("montant", "size"), impact=("impact", "sum"))
                  .sort_values("impact", key=abs, ascending=False))
    par_mois = doublons.assign(mois=doublons.date.str[:7]).groupby("mois").agg(
        mouvements=("montant", "size"), montant=("montant", "sum"))
    materiels = par_compte[par_compte.impact.abs() > ctx.config.seuil_significatif]
    return Constat(
        code="6.7",
        titre="L'interface Calypso déverse certains mouvements en double dans le grand livre",
        gravite=Gravite.CRITIQUE,
        constat=(
            "Chaque mouvement Calypso porte un identifiant de transfert unique. Or des mouvements "
            "apparaissent DEUX FOIS dans le grand livre, sous deux références Flexcube "
            "différentes, le même jour, pour le même compte, le même sens et le même montant. "
            "L'interface n'est donc pas idempotente : elle peut rejouer une opération déjà "
            "déversée sans la détecter.\n"
            "Ce défaut n'est pas théorique : il fausse directement le solde des comptes touchés. "
            "Le compte de règlement de la banque centrale et le compte de portefeuille figurent "
            "parmi eux, ce qui signifie que le nostro et la valeur du portefeuille présentés au "
            "bilan sont affectés. Le phénomène se produit sur toute la période et n'est corrigé "
            "par aucune écriture d'annulation.\n"
            "PÉRIMÈTRE. Le défaut est apparu pendant la période d'audit et se poursuit au-delà. "
            "Les deux volets sont chiffrés séparément : le premier affecte les comptes arrêtés au "
            "30/06/2026, le second relève des événements postérieurs à la clôture et signale que "
            "l'anomalie n'est toujours pas corrigée.\n"
            "Il constitue par ailleurs une CAUSE RACINE d'autres constats du présent rapport, au "
            "premier rang desquels la dérive des comptes de liaison (contrôle 6.4) et le solde "
            "anormal du compte d'emprunt (contrôle 9.4)."
        ),
        chiffres=[
            ("Mouvements déversés en double — PÉRIODE D'AUDIT", str(len(dans_periode))),
            ("Montant dupliqué sur la période d'audit",
             xaf(float(dans_periode.montant.sum()))),
            ("Mouvements déversés en double après la clôture", str(len(hors_periode))),
            ("Montant dupliqué après la clôture", xaf(float(hors_periode.montant.sum()))),
            ("Total sur l'extraction", f"{len(doublons)} mouvements, "
                                       f"{xaf(float(doublons.montant.sum()))}"),
            ("Période couverte", f"{doublons.date.min()} → {doublons.date.max()}"),
            ("Comptes touchés", str(doublons.compte.nunique())),
            ("Dont comptes à impact significatif", str(len(materiels))),
        ],
        tableaux=[
            Tableau(["Compte", "Libellé", "Mouvements", "Impact sur le solde XAF"],
                    [[i[0], i[1][:38], int(r.mouvements), float(r.impact)]
                     for i, r in par_compte.iterrows()],
                    max_lignes=18,
                    note=("Impact = montant dont le solde du compte est faussé par les doublons, "
                          "sur la totalité de l'extraction. Pour un arrêté au 30/06/2026, seule "
                          "la fraction antérieure à cette date est à retenir.")),
            Tableau(["Mois", "Mouvements", "Montant dupliqué XAF"],
                    [[i, int(r.mouvements), float(r.montant)] for i, r in par_mois.iterrows()],
                    max_lignes=18),
            Tableau(["Deal", "Mouvement", "Date", "Compte", "Sens", "Montant XAF"],
                    [[r.deal, r.mouvement, r.date, r.compte, r.sens, float(r.montant)]
                     for _, r in doublons.sort_values("montant", ascending=False).head(12).iterrows()],
                    note="Les douze doublons les plus importants, toutes périodes confondues."),
        ],
        recommandation=(
            "Faire corriger l'interface pour qu'elle rejette tout mouvement déjà déversé, en "
            "s'appuyant sur l'identifiant de transfert. Quantifier l'incidence cumulée sur les "
            "soldes à chaque date d'arrêté et passer les écritures de correction. Mettre en place "
            "un contrôle de rapprochement quotidien entre le nombre de mouvements émis par "
            "Calypso et le nombre d'écritures reçues dans le grand livre."
        ),
    )
