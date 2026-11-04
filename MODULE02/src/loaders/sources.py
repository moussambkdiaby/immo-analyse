"""Chargement des 5 sources brutes vers UN schéma commun (étape 3 du cahier).

IDÉE CENTRALE : chaque source a son propre schéma (noms de colonnes, formats, encodage).
Chaque fonction `charger_<source>` lit le fichier SANS RIEN CONVERTIR (tout en texte) et
renvoie un tableau avec les MÊMES colonnes « brutes ». Le nettoyage vient ensuite, ailleurs.

Colonnes communes (toutes en texte, valeurs brutes intactes) :
  source, id_local, ligne_source,                       <- provenance
  date_brute, date_fin_brute, transaction_brute, categorie_brute, region_brute, ville_brute,
  quartier_brute, montant_brut, devise_brute, surface_brute, chambres_brute, sdb_brute,
  statut_brut, description

`ligne_source` = position (à partir de 1) de l'enregistrement dans le fichier, hors en-tête :
elle permet de retrouver une ligne dans la source quand on l'a mise en quarantaine.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from src.config import SOURCES, SOURCES_CONFIG

COLONNES_COMMUNES = [
    "source", "id_local", "ligne_source", "date_brute", "date_fin_brute", "transaction_brute",
    "categorie_brute", "region_brute", "ville_brute", "quartier_brute", "montant_brut", "devise_brute",
    "surface_brute", "chambres_brute", "sdb_brute", "statut_brut", "description",
]


def _vers_texte(serie: pd.Series) -> pd.Series:
    """Convertit une colonne en texte en gardant les cases vides à None (jamais « nan » ni « None »)."""
    return serie.map(lambda v: None if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v)).astype(object)


def _vers_schema_commun(df: pd.DataFrame, source: str, correspondance: dict) -> pd.DataFrame:
    """Renomme les colonnes de la source vers le schéma commun, ajoute la provenance."""
    sortie = pd.DataFrame(index=df.index)
    sortie["source"] = source
    sortie["ligne_source"] = range(1, len(df) + 1)
    for colonne_commune in COLONNES_COMMUNES:
        if colonne_commune in ("source", "ligne_source"):
            continue
        colonne_source = correspondance.get(colonne_commune)
        sortie[colonne_commune] = _vers_texte(df[colonne_source]) if colonne_source else None
    return sortie[COLONNES_COMMUNES].reset_index(drop=True)


def charger_plateforme(dossier: Path = SOURCES) -> pd.DataFrame:
    cfg = SOURCES_CONFIG["plateforme"]
    # dtype=str : AUCUNE conversion automatique (on perdrait « 57.62 millions », « à négocier »...)
    df = pd.read_csv(dossier / cfg["fichier"], sep=cfg["sep"], encoding=cfg["encodage"], dtype=str)
    return _vers_schema_commun(df, "plateforme", {
        "id_local": "ref_plateforme", "date_brute": "date_mise_en_ligne", "date_fin_brute": "date_expiration",
        "transaction_brute": "type_transaction", "categorie_brute": "categorie", "region_brute": "region",
        "ville_brute": "commune", "quartier_brute": "quartier", "montant_brut": "prix", "devise_brute": "devise",
        "surface_brute": "surface", "chambres_brute": "pieces", "sdb_brute": "sdb", "statut_brut": "statut",
        "description": "description",
    })


def charger_agence(dossier: Path = SOURCES) -> pd.DataFrame:
    cfg = SOURCES_CONFIG["agence"]
    # On lit UNIQUEMENT la feuille « Annonces ». La feuille « Params » contient des métadonnées
    # (version, date d'export...), pas des biens : la concaténer polluerait les données.
    df = pd.read_excel(dossier / cfg["fichier"], sheet_name=cfg["feuille"], dtype=str)
    return _vers_schema_commun(df, "agence", {
        "id_local": "Code", "date_brute": "Date", "categorie_brute": "Type", "region_brute": "Region",
        "ville_brute": "Ville", "montant_brut": "Prix_FCFA", "surface_brute": "Surface_m2",
        "chambres_brute": "Chambres", "sdb_brute": "SDB", "statut_brut": "Statut",
    })


def charger_particuliers(dossier: Path = SOURCES) -> pd.DataFrame:
    cfg = SOURCES_CONFIG["particuliers"]
    with open(dossier / cfg["fichier"], encoding="utf-8") as f:
        enregistrements = json.load(f)
    # json_normalize « aplatit » la structure imbriquée : annonce -> localisation -> ville
    # devient une colonne « localisation_ville » (sep="_").
    df = pd.json_normalize([e["annonce"] for e in enregistrements], sep="_")
    return _vers_schema_commun(df, "particuliers", {
        "id_local": "id", "date_brute": "date", "transaction_brute": "details_transaction",
        "categorie_brute": "details_type", "region_brute": "localisation_region",
        "ville_brute": "localisation_ville", "montant_brut": "details_prix", "surface_brute": "details_surface",
        "chambres_brute": "details_chambres", "sdb_brute": "details_sdb", "statut_brut": "statut",
    })


def charger_notaires(dossier: Path = SOURCES) -> pd.DataFrame:
    cfg = SOURCES_CONFIG["notaires"]
    df = pd.read_csv(dossier / cfg["fichier"], sep=cfg["sep"], encoding=cfg["encodage"], dtype=str)
    return _vers_schema_commun(df, "notaires", {
        "id_local": "id_acte", "date_brute": "date_acte", "categorie_brute": "type_bien",
        "region_brute": "region", "ville_brute": "ville", "montant_brut": "montant_fcfa",
        "surface_brute": "superficie", "chambres_brute": "nb_chambres", "statut_brut": "statut",
    })


def charger_historique(dossier: Path = SOURCES) -> pd.DataFrame:
    cfg = SOURCES_CONFIG["historique"]
    # encoding="latin-1" : ce fichier n'est PAS en UTF-8 (« è » s'y écrit sur 1 octet, 0xE8).
    # Lu en UTF-8, « Thiès » deviendrait « Thi\ufffds » et ne correspondrait plus au référentiel.
    df = pd.read_csv(dossier / cfg["fichier"], sep=cfg["sep"], encoding=cfg["encodage"], dtype=str)
    return _vers_schema_commun(df, "historique", {
        "id_local": "ID", "date_brute": "DateVente", "categorie_brute": "TypeBien", "region_brute": "Region",
        "ville_brute": "Ville", "montant_brut": "Prix", "surface_brute": "Surface",
        "chambres_brute": "Chambres", "sdb_brute": "SallesBain",
    })


CHARGEURS = {
    "plateforme": charger_plateforme, "agence": charger_agence, "particuliers": charger_particuliers,
    "notaires": charger_notaires, "historique": charger_historique,
}


def charger_toutes_les_sources(dossier: Path = SOURCES) -> dict[str, pd.DataFrame]:
    """Charge les 5 sources. Une source illisible lève une erreur explicite (pas de silence)."""
    resultat = {}
    for nom, chargeur in CHARGEURS.items():
        try:
            resultat[nom] = chargeur(dossier)
        except Exception as erreur:   # on ajoute le nom de la source au message, puis on relance
            raise RuntimeError(f"Lecture de la source « {nom} » impossible : {erreur}") from erreur
    return resultat


def empreintes_sources(dossier: Path = SOURCES) -> dict[str, str]:
    """Empreinte SHA-256 de chaque fichier source.

    POURQUOI : le cahier exige que les données brutes restent préservées. En comparant les empreintes
    AVANT et APRÈS l'exécution, on PROUVE qu'aucun fichier brut n'a été modifié.
    """
    return {nom: hashlib.sha256((dossier / cfg["fichier"]).read_bytes()).hexdigest()
            for nom, cfg in SOURCES_CONFIG.items()}
