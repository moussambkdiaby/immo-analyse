"""Exports et vérification des fichiers produits (étape 7 du cahier).

Les originaux (data/raw) ne sont JAMAIS modifiés : tout part dans data/processed, data/quarantine et reports.
Les exports sont IDEMPOTENTS : relancer le pipeline REMPLACE les fichiers, il n'ajoute pas de doublons.
CSV encodés en UTF-8 avec BOM (« utf-8-sig ») pour que les accents s'ouvrent bien dans Excel.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.analysis.qualite import construire_rapport, rapport_markdown, resume_csv
from src.analysis.stats import STATUTS_RETENUS, analyses
from src.config import PROCESSED, QUARANTINE, REPORTS
from src.processing.pipeline import Resultats

ENCODAGE = "utf-8-sig"

COLONNES_PROPRES = [
    "id_bien", "source", "id_local", "ligne_source", "statut_final", "date_collecte", "type_transaction",
    "periodicite", "type_bien", "region", "ville", "quartier_brute", "montant", "prix_vente", "loyer", "loyer_mensuel",
    "surface_m2", "prix_m2", "chambres", "salles_bain", "statut_source", "date_expiration",
    "champs_corriges", "avertissements", "lien_rapprochement", "id_groupe_rapprochement",
    # valeurs BRUTES conservées à côté des valeurs propres : la normalisation est réversible
    "date_brute", "transaction_brute", "categorie_brute", "ville_brute", "montant_brut", "surface_brute",
]
COLONNES_QUARANTAINE = [
    "id_bien", "source", "id_local", "ligne_source", "motifs_bloquants", "avertissements",
    "date_brute", "transaction_brute", "categorie_brute", "region_brute", "ville_brute",
    "montant_brut", "devise_brute", "surface_brute", "chambres_brute", "sdb_brute", "statut_brut",
]


def _ecrire(df: pd.DataFrame, chemin: Path, json_aussi: bool = False) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(chemin, index=False, encoding=ENCODAGE)
    if json_aussi:
        # to_json : NaN devient null ; force_ascii=False garde les accents lisibles
        chemin.with_suffix(".json").write_text(df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")


def exporter(R: Resultats) -> dict:
    """Écrit tous les fichiers de sortie et renvoie le rapport de qualité (dictionnaire)."""
    d = R.donnees
    propres = d[d["statut_final"].isin(STATUTS_RETENUS)]
    quarantaine = d[d["statut_final"] == "quarantaine"]
    copies = d[d["statut_final"] == "doublon_exact_ecarte"]

    _ecrire(propres[COLONNES_PROPRES], PROCESSED / "donnees_propres.csv", json_aussi=True)
    _ecrire(quarantaine[COLONNES_QUARANTAINE], QUARANTINE / "quarantaine.csv", json_aussi=True)
    _ecrire(copies[["id_bien", "source", "ligne_source", "copie_de"]], QUARANTINE / "doublons_exacts_ecartes.csv")

    _ecrire(R.anomalies, REPORTS / "anomalies.csv")
    _ecrire(R.rapprochements, REPORTS / "rapprochements.csv")
    catalogue = pd.DataFrame([{"code": r.code, "regle": r.nom, "gravite": r.gravite, "champ": r.champ,
                               "description": r.description, "justification": r.justification} for r in R.regles])
    _ecrire(catalogue, REPORTS / "catalogue_regles.csv")

    rapport = construire_rapport(R)
    (REPORTS / "quality_report.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _ecrire(resume_csv(rapport), REPORTS / "quality_summary.csv")
    (REPORTS / "rapport_qualite.md").write_text(rapport_markdown(rapport, R), encoding="utf-8")

    for nom, tableau in analyses(R).items():
        _ecrire(tableau, REPORTS / f"analyse_{nom}.csv")
    return rapport


def verifier_exports(R: Resultats) -> dict:
    """Relit les fichiers écrits et contrôle leur cohérence. Renvoie {contrôle: True/False}."""
    propres = pd.read_csv(PROCESSED / "donnees_propres.csv", encoding=ENCODAGE)
    quarantaine = pd.read_csv(QUARANTINE / "quarantaine.csv", encoding=ENCODAGE)
    copies = pd.read_csv(QUARANTINE / "doublons_exacts_ecartes.csv", encoding=ENCODAGE)
    json_propres = json.loads((PROCESSED / "donnees_propres.json").read_text(encoding="utf-8"))
    total = len(R.donnees)
    return {
        "somme propres + quarantaine + copies = lignes reçues": len(propres) + len(quarantaine) + len(copies) == total,
        "identifiants uniques dans donnees_propres": bool(propres["id_bien"].is_unique),
        "aucun identifiant de donnees_propres en quarantaine": not set(propres["id_bien"]) & set(quarantaine["id_bien"]),
        "chaque ligne en quarantaine a un motif": bool(quarantaine["motifs_bloquants"].notna().all()),
        "JSON et CSV propres ont le même nombre de lignes": len(json_propres) == len(propres),
        "aucun prix de vente <= 0 dans les données propres": bool((propres["prix_vente"].dropna() > 0).all()),
        "aucune surface <= 0 dans les données propres": bool((propres["surface_m2"].dropna() > 0).all()),
        "aucune date future dans les données propres": bool(
            (pd.to_datetime(propres["date_collecte"], errors="coerce").dropna() <= pd.Timestamp(R.date_reference)).all()),
        "fichiers bruts intacts (SHA-256 avant = après)": R.sources_intactes,
    }
