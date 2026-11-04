"""Exécute le projet ImmoAnalyse depuis la racine du dépôt, module par module.

    python executer_project.py                    # vérifie les données, puis lance les modules 1 et 2
    python executer_project.py --module 2         # un seul module
    python executer_project.py --tests            # lance les tests de chaque module
    python executer_project.py --date-ref 2026-11-03

POURQUOI UN SCRIPT À LA RACINE ?
Chaque module est AUTONOME : il a son propre dossier, son propre code (`src/`), ses propres tests
et ses propres données brutes. On exécute donc chaque module DEPUIS son dossier (cwd), sinon les deux
paquets `src` se mélangeraient. Ce script fait ce travail et vérifie que les copies des données
brutes des deux modules sont IDENTIQUES (octet pour octet).
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
MODULES = {"1": RACINE / "MODULE01", "2": RACINE / "MODULE02"}
# (dossier des données brutes du module, nom du sous-dossier)
DONNEES = {"1": RACINE / "MODULE01" / "data" / "raw", "2": RACINE / "MODULE02"}


def empreintes(dossier: Path, sous_dossiers=("sources", "referentiels")) -> dict[str, str]:
    """SHA-256 de chaque fichier de données brutes, indexé par son chemin relatif."""
    resultat = {}
    for sous in sous_dossiers:
        for fichier in sorted((dossier / sous).rglob("*")):
            if fichier.is_file():
                resultat[str(fichier.relative_to(dossier))] = hashlib.sha256(fichier.read_bytes()).hexdigest()
    return resultat


def verifier_donnees() -> bool:
    """Les deux modules lisent-ils exactement les mêmes données brutes ?"""
    a, b = empreintes(DONNEES["1"]), empreintes(DONNEES["2"])
    if not a or not b:
        print("[ÉCHEC] données brutes introuvables (MODULE01/data/raw ou MODULE02/sources)")
        return False
    identiques = a == b
    print(f"[{'OK' if identiques else 'ÉCHEC'}] données brutes identiques dans MODULE01 et MODULE02 ({len(a)} fichiers)")
    return identiques


def lancer(module: str, arguments: list[str], titre: str) -> int:
    print(f"\n=== {titre} ===")
    return subprocess.run([sys.executable, *arguments], cwd=MODULES[module]).returncode


def main() -> int:
    p = argparse.ArgumentParser(description="Exécute les modules d'ImmoAnalyse")
    p.add_argument("--module", choices=["1", "2", "tous"], default="tous")
    p.add_argument("--tests", action="store_true", help="lance pytest dans chaque module au lieu du pipeline")
    p.add_argument("--date-ref", default=None, help="date d'exécution AAAA-MM-JJ")
    p.add_argument("--sans-simulation", action="store_true", help="saute l'estimation des faux doublons")
    args = p.parse_args()

    codes = [] if verifier_donnees() else [1]
    choisis = ["1", "2"] if args.module == "tous" else [args.module]
    option_date = ["--date-ref", args.date_ref] if args.date_ref else []
    option_sim = ["--sans-simulation"] if args.sans_simulation else []
    for m in choisis:
        if args.tests:
            codes.append(lancer(m, ["-m", "pytest", "-p", "no:cacheprovider"], f"Tests du MODULE0{m}"))
        elif m == "1":
            codes.append(lancer("1", ["-m", "src.main", *option_date, *option_sim], "MODULE01 : pipeline de qualité"))
        else:
            codes.append(lancer("2", ["-m", "src.preparation.nettoyage", *option_date, *option_sim], "MODULE02 : nettoyage et sortie/"))
    echec = any(codes)
    print("\n" + ("ÉCHEC : voir les messages ci-dessus" if echec else "Tout est OK"))
    return 1 if echec else 0


if __name__ == "__main__":
    raise SystemExit(main())
