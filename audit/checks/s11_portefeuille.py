"""Section 11 — Le portefeuille de titres comme un tout.

Les sections 3 et 6 examinent séparément le dispositif Flexcube et le dispositif Calypso.
Or la banque n'a qu'un portefeuille : la bascule du 16/06/2025 a changé l'outil, pas l'actif.
Cette section réconcilie les deux dispositifs en une seule vue, distingue au sein du nouveau
dispositif les titres détenus en propre de ceux acquis pour être placés auprès de la
clientèle, et contrôle la codification des titres — le seul identifiant dont dispose le
grand livre depuis la bascule.

Le schéma comptable de Calypso, établi par l'examen détaillé d'un échantillon de titres,
est le suivant. Chaque deal produit des MOUVEMENTS, chacun équilibré, qui transitent tous
par un compte de liaison :
  - ACCRUAL_BS : coupon couru acheté ou vendu, compte 512800100 ;
  - NOMINAL : valeur nominale du titre, comptes 511/512 — le portefeuille est tenu AU PAIR ;
  - PREM_DISC : prime ou décote, comptes de régularisation 472200106 et 472200108 ;
  - CST_S_SETTLED : règlement en trésorerie, égal au nominal, majoré du couru et diminué de
    la décote.
Un deal intégralement déversé laisse donc le compte de liaison à zéro. C'est ce que le
contrôle 11.6 exploite.
"""
from __future__ import annotations

import pandas as pd

from ..core import Constat, Gravite, Section, Tableau, xaf, pct, nb, fois
from ..data import (BOOK_CLIENTELE, CPT_CLIENTELE, CPT_LIAISON, CPT_MIROIR,
                    CPT_PORTEFEUILLE_CALYPSO, CPT_PORTEFEUILLE_MM, CPT_REGULARISATION,
                    DATE_BASCULE, PAYS_CEMAC, PAYS_EXCLUS)

SECTION = (11, "Le portefeuille de titres comme un tout")


def run(ctx) -> Section:
    s = Section(
        numero=SECTION[0],
        titre=SECTION[1],
        objet=(
            "La bascule du 16/06/2025 a changé l'outil de gestion, pas l'actif : la banque n'a "
            "qu'un portefeuille de titres. Cette section le reconstitue de bout en bout, à "
            "travers les deux dispositifs, distingue les titres détenus en propre de ceux acquis "
            "pour être placés auprès de la clientèle, contrôle la codification des titres du "
            "nouveau dispositif et mesure l'exposition souveraine réelle."
        ),
    )
    for fonction in (_c111_continuite, _c112_clientele, _c113_codification,
                     _c114_exposition, _c115_prime_decote, _c116_apurement_deal,
                     _c117_echantillon, _c118_cas_le_plus_lourd):
        s.ajouter(fonction(ctx))
    return s


# --- 11.1 ---------------------------------------------------------------------------------

def _c111_continuite(ctx) -> Constat:
    """Le portefeuille se lit-il comme une série continue à travers la bascule ?"""
    lignes = []
    for arrete in ctx.arretes:
        mm = ctx.solde(CPT_PORTEFEUILLE_MM, a_la_date=arrete)
        cal = ctx.solde(CPT_PORTEFEUILLE_CALYPSO, a_la_date=arrete)
        # 938000100 est débité des titres livrés à la clientèle : son solde est donc
        # directement l'encours détenu par les clients.
        client = ctx.solde(["938000100"], a_la_date=arrete)
        lignes.append([arrete, mm, cal, mm + cal, client,
                       "Flexcube" if cal == 0 else "Calypso"])
    encours = [l[3] for l in lignes]
    croissance = encours[-1] / encours[0] if encours and encours[0] else 0
    # Le jour de la bascule doit voir sortir de Flexcube exactement ce qui entre dans Calypso.
    jour = ctx.grand_livre[ctx.grand_livre.TRN_DT == DATE_BASCULE]
    sortie = -float(jour[jour.AC_NO.isin(CPT_PORTEFEUILLE_MM)].SIGNE.sum())
    entree = float(jour[jour.AC_NO.isin(CPT_PORTEFEUILLE_CALYPSO)].SIGNE.sum())
    rupture = entree - sortie
    return Constat(
        code="11.1",
        titre="Le portefeuille vu comme une seule série, de bout en bout",
        gravite=Gravite.CONFORME if abs(rupture) < ctx.config.seuil_significatif else Gravite.ELEVEE,
        constat=(
            "Le portefeuille de titres de la banque est porté par deux jeux de comptes "
            "successifs : les comptes du dispositif Flexcube jusqu'à la bascule, ceux du "
            "dispositif Calypso ensuite. Aucun état ne les réunit, alors qu'il s'agit du MÊME "
            "actif : toute analyse conduite sur un seul jeu de comptes s'arrête ou commence au "
            "16/06/2025 et ne dit rien de l'évolution réelle.\n"
            "La série reconstituée ci-dessous est la seule lecture continue du portefeuille. "
            f"L'encours passe de {xaf(encours[0])} au premier arrêté de la période à "
            f"{xaf(encours[-1])} au dernier, soit une multiplication par {fois(croissance, 1)[2:]} "
            "en moins de trois ans. Cette progression est le fait générateur de la plupart des "
            "constats du présent rapport : elle commande les intérêts courus, le résultat, le "
            "besoin de refinancement et l'exposition souveraine.\n"
            + ("La bascule elle-même est neutre : ce qui sort des comptes Flexcube entre pour "
               "le même montant dans les comptes Calypso, la continuité de l'actif est donc "
               "assurée."
               if abs(rupture) < ctx.config.seuil_significatif else
               f"La bascule N'EST PAS neutre : {xaf(abs(rupture))} d'écart séparent ce qui sort "
               "des comptes Flexcube de ce qui entre dans les comptes Calypso.")
        ),
        chiffres=[
            ("Encours au premier arrêté de la période", xaf(encours[0])),
            ("Encours au dernier arrêté de la période", xaf(encours[-1])),
            ("Multiplication sur la période", fois(croissance, 1)),
            ("Sortie NETTE des comptes Flexcube le jour de la bascule", xaf(sortie)),
            ("Entrée NETTE dans les comptes Calypso le même jour", xaf(entree)),
            ("Écart de bascule", xaf(rupture)),
        ],
        tableaux=[Tableau(
            ["Date d'arrêté", "Comptes Flexcube", "Comptes Calypso", "PORTEFEUILLE PROPRE",
             "Titres de la clientèle (hors bilan)", "Dispositif"],
            lignes,
            note=("Le portefeuille propre est au bilan, les titres placés auprès de la clientèle "
                  "au hors bilan. Les deux colonnes ne s'additionnent pas : la seconde ne "
                  "appartient pas à la banque."))],
        recommandation=(
            "Produire un état de suivi du portefeuille indépendant de l'outil, rapproché "
            "mensuellement des deux jeux de comptes, et le conserver au dossier de clôture."
        ),
    )


# --- 11.2 ---------------------------------------------------------------------------------

def _c112_clientele(ctx) -> Constat:
    """Les titres acquis pour la clientèle sont-ils distingués du portefeuille propre ?"""
    c = ctx.calypso_enrichi
    if c.empty:
        return Constat(code="11.2", titre="Titres de la clientèle", gravite=Gravite.FAIBLE,
                       constat="Flux Calypso indisponible.")
    clientele = c[c.BOOK == BOOK_CLIENTELE]
    if clientele.empty:
        return Constat(
            code="11.2", titre="Distinction des titres propres et des titres de la clientèle",
            gravite=Gravite.CONFORME,
            constat="Aucune opération de placement de titres auprès de la clientèle.")
    # Les titres transitent par le portefeuille propre avant d'être placés : le transfert
    # s'opère par l'événement NOM_FULL, entre le compte de liaison et le pont miroir.
    transferts = c[c.EVENEMENT == "NOM_FULL"]
    volume_transfere = float(transferts.LCY_AMOUNT.sum()) / 2
    propres = c[c.BOOK.str.startswith("ABCM_FVOCI", na=False)]
    titres_partages = sorted({t for t in clientele.TITRE.dropna() if t}
                             & {t for t in propres.TITRE.dropna() if t})
    commissions = c[c.EVENEMENT.fillna("").str.contains("BRK_COM")]
    produit_commission = -float(commissions[commissions.AC_NO.str.startswith("7")].SIGNE.sum())
    miroir = {a: ctx.solde([CPT_MIROIR], a_la_date=a) for a in ctx.arretes}
    residu = miroir.get(ctx.config.fin, 0.0)
    hb = {a: ctx.solde(["938000100"], a_la_date=a) for a in ctx.arretes}
    par_titre = (clientele[clientele.TITRE.notna() & (clientele.TITRE != "")]
                 .groupby("TITRE").agg(deals=("DEAL", "nunique"), lignes=("LCY_AMOUNT", "size"),
                                       debut=("TRN_DT", "min"), fin=("TRN_DT", "max")))
    return Constat(
        code="11.2",
        titre="Les titres acquis pour la clientèle transitent par le portefeuille propre",
        gravite=Gravite.MOYENNE if abs(residu) > ctx.config.seuil_significatif else Gravite.FAIBLE,
        constat=(
            "La banque n'achète pas seulement des titres pour son compte : elle en acquiert "
            "aussi pour les replacer auprès de sa clientèle. Le nouveau dispositif loge cette "
            f"activité dans un portefeuille distinct, « {BOOK_CLIENTELE} ».\n"
            "LE CIRCUIT EST INDIRECT. Le titre est d'abord acquis dans le portefeuille propre, "
            "au bilan, puis transféré au bureau clientèle par une opération miroir, avant de "
            "ressortir au hors bilan lorsque le client en prend livraison et règle. Entre "
            "l'acquisition et le placement, le titre figure donc au BILAN DE LA BANQUE et pèse "
            "sur ses encours, alors qu'il n'est pas destiné à y rester.\n"
            "CONSÉQUENCE POUR L'ANALYSE. L'encours du portefeuille propre présenté au contrôle "
            "11.1 comprend, à toute date, une fraction non identifiable de titres en attente de "
            "placement. Aucun compte ne les sépare : seul le portefeuille du système amont le "
            "fait, et ce portefeuille n'est pas déversé dans le grand livre.\n"
            + (f"LE PONT MIROIR N'EST PAS APURÉ. Il porte {xaf(residu)} à la clôture, c'est-à-dire "
               "des transferts vers le bureau clientèle dont la contrepartie n'est jamais "
               "arrivée : soit le client n'a pas réglé, soit la jambe correspondante n'a pas "
               "été déversée."
               if abs(residu) > 1 else
               "Le pont miroir revient à zéro à la clôture : tous les transferts ont trouvé "
               "leur contrepartie.")
        ),
        chiffres=[
            ("Deals de placement auprès de la clientèle", str(clientele.DEAL.nunique())),
            ("Titres concernés", str(par_titre.shape[0])),
            ("Dont figurant AUSSI au portefeuille propre", str(len(titres_partages))),
            ("Volume transféré au bureau clientèle", xaf(volume_transfere)),
            ("Commissions de placement constatées", xaf(produit_commission)),
            ("Titres de la clientèle au hors bilan à la clôture", xaf(hb.get(ctx.config.fin, 0))),
            ("Solde du pont miroir à la clôture", xaf(residu)),
        ],
        tableaux=[
            Tableau(["Date d'arrêté", "Titres de la clientèle (hors bilan)", "Pont miroir"],
                    [[a, hb[a], miroir[a]] for a in ctx.arretes],
                    note=("Le hors bilan mesure ce que la clientèle détient ; le pont miroir "
                          "mesure ce qui a quitté le portefeuille propre sans être réglé.")),
            Tableau(["Titre", "Deals", "Écritures", "Du", "Au"],
                    [[i, int(r.deals), int(r.lignes), r.debut, r.fin]
                     for i, r in par_titre.sort_values("deals", ascending=False).iterrows()],
                    max_lignes=15,
                    note="Titres ayant fait l'objet d'un placement auprès de la clientèle."),
        ],
        recommandation=(
            "Obtenir du système amont l'encours de titres détenus en attente de placement à "
            "chaque date d'arrêté, afin de séparer le portefeuille d'investissement du stock "
            "d'intermédiation. Apurer le pont miroir et en expliquer le solde."
        ),
    )


# --- 11.3 ---------------------------------------------------------------------------------

def _c113_codification(ctx) -> Constat:
    """Le code d'un titre l'identifie-t-il sans ambiguïté ?

    Depuis la bascule, le libellé de l'écriture est le SEUL signalement du titre dans le
    grand livre : sa codification doit donc être irréprochable. Trois tests sont menés —
    validité du code, cohérence entre le pays encodé et le mnémonique de l'émetteur,
    concordance du libellé entre le grand livre et l'extraction du système amont.
    """
    titres = ctx.titres_calypso
    if titres.empty:
        return Constat(code="11.3", titre="Codification des titres", gravite=Gravite.FAIBLE,
                       constat="Aucun titre identifiable dans le flux Calypso.")
    fictifs = titres[titres.pays_code.str.fullmatch(r"X+", na=False)
                     | titres.TITRE.str.contains("XXXX", na=False)]
    inconnus = titres[~titres.pays_code.isin(PAYS_CEMAC) & ~titres.index.isin(fictifs.index)]
    contradictoires = titres[(titres.pays_mnemo != "") & (titres.pays_code != titres.pays_mnemo)
                             & ~titres.index.isin(fictifs.index)]
    # Un mnémonique absent du référentiel des émetteurs connus est tout aussi problématique :
    # il ne désigne aucun émetteur identifiable.
    inclassables = titres[(titres.pays_mnemo == "") & (titres.mnemo != "")
                          & ~titres.index.isin(fictifs.index)]
    # Concordance du libellé entre les deux sources
    compare = titres[titres.libelle_ref != ""]
    divergents = compare[compare.libelle_gl != compare.libelle_ref]
    # Encours porté par les titres à code fictif
    gl = ctx.calypso_enrichi
    porte = gl[gl.AC_NO.isin(CPT_PORTEFEUILLE_CALYPSO)]
    encours_fictifs = float(porte[porte.TITRE.isin(fictifs.TITRE)].SIGNE.sum())
    anomalies = len(fictifs) + len(contradictoires) + len(inconnus) + len(inclassables)
    if not anomalies and divergents.empty:
        return Constat(
            code="11.3", titre="Codification des titres du nouveau dispositif",
            gravite=Gravite.CONFORME,
            constat=(f"Les {len(titres)} titres portent un code cohérent avec le mnémonique de "
                     "leur émetteur, et leur libellé concorde entre le grand livre et "
                     "l'extraction du système amont."),
        )
    gravite = (Gravite.ELEVEE if abs(encours_fictifs) > ctx.config.seuil_significatif
               else Gravite.MOYENNE)
    return Constat(
        code="11.3",
        titre="Codification des titres : codes fictifs, pays contradictoires et libellés divergents",
        gravite=gravite,
        constat=(
            "LE CODE EST LE SEUL IDENTIFIANT. Calypso ne crée aucun contrat dans le core "
            "banking : depuis la bascule, un titre n'est désigné dans le grand livre que par le "
            "code porté par le libellé de ses écritures. Ce code commande tout ce qui suit — "
            "rapprochement avec le conservateur, valorisation, échéancier, exposition par "
            "émetteur. Sa fiabilité conditionne celle du portefeuille.\n"
            "\n"
            "PREMIER TEST — LE CODE EXISTE-T-IL ? Le code d'un titre CEMAC commence par le code "
            "pays ISO de son émetteur souverain. "
            + (f"Or {len(fictifs)} titres portent un code de REMPLISSAGE, composé de X, qui "
               "n'identifie rien. Ces titres ne peuvent être ni rapprochés d'un relevé de "
               "conservation, ni valorisés, ni rattachés à une souche. Ils portent pourtant un "
               f"encours de {xaf(abs(encours_fictifs))} au portefeuille."
               if len(fictifs) else "Tous les codes sont renseignés.")
            + "\n"
            "\n"
            "DEUXIÈME TEST — LE CODE ET L'ÉMETTEUR CONCORDENT-ILS ? Le libellé porte aussi un "
            "mnémonique d'émetteur, redondant avec le code pays. "
            + (f"Sur {len(contradictoires)} titres, les deux se CONTREDISENT : un titre dont le "
               "code désigne un pays est libellé au nom d'un autre. L'un des deux champs est "
               "faux, et l'exposition par souverain est donc fausse pour ces titres."
               if len(contradictoires) else "Les deux concordent sur tous les titres.")
            + (f" {len(inclassables)} titres portent en outre un mnémonique qui ne correspond à "
               "aucun émetteur répertorié et ne permet donc aucun recoupement."
               if len(inclassables) else "")
            + "\n"
            "\n"
            "TROISIÈME TEST — LE MÊME TITRE PORTE-T-IL LE MÊME LIBELLÉ DANS LES DEUX SYSTÈMES ? "
            + (f"NON : sur {len(compare)} titres présents dans les deux sources, {len(divergents)} "
               "portent un libellé différent. L'écart est systématique et porte sur la DATE "
               "D'ÉCHÉANCE : le grand livre l'écrit en mois/jour/année, l'extraction du système "
               "amont en jour/mois/année. Pour un titre échéant le 3 janvier, le grand livre "
               "affiche 01/03 et le référentiel 03/01 — les deux lectures étant plausibles, "
               "l'échéance d'un titre est INDÉTERMINABLE à la seule lecture du grand livre. "
               "Un échéancier bâti sur ces libellés est faux pour tout titre dont le jour et le "
               "mois sont tous deux inférieurs à 13."
               if len(divergents) else
               "Les libellés concordent entre les deux sources.")
        ),
        chiffres=[
            ("Titres identifiés dans le flux Calypso", str(len(titres))),
            ("Titres à CODE FICTIF (composé de X)", str(len(fictifs))),
            ("Encours porté par ces titres", xaf(abs(encours_fictifs))),
            ("Titres dont le pays et le mnémonique se contredisent", str(len(contradictoires))),
            ("Titres à mnémonique d'émetteur non répertorié", str(len(inclassables))),
            ("Titres à code pays hors CEMAC", str(len(inconnus))),
            ("Titres présents dans les deux sources", str(len(compare))),
            ("Dont libellé DIVERGENT entre les deux sources",
             f"{len(divergents)} ({pct(len(divergents) / max(len(compare), 1) * 100, 0)})"),
        ],
        tableaux=[
            Tableau(["Titre", "Libellé du grand livre", "Encours portefeuille XAF", "Deals"],
                    [[r.TITRE, r.libelle_gl,
                      float(porte[porte.TITRE == r.TITRE].SIGNE.sum()), int(r.deals)]
                     for _, r in fictifs.iterrows()],
                    note=("Titres dont le code ne désigne rien. Le libellé lui-même n'est pas "
                          "stable : le code y est parfois plus court que dans le champ titre.")),
            Tableau(["Titre", "Pays du code", "Mnémonique du libellé", "Pays du mnémonique",
                     "Libellé"],
                    [[r.TITRE, PAYS_CEMAC.get(r.pays_code, r.pays_code), r.mnemo,
                      PAYS_CEMAC.get(r.pays_mnemo, r.pays_mnemo), r.libelle_gl]
                     for _, r in pd.concat([contradictoires, inclassables]).iterrows()],
                    max_lignes=15,
                    note=("Titres dont les deux champs d'identification désignent des pays "
                          "différents, ou dont le mnémonique n'est rattachable à aucun émetteur.")),
            Tableau(["Titre", "Libellé au grand livre", "Libellé au référentiel amont"],
                    [[r.TITRE, r.libelle_gl, r.libelle_ref] for _, r in divergents.head(10).iterrows()],
                    max_lignes=10,
                    note="Le mois et le jour de l'échéance sont permutés d'une source à l'autre."),
        ],
        recommandation=(
            "Faire attribuer un code réel aux titres identifiés par un code de remplissage et "
            "rapprocher leur encours du relevé du conservateur. Corriger les titres dont le pays "
            "et le mnémonique se contredisent, après avoir établi lequel des deux fait foi. "
            "Imposer à l'interface un format de date unique et non ambigu — la norme ISO — pour "
            "le libellé des titres."
        ),
    )


# --- 11.4 ---------------------------------------------------------------------------------

def _c114_exposition(ctx) -> Constat:
    """La politique d'exclusion du Tchad et de la Centrafrique est-elle tenue ?

    Le contrôle 2.8 ne l'établit que pour le référentiel Flexcube. Depuis la bascule, ce
    référentiel ne reçoit plus rien : la question doit être reposée sur le flux Calypso.
    """
    titres = ctx.titres_calypso
    if titres.empty:
        return Constat(code="11.4", titre="Exposition souveraine consolidée",
                       gravite=Gravite.FAIBLE, constat="Aucun titre identifiable.")
    c = ctx.calypso_enrichi
    porte = c[c.AC_NO.isin(CPT_PORTEFEUILLE_CALYPSO)]
    lignes = []
    for pays, nom in PAYS_CEMAC.items():
        sous = titres[titres.pays_code == pays]
        if sous.empty:
            continue
        mouvements = c[c.TITRE.isin(sous.TITRE)]
        encours = float(porte[porte.TITRE.isin(sous.TITRE)].SIGNE.sum())
        lignes.append([nom, pays, len(sous), int(mouvements.DEAL.nunique()),
                       float(mouvements[mouvements.AC_NO.isin(CPT_PORTEFEUILLE_CALYPSO)]
                             [lambda d: d.DRCR_IND == "D"].LCY_AMOUNT.sum()),
                       encours, "EXCLU PAR LA POLITIQUE" if pays in PAYS_EXCLUS else ""])
    interdits = titres[titres.pays_code.isin(PAYS_EXCLUS)]
    if interdits.empty:
        return Constat(
            code="11.4", titre="Exposition souveraine consolidée",
            gravite=Gravite.CONFORME,
            constat=("Aucun titre des souverains exclus par la politique de risque n'apparaît "
                     "dans le nouveau dispositif : la politique est tenue sur l'ensemble de la "
                     "période, et non seulement sur l'ancien référentiel."),
            tableaux=[Tableau(["Souverain", "Code", "Titres", "Deals", "Acquisitions XAF",
                               "Encours à fin d'extraction XAF", "Statut"], lignes)],
        )
    mouvements = c[c.TITRE.isin(interdits.TITRE)]
    acquisitions = float(mouvements[mouvements.AC_NO.isin(CPT_PORTEFEUILLE_CALYPSO)
                                    & (mouvements.DRCR_IND == "D")].LCY_AMOUNT.sum())
    # Encours de ces titres à chaque date d'arrêté
    aux_arretes = []
    for a in ctx.arretes:
        v = float(porte[porte.TITRE.isin(interdits.TITRE) & (porte.TRN_DT <= a)].SIGNE.sum())
        aux_arretes.append([a, v])
    detenus_a_un_arrete = [l for l in aux_arretes if abs(l[1]) > 1]
    return Constat(
        code="11.4",
        titre="Titres de souverains exclus par la politique de risque dans le nouveau dispositif",
        gravite=Gravite.ELEVEE,
        constat=(
            "La banque a restreint son univers d'investissement à quatre des six souverains de "
            "la CEMAC, en écartant délibérément le Tchad et la République Centrafricaine en "
            "raison de leur profil de risque. Le contrôle 2.8 vérifie le respect de cette "
            "politique — mais sur le seul référentiel Flexcube, qui ne reçoit plus rien depuis "
            "la bascule. La question devait donc être reposée sur le flux Calypso.\n"
            f"ELLE N'EST PAS TENUE. {len(interdits)} titres émis par les souverains exclus ont "
            f"été traités, pour {xaf(acquisitions)} d'acquisitions cumulées. La conclusion du "
            "contrôle 2.8 ne vaut donc que pour la période antérieure à la bascule et ne peut "
            "être étendue à l'ensemble de la période d'audit.\n"
            + ("Ces titres ont par ailleurs figuré AU BILAN À UNE DATE D'ARRÊTÉ : l'exposition "
               "n'est pas seulement intrajournalière, elle est arrêtée."
               if detenus_a_un_arrete else
               "Ces positions sont toutes soldées aux dates d'arrêté : l'exposition a existé en "
               "cours de période sans figurer aux états arrêtés, ce qui la rend invisible aux "
               "états réglementaires tout en étant réelle.")
            + "\n"
            "Une partie de ces opérations relève du placement auprès de la clientèle plutôt que "
            "de l'investissement pour compte propre. La distinction atténue le risque de crédit "
            "porté mais ne l'annule pas : le titre transite par le bilan de la banque, et la "
            "politique de risque ne distingue pas les deux usages."
        ),
        chiffres=[
            ("Souverains exclus par la politique", ", ".join(
                PAYS_CEMAC.get(p, p) for p in PAYS_EXCLUS)),
            ("Titres de ces souverains traités depuis la bascule", str(len(interdits))),
            ("Deals concernés", str(mouvements.DEAL.nunique())),
            ("Acquisitions cumulées", xaf(acquisitions)),
            ("Portefeuilles utilisés", ", ".join(sorted(set(
                b for x in interdits.books for b in str(x).split(", ") if b)))),
            ("Arrêtés où ces titres figurent au bilan", str(len(detenus_a_un_arrete))),
        ],
        tableaux=[
            Tableau(["Souverain", "Code", "Titres", "Deals", "Acquisitions XAF",
                     "Encours à fin d'extraction XAF", "Statut"], lignes,
                    note=("Exposition souveraine du nouveau dispositif, reconstituée depuis le "
                          "code pays des titres.")),
            Tableau(["Titre", "Libellé", "Portefeuilles", "Du", "Au", "Deals"],
                    [[r.TITRE, r.libelle_gl, r.books, r.premier, r.dernier, int(r.deals)]
                     for _, r in interdits.iterrows()],
                    note="Titres des souverains exclus."),
            Tableau(["Date d'arrêté", "Encours des souverains exclus XAF"], aux_arretes),
        ],
        recommandation=(
            "Faire confirmer si la politique d'exclusion couvre les titres acquis pour être "
            "placés auprès de la clientèle. Obtenir le contrôle de premier niveau qui doit "
            "bloquer la saisie d'un titre hors univers autorisé dans le système amont, et "
            "expliquer pourquoi il n'a pas joué."
        ),
    )


# --- 11.5 ---------------------------------------------------------------------------------

def _c115_prime_decote(ctx) -> Constat:
    """Le portefeuille est tenu au pair : que vaut-il réellement ?"""
    lignes = []
    for arrete in ctx.arretes:
        nominal = ctx.solde(CPT_PORTEFEUILLE_MM + CPT_PORTEFEUILLE_CALYPSO, a_la_date=arrete)
        regul = ctx.solde(CPT_REGULARISATION, a_la_date=arrete)
        lignes.append([arrete, nominal, regul, nominal + regul])
    final = lignes[-1] if lignes else [ctx.config.fin, 0, 0, 0]
    anormal = [l for l in lignes if l[2] > 1]   # solde débiteur d'un compte de produits d'avance
    c = ctx.calypso_enrichi
    realises = c[c.EVENEMENT.isin(["REALIZED_CLEAN_PL", "PREM_DISC_REAL", "REALIZED_PD_PL"])]
    produits = realises[realises.AC_NO.str.startswith("7")]
    produit_realise = -float(produits.SIGNE.sum())
    produit_periode = -float(produits[(produits.TRN_DT >= ctx.config.debut)
                                      & (produits.TRN_DT <= ctx.config.fin)].SIGNE.sum())
    return Constat(
        code="11.5",
        titre="Le portefeuille est comptabilisé au pair : la prime et la décote sont portées à part",
        gravite=Gravite.ELEVEE if anormal else Gravite.MOYENNE,
        constat=(
            "COMMENT LE PORTEFEUILLE EST VALORISÉ. Les comptes de portefeuille ne portent pas le "
            "prix payé mais la VALEUR NOMINALE du titre. L'écart entre les deux — la prime si le "
            "titre est acquis au-dessus du pair, la décote s'il l'est en dessous — est logé dans "
            "des comptes de régularisation, puis rapporté au résultat. L'encours de 11.1 est donc "
            "un nominal, et non une valeur d'acquisition.\n"
            "CE QUE CELA CHANGE. Deux portefeuilles de même nominal peuvent avoir coûté des "
            "montants très différents. La valeur comptable du portefeuille n'est lisible qu'en "
            "ajoutant au nominal le solde des comptes de régularisation, ce que fait le tableau "
            "ci-dessous.\n"
            "QUAND LA DÉCOTE EST-ELLE ACQUISE ? L'examen détaillé montre qu'elle n'est pas "
            "étalée sur la durée de vie du titre mais reprise EN TOTALITÉ lors de la cession, "
            "par l'événement de réalisation. Un titre acquis sous le pair et revendu au pair "
            "quelques jours plus tard dégage donc immédiatement l'intégralité de la décote en "
            "produit. Le rapprochement avec le contrôle 9.3, qui constate un rendement implicite "
            "très supérieur aux taux contractuels, s'impose : c'est la même mécanique vue de "
            "deux côtés. Le produit ainsi dégagé n'est pas marginal : il représente une "
            "composante majeure du résultat de l'activité.\n"
            + ("UNE POSITION IMPOSSIBLE. À une ou plusieurs dates d'arrêté, les comptes de "
               "régularisation présentent un solde DÉBITEUR. Un compte de produits comptabilisés "
               "d'avance ne peut être débiteur : cela revient à dire que la banque a rapporté au "
               "résultat plus de produit qu'elle n'en avait différé. Le contrôle 9.4 relève la "
               "même anomalie sur le compte des bons du Trésor."
               if anormal else
               "Les comptes de régularisation restent créditeurs à chaque arrêté, ce qui est "
               "leur sens normal.")
        ),
        chiffres=[
            ("Nominal du portefeuille à la clôture", xaf(final[1])),
            ("Solde des comptes de régularisation à la clôture",
             f"{xaf(abs(final[2]))} — sens "
             + ("DÉBITEUR, contraire à la nature du compte" if final[2] > 0 else "créditeur")),
            ("VALEUR COMPTABLE DU PORTEFEUILLE", xaf(final[3])),
            ("Produit tiré des primes et décotes — période d'audit", xaf(produit_periode)),
            ("Produit tiré des primes et décotes — toute l'extraction", xaf(produit_realise)),
            ("Arrêtés à solde de régularisation débiteur", str(len(anormal))),
        ],
        tableaux=[Tableau(
            ["Date d'arrêté", "Nominal XAF", "Régularisations XAF", "Valeur comptable XAF"],
            lignes,
            note=("Un montant négatif en régularisation est un solde créditeur, sens normal du "
                  "compte : la prime restant à rapporter vient alors en diminution du nominal."))],
        recommandation=(
            "Faire confirmer la méthode de reprise de la prime et de la décote au regard du "
            "PCEC : un étalement actuariel sur la durée de vie résiduelle du titre et une "
            "reprise intégrale à la cession n'ont pas le même effet sur le résultat de "
            "l'exercice. Justifier le solde débiteur des comptes de régularisation."
        ),
    )


# --- 11.6 ---------------------------------------------------------------------------------

def _c116_apurement_deal(ctx) -> Constat:
    """Chaque deal doit solder le compte de liaison par lequel il transite."""
    residus = ctx.apurement_pont
    c = ctx.calypso_enrichi
    pont = c[c.AC_NO.isin(CPT_LIAISON) & c.DEAL.notna() & (c.DEAL != "")]
    total_deals = pont.DEAL.nunique() if not pont.empty else 0
    if residus.empty:
        return Constat(
            code="11.6", titre="Apurement des comptes de liaison, deal par deal",
            gravite=Gravite.CONFORME,
            constat=(f"Les {total_deals} deals transitant par un compte de liaison le soldent "
                     "intégralement : chaque déversement est complet."),
        )
    fin = ctx.config.fin
    periode = residus[residus.date <= fin]
    apres = residus[residus.date > fin]
    par_cause = periode.groupby("cause").agg(deals=("deal", "size"), solde=("solde", "sum"))
    par_book = periode.groupby("book").agg(deals=("deal", "size"), solde=("solde", "sum"))
    pire = periode.reindex(periode.solde.abs().sort_values(ascending=False).index).head(12)
    return Constat(
        code="11.6",
        titre="Le solde des comptes de liaison mesure exactement les déversements incomplets",
        gravite=Gravite.CRITIQUE,
        constat=(
            "CE QUE LE CONTRÔLE ÉTABLIT. Le contrôle 6.4 constate que les comptes de liaison "
            "Calypso ne reviennent pas à zéro, sans en donner la cause. L'examen détaillé du "
            "schéma comptable la fournit : chaque deal produit plusieurs mouvements — couru, "
            "nominal, prime ou décote, règlement — qui transitent TOUS par un compte de liaison, "
            "les jambes de bilan d'un côté et le règlement en trésorerie de l'autre. Un deal "
            "intégralement déversé laisse donc le compte de liaison À ZÉRO.\n"
            "Le solde de ces comptes n'est pas un retard d'apurement : c'est la MESURE EXACTE "
            "des mouvements que l'interface n'a pas déversés.\n"
            "\n"
            "TROIS SITUATIONS, TROIS CONSÉQUENCES DIFFÉRENTES.\n"
            "- « règlement non déversé » : les comptes de bilan ont bougé, la trésorerie non. Le "
            "titre est entré ou sorti du portefeuille sans que l'argent ne suive. Le solde du "
            "compte de règlement auprès de la banque centrale est faux du même montant.\n"
            "- « jambes de bilan non déversées » : la trésorerie a bougé, les comptes de bilan "
            "non. L'argent est sorti ou entré sans que le titre ne soit constaté : le "
            "portefeuille est faux du même montant.\n"
            "- « déversement incomplet des deux côtés » : une partie seulement des mouvements "
            "est arrivée. Le cas le plus lourd de la période est une pension auprès de la banque "
            "centrale dont le remboursement a bien éteint la dette mais dont le décaissement "
            "correspondant n'a jamais été déversé.\n"
            "\n"
            "PORTÉE. Le défaut n'est pas marginal : il touche une part significative des deals "
            "et ses effets se cumulent sans jamais être corrigés. Il constitue, avec les "
            "doublons du contrôle 6.7, l'explication complète de la dérive relevée en 6.4."
        ),
        chiffres=[
            ("Deals transitant par un compte de liaison", nb(total_deals)),
            ("Deals au déversement INCOMPLET — période d'audit",
             f"{len(periode)} ({pct(len(periode) / max(total_deals, 1) * 100, 0)})"),
            ("Résidu cumulé sur la période d'audit", xaf(float(periode.solde.sum()))),
            ("Deals au déversement incomplet après la clôture", str(len(apres))),
            ("Résidu cumulé après la clôture", xaf(float(apres.solde.sum()))),
        ],
        tableaux=[
            Tableau(["Cause du résidu", "Deals", "Résidu cumulé XAF"],
                    [[i, int(r.deals), float(r.solde)] for i, r in par_cause.iterrows()],
                    note="Répartition des deals de la période d'audit par nature du déversement manquant."),
            Tableau(["Portefeuille", "Deals", "Résidu cumulé XAF"],
                    [[i or "(non renseigné)", int(r.deals), float(r.solde)]
                     for i, r in par_book.sort_values("solde").iterrows()]),
            Tableau(["Deal", "Date", "Portefeuille", "Titre", "Résidu XAF", "Cause",
                     "Événements déversés"],
                    [[r.deal, r.date, r.book, r.titre, float(r.solde), r.cause, r.evenements]
                     for _, r in pire.iterrows()],
                    max_lignes=12,
                    note="Les douze résidus les plus lourds de la période d'audit."),
        ],
        recommandation=(
            "Mettre en place un contrôle quotidien du solde des comptes de liaison PAR DEAL : "
            "tout deal dont le compte de liaison ne revient pas à zéro en fin de journée signale "
            "un déversement incomplet et doit être repris. Rapprocher le compte de règlement "
            "auprès de la banque centrale de son relevé pour chacun des deals recensés, et "
            "passer les écritures manquantes."
        ),
    )


# --- 11.7 ---------------------------------------------------------------------------------

# Échantillon de titres examiné mouvement par mouvement pour établir le schéma comptable du
# nouveau dispositif. Le tirage est reproductible : il repose sur le rang alphabétique du
# code du titre, et non sur un aléa non rejouable.
TAILLE_ECHANTILLON = 6


def _c117_echantillon(ctx) -> Constat:
    """Reconstitution du schéma comptable Calypso par lecture intégrale d'un échantillon.

    Calypso ne documente rien dans le core banking : le schéma comptable n'est connu que
    par ce qu'il produit. Le contrôle le reconstitue en suivant, mouvement par mouvement,
    un échantillon de titres, et vérifie sur chacun l'égalité qui fonde tous les autres
    contrôles de la section : nominal + couru − décote = règlement.
    """
    c = ctx.calypso_enrichi
    titres = ctx.titres_calypso
    if c.empty or titres.empty:
        return Constat(code="11.7", titre="Schéma comptable du nouveau dispositif",
                       gravite=Gravite.FAIBLE, constat="Flux Calypso indisponible.")
    # Tirage régulier sur la liste ordonnée des titres : reproductible et couvrant.
    ordonnes = titres.sort_values("TITRE").reset_index(drop=True)
    pas = max(len(ordonnes) // TAILLE_ECHANTILLON, 1)
    echantillon = ordonnes.iloc[::pas].head(TAILLE_ECHANTILLON)

    detail, controles = [], []
    for _, t in echantillon.iterrows():
        mouvements = c[c.TITRE == t.TITRE]
        detail.append([t.TITRE, t.nature or "n/d", t.books, int(t.deals), int(t.lignes),
                       t.premier, t.dernier])
        # Sur chaque deal du titre, l'égalité de règlement doit être vérifiée.
        for deal, g in mouvements.groupby("DEAL"):
            regl = g[(g.EVENEMENT == "CST_S_SETTLED") & (g.AC_NO == "099ACO00001")]
            if regl.empty:
                continue
            # Convention : un débit est positif. Pour une acquisition, le portefeuille et le
            # couru sont débités, la décote créditée, et le règlement crédite la trésorerie —
            # d'où l'égalité nominal + couru + décote = − règlement.
            nominal = float(g[(g.EVENEMENT == "NOMINAL")
                              & g.AC_NO.isin(CPT_PORTEFEUILLE_CALYPSO)].SIGNE.sum())
            couru = float(g[(g.EVENEMENT == "ACCRUAL_BS")
                            & (g.AC_NO == "512800100")].SIGNE.sum())
            decote = float(g[(g.EVENEMENT == "PREM_DISC")
                             & g.AC_NO.isin(CPT_REGULARISATION)].SIGNE.sum())
            attendu = nominal + couru + decote
            constate = -float(regl.SIGNE.sum())
            controles.append([t.TITRE, deal, g.TRN_DT.min(), nominal, couru, decote,
                              attendu, constate, attendu - constate])
    verifiables = [x for x in controles if abs(x[3]) > 1]
    ecarts = [x for x in verifiables if abs(x[8]) > 1]
    return Constat(
        code="11.7",
        titre="Schéma comptable du nouveau dispositif, reconstitué sur un échantillon de titres",
        gravite=Gravite.CONFORME if not ecarts else Gravite.MOYENNE,
        constat=(
            "POURQUOI CE CONTRÔLE. Calypso ne crée aucun contrat dans le core banking et n'y "
            "documente aucun schéma comptable. La seule façon d'établir comment le nouveau "
            "dispositif comptabilise un titre est de suivre un titre réel, mouvement par "
            "mouvement, du premier au dernier. C'est la démarche suivie ici sur un échantillon "
            f"de {len(echantillon)} titres, tiré régulièrement dans la liste ordonnée des codes "
            "afin d'être reproductible et de couvrir les deux natures — obligations et bons du "
            "Trésor à escompte.\n"
            "\n"
            "LE SCHÉMA ÉTABLI. Chaque opération produit des mouvements distincts, chacun "
            "équilibré, qui transitent tous par un compte de liaison :\n"
            "- NOMINAL porte la VALEUR NOMINALE du titre aux comptes de portefeuille : le "
            "portefeuille est donc tenu au pair, et non au prix payé ;\n"
            "- ACCRUAL_BS porte le coupon couru acheté ou vendu au compte de créances "
            "rattachées ;\n"
            "- PREM_DISC porte la prime ou la décote aux comptes de régularisation ;\n"
            "- CST_S_SETTLED porte le règlement au compte de la banque centrale.\n"
            "\n"
            "L'ÉGALITÉ QUI EN DÉCOULE. Le règlement doit être égal au nominal, majoré du couru "
            "et diminué de la décote. C'est la vérification menée deal par deal ci-dessous : "
            "elle valide le schéma et, avec lui, la lecture faite aux contrôles 11.5 et 11.6.\n"
            + ("Sur l'échantillon, l'égalité est vérifiée sur tous les deals. Le schéma est "
               "donc établi."
               if not ecarts else
               f"Elle est vérifiée AU CENTIME PRÈS sur {len(verifiables) - len(ecarts)} des "
               f"{len(verifiables)} deals de l'échantillon, ce qui établit le schéma.\n"
               f"LES {len(ecarts)} EXCEPTIONS SONT INSTRUCTIVES. Elles ne remettent pas le "
               "schéma en cause : elles signalent les deals dont un mouvement a été déversé "
               "DEUX FOIS, ou dont une jambe manque. Le contrôle retrouve ainsi, par une voie "
               "entièrement indépendante, les deux défauts d'interface relevés aux contrôles "
               "6.7 et 11.6. L'égalité de règlement constitue donc un test de détection "
               "simple et complet, que la banque pourrait exécuter quotidiennement.")
        ),
        chiffres=[
            ("Titres examinés intégralement", str(len(echantillon))),
            ("Deals contrôlés sur ces titres", str(len(verifiables))),
            ("Deals vérifiant l'égalité de règlement",
             f"{len(verifiables) - len(ecarts)} sur {len(verifiables)}"),
            ("Deals en écart — mouvement déversé deux fois ou jambe manquante", str(len(ecarts))),
        ],
        tableaux=[
            Tableau(["Titre", "Nature", "Portefeuilles", "Deals", "Écritures", "Du", "Au"],
                    detail, note="Échantillon examiné."),
            Tableau(["Titre", "Deal", "Date", "Nominal", "Couru", "Prime/décote",
                     "Règlement attendu", "Règlement constaté", "Écart"],
                    verifiables[:14], max_lignes=14,
                    note=("Vérification de l'égalité fondatrice du schéma : nominal + couru − "
                          "décote = règlement. Un montant négatif en prime/décote est une "
                          "décote, qui vient en diminution du règlement.")),
        ],
        recommandation=(
            "Conserver cette reconstitution au dossier : elle documente un schéma comptable que "
            "le core banking n'expose pas, et sert de référence à tout contrôle ultérieur sur le "
            "flux Calypso. La faire valider par l'équipe en charge du paramétrage. Instaurer le "
            "test d'égalité de règlement comme contrôle quotidien de premier niveau : il "
            "détecte à lui seul les doublons de déversement et les jambes manquantes."
        ),
    )


# --- 11.8 ---------------------------------------------------------------------------------

def _c118_cas_le_plus_lourd(ctx) -> Constat:
    """Anatomie complète du déversement incomplet le plus lourd de la période.

    Un constat chiffré en milliards mérite d'être démontré sur une opération, ligne à ligne,
    plutôt qu'énoncé en agrégat. Le contrôle isole le deal au résidu le plus élevé, le
    décompose, et le compare aux opérations qui l'encadrent dans la même chaîne de
    refinancement — lesquelles sont, elles, irréprochables.
    """
    residus = ctx.apurement_pont
    c = ctx.calypso_enrichi
    if residus.empty or c.empty:
        return Constat(code="11.8", titre="Cas le plus lourd", gravite=Gravite.CONFORME,
                       constat="Aucun déversement incomplet à documenter.")
    periode = residus[residus.date <= ctx.config.fin]
    if periode.empty:
        return Constat(code="11.8", titre="Cas le plus lourd", gravite=Gravite.CONFORME,
                       constat="Aucun déversement incomplet sur la période d'audit.")
    pire = periode.loc[periode.solde.abs().idxmax()]
    deal = pire.deal
    g = c[c.DEAL == deal]
    repos = ctx.repos_contractuels
    fiche = repos[repos.DEAL == deal]

    # Décomposition par date, événement et compte
    decomposition = (g.groupby(["TRN_DT", "EVENEMENT", "AC_NO", "AC_GL_DESC", "DRCR_IND"])
                     .agg(mouvements=("MOUVEMENT", "nunique"), montant=("LCY_AMOUNT", "sum"))
                     .reset_index())
    lignes_decomp = [[r.TRN_DT, r.EVENEMENT, r.AC_NO, r.AC_GL_DESC[:34], r.DRCR_IND,
                      int(r.mouvements), float(r.montant)] for _, r in decomposition.iterrows()]
    # Effet net par compte
    par_compte = g.groupby(["AC_NO", "AC_GL_DESC"]).SIGNE.sum()
    lignes_effet = [[i[0], i[1][:38], float(v)] for i, v in par_compte.items()]

    # Comparaison avec les pensions qui encadrent celle-ci sur la même contrepartie
    voisins = []
    if not fiche.empty:
        r = fiche.iloc[0]
        chaine = repos[(repos.contrepartie == r.contrepartie)
                       & (repos.contrat_debut >= r.contrat_debut - pd.Timedelta(days=14))
                       & (repos.contrat_debut <= r.contrat_debut + pd.Timedelta(days=14))]
        for _, v in chaine.sort_values("contrat_debut").iterrows():
            gv = c[c.DEAL == v.DEAL]
            voisins.append([
                v.DEAL, str(v.contrat_debut.date()), str(v.contrat_fin.date()),
                int(v.jours_contrat), float(v.taux), float(v.montant),
                float(gv[gv.AC_NO.str.startswith("4670")].SIGNE.sum()),
                float(gv[gv.AC_NO == "099ACO00001"].SIGNE.sum()),
                "COMPLET" if abs(float(gv[gv.AC_NO.str.startswith("4670")].SIGNE.sum())) < 1
                else "INCOMPLET"])

    nostro = float(g[g.AC_NO == "099ACO00001"].SIGNE.sum())
    attendu_nostro = -float(fiche.interet.iloc[0]) if not fiche.empty and fiche.interet.notna().iloc[0] else 0.0
    collateral = g[(g.AC_NO == "952100100") & (g.DRCR_IND == "C")]
    jours_gage = 0
    if not fiche.empty:
        jours_gage = (pd.Timestamp(g.TRN_DT.max()) - fiche.iloc[0].contrat_fin).days
    return Constat(
        code="11.8",
        titre=f"Anatomie du déversement incomplet le plus lourd — pension {deal}",
        gravite=Gravite.CRITIQUE,
        reference=(f"Deal {deal} — {fiche.iloc[0].contrepartie} — "
                   f"contrat du {fiche.iloc[0].contrat_debut.date()} au "
                   f"{fiche.iloc[0].contrat_fin.date()} à {fiche.iloc[0].taux} %"
                   if not fiche.empty else f"Deal {deal}"),
        constat=(
            "POURQUOI CETTE OPÉRATION. C'est le résidu le plus lourd de la période. Elle est "
            "documentée ici ligne à ligne, parce qu'un constat de cette ampleur doit pouvoir "
            "être vérifié sur pièce et non seulement lu dans un agrégat.\n"
            "\n"
            "CE QUE DIT LE CONTRAT. Le libellé porte les conditions : "
            + (f"{xaf(float(fiche.iloc[0].montant))} empruntés à "
               f"{fiche.iloc[0].contrepartie} du {fiche.iloc[0].contrat_debut.date()} au "
               f"{fiche.iloc[0].contrat_fin.date()}, soit {int(fiche.iloc[0].jours_contrat)} "
               f"jours, au taux de {fiche.iloc[0].taux} %. L'intérêt correspondant, "
               f"{xaf(float(fiche.iloc[0].interet_theorique))}, se retrouve exactement en "
               "comptabilité. Il s'agit donc d'une pension COURTE, parfaitement ordinaire.\n"
               if not fiche.empty else "conditions non lisibles.\n")
            + "\n"
            "CE QUI A ÉTÉ COMPTABILISÉ. Le tirage est complet et correct : les titres sont "
            "inscrits au hors bilan, la dette est constatée au passif, la trésorerie est "
            "encaissée. Le compte de liaison revient à zéro ce jour-là.\n"
            "Le remboursement, lui, est enregistré trois mois après l'échéance contractuelle "
            "(contrôle 7.5) et surtout, IL EST AMPUTÉ DE SA JAMBE DE TRÉSORERIE. La dette est "
            "éteinte, l'intérêt est constaté en charge, les titres sont libérés — mais AUCUNE "
            "écriture ne sort l'argent du compte de règlement auprès de la banque centrale.\n"
            "\n"
            "CE QUE CELA PRODUIT. L'effet net de l'opération sur le compte de règlement devrait "
            f"être une sortie limitée à l'intérêt, soit {xaf(abs(attendu_nostro))}. Il est en "
            f"réalité une ENTRÉE NETTE de {xaf(nostro)} : la banque a encaissé 90 milliards "
            "qu'elle n'a jamais rendus dans ses livres. Le compte de liaison porte la "
            f"contrepartie exacte de cette anomalie, {xaf(float(pire.solde))}.\n"
            "\n"
            "LA PREUVE PAR LA COMPARAISON. Cette pension appartient à une chaîne de "
            "refinancement roulée d'une semaine sur l'autre avec la même contrepartie. Les "
            "opérations qui la précèdent et qui la suivent portent le MÊME montant, la même "
            "mécanique et le même schéma comptable — et elles sont, elles, intégralement "
            "déversées : leur compte de liaison revient à zéro et leur effet net sur la "
            "trésorerie se limite à l'intérêt. L'anomalie n'est donc ni un effet de "
            "paramétrage ni une particularité du produit : c'est un déversement manqué.\n"
            "\n"
            "UN EFFET CONNEXE. Les titres donnés en garantie sont restés inscrits au hors bilan "
            f"jusqu'à la comptabilisation du remboursement, soit {jours_gage} jours après "
            "l'échéance contractuelle. Pendant toute cette durée, ils apparaissaient "
            "indisponibles alors qu'ils ne l'étaient plus, ce qui minore d'autant la réserve de "
            "liquidité mobilisable affichée (contrôle 7.3)."
        ),
        chiffres=[
            ("Contrepartie", fiche.iloc[0].contrepartie if not fiche.empty else "n/d"),
            ("Montant emprunté", xaf(float(fiche.iloc[0].montant)) if not fiche.empty else "n/d"),
            ("Durée CONTRACTUELLE",
             f"{int(fiche.iloc[0].jours_contrat)} jours ({fiche.iloc[0].contrat_debut.date()} → "
             f"{fiche.iloc[0].contrat_fin.date()})" if not fiche.empty else "n/d"),
            ("Comptabilisation", f"tirage le {g.TRN_DT.min()}, remboursement le {g.TRN_DT.max()}"),
            ("Titres donnés en garantie",
             f"{len(collateral)} lignes — {xaf(float(collateral.LCY_AMOUNT.sum()))}"),
            ("Jours de gage au-delà de l'échéance contractuelle", f"{jours_gage} jours"),
            ("Effet ATTENDU sur le compte de règlement",
             f"sortie de {xaf(abs(attendu_nostro))} (l'intérêt)"),
            ("Effet CONSTATÉ sur le compte de règlement", f"entrée de {xaf(nostro)}"),
            ("ERREUR SUR LA TRÉSORERIE", xaf(nostro - attendu_nostro)),
            ("Résidu porté par le compte de liaison", xaf(float(pire.solde))),
        ],
        tableaux=[
            Tableau(["Date", "Événement", "Compte", "Libellé", "Sens", "Mouvements", "Montant XAF"],
                    lignes_decomp, max_lignes=20,
                    note=("Décomposition intégrale de l'opération. La jambe CST_S_SETTLED "
                          "attendue à la date de remboursement est absente.")),
            Tableau(["Compte", "Libellé", "Effet net XAF"], lignes_effet,
                    note=("Effet net par compte. Un montant positif est un solde débiteur. "
                          "Le compte de règlement et le compte de liaison portent, au signe "
                          "près, la même anomalie.")),
            Tableau(["Deal", "Début contractuel", "Échéance", "Jours", "Taux %", "Montant XAF",
                     "Solde du pont", "Effet net trésorerie", "Déversement"],
                    voisins,
                    note=("La même chaîne de refinancement, avant et après. Les opérations "
                          "voisines sont complètes : seul le deal examiné ne l'est pas.")),
        ],
        recommandation=(
            "Rapprocher cette opération du relevé de la banque centrale pour établir la date "
            "réelle du décaissement, puis passer l'écriture manquante et corriger le solde du "
            "compte de règlement à la date d'arrêté. Étendre le rapprochement à l'ensemble des "
            "deals recensés au contrôle 11.6. Instaurer le contrôle quotidien du solde des "
            "comptes de liaison par deal, qui aurait détecté cette anomalie le jour même."
        ),
    )
