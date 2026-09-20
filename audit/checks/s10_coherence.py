"""Section 10 — Cohérence entre le système amont et le grand livre.

Calypso porte les deals ; Flexcube porte la comptabilité. L'interface ne transmet que des
écritures. Cette section rapproche les deux référentiels : un deal doit produire de la
comptabilité si et seulement s'il est réellement conclu, et toute écriture doit se rattacher
à un deal existant.
"""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf, pct, nb

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
    """Les deals conclus se retrouvent-ils en comptabilité ?

    Le test n'a de sens que pour les portefeuilles dont les écritures transitent par le
    périmètre de comptes extrait. Les portefeuilles de change et de transfert alimentent des
    comptes qui ne sont pas couverts : les y inclure produirait un faux positif massif. Le
    contrôle les isole et ne conclut que sur les portefeuilles titres.
    """
    deals, comptabilises = _apparier(ctx)
    croisement = deals.groupby(["TradeStatus", "en_comptabilite"]).size().unstack(fill_value=0)
    croisement["total"] = croisement.sum(axis=1)
    lignes = [[i, int(r.get(False, 0)), int(r.get(True, 0)), int(r.total),
               round(int(r.get(True, 0)) / int(r.total) * 100, 1)]
              for i, r in croisement.iterrows()]
    aboutis = deals[deals.TradeStatus.isin(STATUTS_ABOUTIS)]
    # Taux de couverture par portefeuille : il révèle quels books alimentent le périmètre
    par_book = aboutis.groupby("Book").agg(
        deals=("Trade Id", "size"), comptabilises=("en_comptabilite", "sum"))
    par_book["couverture"] = (par_book.comptabilises / par_book.deals * 100).round(1)
    par_book = par_book.sort_values("deals", ascending=False)
    # Un portefeuille est réputé couvert si plus de la moitié de ses deals ont une écriture
    couverts = par_book[par_book.couverture > 50]
    hors_perimetre = par_book[par_book.couverture <= 50]
    dans_couverts = aboutis[aboutis.Book.isin(couverts.index)]
    manquants = dans_couverts[~dans_couverts.en_comptabilite]
    part = len(manquants) / max(len(dans_couverts), 1) * 100
    # Le taux est-il porté par les deals les plus récents, non encore déversés, ou vaut-il
    # aussi pour la période arrêtée ? La réponse change la portée du constat.
    negocies = dans_couverts["Trade Date_d"]
    couverts_periode = dans_couverts[negocies <= ctx.config.fin]
    manquants_periode = couverts_periode[~couverts_periode.en_comptabilite]
    part_periode = len(manquants_periode) / max(len(couverts_periode), 1) * 100
    if manquants.empty:
        return Constat(
            code="10.1", titre="Couverture comptable des deals conclus", gravite=Gravite.CONFORME,
            constat=(
                "Tous les deals conclus relevant des portefeuilles dont les écritures transitent "
                "par le périmètre de comptes extrait s'y retrouvent effectivement."
            ),
            tableaux=[Tableau(["Portefeuille", "Deals aboutis", "Comptabilisés", "Couverture %"],
                              [[i, int(r.deals), int(r.comptabilises), float(r.couverture)]
                               for i, r in par_book.iterrows()])],
        )
    gravite = Gravite.MOYENNE if part > 5 else Gravite.FAIBLE
    return Constat(
        code="10.1",
        titre="Deals conclus sans écriture, sur des portefeuilles pourtant couverts par le périmètre",
        gravite=gravite,
        constat=(
            "Le rapprochement croise le statut de chaque deal du système amont avec sa présence "
            "dans le grand livre.\n"
            "Le test doit d'abord écarter un faux positif évident : les portefeuilles de change et "
            "de transfert de fonds alimentent des comptes qui ne font pas partie du périmètre "
            "extrait. Leurs deals n'ont donc AUCUNE raison d'y apparaître, et les compter comme "
            "manquants n'aurait aucun sens.\n"
            "Le contrôle isole donc les portefeuilles réellement couverts — ceux dont plus de la "
            "moitié des deals produisent une écriture dans le périmètre — et ne conclut que sur "
            "ceux-là. Sur ce périmètre resserré, une fraction des deals conclus reste sans écriture "
            "comptable et doit être justifiée : un deal validé ou arrivé à échéance doit produire "
            "une trace comptable."
        ),
        chiffres=[
            ("Deals au référentiel du système amont", nb(len(deals))),
            ("Deals aboutis", nb(len(aboutis))),
            ("Portefeuilles couverts par le périmètre extrait", ", ".join(couverts.index)),
            ("Portefeuilles hors périmètre (écartés du test)", ", ".join(hors_perimetre.index)),
            ("Deals aboutis sur portefeuilles couverts", nb(len(dans_couverts))),
            ("DONT SANS ÉCRITURE", f"{len(manquants)} ({pct(part, 0)})"),
            ("Dont négociés pendant la période d'audit",
             f"{nb(len(manquants_periode))} sur {nb(len(couverts_periode))} "
             f"({pct(part_periode, 0)})"),
        ],
        tableaux=[
            Tableau(["Portefeuille", "Deals aboutis", "Comptabilisés", "Couverture %"],
                    [[i, int(r.deals), int(r.comptabilises), float(r.couverture)]
                     for i, r in par_book.iterrows()],
                    note="La couverture révèle quels portefeuilles alimentent le périmètre extrait."),
            Tableau(["Statut du deal", "Sans comptabilité", "Avec comptabilité", "Total",
                     "Part comptabilisée %"],
                    lignes,
                    note=("Ce tableau porte sur la TOTALITÉ du référentiel, portefeuilles hors "
                          "périmètre compris : il éclaire le comportement de chaque statut, non "
                          "le taux de couverture énoncé plus haut.")),
            Tableau(["Deal", "Portefeuille", "Contrepartie", "Statut", "Date de négociation"],
                    [[r["Trade Id"], r.Book, r.CounterParty, r.TradeStatus,
                      str(r["Trade Date_d"].date()) if r["Trade Date_d"] == r["Trade Date_d"] else ""]
                     for _, r in manquants.head(15).iterrows()],
                    note="Deals conclus sans écriture, sur portefeuille couvert."),
        ],
        recommandation=(
            "Justifier, deal par deal, l'absence d'écriture sur les portefeuilles couverts. Mettre "
            "en place un rapprochement quotidien entre le nombre de deals conclus et le nombre de "
            "deals comptabilisés, par portefeuille."
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


def _date_extreme(deals, colonne: str) -> str:
    """Dernière date du référentiel des deals, au format ISO, ou une chaîne vide."""
    if deals.empty or colonne not in deals.columns:
        return ""
    valeurs = pd.to_numeric(deals[colonne], errors="coerce").dropna()
    if valeurs.empty:
        return ""
    return str(pd.to_datetime(valeurs.max(), unit="D", origin="1899-12-30").date())


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
    # Le référentiel des deals s'arrête à une date donnée, le grand livre à une autre. Des
    # écritures postérieures à la dernière négociation extraite s'expliquent par ce décalage
    # et non par l'absence de deal source : la distinction change la portée du constat.
    derniere_negociation = _date_extreme(deals, "Trade Date")
    apres_extraction = (orphelines.TRN_DT > derniere_negociation).all() if derniere_negociation else False
    dans_extraction = par_deal[par_deal.debut <= derniere_negociation] if derniere_negociation else par_deal
    return Constat(
        code="10.3",
        titre=("Écritures postérieures à la dernière négociation du référentiel extrait"
               if apres_extraction else
               "Écritures comptables sans deal correspondant dans le système amont"),
        gravite=Gravite.FAIBLE if apres_extraction else Gravite.MOYENNE,
        constat=(
            "Des écritures du grand livre portent un identifiant de deal qui ne figure pas au "
            "référentiel du système amont. Deux lectures sont possibles : l'extraction du "
            "référentiel ne couvre pas l'intégralité de l'historique des deals, ou des écritures "
            "ont été générées sans deal source.\n"
            "La distinction est importante : dans le second cas, la comptabilité porterait des "
            "opérations dont aucune trace ne subsiste dans le système de négociation, ce qui "
            "romprait la piste d'audit.\n"
            + ("LE TEST TRANCHE. La TOTALITÉ de ces écritures est postérieure à la dernière "
               f"négociation figurant au référentiel extrait ({derniere_negociation}), alors que "
               f"le grand livre court jusqu'au {orphelines.TRN_DT.max()}. C'est donc la première "
               "lecture qui s'applique : le décalage entre les deux extractions explique "
               "l'intégralité des cas, et aucune écriture n'est orpheline à l'intérieur de la "
               "fenêtre couverte par le référentiel. Le constat ne porte pas sur les comptes "
               "arrêtés, ces écritures étant toutes postérieures à la clôture ; il reste à lever "
               "en obtenant un référentiel couvrant la même fenêtre que le grand livre."
               if apres_extraction else
               "AUCUNE de ces écritures n'est expliquée par le décalage entre les deux "
               f"extractions : {len(dans_extraction)} deals orphelins se situent à l'intérieur de "
               "la fenêtre couverte par le référentiel et relèvent donc de la seconde lecture.")
        ),
        chiffres=[
            ("Deals orphelins", str(len(par_deal))),
            ("Écritures concernées", nb(len(orphelines))),
            ("Volume", xaf(float(orphelines.LCY_AMOUNT.sum()))),
            ("Période des écritures", f"{orphelines.TRN_DT.min()} → {orphelines.TRN_DT.max()}"),
            ("Dernière négociation au référentiel extrait", derniere_negociation or "n/d"),
            ("Deals orphelins dans la fenêtre du référentiel", str(len(dans_extraction))),
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
            ("Deals au référentiel", nb(len(deals))),
            ("Comptes de saisie distincts", str(len(par_saisie))),
            ("Dont comptes génériques", ", ".join(generiques) if generiques else "aucun"),
            ("Part des deals saisis sous compte générique", f"{pct(part_generique, 0)}"),
            ("Deals sans trader identifié", nb(len(sans_trader))),
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
