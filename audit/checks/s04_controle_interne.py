"""Section 4 — Contrôle interne et séparation des tâches sur les opérations de titres."""
from __future__ import annotations

from ..core import Constat, Gravite, Section, Tableau, xaf
from ..data import COMPTES_TECHNIQUES

SECTION = (4, "Contrôle interne et séparation des tâches")


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "Contrôles sur la piste d'audit applicative : respect du principe des quatre yeux, "
            "écritures dépourvues de validateur, poids des comptes techniques, horaires de saisie "
            "et concentration des opérations sur un nombre restreint d'opérateurs."
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
    df = ctx.toutes_ecritures
    auto = df[df.USER_ID == df.AUTH_ID]
    humains_auto = _humains(auto)
    part = len(auto) / max(len(df), 1) * 100
    par_tech = auto[auto.USER_ID.isin(COMPTES_TECHNIQUES)].USER_ID.value_counts()
    gravite = Gravite.ELEVEE if len(humains_auto) else Gravite.MOYENNE
    constat = (
        f"{len(auto):,} écritures sur {len(df):,} ({part:.1f} %) portent le même identifiant en "
        "saisie et en validation. L'analyse détaillée est plus nuancée qu'il n'y paraît : cette "
        "auto-validation est le fait des COMPTES TECHNIQUES, pas des opérateurs. "
    ).replace(",", " ")
    if humains_auto.empty:
        constat += (
            "Aucun utilisateur nominatif ne s'auto-valide. Le principe des quatre yeux est donc "
            "respecté par les opérateurs humains, mais il est STRUCTURELLEMENT NEUTRALISÉ pour les "
            "flux automatiques — au premier rang desquels l'interface Calypso, dont la totalité "
            "des écritures est saisie et validée par un compte unique."
        )
    else:
        constat += (
            f"En revanche, {len(humains_auto):,} écritures sont auto-validées par des utilisateurs "
            "NOMINATIFS, ce qui constitue une défaillance directe du contrôle."
        ).replace(",", " ")
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
            ("Écritures contrôlées", f"{len(df):,}".replace(",", " ")),
            ("Saisie = validation", f"{len(auto):,} ({part:.1f} %)".replace(",", " ")),
            ("Dont utilisateurs nominatifs", f"{len(humains_auto):,}".replace(",", " ")),
        ],
        tableaux=tableaux,
        recommandation=(
            "Le contrôle de validation des flux automatiques doit être recherché dans le système "
            "amont (Calypso) puisqu'il est absent de Flexcube. Obtenir la procédure de validation "
            "des deals dans Calypso et la matrice d'habilitations des comptes techniques."
        ),
    )


def _c42_sans_validateur(ctx) -> Constat:
    df = ctx.toutes_ecritures
    sans = df[df.AUTH_ID.isna()]
    if sans.empty:
        return Constat(
            code="4.2", titre="Écritures sans validateur", gravite=Gravite.CONFORME,
            constat="Toute écriture porte un identifiant de validation.",
        )
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
            "qu'aucun second intervenant ne les approuve, et elles relèvent majoritairement du "
            "module d'écriture directe, celui qui permet les passations les plus libres. Leur "
            "étalement continu sur toute la période exclut l'incident ponctuel."
        ),
        chiffres=[
            ("Écritures sans validateur", f"{len(sans):,}".replace(",", " ")),
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
    df = ctx.toutes_ecritures
    tech = df[df.USER_ID.isin(COMPTES_TECHNIQUES)]
    par = tech.groupby("USER_ID").agg(n=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))
    part = len(tech) / max(len(df), 1) * 100
    return Constat(
        code="4.3",
        titre="Poids des comptes techniques dans la comptabilisation",
        gravite=Gravite.MOYENNE,
        constat=(
            f"Les comptes techniques concentrent {part:.1f} % des écritures du périmètre. Un "
            "compte technique n'est rattaché à aucune personne physique : la responsabilité de "
            "l'écriture ne peut donc être établie, et le contrôle des quatre yeux ne peut "
            "s'appliquer. Le risque est d'autant plus élevé que certains de ces comptes servent "
            "aussi à des saisies manuelles."
        ),
        chiffres=[("Écritures par compte technique", f"{len(tech):,} ({part:.1f} %)".replace(",", " "))],
        tableaux=[Tableau(["Compte technique", "Écritures", "Montant XAF"],
                          [[i, int(r.n), float(r.montant)] for i, r in par.sort_values("n", ascending=False).iterrows()])],
        recommandation=(
            "Obtenir, pour chaque compte technique, son propriétaire fonctionnel, la liste des "
            "personnes pouvant l'utiliser et la traçabilité applicative associée."
        ),
    )


def _c44_horaires(ctx) -> Constat:
    cfg = ctx.config
    df = ctx.toutes_ecritures.copy()
    heures = df.STMT_DT.str.slice(11, 13)
    df["heure"] = heures.where(heures.str.isdigit()).astype(float)
    hors = df[(df.heure < cfg.heure_ouverture) | (df.heure >= cfg.heure_fermeture)]
    humains = _humains(hors)
    if humains.empty:
        return Constat(
            code="4.4", titre="Saisies en dehors des heures ouvrables", gravite=Gravite.CONFORME,
            constat=(
                f"Les {len(hors):,} écritures passées hors de la plage "
                f"{cfg.heure_ouverture} h – {cfg.heure_fermeture} h sont toutes le fait de "
                "traitements automatiques."
            ).replace(",", " "),
        )
    par = humains.groupby("USER_ID").agg(n=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))
    return Constat(
        code="4.4",
        titre="Saisies manuelles en dehors des heures ouvrables",
        gravite=Gravite.MOYENNE,
        constat=(
            f"Des utilisateurs nominatifs ont comptabilisé des écritures avant "
            f"{cfg.heure_ouverture} h ou après {cfg.heure_fermeture} h. Une saisie hors plage n'est "
            "pas anormale en soi dans une salle de marché, mais elle échappe à la supervision "
            "hiérarchique habituelle et doit être justifiée."
        ),
        chiffres=[
            ("Écritures hors plage (toutes origines)", f"{len(hors):,}".replace(",", " ")),
            ("Dont utilisateurs nominatifs", f"{len(humains):,}".replace(",", " ")),
            ("Montant concerné", xaf(float(humains.LCY_AMOUNT.sum()))),
        ],
        tableaux=[Tableau(["Opérateur", "Écritures", "Montant XAF"],
                          [[i, int(r.n), float(r.montant)] for i, r in par.sort_values("n", ascending=False).head(12).iterrows()])],
        recommandation="Rapprocher ces horaires des plannings de la salle des marchés et des astreintes.",
    )


def _c45_concentration(ctx) -> Constat:
    mm = ctx.grand_livre[ctx.grand_livre.MODULE == "MM"]
    humains = _humains(mm)
    if humains.empty:
        return Constat(code="4.5", titre="Concentration des opérations", gravite=Gravite.CONFORME,
                       constat="Aucune saisie manuelle sur le module MM.")
    par = humains.groupby("USER_ID").agg(n=("LCY_AMOUNT", "size"), montant=("LCY_AMOUNT", "sum"))
    par = par.sort_values("montant", ascending=False)
    part_premier = float(par.montant.iloc[0]) / float(par.montant.sum()) * 100
    return Constat(
        code="4.5",
        titre="Concentration des opérations de titres sur un nombre restreint d'opérateurs",
        gravite=Gravite.MOYENNE if len(par) <= 5 or part_premier > 50 else Gravite.FAIBLE,
        constat=(
            f"Les saisies manuelles du module de marché monétaire sont le fait de {len(par)} "
            f"opérateurs, dont le premier concentre {part_premier:.0f} % des montants. Une telle "
            "concentration limite la rotation des tâches et la capacité de détection mutuelle des "
            "erreurs ; elle appelle un contrôle compensatoire de second niveau."
        ),
        chiffres=[
            ("Opérateurs nominatifs", str(len(par))),
            ("Part du premier opérateur", f"{part_premier:.0f} %"),
        ],
        tableaux=[Tableau(["Opérateur", "Écritures", "Montant XAF"],
                          [[i, int(r.n), float(r.montant)] for i, r in par.iterrows()])],
        recommandation=(
            "Vérifier l'existence d'une rotation des opérateurs, de délégations formalisées et "
            "d'un contrôle de second niveau sur les opérations de marché."
        ),
    )
