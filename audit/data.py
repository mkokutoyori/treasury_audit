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
CPT_BEAC = "099ACO00001"

COMPTES_TECHNIQUES = {
    "SYSTEM", "CALYPSOUSR", "ADMINUSER1", "FLEXSWITCH", "PRIMUSUSR",
    "PROCESSMAKER", "NEXTGENUSR", "ONLINETAXPAY", "MIGRATION",
}

DATE_BASCULE = "2025-06-16"


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
        return self.contrats.drop_duplicates("CONTRACT_REF_NO")

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
        sources = [self.ecritures_calypso, self.comptes_calypso, self.grand_livre]
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

    def solde(self, comptes, df: pd.DataFrame | None = None) -> float:
        """Solde net (débits moins crédits) d'un ou plusieurs comptes."""
        source = self.grand_livre if df is None else df
        if source.empty:
            return 0.0
        if isinstance(comptes, str):
            comptes = [comptes]
        return float(source[source.AC_NO.isin(comptes)].SIGNE.sum())
