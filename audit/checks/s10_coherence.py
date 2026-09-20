"""Section 10 — Cohérence entre le système amont et le grand livre.

Calypso porte les deals ; Flexcube porte la comptabilité. L'interface ne transmet que des
écritures. Cette section rapproche les deux référentiels : un deal doit produire de la
comptabilité si et seulement s'il est réellement conclu, et toute écriture doit se rattacher
à un deal existant.
"""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf

SECTION = (10, "Cohérence entre le système amont et le grand livre")

# Seuls ces statuts correspondent à une opération réellement conclue.
STATUTS_ABOUTIS = ["VERIFIED", "MATURED"]
# Un deal hypothétique est une simulation : il ne doit jamais atteindre la comptabilité.
STATUT_SIMULATION = "HYPO_TRADE"


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "Rapprochement du référentiel des deals du système amont avec les écritures reçues "
            "dans le grand livre : deals non aboutis ayant néanmoins produit de la comptabilité, "
            "écritures sans deal source, séparation des tâches dans le système amont et qualité "
            "du référentiel des opérateurs."
        ),
    )
    if ctx.deals_calypso.empty:
        s.erreurs.append("Référentiel des deals du système amont non disponible.")
        return s
    s.ajouter(_c101_couverture(ctx))
    s.ajouter(_c102_deals_non_aboutis(ctx))
    s.ajouter(_c103_ecritures_orphelines(ctx))
    s.ajouter(_c104_separation_amont(ctx))
    s.ajouter(_c105_referentiel_operateurs(ctx))
    return s


def _apparier(ctx):
    deals = ctx.deals_calypso.copy()
    comptabilises = set(ctx.calypso_enrichi.DEAL.dropna())
    deals["en_comptabilite"] = deals["Trade Id"].isin(comptabilises)
    return deals, comptabilises


def _c101_couverture(ctx) -> Constat:
    deals, comptabilises = _apparier(ctx)
    croisement = deals.groupby(["TradeStatus", "en_comptabilite"]).size().unstack(fill_value=0)
    croisement["total"] = croisement.sum(axis=1)
    aboutis = deals[deals.TradeStatus.isin(STATUTS_ABOUTIS)]
    sans_compta = aboutis[~aboutis.en_comptabilite]
    part = len(sans_compta) / max(len(aboutis), 1) * 100
    lignes = [[i, int(r.get(False, 0)), int(r.get(True, 0)), int(r.total),
               round(int(r.get(True, 0)) / int(r.total) * 100, 1)]
              for i, r in croisement.iterrows()]
    gravite = Gravite.ELEVEE if part > 20 else Gravite.MOYENNE
    return Constat(
        code="10.1",
        titre="Deals conclus n'ayant produit aucune écriture comptable",
        gravite=gravite,
        constat=(
            "Le rapprochement croise le statut de chaque deal dans le système amont avec sa "
            "présence dans le grand livre.\n"
            "Une part importante des deals ABOUTIS — validés ou arrivés à échéance — ne se "
            "retrouve dans aucune écriture comptable. Plusieurs explications sont possibles et "
            "doivent être départagées : l'opération ne génère pas d'écriture dans le périmètre de "
            "comptes extrait ; son déversement a échoué ; ou elle relève d'un portefeuille dont "
            "les écritures ne transitent pas par ce périmètre — notamment le change, dont les "
            "comptes ne sont pas tous couverts.\n"
            "Ce contrôle ne conclut donc pas à une anomalie, mais il délimite une zone que "
            "l'établissement doit justifier : un deal conclu doit produire une trace comptable "
            "quelque part."
        ),
        chiffres=[
            ("Deals au référentiel du système amont", f"{len(deals):,}".replace(",", " ")),
            ("Deals retrouvés en comptabilité", f"{int(deals.en_comptabilite.sum()):,}".replace(",", " ")),
            ("Deals aboutis", f"{len(aboutis):,}".replace(",", " ")),
            ("Dont sans écriture comptable", f"{len(sans_compta):,} ({part:.0f} %)".replace(",", " ")),
        ],
        tableaux=[
            Tableau(["Statut du deal", "Sans comptabilité", "Avec comptabilité", "Total", "Part %"],
                    lignes),
            Tableau(["Portefeuille", "Deals aboutis sans écriture"],
                    [[i, int(n)] for i, n in sans_compta.Book.value_counts().items()]),
        ],
        recommandation=(
            "Obtenir la cartographie des portefeuilles dont les écritures transitent par le "
            "périmètre extrait, afin de distinguer l'absence normale de l'échec de déversement. "
            "Mettre en place un rapprochement quotidien du nombre de deals conclus et du nombre "
            "de deals comptabilisés."
        ),
    )


def _c102_deals_non_aboutis(ctx) -> Constat:
    """Un deal annulé, en attente ou hypothétique ne doit pas laisser de trace au bilan."""
    deals, _ = _apparier(ctx)
    gl = ctx.calypso_enrichi
    non_aboutis = deals[~deals.TradeStatus.isin(STATUTS_ABOUTIS) & deals.en_comptabilite]
    if non_aboutis.empty:
        return Constat(
            code="10.2", titre="Deals non aboutis présents en comptabilité", gravite=Gravite.CONFORME,
            constat="Aucun deal annulé, en attente ou hypothétique n'a produit d'écriture comptable.",
        )
    detail, residus = [], []
    for _, r in non_aboutis.iterrows():
        ecritures = gl[gl.DEAL == r["Trade Id"]]
        bilan = ecritures[~ecritures.AC_NO.str.startswith(("6", "7"))]
        resultat = ecritures[ecritures.AC_NO.str.startswith(("6", "7"))]
        solde_bilan = float(bilan.SIGNE.sum())
        impact_resultat = -float(resultat.SIGNE.sum())
        ligne = [r["Trade Id"], r.TradeStatus, r.Book, r.CounterParty, len(ecritures),
                 float(ecritures.LCY_AMOUNT.sum()), solde_bilan, impact_resultat]
        detail.append(ligne)
        if abs(solde_bilan) > 0.5 or abs(impact_resultat) > 0.5:
            residus.append(ligne)
    detail.sort(key=lambda l: -l[5])
    # Solde résiduel de ces deals à chaque date d'arrêté
    par_arrete = []
    for arrete in ctx.arretes:
        total, nb = 0.0, 0
        for _, r in non_aboutis.iterrows():
            e = gl[(gl.DEAL == r["Trade Id"]) & (gl.TRN_DT <= arrete)]
            if e.empty:
                continue
            solde = float(e[~e.AC_NO.str.startswith(("6", "7"))].SIGNE.sum())
            if abs(solde) > 0.5:
                total += abs(solde)
                nb += 1
        par_arrete.append([arrete, nb, total])
    simulations = [d for d in detail if d[1] == STATUT_SIMULATION]
    return Constat(
        code="10.2",
        titre="Deals annulés, en attente ou hypothétiques ayant produit de la comptabilité",
        gravite=Gravite.ELEVEE,
        constat=(
            "Le système amont distingue les deals réellement conclus de ceux qui ne le sont pas : "
            "annulés, en attente de validation, en cours de contrôle de limite, ou "
            "HYPOTHÉTIQUES — c'est-à-dire de simples simulations.\n"
            "\n"
            "Or des deals relevant de ces catégories ont produit des écritures dans le grand "
            "livre. Le point mérite d'être nuancé, car le mécanisme d'annulation fonctionne "
            "largement : pour la grande majorité de ces deals, les écritures ont été correctement "
            "CONTRE-PASSÉES et leur solde au bilan revient à zéro.\n"
            "\n"
            "Deux réserves subsistent néanmoins. D'abord, quelques deals laissent un RÉSIDU "
            "définitif, au bilan comme au compte de résultat. Ensuite et surtout, un deal "
            "HYPOTHÉTIQUE ne devrait JAMAIS atteindre la comptabilité, quel que soit le montant et "
            "quelle que soit la contre-passation ultérieure : une simulation n'est pas une "
            "opération. Sa présence révèle que le filtre entre le système amont et le grand livre "
            "ne contrôle pas le statut du deal avant déversement."
        ),
        chiffres=[
            ("Deals non aboutis ayant produit de la comptabilité", str(len(non_aboutis))),
            ("Dont deals hypothétiques (simulations)", str(len(simulations))),
            ("Écritures générées", str(sum(d[4] for d in detail))),
            ("Volume comptabilisé", xaf(sum(d[5] for d in detail))),
            ("Deals laissant un résidu définitif", str(len(residus))),
            ("Impact résultat résiduel", xaf(sum(d[7] for d in residus))),
        ],
        tableaux=[
            Tableau(["Deal", "Statut", "Portefeuille", "Contrepartie", "Écritures", "Volume XAF",
                     "Solde bilan résiduel", "Impact résultat"],
                    detail, max_lignes=16),
            Tableau(["Date d'arrêté", "Deals à solde résiduel", "Impact bilan XAF"], par_arrete,
                    note="Résidu porté par ces deals à chaque date d'arrêté."),
        ],
        recommandation=(
            "Faire contrôler le statut du deal par l'interface avant tout déversement : seuls les "
            "deals validés doivent générer des écritures. Apurer les résidus constatés et obtenir "
            "l'explication de la présence d'un deal hypothétique en comptabilité."
        ),
    )


def _c103_ecritures_orphelines(ctx) -> Constat:
    """Toute écriture doit se rattacher à un deal existant dans le système amont."""
    deals, _ = _apparier(ctx)
    gl = ctx.calypso_enrichi
    connus = set(deals["Trade Id"])
    orphelines = gl[~gl.DEAL.isin(connus)]
    if orphelines.empty:
        return Constat(code="10.3", titre="Écritures sans deal source", gravite=Gravite.CONFORME,
                       constat="Toute écriture se rattache à un deal du référentiel amont.")
    par_deal = orphelines.groupby("DEAL").agg(
        ecritures=("LCY_AMOUNT", "size"), volume=("LCY_AMOUNT", "sum"),
        debut=("TRN_DT", "min"), fin=("TRN_DT", "max"), book=("BOOK", "first"),
        titre=("TITRE", "first"))
    return Constat(
        code="10.3",
        titre="Écritures comptables sans deal correspondant dans le système amont",
        gravite=Gravite.MOYENNE,
        constat=(
            "Des écritures du grand livre portent un identifiant de deal qui ne figure pas au "
            "référentiel du système amont. Deux lectures sont possibles : l'extraction du "
            "référentiel ne couvre pas l'intégralité de l'historique des deals, ou des écritures "
            "ont été générées sans deal source.\n"
            "La distinction est importante : dans le second cas, la comptabilité porterait des "
            "opérations dont aucune trace ne subsiste dans le système de négociation, ce qui "
            "romprait la piste d'audit."
        ),
        chiffres=[
            ("Deals orphelins", str(len(par_deal))),
            ("Écritures concernées", f"{len(orphelines):,}".replace(",", " ")),
            ("Volume", xaf(float(orphelines.LCY_AMOUNT.sum()))),
            ("Période", f"{orphelines.TRN_DT.min()} → {orphelines.TRN_DT.max()}"),
        ],
        tableaux=[
            Tableau(["Deal", "Portefeuille", "Titre", "Écritures", "Volume XAF", "Du", "Au"],
                    [[i, r.book, str(r.titre)[:22], int(r.ecritures), float(r.volume), r.debut, r.fin]
                     for i, r in par_deal.sort_values("volume", ascending=False).iterrows()],
                    max_lignes=15)
        ],
        recommandation=(
            "Confirmer l'étendue de l'extraction du référentiel des deals. Pour les deals qui n'y "
            "figureraient réellement pas, obtenir la justification des écritures correspondantes."
        ),
    )


def _c104_separation_amont(ctx) -> Constat:
    """Le contrôle des quatre yeux, absent du grand livre, existe-t-il dans le système amont ?"""
    deals = ctx.deals_calypso
    aboutis = deals[deals.TradeStatus.isin(STATUTS_ABOUTIS)]
    par_saisie = deals["Entered User"].value_counts()
    generiques = [u for u in par_saisie.index
                  if str(u).lower() in {"admin", "calypso_user", "system", "trader1"}]
    part_generique = int(par_saisie[generiques].sum()) / max(len(deals), 1) * 100
    croisement = deals.groupby(["Entered User", "Trader"]).size().reset_index(name="deals")
    sans_trader = deals[deals.Trader.isin(["NONE", "0", "Trader", "TRADER1"]) | deals.Trader.isna()]
    return Constat(
        code="10.4",
        titre="Saisie des deals par des comptes génériques dans le système amont",
        gravite=Gravite.ELEVEE,
        constat=(
            "Le contrôle des quatre yeux de Flexcube est sans effet sur le flux issu du système "
            "amont, puisqu'un compte technique unique saisit et valide toutes les écritures "
            "(contrôle 6.2). Le référentiel des deals permet enfin de vérifier si ce contrôle "
            "existe EN AMONT.\n"
            "\n"
            "Le système amont distingue bien deux rôles : l'UTILISATEUR qui saisit le deal et le "
            "TRADER auquel l'opération est attribuée. C'est la base d'une séparation des tâches.\n"
            "\n"
            "Mais deux faiblesses apparaissent. D'une part, une fraction notable des deals est "
            "saisie sous des COMPTES GÉNÉRIQUES — « admin », « calypso_user » — non rattachés à "
            "une personne physique : pour ces opérations, la responsabilité de la saisie ne peut "
            "être établie. D'autre part, un nombre important de deals ne porte AUCUN TRADER "
            "identifié, le champ étant renseigné par une valeur de remplissage.\n"
            "\n"
            "Le référentiel ne comporte par ailleurs aucun champ de validation distinct : rien "
            "n'indique qu'un second intervenant approuve le deal avant qu'il ne produise de la "
            "comptabilité. Le statut « validé » existe, mais son auteur n'est pas tracé dans "
            "l'extraction."
        ),
        chiffres=[
            ("Deals au référentiel", f"{len(deals):,}".replace(",", " ")),
            ("Comptes de saisie distincts", str(len(par_saisie))),
            ("Dont comptes génériques", ", ".join(generiques) if generiques else "aucun"),
            ("Part des deals saisis sous compte générique", f"{part_generique:.0f} %"),
            ("Deals sans trader identifié", f"{len(sans_trader):,}".replace(",", " ")),
            ("Champ de validation dans le référentiel", "absent"),
        ],
        tableaux=[
            Tableau(["Compte de saisie", "Deals"], [[i, int(n)] for i, n in par_saisie.items()]),
            Tableau(["Compte de saisie", "Trader attribué", "Deals"],
                    [[r["Entered User"], r.Trader, int(r.deals)]
                     for _, r in croisement.sort_values("deals", ascending=False).iterrows()],
                    max_lignes=16, note="Croisement saisie / attribution."),
        ],
        recommandation=(
            "Obtenir le journal d'audit applicatif du système amont, qui trace la validation de "
            "chaque deal et son auteur. Supprimer l'usage des comptes génériques pour la saisie "
            "des opérations. Rendre le champ trader obligatoire et contrôlé."
        ),
    )


def _c105_referentiel_operateurs(ctx) -> Constat:
    """La qualité du référentiel des opérateurs conditionne toute analyse par intervenant."""
    deals = ctx.deals_calypso
    traders = deals.Trader.value_counts()
    # Un même opérateur enregistré sous plusieurs libellés fausse toute analyse
    doublons = []
    noms = [str(t) for t in traders.index if str(t) not in {"NONE", "0", "Trader", "TRADER1", "nan"}]
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            mots_a, mots_b = set(a.upper().split()), set(b.upper().split())
            if mots_a and mots_b and (mots_a <= mots_b or mots_b <= mots_a) and a != b:
                doublons.append([a, int(traders[a]), b, int(traders[b])])
    placeholders = [[str(t), int(traders[t])] for t in traders.index
                    if str(t) in {"NONE", "0", "Trader", "TRADER1"}]
    if not doublons and not placeholders:
        return Constat(code="10.5", titre="Qualité du référentiel des opérateurs",
                       gravite=Gravite.CONFORME,
                       constat="Chaque opérateur est identifié par un libellé unique et explicite.")
    return Constat(
        code="10.5",
        titre="Référentiel des opérateurs non normalisé",
        gravite=Gravite.MOYENNE,
        constat=(
            "Le champ identifiant l'opérateur d'un deal n'est pas normalisé. Un même intervenant "
            "y figure sous plusieurs libellés — prénom et nom, puis prénom, deuxième prénom et "
            "nom — et des valeurs de remplissage tiennent lieu d'identité pour une part notable "
            "des opérations.\n"
            "La conséquence est directe pour l'audit : toute analyse par intervenant — volume "
            "traité, concentration, respect des limites individuelles — est faussée, puisqu'un "
            "même opérateur est compté plusieurs fois et qu'une partie des opérations n'est "
            "attribuée à personne."
        ),
        chiffres=[
            ("Libellés d'opérateur distincts", str(len(traders))),
            ("Libellés se recouvrant (même personne probable)", str(len(doublons))),
            ("Deals sans opérateur identifié", str(sum(p[1] for p in placeholders))),
        ],
        tableaux=[
            Tableau(["Libellé A", "Deals", "Libellé B", "Deals"], doublons,
                    note="Libellés se recouvrant : vraisemblablement la même personne."),
            Tableau(["Valeur de remplissage", "Deals"], placeholders),
            Tableau(["Opérateur", "Deals"], [[i, int(n)] for i, n in traders.items()]),
        ],
        recommandation=(
            "Normaliser le référentiel des opérateurs et rendre le champ obligatoire, afin que "
            "l'attribution des opérations soit exploitable."
        ),
    )
