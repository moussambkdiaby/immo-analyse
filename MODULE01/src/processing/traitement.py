"""Traitement des données : de « 5 sources brutes » à « un tableau normalisé unique ».

Étapes de ce module (cahier § 4, étapes 3 à 5) :
  1. combiner les 5 sources en un seul tableau (provenance conservée)
  2. normaliser chaque champ : on AJOUTE des colonnes (jamais d'écrasement de la valeur brute)
  3. repérer les doublons EXACTS (copies) et les écarter du jeu traité

RÈGLE D'OR : la colonne brute (`montant_brut`) reste à côté de la colonne propre (`montant`),
avec un statut (`montant_statut`). On peut ainsi compter les corrections et tout retracer.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.config import PERIODICITES, STATUT_VERS_TRANSACTION, TRANSACTION_PAR_NATURE
from src.loaders.sources import COLONNES_COMMUNES
from src.processing import normalisation as nz
from src.processing.referentiels import Referentiels

# Un champ « corrigé » = sa valeur a été modifiée par une règle sûre.
# (« deduit » et « extrait_devise » = information COMPLÉTÉE, pas une valeur modifiée : comptées à part.)
CHAMPS_NORMALISES = ["date", "transaction", "categorie", "region", "ville", "montant", "surface", "chambres", "sdb", "statut"]


def combiner_sources(sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Empile les 5 sources (même schéma commun) et crée l'identifiant global `id_bien`.

    `id_bien` = « source:id_local ». On n'utilise PAS l'id local seul : deux sources peuvent
    réutiliser le même numéro pour des biens différents (cahier § 5.3).
    """
    tout = pd.concat(sources.values(), ignore_index=True)
    tout["id_bien"] = np.where(
        tout["id_local"].map(nz.est_vide), None, tout["source"] + ":" + tout["id_local"].fillna("")
    )
    return tout


def _appliquer(serie: pd.Series, fonction, **kwargs) -> tuple[pd.Series, pd.Series]:
    """Applique une fonction (valeur, statut) à une colonne et renvoie DEUX colonnes."""
    resultats = [fonction(v, **kwargs) for v in serie]
    valeurs = pd.Series([r[0] for r in resultats], index=serie.index, dtype=object)
    statuts = pd.Series([r[1] for r in resultats], index=serie.index, dtype=object)
    return valeurs, statuts


def _normaliser_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Détermine vente / location, ET d'où vient l'information.

    Ordre de priorité :
      1. valeur écrite dans la source (plateforme, particuliers)           -> origine « source »
      2. nature de la source (notaires = actes de vente, historique = ventes) -> origine « nature_source »
      3. déduction depuis le statut (agence : « Loué » -> location...)      -> origine « statut »
    La transaction doit être connue AVANT de normaliser un prix (un loyer n'est pas un prix de vente).
    """
    valeurs, statuts, origines = [], [], []
    for source, brute, statut_brut in zip(df["source"], df["transaction_brute"], df["statut_brut"]):
        valeur, statut = nz.normaliser_transaction(brute)
        origine = "source"
        if statut == "manquant":
            if source in TRANSACTION_PAR_NATURE:
                valeur, statut, origine = TRANSACTION_PAR_NATURE[source], "deduit", "nature_source"
            else:
                valeur = STATUT_VERS_TRANSACTION.get(nz.normaliser_statut(statut_brut)[0])
                statut, origine = ("deduit", "statut") if valeur else ("manquant", None)
        valeurs.append(valeur), statuts.append(statut), origines.append(origine)
    df["type_transaction"], df["transaction_statut"], df["transaction_origine"] = valeurs, statuts, origines
    return df


def _normaliser_periodicite(df: pd.DataFrame) -> pd.DataFrame:
    """Périodicité d'un loyer. Elle n'est écrite que dans la plateforme (devise « FCFA/mois »).

    Pour les autres locations, on NE DEVINE PAS : périodicité inconnue (elle sera signalée).
    """
    valeurs, statuts = [], []
    for transaction, devise in zip(df["type_transaction"], df["devise_brute"]):
        if transaction != "location":
            valeurs.append(None), statuts.append("non_applicable")
            continue
        valeur, statut = nz.normaliser_periodicite(devise)
        if valeur:
            statut = "extrait_devise"          # information lue dans la devise, pas une correction
        valeurs.append(valeur), statuts.append(statut if valeur else "inconnue")
    df["periodicite"], df["periodicite_statut"] = valeurs, statuts
    return df


def normaliser_donnees(brut: pd.DataFrame, ref: Referentiels, date_ref: date | None = None) -> pd.DataFrame:
    """Ajoute à chaque ligne les colonnes normalisées et leurs statuts. Ne modifie pas `brut`."""
    df = brut.copy()                                 # .copy() : on ne touche jamais au tableau d'entrée

    # --- dates : la convention JJ/MM ou MM/JJ est déduite PAR SOURCE, à partir de preuves
    df["convention_date"] = df["source"].map(
        {s: nz.inferer_convention_date(g["date_brute"]) for s, g in df.groupby("source")}
    )
    resultats = [nz.normaliser_date(t, c, date_ref) for t, c in zip(df["date_brute"], df["convention_date"])]
    df["date_collecte"] = [r[0] for r in resultats]
    df["date_statut"] = [r[1] for r in resultats]
    resultats = [nz.normaliser_date(t, "ambigu", date_ref) for t in df["date_fin_brute"]]
    df["date_expiration"] = [r[0] for r in resultats]
    df["date_expiration_statut"] = [r[1] for r in resultats]

    # --- transaction AVANT le prix, puis périodicité
    df = _normaliser_transactions(df)
    df = _normaliser_periodicite(df)

    # --- statut, catégorie
    df["statut_source"], df["statut_statut"] = _appliquer(df["statut_brut"], nz.normaliser_statut)
    df["type_bien"], df["categorie_statut"] = _appliquer(
        df["categorie_brute"], nz.normaliser_categorie, synonymes=ref.synonymes, officielles=ref.officielles
    )

    # --- lieu
    df["ville"], df["ville_statut"] = _appliquer(df["ville_brute"], lambda v: ref.normaliser_ville(v))
    df["region"], df["region_statut"] = _appliquer(df["region_brute"], lambda v: ref.normaliser_region(v))

    # --- nombres
    df["montant"], df["montant_statut"] = _appliquer(df["montant_brut"], nz.normaliser_prix)
    df["surface_m2"], df["surface_statut"] = _appliquer(df["surface_brute"], nz.normaliser_surface)
    df["chambres"], df["chambres_statut"] = _appliquer(df["chambres_brute"], nz.normaliser_entier)
    df["salles_bain"], df["sdb_statut"] = _appliquer(df["sdb_brute"], nz.normaliser_entier)

    for colonne in ("montant", "surface_m2"):
        df[colonne] = pd.to_numeric(df[colonne], errors="coerce")
    for colonne in ("chambres", "salles_bain"):
        df[colonne] = pd.to_numeric(df[colonne], errors="coerce").astype("Int64")

    # --- colonnes dérivées : on SÉPARE ventes et locations dans tout le pipeline
    df["prix_vente"] = df["montant"].where(df["type_transaction"] == "vente")
    df["loyer"] = df["montant"].where(df["type_transaction"] == "location")
    df["loyer_mensuel"] = df["loyer"].where(df["periodicite"] == "mensuel")
    valide = (df["prix_vente"] > 0) & (df["surface_m2"] > 0)
    df["prix_m2"] = (df["prix_vente"] / df["surface_m2"]).where(valide)

    # --- nombre de corrections (valeurs MODIFIÉES par une règle sûre)
    statuts = pd.DataFrame({
        "date": df["date_statut"], "transaction": df["transaction_statut"], "categorie": df["categorie_statut"],
        "region": df["region_statut"], "ville": df["ville_statut"], "montant": df["montant_statut"],
        "surface": df["surface_statut"], "chambres": df["chambres_statut"], "sdb": df["sdb_statut"],
        "statut": df["statut_statut"],
    })
    df["champs_corriges"] = (statuts == "corrige").sum(axis=1)
    df["champs_completes"] = (statuts == "deduit").sum(axis=1) + (df["periodicite_statut"] == "extrait_devise")
    return df


def marquer_doublons_exacts(df: pd.DataFrame) -> pd.DataFrame:
    """Repère les COPIES exactes à l'intérieur d'une même source.

    Définition : deux lignes d'une même source dont TOUS les champs bruts sont identiques
    (seule leur position dans le fichier diffère). On garde la première, les suivantes sont des copies.
    On compare les valeurs BRUTES : deux lignes brutes identiques le restent après normalisation.
    """
    colonnes = [c for c in COLONNES_COMMUNES if c != "ligne_source"]          # source incluse
    df = df.copy()
    # On fabrique une « clé » texte avec tous les champs bruts (une case vide devient « ∅ »),
    # puis on compare les clés : deux lignes de même clé sont identiques.
    cle = df[colonnes].astype(object).fillna("\u2205").astype(str).agg("\x1f".join, axis=1)
    df["est_copie_exacte"] = cle.duplicated(keep="first")
    premiers = df.loc[~df["est_copie_exacte"]].assign(_cle=cle).set_index("_cle")["id_bien"]
    df["copie_de"] = cle.map(premiers).where(df["est_copie_exacte"])      # id_bien de l'original
    return df
