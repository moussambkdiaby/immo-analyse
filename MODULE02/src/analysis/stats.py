"""Analyses descriptives des données RETENUES (étape 5 du cahier : NumPy et Pandas).

Données retenues = statuts « conforme », « corrige » et « conserve_avertissement » (la quarantaine et
les copies exactes sont exclues). Principes appliqués :
  - on SÉPARE ventes et locations : un loyer mensuel n'est pas comparable à un prix de vente ;
  - on regarde la MÉDIANE autant que la moyenne : quelques valeurs extrêmes tirent la moyenne ;
  - un prix au m² n'a de sens qu'à l'intérieur d'une catégorie de bien (un terrain n'est pas un studio) ;
  - les prix de vente sont des prix DEMANDÉS (annonces), pas des prix de transaction conclue.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.processing.pipeline import Resultats

STATUTS_RETENUS = ["conforme", "corrige", "conserve_avertissement"]


def resume_numerique(valeurs: pd.Series) -> pd.Series:
    """Statistiques descriptives calculées avec NumPy (les valeurs manquantes sont ignorées)."""
    x = valeurs.dropna().to_numpy(dtype=float)
    if x.size == 0:
        return pd.Series({"n": 0}, dtype=float)
    return pd.Series({
        "n": x.size, "moyenne": np.mean(x), "mediane": np.median(x),
        "ecart_type": np.std(x, ddof=1) if x.size > 1 else np.nan,
        "min": np.min(x), "q1": np.percentile(x, 25), "q3": np.percentile(x, 75), "max": np.max(x),
    })


def _par_groupe(df: pd.DataFrame, colonne_groupe: str, colonne_valeur: str, minimum: int = 1) -> pd.DataFrame:
    lignes = {k: resume_numerique(g[colonne_valeur]) for k, g in df.groupby(colonne_groupe)}
    tab = pd.DataFrame(lignes).T
    tab = tab[tab["n"] >= minimum]
    tab.index.name = colonne_groupe
    return tab.round(1).sort_values("mediane", ascending=False).reset_index()


def retenues(R: Resultats) -> pd.DataFrame:
    return R.donnees[R.donnees["statut_final"].isin(STATUTS_RETENUS)]


def analyses(R: Resultats) -> dict[str, pd.DataFrame]:
    d = retenues(R)
    ventes = d[d["type_transaction"] == "vente"]
    locations = d[d["type_transaction"] == "location"]

    # Effet de la séparation vente / location sur la médiane du « montant » (cahier, Axe 5)
    melange = resume_numerique(d["montant"])
    separe_v = resume_numerique(ventes["montant"])
    separe_l = resume_numerique(locations["loyer_mensuel"])
    effet = pd.DataFrame({
        "ensemble": ["tout mélangé (ventes + locations)", "ventes seules (prix demandé)", "locations seules (loyer mensuel)"],
        "n": [melange["n"], separe_v["n"], separe_l["n"]],
        "mediane": [melange["mediane"], separe_v["mediane"], separe_l["mediane"]],
        "moyenne": [melange["moyenne"], separe_v["moyenne"], separe_l["moyenne"]],
    }).round(0)

    return {
        "ventes_prix_m2_par_type": _par_groupe(ventes, "type_bien", "prix_m2"),
        "ventes_prix_par_type": _par_groupe(ventes, "type_bien", "prix_vente"),
        "ventes_prix_m2_par_region": _par_groupe(ventes, "region", "prix_m2"),
        "ventes_prix_m2_par_ville": _par_groupe(ventes, "ville", "prix_m2", minimum=10),
        "locations_loyer_mensuel_par_type": _par_groupe(locations, "type_bien", "loyer_mensuel"),
        "effet_separation_ventes_locations": effet,
        "surface_par_type": _par_groupe(d, "type_bien", "surface_m2"),
    }
