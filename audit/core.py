"""Socle du moteur d'audit : niveaux de gravité, constats, sections et rendu du rapport."""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Sequence

LARGEUR = 100


class Gravite:
    """Niveaux de gravité, du plus grave au plus anodin.

    L'ordre déclaré ici pilote le tri du récapitulatif final.
    """

    CRITIQUE = "CRITIQUE"
    ELEVEE = "ELEVEE"
    MOYENNE = "MOYENNE"
    FAIBLE = "FAIBLE"
    CONFORME = "CONFORME"

    ORDRE = [CRITIQUE, ELEVEE, MOYENNE, FAIBLE, CONFORME]

    @classmethod
    def rang(cls, niveau: str) -> int:
        return cls.ORDRE.index(niveau) if niveau in cls.ORDRE else len(cls.ORDRE)


@dataclass
class Tableau:
    """Tableau de détail joint à un constat."""

    entetes: Sequence[str]
    lignes: Sequence[Sequence[object]]
    note: str = ""
    max_lignes: int = 15

    def rendu(self) -> list[str]:
        if not self.lignes:
            return []
        lignes = [[_fmt(c) for c in ligne] for ligne in self.lignes]
        tronque = len(lignes) > self.max_lignes
        visibles = lignes[: self.max_lignes]
        largeurs = [
            max(len(str(self.entetes[i])), max((len(l[i]) for l in visibles), default=0))
            for i in range(len(self.entetes))
        ]
        sep = "  "
        out = [sep.join(str(h).ljust(largeurs[i]) for i, h in enumerate(self.entetes))]
        out.append(sep.join("-" * w for w in largeurs))
        for l in visibles:
            out.append(sep.join(l[i].ljust(largeurs[i]) for i in range(len(largeurs))))
        if tronque:
            out.append(f"... et {len(lignes) - self.max_lignes} autre(s) ligne(s)")
        if self.note:
            out.append(self.note)
        return out


def _fmt(valeur: object) -> str:
    """Formate une cellule : les nombres sont alignés et séparés par des espaces fines."""
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, int):
        return f"{valeur:,}".replace(",", " ")
    if isinstance(valeur, float):
        if valeur != valeur:  # NaN
            return ""
        if abs(valeur - round(valeur)) < 1e-9 and abs(valeur) >= 1000:
            return f"{int(round(valeur)):,}".replace(",", " ")
        return f"{valeur:,.2f}".replace(",", " ")
    return str(valeur)


def xaf(montant: float) -> str:
    """Montant en XAF, formaté pour le rapport."""
    return f"{montant:,.0f} XAF".replace(",", " ")


@dataclass
class Constat:
    """Un constat d'audit : ce qui a été testé, ce qui a été trouvé, ce qu'il faut faire."""

    code: str
    titre: str
    gravite: str
    constat: str
    chiffres: list[tuple[str, str]] = field(default_factory=list)
    tableaux: list[Tableau] = field(default_factory=list)
    recommandation: str = ""
    reference: str = ""

    @property
    def anomalie(self) -> bool:
        return self.gravite != Gravite.CONFORME

    def rendu(self) -> list[str]:
        out = [f"[{self.code}] {self.titre}", f"  Gravité : {self.gravite}"]
        if self.reference:
            out.append(f"  Référence : {self.reference}")
        out.append("")
        for ligne in _paragraphe(self.constat, indent="  "):
            out.append(ligne)
        if self.chiffres:
            out.append("")
            largeur = max(len(l) for l, _ in self.chiffres)
            for label, valeur in self.chiffres:
                out.append(f"    {label.ljust(largeur)} : {valeur}")
        for tableau in self.tableaux:
            rendu = tableau.rendu()
            if rendu:
                out.append("")
                out.extend("    " + l for l in rendu)
        if self.recommandation:
            out.append("")
            out.append("  Recommandation :")
            out.extend(_paragraphe(self.recommandation, indent="    "))
        return out


def _paragraphe(texte: str, indent: str = "") -> list[str]:
    lignes: list[str] = []
    for bloc in texte.strip().split("\n"):
        bloc = bloc.rstrip()
        if not bloc:
            lignes.append("")
            continue
        puce = bloc.lstrip().startswith(("- ", "* ", "› "))
        sous_indent = indent + ("  " if puce else "")
        lignes.extend(
            textwrap.wrap(
                bloc.strip(),
                width=LARGEUR,
                initial_indent=indent,
                subsequent_indent=sous_indent,
            )
            or [indent]
        )
    return lignes


@dataclass
class Section:
    """Une section du rapport : un thème de revue et les constats qui en découlent."""

    numero: int
    titre: str
    objet: str = ""
    constats: list[Constat] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)

    def ajouter(self, constat: Constat) -> None:
        self.constats.append(constat)

    @property
    def anomalies(self) -> list[Constat]:
        return [c for c in self.constats if c.anomalie]

    def rendu(self) -> list[str]:
        out = ["", "=" * LARGEUR, f"SECTION {self.numero} — {self.titre.upper()}", "=" * LARGEUR]
        if self.objet:
            out.append("")
            out.extend(_paragraphe(self.objet))
        conformes = [c for c in self.constats if not c.anomalie]
        out.append("")
        out.append(
            f"  {len(self.constats)} contrôle(s) exécuté(s) — "
            f"{len(self.anomalies)} anomalie(s), {len(conformes)} sans anomalie."
        )
        for constat in sorted(self.anomalies, key=lambda c: (Gravite.rang(c.gravite), c.code)):
            out.append("")
            out.append("-" * LARGEUR)
            out.extend(constat.rendu())
        if conformes:
            out.append("")
            out.append("-" * LARGEUR)
            out.append("CONTRÔLES SANS ANOMALIE")
            out.append("")
            for c in sorted(conformes, key=lambda c: c.code):
                out.append(f"  [{c.code}] {c.titre}")
                for ligne in _paragraphe(c.constat, indent="      "):
                    out.append(ligne)
                # Un contrôle sans anomalie peut porter une information utile : encours aux
                # dates d'arrêté, éléments de preuve. On la restitue.
                if c.chiffres:
                    out.append("")
                    largeur = max(len(l) for l, _ in c.chiffres)
                    for label, valeur in c.chiffres:
                        out.append(f"        {label.ljust(largeur)} : {valeur}")
                for tableau in c.tableaux:
                    rendu = tableau.rendu()
                    if rendu:
                        out.append("")
                        out.extend("        " + l for l in rendu)
                out.append("")
        if self.erreurs:
            out.append("")
            out.append("  AVERTISSEMENTS D'EXÉCUTION :")
            for e in self.erreurs:
                out.append(f"    - {e}")
        return out


@dataclass
class Rapport:
    """Le rapport complet : en-tête, sections, récapitulatif."""

    titre: str
    perimetre: str
    periode: str
    sections: list[Section] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    def rendu(self) -> str:
        horodatage = datetime.now().strftime("%d/%m/%Y à %H:%M")
        out = [
            "=" * LARGEUR,
            self.titre.upper().center(LARGEUR),
            "=" * LARGEUR,
            "",
            f"  Périmètre        : {self.perimetre}",
            f"  Période d'audit  : {self.periode}",
            f"  Rapport généré le: {horodatage}",
            f"  Référentiel      : Plan Comptable des Établissements de Crédit (PCEC) — CEMAC / COBAC",
            "",
            "  Ce rapport est produit automatiquement. Chaque constat indique le test exécuté, sa",
            "  quantification et les éléments à obtenir pour conclure. Les constats ne valent pas",
            "  conclusion d'audit tant qu'ils n'ont pas été discutés avec les services concernés.",
        ]
        if self.avertissements:
            out += ["", "  LIMITES DE L'EXTRACTION :"]
            for a in self.avertissements:
                out.extend(_paragraphe(f"- {a}", indent="    "))
        out.extend(self._sommaire())
        out.extend(self._recapitulatif())
        for section in self.sections:
            out.extend(section.rendu())
        out += ["", "=" * LARGEUR, "FIN DU RAPPORT".center(LARGEUR), "=" * LARGEUR, ""]
        return "\n".join(out)

    def _sommaire(self) -> list[str]:
        out = ["", "-" * LARGEUR, "SOMMAIRE", "-" * LARGEUR, ""]
        for s in self.sections:
            out.append(
                f"  Section {s.numero} — {s.titre}"
                f"  ({len(s.anomalies)} anomalie(s) / {len(s.constats)} contrôle(s))"
            )
        return out

    @property
    def toutes_anomalies(self) -> list[tuple[Section, Constat]]:
        return [(s, c) for s in self.sections for c in s.anomalies]

    def _recapitulatif(self) -> list[str]:
        anomalies = self.toutes_anomalies
        out = ["", "-" * LARGEUR, "RÉCAPITULATIF DES ANOMALIES PAR GRAVITÉ", "-" * LARGEUR, ""]
        compte = {g: 0 for g in Gravite.ORDRE}
        for _, c in anomalies:
            compte[c.gravite] = compte.get(c.gravite, 0) + 1
        for g in Gravite.ORDRE:
            if g != Gravite.CONFORME:
                out.append(f"  {g.ljust(10)} : {compte.get(g, 0)}")
        out.append(f"  {'TOTAL'.ljust(10)} : {len(anomalies)}")
        out.append("")
        ranges = sorted(anomalies, key=lambda x: (Gravite.rang(x[1].gravite), x[1].code))
        for section, c in ranges:
            out.append(f"  {c.gravite.ljust(9)} [{c.code}] {c.titre}")
        return out


def executer(sections: Iterable, ctx) -> list[Section]:
    """Exécute les modules de contrôle et isole les erreurs pour ne pas interrompre le rapport."""
    resultats = []
    for module in sections:
        numero, titre = module.SECTION
        try:
            section = module.run(ctx)
        except Exception as exc:  # noqa: BLE001 — un test qui échoue ne doit pas tuer le rapport
            section = Section(numero=numero, titre=titre)
            section.erreurs.append(f"{type(exc).__name__}: {exc}")
        resultats.append(section)
    return sorted(resultats, key=lambda s: s.numero)
