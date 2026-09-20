"""Chargement des extractions et mise à disposition des jeux de données dérivés.

Toutes les colonnes d'identifiants (numéros de compte, références, codes) sont lues en
chaînes de caractères : les zéros de tête sont significatifs dans Flexcube.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from functools import cached_property

import pandas as pd

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Plan de comptes du périmètre titres -------------------------------------------------
CPT_PORTEFEUILLE_MM = ["511410100", "512200100"]        # dispositif Flexcube
CPT_PORTEFEUILLE_CALYPSO = ["512410100", "511210100"]   # dispositif Calypso
CPT_PORTEFEUILLE = CPT_PORTEFEUILLE_MM + CPT_PORTEFEUILLE_CALYPSO
CPT_COURUS_MM = "511800100"
CPT_COURUS_CALYPSO = "512800100"
CPT_REGULARISATION = ["472200106", "472200108"]
CPT_PRODUITS = ["733200100", "733400100", "734200100", "734400100"]
CPT_LIAISON = ["467000186", "467000188", "467000243"]
CPT_REPO_PASSIF = "552400100"
CPT_REPO_DETTES = "559000101"
CPT_REPO_CHARGE = "601100100"
CPT_COLLATERAL = ["952100100", "995000100"]
CPT_PROVISION = "591400100"
# Hors bilan de la clientèle : les titres placés auprès des clients y sont logés, le
# portefeuille propre de la banque restant au bilan (comptes 511 et 512).
CPT_CLIENTELE = ["938000100", "998000100"]
CPT_MIROIR = "467000243"
BOOK_CLIENTELE = "ABCM_FI.Sales"
BOOKS_TITRES = ["ABCM_FVOCI.Bond", "ABCM_FVOCI.Bills", "ABCM_BSB.Bond", "ABCM_FI.Sales"]

# Codes pays ISO des souverains CEMAC, tels qu'ils préfixent le code des titres, et
# mnémoniques d'émetteur rencontrés dans les libellés. Le rapprochement des deux permet de
# détecter les titres dont l'identification se contredit d'un champ à l'autre.
PAYS_CEMAC = {
    "CM": "CAMEROUN", "GA": "GABON", "CG": "CONGO", "GQ": "GUINEE EQUATORIALE",
    "TD": "TCHAD", "CF": "REPUBLIQUE CENTRAFRICAINE",
}
MNEMONIQUES_EMETTEUR = {
    "GOCM": "CM", "CMTB": "CM",
    "GOGA": "GA", "GATB": "GA",
    "GOCG": "CG", "GOCO": "CG", "GOCON": "CG",
    "GOGQ": "GQ", "GQTB": "GQ",
    "GOCF": "CF", "GOTD": "TD",
}
# Codes pays exclus du périmètre d'investissement, correspondants de SOUVERAINS_EXCLUS.
PAYS_EXCLUS = ["TD", "CF"]
CPT_BEAC = "099ACO00001"

# --- Deuxième vague d'extractions : comptes absents de la liste initiale des 41 -----------
# Comptes d'attente de la direction financière, où transitent les régularisations.
CPT_ATTENTE = ["466000107", "467000103"]
# Charge d'exploitation sur titres. Le PCEC la réserve aux commissions et frais de garde.
CPT_COMM_TITRES = "622000100"
# Titres remis en garantie des refinancements BEAC (classe 2 du PCEC) et comptes de
# conversion utilisés lors des reprises manuelles de portefeuille.
CPT_NANTISSEMENT = ["265110100", "265210100"]
CPT_CONVERSION = ["454000101", "454000106"]
# Comptes de résultat de change, extraits pour la phase ultérieure consacrée au change.
CPT_CHANGE_RESULTAT = ["623300100", "723300100"]

# Comptes que le PCEC destine à l'enregistrement d'une PENSION LIVRÉE : la dette au passif,
# les dettes rattachées, la charge d'intérêt et la commission. Aucun ne doit rester vide si
# la banque cède des titres avec engagement de rachat.
CPT_PENSION_PCEC = [
    "521300100", "521600100", "531000100", "532000100", "538000100", "539000100",
    "522100100", "522200100", "522300100", "522400100",
    "602000100", "702000100", "606200100", "706200100",
]
# Comptes de provision pour dépréciation du portefeuille de placement.
CPT_PROVISIONS_TITRES = ["591410100", "591420100", "591500100"]
# Hors bilan : titres à recevoir ou à livrer, et garanties du marché monétaire.
CPT_HORS_BILAN_TITRES = ["951100100", "953000100", "954000100", "955000100"]

# Liste exhaustive des comptes demandés lors de la deuxième extraction. Ceux qui n'y
# figurent pas en retour n'ont porté AUCUN mouvement : c'est en soi un résultat.
CPT_VAGUE2_DEMANDES = (
    CPT_PENSION_PCEC + CPT_PROVISIONS_TITRES + CPT_HORS_BILAN_TITRES
    + CPT_NANTISSEMENT + CPT_CONVERSION + CPT_ATTENTE + CPT_CHANGE_RESULTAT
    + ["511200100", "511420100", "511700100", "512420100", "467000187"]
)

# Nature attendue du solde de chaque compte du périmètre, au sens du PCEC.
# « debiteur » = compte d'actif, « crediteur » = compte de passif ou de produit,
# « neutre » = compte de passage ou de hors bilan, dont le sens n'est pas contraint.
NATURE_COMPTE = {
    "511210100": "debiteur", "511410100": "debiteur", "512200100": "debiteur",
    "512410100": "debiteur", "511800100": "debiteur", "512800100": "debiteur",
    "472200106": "crediteur", "472200108": "crediteur",   # produits comptabilisés d'avance
    "591400100": "crediteur",                             # provision pour dépréciation
    "552400100": "crediteur", "559000101": "crediteur",   # emprunt et dettes rattachées
    "733200100": "crediteur", "733400100": "crediteur",
    "734200100": "crediteur", "734400100": "crediteur",
    "725000100": "crediteur", "727000102": "crediteur", "729000125": "crediteur",
    "601100100": "debiteur", "625000105": "debiteur",     # charges
    "467000186": "neutre", "467000188": "neutre", "467000243": "neutre",
    "952100100": "neutre", "995000100": "neutre",
    "938000100": "neutre", "998000100": "neutre",
}

# Comptes applicatifs, non rattachés à une personne physique.
# ACCESSAFRIK est le compte de la plateforme Access Africa, le réseau de paiement propriétaire
# du groupe Access Bank : ce n'est pas un utilisateur nominatif.
COMPTES_TECHNIQUES = {
    "SYSTEM", "CALYPSOUSR", "ADMINUSER1", "FLEXSWITCH", "PRIMUSUSR",
    "PROCESSMAKER", "NEXTGENUSR", "ONLINETAXPAY", "MIGRATION", "ACCESSAFRIK",
}

# Comptes du périmètre titres, utilisés pour isoler les opérations de marché.
CPT_TITRES = [
    "511410100", "511210100", "512200100", "512410100", "511800100", "512800100",
    "472200106", "472200108", "552400100", "559000101", "952100100", "995000100",
    "467000186", "467000188", "591400100",
]

# Pays exclus du périmètre d'investissement par décision de la banque, en raison de leur
# profil de risque : la concentration sur les quatre autres souverains CEMAC est donc voulue.
SOUVERAINS_EXCLUS = ["TCHAD", "REPUBLIQUE CENTRAFRICAINE"]

DATE_BASCULE = "2025-06-16"

# Préfixe des références Flexcube produites par l'interface Calypso. Toute autre référence
# désigne une écriture saisie manuellement — correction, régularisation, reprise.
PREFIXE_INTERFACE = "099MNIP"


@dataclass
class Config:
    """Paramètres de la revue : période, seuils de matérialité, conventions."""

    debut: str = "2023-09-27"
    fin: str = "2026-06-30"
    seuil_materialite: float = 5_000_000        # XAF — en deçà, un écart n'est pas rapporté
    seuil_significatif: float = 100_000_000     # XAF — au-delà, la gravité est relevée
    base_jours: int = 365                       # convention de décompte des intérêts
    tolerance_couru: float = 0.10               # écart relatif toléré sur le recalcul des courus
    heure_ouverture: int = 7
    heure_fermeture: int = 20
    taux_min_plausible: float = 4.0             # %
    taux_max_plausible: float = 10.0            # %


@dataclass
class Contexte:
    """Accès paresseux et mis en cache aux jeux de données."""

    config: Config = field(default_factory=Config)
    avertissements: list[str] = field(default_factory=list)

    # --- chargement brut ------------------------------------------------------------------
    @staticmethod
    def _lire(motif: str, encodage: str = "utf-8-sig", date_fmt: str | None = None) -> pd.DataFrame:
        fichiers = sorted(glob.glob(os.path.join(RACINE, motif)))
        if not fichiers:
            return pd.DataFrame()
        morceaux = []
        for chemin in fichiers:
            bloc = pd.read_csv(
                chemin, dtype=str, keep_default_na=False, na_values=[""],
                encoding=encodage, low_memory=False,
            )
            bloc["__fichier"] = os.path.basename(chemin)
            morceaux.append(bloc)
        df = pd.concat(morceaux, ignore_index=True)
        for col in df.columns:
            if df[col].dtype == object or str(df[col].dtype).startswith("str"):
                df[col] = df[col].str.replace("\xa0", " ", regex=False).str.strip()
        for col in ("FCY_AMOUNT", "LCY_AMOUNT"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "TRN_DT" in df.columns:
            df["TRN_DT_d"] = pd.to_datetime(df.TRN_DT, format=date_fmt, errors="coerce")
            if date_fmt:  # ramène la date au format ISO pour des comparaisons homogènes
                df["TRN_DT"] = df.TRN_DT_d.dt.strftime("%Y-%m-%d")
        if "DRCR_IND" in df.columns and "LCY_AMOUNT" in df.columns:
            df["SIGNE"] = df.LCY_AMOUNT * df.DRCR_IND.map({"D": 1, "C": -1})
        return df

    @cached_property
    def contrats(self) -> pd.DataFrame:
        """Référentiel MM_CONTRACT, doublons conservés (ils font l'objet d'un contrôle)."""
        chemin = os.path.join(RACINE, "MM_CONTRACT.csv")
        if not os.path.exists(chemin):
            return pd.DataFrame()
        df = pd.read_csv(chemin, dtype=str, keep_default_na=False, na_values=[""])
        for col in ("AMOUNT", "LCY_AMOUNT", "MAIN_COMP_RATE", "MAIN_COMP_AMOUNT"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in ("BOOKING_DATE", "VALUE_DATE", "MATURITY_DATE", "TRADE_DATE"):
            df[col + "_d"] = pd.to_datetime(df[col], format="%d-%b-%y", errors="coerce")
        return df

    @cached_property
    def contrats_uniques(self) -> pd.DataFrame:
        """Référentiel dédoublonné sur la référence de contrat."""
        return self.contrats.drop_duplicates("CONTRACT_REF_NO")

    @cached_property
    def contrats_periode(self) -> pd.DataFrame:
        """Contrats comptabilisés pendant la période d'audit.

        La revue du référentiel porte sur les contrats bookés dans la période : ceux
        antérieurs relèvent des exercices déjà audités.
        """
        df = self.contrats_uniques
        return df[(df.BOOKING_DATE >= "") & (df.BOOKING_DATE_d >= self.config.debut)
                  & (df.BOOKING_DATE_d <= self.config.fin)]

    @cached_property
    def plan_de_comptes(self) -> pd.DataFrame:
        """Référentiel des comptes généraux, encodé en CP1252."""
        chemin = os.path.join(RACINE, "gltm_master.csv")
        if not os.path.exists(chemin):
            return pd.DataFrame(columns=["GL_CODE", "GL_DESC"])
        return pd.read_csv(chemin, dtype=str, keep_default_na=False, na_values=[""],
                           encoding="cp1252")

    def libelle_compte(self, code: str) -> str:
        """Libellé d'un compte général, depuis le plan de comptes ou les écritures."""
        plan = self.plan_de_comptes
        if not plan.empty:
            ligne = plan[plan.GL_CODE == code]
            if len(ligne):
                return str(ligne.GL_DESC.iloc[0]).strip()
        dans_ecritures = self.toutes_ecritures[self.toutes_ecritures.AC_NO == code]
        if len(dans_ecritures):
            return str(dans_ecritures.AC_GL_DESC.iloc[0]).strip()
        return ""

    @cached_property
    def deals_calypso(self) -> pd.DataFrame:
        """Référentiel des deals extrait directement de Calypso.

        Les dates y sont des numéros de série Excel (origine 30/12/1899).
        """
        chemin = os.path.join(RACINE, "extraction_from_calypso.csv")
        if not os.path.exists(chemin):
            return pd.DataFrame()
        df = pd.read_csv(chemin, dtype=str, keep_default_na=False, na_values=[""])
        df.columns = [c.strip() for c in df.columns]
        for col in ("Trade Date", "Trade Settle Date", "Entered Date"):
            if col in df.columns:
                df[col + "_d"] = pd.to_datetime(
                    pd.to_numeric(df[col], errors="coerce"), unit="D", origin="1899-12-30")
        for col in ("Quantity", "Trade Price"):
            if col in df.columns:
                df[col + "_n"] = pd.to_numeric(df[col], errors="coerce")
        df["DEAL"] = df["Trade Id"]
        return df

    # --- titres du nouveau dispositif -----------------------------------------------------
    # Calypso ne crée aucun contrat dans le core banking : le seul signalement d'un titre
    # est le libellé de ses écritures. On en reconstitue un référentiel, en le rapprochant
    # du libellé porté par l'extraction Calypso elle-même.

    @staticmethod
    def _decoder_libelle(libelle: str) -> dict:
        """Décompose un libellé de titre Calypso.

        Deux formes coexistent :
          BondGOGA/GA2K00000249/XAF/0D/08/15/2029/6.5%   (obligation)
          Discount/CMTB/CM1300000849/XAF/04/22/2026      (bon du Trésor, sans coupon)
        """
        texte = str(libelle or "")
        morceaux = texte.split("/")
        if not morceaux or not morceaux[0]:
            return {}
        tete = morceaux[0]
        if tete.startswith("Discount"):
            nature, mnemo = "Discount", (morceaux[1] if len(morceaux) > 1 else "")
            reste = morceaux[2:]
        elif tete.startswith("Bond"):
            nature, mnemo = "Bond", tete[4:]
            reste = morceaux[1:]
        else:
            return {}
        code = reste[0] if reste else ""
        devise = reste[1] if len(reste) > 1 else ""
        # Le taux, quand il existe, est le dernier morceau et se termine par %.
        taux = morceaux[-1] if morceaux[-1].endswith("%") else ""
        dates = [m for m in morceaux if m.isdigit() and len(m) == 2]
        annee = next((m for m in morceaux if m.isdigit() and len(m) == 4), "")
        return {"nature": nature, "mnemo": mnemo, "code": code, "devise": devise,
                "taux": taux, "jour_mois": dates[-2:], "annee": annee}

    @cached_property
    def titres_calypso(self) -> pd.DataFrame:
        """Un titre par ligne, vu depuis le grand livre et depuis le référentiel Calypso."""
        c = self.calypso_enrichi
        if c.empty:
            return pd.DataFrame()
        vus = c[c.TITRE.notna() & (c.TITRE != "")]
        if vus.empty:
            return pd.DataFrame()
        base = (vus.groupby("TITRE")
                .agg(libelle_gl=("LIBELLE_TITRE", "first"),
                     lignes=("LCY_AMOUNT", "size"),
                     deals=("DEAL", "nunique"),
                     premier=("TRN_DT", "min"),
                     dernier=("TRN_DT", "max"),
                     books=("BOOK", lambda s: ", ".join(sorted(set(s.dropna()))))))
        # Libellé porté par l'extraction Calypso, indexé sur le code du titre
        ref = {}
        deals = self.deals_calypso
        if not deals.empty and "Product Description" in deals.columns:
            for texte in deals["Product Description"].dropna().unique():
                decode = self._decoder_libelle(texte)
                if decode.get("code"):
                    ref[decode["code"]] = texte
        base["libelle_ref"] = [ref.get(i, "") for i in base.index]
        base["pays_code"] = [str(i)[:2] for i in base.index]
        decodes = [self._decoder_libelle(l) for l in base.libelle_gl]
        base["nature"] = [d.get("nature", "") for d in decodes]
        base["mnemo"] = [d.get("mnemo", "") for d in decodes]
        base["pays_mnemo"] = [MNEMONIQUES_EMETTEUR.get(d.get("mnemo", ""), "") for d in decodes]
        base["taux"] = [d.get("taux", "") for d in decodes]
        return base.reset_index()

    @cached_property
    def repos_contractuels(self) -> pd.DataFrame:
        """Caractéristiques CONTRACTUELLES des pensions, extraites de leur libellé.

        Le libellé d'une écriture de pension porte, après le titre donné en garantie, les
        dates de début et de fin du contrat et le taux :
            Repo-(BondGOGQ/GQ2J00000057/XAF/0D/07/03/2028/7%)12/18/2025/12/26/2025/5.05000
        Les dates y sont au format mois/jour/année, comme partout dans le flux déversé.
        C'est la seule source de la DURÉE CONTRACTUELLE : les dates de comptabilisation ne
        la donnent pas, une opération pouvant être enregistrée bien après son dénouement.
        """
        t = self.toutes_ecritures
        if t.empty or "DESCRIPTION" not in t.columns:
            return pd.DataFrame()
        repo = t[t.DESCRIPTION.fillna("").str.contains(r"Repo-\(", regex=True)].copy()
        if repo.empty:
            return pd.DataFrame()
        extrait = repo.DESCRIPTION.str.extract(
            r"\)(\d{2}/\d{2}/\d{4})/(\d{2}/\d{2}/\d{4})/([\d.]+)")
        repo["contrat_debut"] = pd.to_datetime(extrait[0], format="%m/%d/%Y", errors="coerce")
        repo["contrat_fin"] = pd.to_datetime(extrait[1], format="%m/%d/%Y", errors="coerce")
        repo["taux"] = pd.to_numeric(extrait[2], errors="coerce")
        repo["DEAL"] = repo.DESCRIPTION.str.extract(r"^\|(\d+)\|")[0]
        repo["EVENEMENT"] = repo.DESCRIPTION.str.split("|").str[3]
        # Le principal est porté par l'événement de dépôt sur le compte d'emprunt.
        principal = repo[(repo.EVENEMENT == "PRINCIPAL_DEPOSIT") & (repo.AC_NO == CPT_REPO_PASSIF)]
        interet = (repo[(repo.EVENEMENT == "INTEREST") & (repo.AC_NO == CPT_REPO_CHARGE)]
                   .groupby("DEAL").LCY_AMOUNT.sum())
        collateral = (repo[repo.AC_NO == CPT_COLLATERAL[0]]
                      .groupby(["DEAL", "DRCR_IND"]).LCY_AMOUNT.sum().unstack(fill_value=0))
        d = principal.groupby("DEAL").agg(
            contrat_debut=("contrat_debut", "min"), contrat_fin=("contrat_fin", "max"),
            taux=("taux", "max"), montant=("LCY_AMOUNT", "max"),
            booking_debut=("TRN_DT", "min"), booking_fin=("TRN_DT", "max"),
            contrepartie=("DESCRIPTION", lambda s: str(s.iloc[0]).split("|")[5]))
        d["jours_contrat"] = (d.contrat_fin - d.contrat_debut).dt.days
        d["retard_remboursement"] = (pd.to_datetime(d.booking_fin) - d.contrat_fin).dt.days
        d["interet"] = interet
        d["interet_theorique"] = d.montant * d.taux / 100 * d.jours_contrat / 360
        d["ecart_interet"] = d.interet.fillna(0) - d.interet_theorique
        if not collateral.empty:
            d["collateral"] = collateral.get("C", 0)
        return d.reset_index()

    @cached_property
    def apurement_pont(self) -> pd.DataFrame:
        """Solde résiduel de chaque deal sur les comptes de liaison Calypso.

        Le déversement d'un deal se décompose en mouvements, chacun équilibré, qui
        transitent TOUS par un compte de liaison : les jambes de bilan d'un côté, le
        règlement en trésorerie de l'autre. Un deal intégralement déversé laisse donc le
        compte de liaison à zéro. Le solde résiduel mesure exactement ce qui manque.
        """
        c = self.calypso_enrichi
        if c.empty:
            return pd.DataFrame()
        pont = c[c.AC_NO.isin(CPT_LIAISON) & c.DEAL.notna() & (c.DEAL != "")]
        if pont.empty:
            return pd.DataFrame()
        lignes = []
        for deal, g in pont.groupby("DEAL"):
            solde = float(g.SIGNE.sum())
            if abs(solde) < 1:
                continue
            reglement = g[g.EVENEMENT == "CST_S_SETTLED"]
            bilan = g[g.EVENEMENT != "CST_S_SETTLED"]
            if reglement.empty:
                cause = "règlement non déversé"
            elif bilan.empty:
                cause = "jambes de bilan non déversées"
            else:
                cause = "déversement incomplet des deux côtés"
            tout = c[c.DEAL == deal]
            lignes.append({
                "deal": deal, "solde": solde, "cause": cause,
                "date": tout.TRN_DT.min(), "book": tout.BOOK.dropna().iloc[0]
                if len(tout.BOOK.dropna()) else "",
                "titre": tout.TITRE.dropna().iloc[0] if len(tout.TITRE.dropna()) else "",
                "evenements": ", ".join(sorted(set(tout.EVENEMENT.dropna()))),
            })
        return pd.DataFrame(lignes)

    @cached_property
    def ecritures_mm(self) -> pd.DataFrame:
        return self._lire("money_market_transactions.csv")

    @cached_property
    def ecritures_calypso(self) -> pd.DataFrame:
        return self._lire("calypso_transactions_*.csv")

    @cached_property
    def comptes_cles(self) -> pd.DataFrame:
        return self._lire("transaction_history_of_key_account_*.csv")

    @cached_property
    def comptes_calypso(self) -> pd.DataFrame:
        return self._lire("calypson_key_account_*.csv")

    @cached_property
    def courus(self) -> pd.DataFrame:
        """Historique complet du compte 511800100 (encodage CP1252, dates JJ-MMM-AA)."""
        return self._lire("creance_rattaché.csv", encodage="cp1252", date_fmt="%d-%b-%y")

    @cached_property
    def grand_livre(self) -> pd.DataFrame:
        """Les 41 comptes de trésorerie, tous modules — extraction de référence."""
        return self._lire("final_key_accounts_*.csv")

    @cached_property
    def comptes_complementaires(self) -> pd.DataFrame:
        """Deuxième vague d'extractions — comptes absents de la liste initiale des 41.

        Trois fichiers, encodés en CP1252, dates au format JJ-MMM-AA. Deux d'entre eux se
        recouvrent partiellement : le compte d'attente 466000107 y figure deux fois, et le
        nostro BEAC ainsi que les deux comptes de pont Calypso y sont déjà couverts par les
        extractions précédentes. On dédoublonne, puis on écarte ces trois comptes pour que
        les contrôles antérieurs restent établis sur une seule et même source.
        """
        morceaux = [
            self._lire("099ACO00001.csv", encodage="cp1252", date_fmt="%d-%b-%y"),
            self._lire("32_accounts.csv", encodage="cp1252", date_fmt="%d-%b-%y"),
            self._lire("additional key account.csv", encodage="cp1252", date_fmt="%d-%b-%y"),
        ]
        morceaux = [df for df in morceaux if not df.empty]
        if not morceaux:
            return pd.DataFrame()
        df = pd.concat(morceaux, ignore_index=True)
        df["STMT_DT_d"] = pd.to_datetime(df.STMT_DT, format="%d-%b-%y", errors="coerce")
        df["STMT_DT"] = df.STMT_DT_d.dt.strftime("%Y-%m-%d")
        # Le recouvrement entre les deux fichiers porte sur des comptes ENTIERS, non sur des
        # lignes isolées. On ne peut donc pas dédoublonner ligne à ligne : une écriture peut
        # légitimement porter deux jambes identiques sur le même compte (quatre titres nantis
        # le même jour, dont deux de même nominal). Pour chaque compte, on retient la source
        # qui en porte le plus de lignes, et l'on écarte les autres.
        garde = []
        for compte, bloc in df.groupby("AC_NO"):
            meilleur = bloc["__fichier"].value_counts().idxmax()
            garde.append(bloc[bloc["__fichier"] == meilleur])
        df = pd.concat(garde, ignore_index=True)
        return df[~df.AC_NO.isin([CPT_BEAC] + CPT_LIAISON)].reset_index(drop=True)

    def historique_compte(self, code: str, dans_periode: bool = True) -> pd.DataFrame:
        """Mouvements d'un compte de la deuxième vague, triés dans le temps."""
        df = self.comptes_complementaires
        if df.empty:
            return df
        df = df[df.AC_NO == code]
        if dans_periode:
            df = df[(df.TRN_DT >= self.config.debut) & (df.TRN_DT <= self.config.fin)]
        return df.sort_values("TRN_DT")

    def solde_a(self, code: str, date: str) -> float:
        """Solde d'un compte de la deuxième vague à une date, signe débiteur positif."""
        df = self.comptes_complementaires
        if df.empty:
            return 0.0
        return float(df[(df.AC_NO == code) & (df.TRN_DT <= date)].SIGNE.sum())

    # --- jeux de données dérivés ----------------------------------------------------------
    @cached_property
    def toutes_ecritures(self) -> pd.DataFrame:
        """Union dédoublonnée de toutes les sources, pour les contrôles transverses."""
        sources = {
            "MM": self.ecritures_mm,
            "CALYPSO": self.ecritures_calypso,
            "COMPTES_CLES": self.comptes_cles,
            "COMPTES_CALYPSO": self.comptes_calypso,
            "GRAND_LIVRE": self.grand_livre,
        }
        morceaux = [df.assign(SOURCE=nom) for nom, df in sources.items() if not df.empty]
        if not morceaux:
            return pd.DataFrame()
        union = pd.concat(morceaux, ignore_index=True)
        return union.drop_duplicates(
            subset=["TRN_REF_NO", "AC_NO", "DRCR_IND", "LCY_AMOUNT", "STMT_DT"]
        )

    @cached_property
    def calypso_enrichi(self) -> pd.DataFrame:
        """Écritures Calypso avec le champ DESCRIPTION décodé.

        Format à 9 séparateurs : |TradeId|TransferId|Événement|Type|Émetteur|Book|Titre|Libellé|Commentaire
        """
        # Le compte de règlement auprès de la banque centrale ne figure ni au grand livre des
        # 41 comptes clés ni dans l'extraction Calypso : certaines de ses jambes ne vivent que
        # dans l'extraction des comptes clés. L'omettre reviendrait à analyser des opérations
        # amputées de leur jambe de trésorerie.
        sources = [self.ecritures_calypso, self.comptes_calypso, self.comptes_cles,
                   self.grand_livre]
        morceaux = [df for df in sources if not df.empty]
        if not morceaux:
            return pd.DataFrame()
        df = pd.concat(morceaux, ignore_index=True).drop_duplicates(
            subset=["TRN_REF_NO", "AC_NO", "DRCR_IND", "LCY_AMOUNT", "STMT_DT"]
        )
        desc = df.DESCRIPTION.fillna("")
        df = df[desc.str.count(r"\|") == 9].copy()
        parts = df.DESCRIPTION.str.split("|")
        df["DEAL"] = parts.str[1]
        df["MOUVEMENT"] = parts.str[2]
        df["EVENEMENT"] = parts.str[3]
        df["TYPE_PRODUIT"] = parts.str[4]
        df["EMETTEUR"] = parts.str[5]
        df["BOOK"] = parts.str[6]
        df["TITRE"] = parts.str[7]
        df["LIBELLE_TITRE"] = parts.str[8]
        df["COMMENTAIRE"] = parts.str[9]
        return df

    def dans_periode(self, df: pd.DataFrame, colonne: str = "TRN_DT") -> pd.DataFrame:
        """Restreint un jeu de données à la période d'audit."""
        if df.empty or colonne not in df.columns:
            return df
        return df[(df[colonne] >= self.config.debut) & (df[colonne] <= self.config.fin)]

    # --- soldes ---------------------------------------------------------------------------
    # L'extraction des comptes de trésorerie couvre l'historique INTÉGRAL de chaque compte,
    # depuis sa première écriture. Le solde d'ouverture est donc nul par construction et le
    # cumul des mouvements constitue le solde exact à toute date.

    def solde(self, comptes, a_la_date: str | None = None,
              df: pd.DataFrame | None = None) -> float:
        """Solde d'un ou plusieurs comptes à une date donnée (par défaut : à la fin)."""
        source = self.grand_livre if df is None else df
        if source.empty:
            return 0.0
        if isinstance(comptes, str):
            comptes = [comptes]
        sous = source[source.AC_NO.isin(comptes)]
        if a_la_date:
            sous = sous[sous.TRN_DT <= a_la_date]
        return float(sous.SIGNE.sum())

    def serie_solde(self, comptes, frequence: str | None = None) -> pd.Series:
        """Évolution du solde dans le temps, éventuellement rééchantillonnée.

        `frequence` suit les alias pandas : "ME" fin de mois, "QE" fin de trimestre,
        "YE" fin d'année. Sans fréquence, la série est datée à chaque jour de mouvement.
        """
        if isinstance(comptes, str):
            comptes = [comptes]
        sous = self.grand_livre[self.grand_livre.AC_NO.isin(comptes)]
        if sous.empty:
            return pd.Series(dtype=float)
        quotidien = sous.groupby("TRN_DT_d").SIGNE.sum().sort_index().cumsum()
        if frequence:
            return quotidien.resample(frequence).last().ffill()
        return quotidien

    def soldes_aux_arretes(self, comptes, dates: list[str] | None = None) -> dict[str, float]:
        """Solde d'un ou plusieurs comptes à chaque date d'arrêté."""
        return {d: self.solde(comptes, a_la_date=d) for d in (dates or self.arretes)}

    @property
    def arretes(self) -> list[str]:
        """Dates d'arrêté comprises dans la période d'audit, annuelles et semestrielles."""
        debut, fin = self.config.debut, self.config.fin
        candidats = []
        for annee in range(int(debut[:4]), int(fin[:4]) + 1):
            candidats += [f"{annee}-06-30", f"{annee}-12-31"]
        return [d for d in candidats if debut <= d <= fin]

    @cached_property
    def mouvements_dupliques(self) -> pd.DataFrame:
        """Mouvements Calypso déversés plusieurs fois dans le grand livre.

        Chaque mouvement Calypso porte un identifiant de transfert unique. S'il apparaît sous
        plusieurs références Flexcube, pour le même compte, le même sens et le même montant,
        l'interface a déversé deux fois la même opération.
        """
        c = self.calypso_enrichi
        if c.empty:
            return pd.DataFrame()
        # Seules les écritures PRODUITES PAR L'INTERFACE peuvent constituer un doublon
        # d'interface. Les écritures manuelles de régularisation reprennent les mêmes
        # comptes et les mêmes montants : les inclure ferait passer une correction pour
        # l'anomalie qu'elle corrige.
        c = c[c.TRN_REF_NO.str.startswith(PREFIXE_INTERFACE, na=False)]
        if c.empty:
            return pd.DataFrame()
        c = c.assign(cle=c.DEAL + "|" + c.MOUVEMENT + "|" + c.AC_NO + "|" + c.DRCR_IND)
        groupes = c.groupby("cle").agg(
            occurrences=("LCY_AMOUNT", "size"),
            montants_distincts=("LCY_AMOUNT", "nunique"),
            references=("TRN_REF_NO", "nunique"),
            montant=("LCY_AMOUNT", "max"),
            date=("TRN_DT", "min"),
            compte=("AC_NO", "first"),
            libelle=("AC_GL_DESC", "first"),
            sens=("DRCR_IND", "first"),
            deal=("DEAL", "first"),
            mouvement=("MOUVEMENT", "first"),
        )
        doublons = groupes[(groupes.occurrences > 1)
                           & (groupes.montants_distincts == 1)
                           & (groupes.references > 1)].copy()
        doublons["impact"] = doublons.montant * doublons.sens.map({"D": 1, "C": -1})
        return doublons

    @cached_property
    def doublons_par_mouvement(self) -> pd.DataFrame:
        """Les doublons vus au niveau du MOUVEMENT, et non de la jambe d'écriture.

        Un mouvement Calypso produit plusieurs jambes — deux le plus souvent, jusqu'à quatre.
        Les compter séparément revient à compter le même mouvement autant de fois qu'il a de
        jambes, et à additionner un débit et son crédit comme s'ils étaient deux anomalies
        distinctes. Le volume dupliqué se mesure donc UNE FOIS PAR MOUVEMENT.

        Le contrôle recherche en outre, pour chaque mouvement dupliqué, une écriture de
        correction ultérieure : les références de l'interface commencent par « 099MNIP », les
        écritures manuelles non. Un mouvement dont le doublon a été contre-passé ne fausse
        plus les comptes, et ne doit pas être présenté comme s'il les faussait encore.
        """
        legs = self.mouvements_dupliques
        c = self.calypso_enrichi
        if legs.empty or c.empty:
            return pd.DataFrame()
        travail = c.assign(cle2=c.DEAL + "|" + c.MOUVEMENT)
        lignes = []
        for cle in sorted(set(legs.deal + "|" + legs.mouvement)):
            g = travail[travail.cle2 == cle]
            interface = g[g.TRN_REF_NO.str.startswith(PREFIXE_INTERFACE, na=False)]
            correction = g[~g.TRN_REF_NO.str.startswith(PREFIXE_INTERFACE, na=False)]
            # Résidu : pour chaque compte, l'écart entre l'effet net constaté et l'effet
            # d'un déversement unique. Zéro signale un doublon effectivement corrigé.
            residu = 0.0
            for compte, gg in g.groupby("AC_NO"):
                premiere = gg[gg.TRN_REF_NO.str.startswith(PREFIXE_INTERFACE, na=False)]
                if premiere.empty:
                    continue
                attendu = float(premiere.iloc[0].LCY_AMOUNT) * (
                    1 if premiere.iloc[0].DRCR_IND == "D" else -1)
                residu = max(residu, abs(float(gg.SIGNE.sum()) - attendu))
            lignes.append({
                "mouvement": cle,
                "deal": g.DEAL.iloc[0],
                "date": interface.TRN_DT.max() if len(interface) else g.TRN_DT.max(),
                "montant": float(interface.LCY_AMOUNT.max()) if len(interface)
                else float(g.LCY_AMOUNT.max()),
                "jambes": int(len(g)),
                "evenement": g.EVENEMENT.dropna().iloc[0] if len(g.EVENEMENT.dropna()) else "",
                "book": g.BOOK.dropna().iloc[0] if len(g.BOOK.dropna()) else "",
                "corrige": bool(len(correction)),
                "date_correction": correction.TRN_DT.max() if len(correction) else "",
                "residu": residu,
                "comptes": ", ".join(sorted(set(g.AC_NO))),
            })
        return pd.DataFrame(lignes)

    def historique_complet(self) -> pd.DataFrame:
        """Éléments de preuve de la complétude de l'historique, compte par compte.

        Un compte dont le solde revient exactement à zéro sur toute sa vie, ou dont le solde
        ne contredit jamais sa nature comptable, atteste que son historique est intégral.
        """
        lignes = []
        for compte, groupe in self.grand_livre.groupby("AC_NO"):
            groupe = groupe.sort_values(["TRN_DT", "STMT_DT"])
            cumul = groupe.SIGNE.cumsum()
            nature = NATURE_COMPTE.get(compte, "neutre")
            if nature == "debiteur":
                contradictions = int((cumul < -1).sum())
            elif nature == "crediteur":
                contradictions = int((cumul > 1).sum())
            else:
                contradictions = 0
            lignes.append({
                "compte": compte,
                "libelle": groupe.AC_GL_DESC.iloc[0],
                "nature": nature,
                "debut": groupe.TRN_DT.min(),
                "fin": groupe.TRN_DT.max(),
                "ecritures": len(groupe),
                "solde_final": float(cumul.iloc[-1]),
                "jours_contradictoires": contradictions,
                "part_contradictoire": contradictions / len(cumul) * 100,
            })
        return pd.DataFrame(lignes).set_index("compte")
