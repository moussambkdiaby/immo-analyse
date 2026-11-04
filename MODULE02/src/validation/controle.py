"""Application des règles et décision finale pour chaque enregistrement.

Trois produits :
  1. une MATRICE (une colonne par règle : True / False / <NA>)    -> sert aux indicateurs de qualité
  2. un JOURNAL des anomalies (une ligne par violation)           -> chaque décision est traçable
  3. un STATUT FINAL par enregistrement, mutuellement exclusif    -> aucun enregistrement compté deux fois

STATUT FINAL (par ordre de priorité) :
  doublon_exact_ecarte    copie exacte d'une autre ligne de la même source (écartée, comptée à part)
  quarantaine             au moins une règle BLOQUANTE violée
  conserve_avertissement  aucune règle bloquante violée, au moins un AVERTISSEMENT
  corrige                 aucune violation, mais au moins une valeur modifiée par une règle sûre
  conforme                aucune violation et aucune modification
Cette priorité garantit que les 5 statuts s'additionnent EXACTEMENT au nombre de lignes reçues.
"""
from __future__ import annotations

import pandas as pd

from src.validation.regles import AVERTISSEMENT, BLOQUANTE, Regle


def appliquer_regles(df: pd.DataFrame, regles: list[Regle]) -> pd.DataFrame:
    """Matrice des résultats : index = lignes de df, colonnes = codes des règles."""
    return pd.DataFrame({r.code: r.evaluer(df) for r in regles}, index=df.index)


def appliquer_regles_sur_actifs(df: pd.DataFrame, regles: list[Regle]) -> pd.DataFrame:
    """Applique les règles aux seules lignes qui ne sont pas des copies exactes.

    Les copies n'ajoutent aucune information (l'original est évalué) et fausseraient des règles comme
    « identifiant unique ». Leurs lignes de la matrice restent <NA> (non évaluées).
    """
    actifs = df[~df["est_copie_exacte"]]
    return appliquer_regles(actifs, regles).reindex(df.index)


def journal_anomalies(df: pd.DataFrame, matrice: pd.DataFrame, regles: list[Regle]) -> pd.DataFrame:
    """Une ligne par (enregistrement, règle violée), avec la valeur fautive et le motif."""
    morceaux = []
    for r in regles:
        violees = matrice[r.code].eq(False).fillna(False)
        if not violees.any():
            continue
        sous = df.loc[violees]
        morceaux.append(pd.DataFrame({
            "id_bien": sous["id_bien"], "source": sous["source"], "ligne_source": sous["ligne_source"],
            "code_regle": r.code, "regle": r.nom, "gravite": r.gravite, "champ": r.champ,
            "valeur": sous[r.colonne_valeur] if r.colonne_valeur else None,
            "detail_conversion": sous[r.colonne_detail] if r.colonne_detail else None,
            "motif": r.description,
        }))
    colonnes = ["id_bien", "source", "ligne_source", "code_regle", "regle", "gravite", "champ", "valeur",
                "detail_conversion", "motif"]
    if not morceaux:
        return pd.DataFrame(columns=colonnes)
    return pd.concat(morceaux, ignore_index=True)[colonnes]


def statut_final(df: pd.DataFrame, matrice: pd.DataFrame, regles: list[Regle]) -> pd.Series:
    """Décide du sort de chaque enregistrement (voir le docstring du module)."""
    bloquantes = [r.code for r in regles if r.gravite == BLOQUANTE]
    avertissements = [r.code for r in regles if r.gravite == AVERTISSEMENT]

    viole_bloquante = matrice[bloquantes].eq(False).any(axis=1)
    viole_avertissement = matrice[avertissements].eq(False).any(axis=1)

    statut = pd.Series("conforme", index=df.index, dtype=object)
    statut[df["champs_corriges"] > 0] = "corrige"
    statut[viole_avertissement] = "conserve_avertissement"
    statut[viole_bloquante] = "quarantaine"
    statut[df["est_copie_exacte"]] = "doublon_exact_ecarte"      # priorité absolue
    return statut


def motifs_par_enregistrement(journal: pd.DataFrame, gravite: str) -> pd.Series:
    """Texte « regle1 ; regle2 » des motifs d'une gravité donnée, par id_bien (pour la quarantaine)."""
    sous = journal[journal["gravite"] == gravite]
    if sous.empty:
        return pd.Series(dtype=object)
    return sous.groupby("id_bien")["regle"].agg(" ; ".join)
