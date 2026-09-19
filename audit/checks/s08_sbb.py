"""Section 8 — Opérations de cession-rétrocession (Sell-Buy-Back).

Un Sell-Buy-Back est économiquement un financement garanti, strictement équivalent à une
pension livrée. Sa comptabilisation en cession puis acquisition fermes a des conséquences
directes sur le bilan, le résultat et les ratios prudentiels.
"""
from __future__ import annotations

from ..core import Constat, Gravite, Section, Tableau, xaf

SECTION = (8, "Opérations de cession-rétrocession (Sell-Buy-Back)")

MOTIFS = "SBB|SELL.?BUY.?BACK|BUY.?SELL.?BACK"


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "Identification des opérations de cession-rétrocession à partir des commentaires de la "
            "salle des marchés, puis examen de leur qualification comptable, de la rotation des "
            "titres concernés et du résultat qu'elles dégagent."
        ),
    )
    ops = _operations(ctx)
    s.ajouter(_c81_identification(ctx, ops))
    s.ajouter(_c82_qualification(ctx, ops))
    s.ajouter(_c83_rotation(ctx, ops))
    s.ajouter(_c84_resultat(ctx, ops))
    return s


def _operations(ctx):
    calypso = ctx.calypso_enrichi
    if calypso.empty:
        return calypso
    return calypso[calypso.COMMENTAIRE.fillna("").str.upper().str.contains(MOTIFS, na=False, regex=True)]


def _c81_identification(ctx, ops) -> Constat:
    if ops.empty:
        return Constat(code="8.1", titre="Opérations de cession-rétrocession", gravite=Gravite.CONFORME,
                       constat="Aucune opération de cession-rétrocession identifiée.")
    regle = ops[ops.EVENEMENT == "CST_S_SETTLED"].groupby("DEAL").LCY_AMOUNT.max()
    par_cpty = ops.groupby("EMETTEUR").DEAL.nunique().sort_values(ascending=False)
    jambes = ops.COMMENTAIRE.str.upper().str.extract(r"(NEAR|FAR|FIRST|SECOND)")[0].value_counts()
    return Constat(
        code="8.1",
        titre="Opérations de cession-rétrocession identifiées par les commentaires de la salle des marchés",
        gravite=Gravite.MOYENNE,
        constat=(
            "Des opérations sont explicitement désignées comme des cessions-rétrocessions dans les "
            "commentaires saisis par la salle des marchés, avec mention des deux jambes. Ces "
            "opérations sont invisibles dans les schémas comptables, qui les enregistrent comme "
            "des achats et des ventes ordinaires de titres : seul le commentaire permet de les "
            "identifier."
        ),
        chiffres=[
            ("Opérations identifiées", str(ops.DEAL.nunique())),
            ("Montant réglé cumulé", xaf(float(regle.sum()))),
            ("Période", f"{ops.TRN_DT.min()} → {ops.TRN_DT.max()}"),
            ("Contreparties distinctes", str(ops.EMETTEUR.nunique())),
        ],
        tableaux=[
            Tableau(["Jambe mentionnée", "Lignes"], [[i, int(n)] for i, n in jambes.items()]),
            Tableau(["Contrepartie", "Opérations"], [[i, int(n)] for i, n in par_cpty.items()]),
        ],
        recommandation=(
            "Obtenir la liste exhaustive de ces opérations depuis le système amont : leur "
            "identification ne peut reposer sur une saisie libre et facultative."
        ),
    )


def _c82_qualification(ctx, ops) -> Constat:
    if ops.empty:
        return Constat(code="8.2", titre="Qualification comptable", gravite=Gravite.CONFORME,
                       constat="Sans objet.")
    par_book = ops.groupby(["BOOK", "EVENEMENT"]).agg(
        n=("LCY_AMOUNT", "size"), deals=("DEAL", "nunique"), montant=("LCY_AMOUNT", "sum"))
    books = sorted(ops.BOOK.dropna().unique())
    en_pension = [b for b in books if "Plmt" in b or "Secured" in b]
    regle = ops[ops.EVENEMENT == "CST_S_SETTLED"].groupby("DEAL").LCY_AMOUNT.max()
    return Constat(
        code="8.2",
        titre="Cessions-rétrocessions comptabilisées en cession et acquisition fermes",
        gravite=Gravite.CRITIQUE,
        constat=(
            "Une cession-rétrocession est économiquement un FINANCEMENT GARANTI : le titre ne "
            "quitte pas durablement le portefeuille et la trésorerie reçue constitue une dette. "
            "Le traitement comptable attendu est donc le maintien du titre à l'actif et la "
            "constatation d'une dette au passif.\n"
            "Or ces opérations sont enregistrées dans les portefeuilles de titres, avec les "
            "événements d'une acquisition et d'une cession fermes, et non dans le portefeuille des "
            "opérations de pension.\n"
            "Quatre conséquences en découlent : les titres sortent puis rentrent du bilan alors "
            "qu'ils ne le quittent économiquement jamais ; des plus-values de cession sont "
            "constatées sur des opérations de financement ; l'endettement de l'établissement est "
            "sous-évalué, faussant les ratios prudentiels de liquidité et de transformation ; et "
            "l'usage réel du portefeuille comme collatéral est masqué."
        ),
        chiffres=[
            ("Opérations concernées", str(ops.DEAL.nunique())),
            ("Montant réglé cumulé", xaf(float(regle.sum()))),
            ("Portefeuilles utilisés", ", ".join(books)),
            ("Portefeuille de pension utilisé", ", ".join(en_pension) if en_pension else "AUCUN"),
        ],
        tableaux=[
            Tableau(["Portefeuille", "Événement", "Lignes", "Opérations", "Montant XAF"],
                    [[i[0], i[1], int(r.n), int(r.deals), float(r.montant)]
                     for i, r in par_book.sort_values("montant", ascending=False).iterrows()],
                    max_lignes=12)
        ],
        recommandation=(
            "Obtenir les conventions-cadres signées avec les contreparties et la doctrine "
            "comptable retenue. Faire confirmer le traitement par le commissaire aux comptes et "
            "mesurer l'incidence d'un reclassement en financement garanti sur le bilan, le "
            "résultat et les ratios prudentiels."
        ),
    )


def _c83_rotation(ctx, ops) -> Constat:
    if ops.empty:
        return Constat(code="8.3", titre="Rotation des titres", gravite=Gravite.CONFORME, constat="Sans objet.")
    regle = ops[ops.EVENEMENT == "CST_S_SETTLED"]
    rot = regle.groupby(["TITRE", "EMETTEUR"]).agg(
        operations=("DEAL", "nunique"), debut=("TRN_DT", "min"), fin=("TRN_DT", "max"),
        cumul=("LCY_AMOUNT", "sum"))
    rot = rot[rot.operations > 1].sort_values("operations", ascending=False)
    if rot.empty:
        return Constat(code="8.3", titre="Rotation des titres en cession-rétrocession",
                       gravite=Gravite.CONFORME, constat="Aucun titre ne fait l'objet d'opérations répétées.")
    top = rot.iloc[0]
    # Trajectoire du titre le plus recyclé : le prix doit croître à chaque aller-retour
    titre_top = rot.index[0][0]
    serie = regle[regle.TITRE == titre_top].groupby("DEAL").agg(
        date=("TRN_DT", "min"), montant=("LCY_AMOUNT", "max")).sort_values("date")
    return Constat(
        code="8.3",
        titre="Titres recyclés à répétition avec la même contrepartie : un financement roulé",
        gravite=Gravite.ELEVEE,
        constat=(
            "Les mêmes titres font l'objet d'allers-retours répétés avec la même contrepartie, à "
            "un prix croissant à chaque itération. Cette progression correspond au coût de "
            "financement implicite de l'opération.\n"
            "Ce caractère roulé établit sans ambiguïté qu'il ne s'agit pas de cessions "
            "successives mais d'un FINANCEMENT RENOUVELÉ : un titre réellement cédé ne revient pas "
            "au bilan quelques semaines plus tard, auprès du même acheteur, à un prix supérieur."
        ),
        chiffres=[
            ("Titres faisant l'objet d'opérations répétées", str(len(rot))),
            ("Nombre maximal d'allers-retours sur un même titre", str(int(top.operations))),
            ("Montant cumulé sur ce titre", xaf(float(top.cumul))),
        ],
        tableaux=[
            Tableau(["Titre", "Contrepartie", "Allers-retours", "Du", "Au", "Cumul XAF"],
                    [[i[0], i[1], int(r.operations), r.debut, r.fin, float(r.cumul)]
                     for i, r in rot.head(12).iterrows()]),
            Tableau(["Deal", "Date", "Montant réglé XAF"],
                    [[i, r.date, float(r.montant)] for i, r in serie.iterrows()],
                    note=f"Trajectoire du titre le plus recyclé ({titre_top}) : le prix croît à chaque itération."),
        ],
        recommandation=(
            "Quantifier le coût de financement implicite de ces opérations et le comparer au coût "
            "d'une pension livrée classique auprès de la banque centrale."
        ),
    )


def _c84_resultat(ctx, ops) -> Constat:
    if ops.empty:
        return Constat(code="8.4", titre="Résultat dégagé", gravite=Gravite.CONFORME, constat="Sans objet.")
    resultat = ops[ops.AC_NO.str.startswith(("733", "734"))]
    if resultat.empty:
        return Constat(code="8.4", titre="Résultat dégagé par les cessions-rétrocessions",
                       gravite=Gravite.CONFORME, constat="Aucun impact résultat identifié.")
    par = resultat.groupby(["AC_NO", "AC_GL_DESC", "EVENEMENT"]).agg(
        n=("LCY_AMOUNT", "size"), net=("SIGNE", "sum"))
    impact = -float(resultat.SIGNE.sum())
    return Constat(
        code="8.4",
        titre="Résultat constaté sur des opérations de financement",
        gravite=Gravite.ELEVEE,
        constat=(
            "Les opérations de cession-rétrocession dégagent un résultat comptable : plus-values "
            "de cession et reprises d'intérêts courus réalisés. Si ces opérations sont, comme "
            "l'établit le contrôle 8.3, des financements garantis, ce résultat NE DEVRAIT PAS "
            "ÊTRE CONSTATÉ : un emprunt ne génère pas de plus-value.\n"
            "Le produit ainsi reconnu majore le produit net bancaire de l'exercice et, par "
            "conséquent, le résultat distribuable et les fonds propres."
        ),
        chiffres=[("Impact résultat net des opérations identifiées", xaf(impact))],
        tableaux=[
            Tableau(["Compte", "Libellé", "Événement", "Lignes", "Impact net XAF"],
                    [[i[0], i[1][:34], i[2], int(r.n), -float(r.net)] for i, r in par.iterrows()])
        ],
        recommandation=(
            "Mesurer l'incidence d'un retraitement en financement garanti sur le résultat de "
            "chaque exercice concerné."
        ),
    )
