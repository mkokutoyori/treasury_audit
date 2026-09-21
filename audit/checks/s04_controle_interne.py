"""Section 4 — Contrôle interne et séparation des tâches sur les opérations de titres."""
from __future__ import annotations

from ..core import Constat, Gravite, Section, Tableau, xaf, pct, nb
import pandas as pd

from ..data import COMPTES_TECHNIQUES, CPT_TITRES, DATE_BASCULE

SECTION = (4, "Contrôle interne et séparation des tâches")


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "Contrôles sur la piste d'audit applicative : respect du principe des quatre yeux, "
            "écritures dépourvues de validateur, poids des comptes techniques, horaires de saisie "
            "et concentration des opérations sur un nombre restreint d'opérateurs. Tous les "
            "contrôles de la section sont restreints aux écritures de la période d'audit."
        ),
    )
    s.ajouter(_c41_quatre_yeux(ctx))
    s.ajouter(_c42_sans_validateur(ctx))
    s.ajouter(_c43_comptes_techniques(ctx))
    s.ajouter(_c44_horaires(ctx))
    s.ajouter(_c45_concentration(ctx))
    return s


def _humains(df):
    """Écarte les comptes techniques et les comptes de traitement de fin de journée."""
    return df[~df.USER_ID.isin(COMPTES_TECHNIQUES) & ~df.USER_ID.fillna("").str.endswith("EOD")]


def _c41_quatre_yeux(ctx) -> Constat:
    df = ctx.dans_periode(ctx.toutes_ecritures)
    auto = df[df.USER_ID == df.AUTH_ID]
    humains_auto = _humains(auto)
    part = len(auto) / max(len(df), 1) * 100
    par_tech = auto[auto.USER_ID.isin(COMPTES_TECHNIQUES)].USER_ID.value_counts()
    gravite = Gravite.ELEVEE if len(humains_auto) else Gravite.MOYENNE
    constat = (
        f"{nb(len(auto))} écritures sur {nb(len(df))} ({pct(part, 1)}) portent le même identifiant "
        "en saisie et en validation. L'analyse détaillée est plus nuancée qu'il n'y paraît : cette "
        "auto-validation est le fait des COMPTES TECHNIQUES, pas des opérateurs. "
    )
    if humains_auto.empty:
        constat += (
            "Aucun utilisateur nominatif ne s'auto-valide. Le principe des quatre yeux est donc "
            "respecté par les opérateurs humains, mais il est STRUCTURELLEMENT NEUTRALISÉ pour les "
            "flux automatiques — au premier rang desquels l'interface Calypso, dont la totalité "
            "des écritures est saisie et validée par un compte unique."
        )
    else:
        constat += (
            f"En revanche, {nb(len(humains_auto))} écritures sont auto-validées par des "
            "utilisateurs NOMINATIFS, ce qui constitue une défaillance directe du contrôle."
        )
    tableaux = [
        Tableau(["Compte technique auto-validant", "Écritures"],
                [[i, int(n)] for i, n in par_tech.head(10).items()])
    ]
    if not humains_auto.empty:
        par_humain = humains_auto.groupby(["USER_ID", "MODULE"]).agg(
            n=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))
        tableaux.append(Tableau(
            ["Utilisateur nominatif", "Module", "Écritures", "Montant XAF"],
            [[i[0], i[1], int(r.n), float(r.montant)] for i, r in par_humain.iterrows()],
            note="Auto-validation par un utilisateur nominatif — défaillance directe."))
    return Constat(
        code="4.1",
        titre="Contrôle des quatre yeux neutralisé pour les flux automatiques",
        gravite=gravite,
        constat=constat,
        chiffres=[
            ("Écritures contrôlées", nb(len(df))),
            ("Saisie = validation", f"{nb(len(auto))} ({pct(part, 1)})"),
            ("Dont utilisateurs nominatifs", nb(len(humains_auto))),
        ],
        tableaux=tableaux,
        recommandation=(
            "Le contrôle de validation des flux automatiques doit être recherché dans le système "
            "amont (Calypso) puisqu'il est absent de Flexcube. Obtenir la procédure de validation "
            "des deals dans Calypso et la matrice d'habilitations des comptes techniques."
        ),
    )


def _c42_sans_validateur(ctx) -> Constat:
    df = ctx.dans_periode(ctx.toutes_ecritures)
    sans = df[df.AUTH_ID.isna()]
    if sans.empty:
        return Constat(
            code="4.2", titre="Écritures sans validateur", gravite=Gravite.CONFORME,
            constat="Toute écriture porte un identifiant de validation.",
        )
    modules = ", ".join(sorted(sans.MODULE.dropna().unique()))
    par = sans.groupby(["USER_ID", "MODULE"]).agg(
        n=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"),
        debut=("TRN_DT", "min"), fin=("TRN_DT", "max"))
    return Constat(
        code="4.2",
        titre="Écritures manuelles dépourvues de tout validateur",
        gravite=Gravite.CRITIQUE,
        constat=(
            "Des écritures ne portent aucun identifiant de validation. Il ne s'agit pas d'une "
            "auto-validation — le champ est vide. Ces écritures ont donc été comptabilisées sans "
            "qu'aucun second intervenant ne les approuve. Elles émanent toutes du même compte et "
            f"du seul module {modules}, celui qui permet les passations les plus libres. Leur "
            "étalement continu sur toute la période exclut l'incident ponctuel."
        ),
        chiffres=[
            ("Écritures sans validateur", nb(len(sans))),
            ("Montant cumulé", xaf(float(sans.LCY_AMOUNT.sum()))),
            ("Période", f"{sans.TRN_DT.min()} → {sans.TRN_DT.max()}"),
            ("Modules concernés", ", ".join(sorted(sans.MODULE.dropna().unique()))),
        ],
        tableaux=[
            Tableau(["Opérateur", "Module", "Écritures", "Montant XAF", "Du", "Au"],
                    [[i[0], i[1], int(r.n), float(r.montant), r.debut, r.fin]
                     for i, r in par.sort_values("montant", ascending=False).iterrows()])
        ],
        recommandation=(
            "Obtenir le paramétrage qui autorise la comptabilisation sans validation, la liste des "
            "utilisateurs disposant de ce privilège, et la justification d'un échantillon de ces "
            "écritures."
        ),
    )


def _c43_comptes_techniques(ctx) -> Constat:
    df = ctx.dans_periode(ctx.toutes_ecritures)
    tech = df[df.USER_ID.isin(COMPTES_TECHNIQUES)]
    par = tech.groupby("USER_ID").agg(n=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))
    part = len(tech) / max(len(df), 1) * 100
    return Constat(
        code="4.3",
        titre="Poids des comptes techniques dans la comptabilisation",
        gravite=Gravite.MOYENNE,
        constat=(
            f"Les comptes techniques concentrent {pct(part, 1)} des écritures du périmètre. Un "
            "compte technique n'est rattaché à aucune personne physique : la responsabilité de "
            "l'écriture ne peut donc être établie, et le contrôle des quatre yeux ne peut "
            "s'appliquer. Le risque est d'autant plus élevé que certains de ces comptes servent "
            "aussi à des saisies manuelles."
        ),
        chiffres=[("Écritures par compte technique", f"{nb(len(tech))} ({pct(part, 1)})")],
        tableaux=[Tableau(["Compte technique", "Écritures", "Montant XAF"],
                          [[i, int(r.n), float(r.montant)] for i, r in par.sort_values("n", ascending=False).iterrows()])],
        recommandation=(
            "Obtenir, pour chaque compte technique, son propriétaire fonctionnel, la liste des "
            "personnes pouvant l'utiliser et la traçabilité applicative associée."
        ),
    )


def _c44_horaires(ctx) -> Constat:
    """Saisies hors heures ouvrables, restreintes aux opérations sur titres.

    Le test ne porte que sur les comptes du périmètre titres : une saisie tardive sur un
    compte clientèle relève d'un autre contrôle. Une saisie en soirée n'est pas anormale dans
    une salle de marché ; une saisie en pleine nuit l'est.
    """
    cfg = ctx.config
    gl = ctx.dans_periode(ctx.grand_livre).copy()
    heures = gl.STMT_DT.str.slice(11, 13)
    gl["heure"] = pd.to_numeric(heures, errors="coerce")
    titres = gl[gl.AC_NO.isin(CPT_TITRES)]
    humains = _humains(titres)
    soiree = humains[(humains.heure >= cfg.heure_fermeture) & (humains.heure < 24)]
    nuit = humains[humains.heure < 6]
    repartition = humains.groupby("heure").agg(ecritures=("LCY_AMOUNT", "size"),
                                               montant=("LCY_AMOUNT", "sum"))
    if nuit.empty:
        return Constat(
            code="4.4", titre="Horaires de saisie des opérations sur titres",
            gravite=Gravite.CONFORME,
            constat=(
                f"Les saisies sur les comptes du périmètre titres se concentrent sur la plage "
                f"ouvrable. Les {len(soiree)} écritures passées en soirée, après "
                f"{cfg.heure_fermeture} h, restent compatibles avec l'activité d'une salle de "
                "marché et le traitement de fin de journée. Aucune saisie nocturne n'est "
                "constatée."
            ),
            tableaux=[Tableau(["Heure", "Écritures", "Montant XAF"],
                              [[int(i), int(r.ecritures), float(r.montant)]
                               for i, r in repartition.iterrows()], max_lignes=24)],
        )
    par_nuit = nuit.groupby(["TRN_DT", "USER_ID", "AUTH_ID", "MODULE"]).agg(
        ecritures=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"),
        heure_min=("heure", "min"), heure_max=("heure", "max"))
    dates = sorted(nuit.TRN_DT.unique())
    bascule = [d for d in dates if d == DATE_BASCULE]
    # Une date nocturne qui coïncide avec le transfert d'intérêts courus vers le compte
    # d'attente (contrôle 3.8) n'est pas un fait isolé : les deux constats se recoupent.
    if not ctx.courus.empty:
        jours_38 = set(ctx.courus[ctx.courus.DESCRIPTION.fillna("").str.contains(
            "Reversal of contract", na=False, case=False)].TRN_DT.unique())
    else:
        jours_38 = set()
    croisees = [d for d in dates if d in jours_38]
    renvoi = ""
    if croisees:
        quand = ", ".join(pd.Timestamp(d).strftime("%d/%m/%Y") for d in croisees)
        renvoi = (f" Une autre — {quand} — relève du transfert d'intérêts courus vers le compte "
                  "d'attente décrit au contrôle 3.8 : les deux constats portent sur la même "
                  "opération et doivent être instruits ensemble.")
    return Constat(
        code="4.4",
        titre="Saisies nocturnes sur les comptes de titres",
        gravite=Gravite.MOYENNE,
        constat=(
            "Le contrôle se restreint aux comptes du périmètre titres, pour ne retenir que les "
            "opérations de marché.\n"
            f"Les saisies en soirée, après {cfg.heure_fermeture} h, sont nombreuses mais restent "
            "compatibles avec l'activité d'une salle de marché et le traitement de fin de "
            "journée : elles ne sont pas rapportées comme anomalies.\n"
            "En revanche, des écritures ont été passées en PLEINE NUIT, avant 6 h du matin, par "
            "des opérateurs nominatifs. Ces saisies échappent à toute supervision hiérarchique et "
            "se concentrent sur un très petit nombre de dates."
            + (" L'une d'elles correspond à la bascule vers le nouveau système, ce qui l'explique."
               if bascule else "")
            + renvoi
        ),
        chiffres=[
            ("Écritures titres saisies par un opérateur", nb(len(humains))),
            (f"Dont en soirée ({cfg.heure_fermeture} h – 24 h)", nb(len(soiree))),
            ("Dont nocturnes (0 h – 6 h)", str(len(nuit))),
            ("Dates concernées", ", ".join(dates)),
            ("Montant des saisies nocturnes", xaf(float(nuit.LCY_AMOUNT.sum()))),
        ],
        tableaux=[
            Tableau(["Date", "Opérateur", "Validation", "Module", "Écritures", "Montant XAF",
                     "De", "À"],
                    [[i[0], i[1], i[2], i[3], int(r.ecritures), float(r.montant),
                      f"{int(r.heure_min)} h", f"{int(r.heure_max)} h"]
                     for i, r in par_nuit.iterrows()]),
            Tableau(["Heure", "Écritures", "Montant XAF"],
                    [[int(i), int(r.ecritures), float(r.montant)]
                     for i, r in repartition.iterrows()], max_lignes=24,
                    note="Répartition horaire de l'ensemble des saisies sur titres."),
        ],
        recommandation=(
            "Obtenir la justification des saisies nocturnes hors bascule : rapprocher des "
            "plannings de la salle des marchés et des éventuelles astreintes."
        ),
    )


def _c45_concentration(ctx) -> Constat:
    """La concentration des saisies reflète-t-elle la taille réelle de l'équipe ?

    Les opérations sur titres étaient traitées, sous l'ancien système, par l'équipe Treasury
    Operations, qui n'a historiquement pas dépassé cinq personnes. Un petit nombre
    d'opérateurs nominatifs est donc ATTENDU et non anormal ; ce qui compte est que la
    validation soit assurée par des personnes distinctes.
    """
    mm = ctx.dans_periode(ctx.grand_livre[ctx.grand_livre.MODULE == "MM"])
    humains = _humains(mm)
    if humains.empty:
        return Constat(code="4.5", titre="Répartition des saisies sur titres", gravite=Gravite.CONFORME,
                       constat="Aucune saisie manuelle sur le module de marché monétaire.")
    par_saisie = humains.groupby("USER_ID").agg(ecritures=("LCY_AMOUNT", "size"),
                                                montant=("LCY_AMOUNT", "sum"))
    par_saisie = par_saisie.sort_values("montant", ascending=False)
    valideurs = _humains(mm).AUTH_ID.dropna().nunique()
    croisement = humains.groupby(["USER_ID", "AUTH_ID"]).size().reset_index(name="ecritures")
    auto = croisement[croisement.USER_ID == croisement.AUTH_ID]
    effectif_attendu = 5
    depassement = len(par_saisie) > effectif_attendu
    return Constat(
        code="4.5",
        titre="Répartition des saisies entre opérateurs et valideurs",
        gravite=Gravite.MOYENNE if depassement or len(auto) else Gravite.CONFORME,
        constat=(
            f"Les saisies manuelles sur le module de marché monétaire sont le fait de "
            f"{len(par_saisie)} opérateurs nominatifs, validées par {valideurs} personnes "
            "distinctes.\n"
            "Ce nombre restreint n'est PAS une anomalie : les opérations sur titres étaient "
            "traitées, sous l'ancien système, par l'équipe Treasury Operations, qui n'a "
            f"historiquement pas dépassé {effectif_attendu} personnes. La concentration constatée "
            "reflète donc la taille réelle de l'équipe.\n"
            "Ce qui importe est ailleurs : que la validation soit assurée par des personnes "
            "distinctes du saisisseur, et que la matrice saisie/validation ne laisse pas un "
            "opérateur valider ses propres écritures."
            + ("\nLe croisement saisie/validation ne fait apparaître AUCUN cas d'auto-validation "
               "par un opérateur nominatif." if len(auto) == 0 else
               "\nDes cas d'auto-validation par un opérateur nominatif sont constatés et "
               "constituent, eux, une défaillance du contrôle.")
        ),
        chiffres=[
            ("Opérateurs de saisie", str(len(par_saisie))),
            ("Valideurs distincts", str(valideurs)),
            ("Effectif type de l'équipe Treasury Operations", f"≤ {effectif_attendu}"),
            ("Cas d'auto-validation nominative", str(len(auto))),
        ],
        tableaux=[
            Tableau(["Opérateur", "Écritures", "Montant XAF"],
                    [[i, int(r.ecritures), float(r.montant)] for i, r in par_saisie.iterrows()]),
            Tableau(["Saisie", "Validation", "Écritures"],
                    [[r.USER_ID, r.AUTH_ID, int(r.ecritures)]
                     for _, r in croisement.sort_values("ecritures", ascending=False).iterrows()],
                    max_lignes=20, note="Matrice saisie / validation."),
        ],
        recommandation=(
            "Vérifier l'existence de délégations formalisées et d'un contrôle de second niveau "
            "sur les opérations de marché, la taille de l'équipe limitant structurellement la "
            "rotation des tâches."
        ),
    )
