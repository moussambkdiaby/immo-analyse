"""Rapprochement des enregistrements : doublons PROBABLES et CONFLITS (cahier § 5.3, § 6.1).

PROBLÈME : aucun identifiant n'est universel et les identifiants ne sont pas fiables. Un même bien
peut apparaître dans plusieurs sources (ou deux fois dans la même) sous des identifiants différents.
On rapproche donc sur des ATTRIBUTS MÉTIER, jamais sur l'identifiant.

STRATÉGIE (documentée, seuil justifié) :
  1. BLOCAGE : on ne compare que des biens de même ville, même type de bien, même transaction.
     (Évite de comparer 3 000 x 3 000 lignes ; une vente n'est jamais le doublon d'une location.)
  2. SIMILARITÉ : on combine PLUSIEURS attributs, chacun noté de 0 (différent) à 1 (identique) :
        surface (poids 0,4)  prix (0,4)  chambres + salles de bain (0,1)  date (0,1)
     La date pèse peu : un même bien est annoncé, vendu, réannoncé à des mois d'écart.
  3. DÉCISION : score >= seuil (0,75) -> les deux lignes décrivent probablement le MÊME bien.
        - tous les attributs concordent  -> « doublon_probable »
        - un attribut se contredit       -> « conflit » (on liste les champs en conflit)
  4. ON NE FUSIONNE RIEN et on ne choisit pas la « bonne » valeur (regles_metier.md : « ne pas
     fusionner sans justification »). Les lignes sont conservées avec un avertissement et un
     identifiant de groupe, pour qu'un humain tranche.

POURQUOI 0,75 ? Sur les données du projet, les scores des paires comparables forment un continuum
jusqu'à ~0,70 (coïncidences : même ville, même type, surface voisine), puis un vide avant les
paires vraiment suspectes (surface identique à la décimale ET prix quasi identique).
Le seuil est dans config.py : il se change sans toucher au code.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from src.config import RAPPROCHEMENT

COLONNES_BLOC = ["ville", "type_bien", "type_transaction"]


def _similarite_relative(a: float, b: float, tolerance: float) -> float:
    """1 si a == b ; décroît linéairement jusqu'à 0 quand l'écart relatif atteint `tolerance`."""
    ecart = abs(a - b) / max(a, b)
    return max(0.0, 1.0 - ecart / tolerance)


def _similarite_date(a, b, params: dict) -> float:
    """1 si les dates sont proches (<= 30 jours) ; décroît jusqu'à 0 à un an d'écart ; 0 si inconnue."""
    if pd.isna(a) or pd.isna(b):
        return 0.0
    jours = abs((a - b).days)
    pleine, nulle = params["jours_pleine_similarite"], params["jours_similarite_nulle"]
    if jours <= pleine:
        return 1.0
    return max(0.0, 1.0 - (jours - pleine) / (nulle - pleine))


def _similarite_pieces(a_ch, b_ch, a_sdb, b_sdb) -> float:
    """Part des comptes CONNUS (chambres, salles de bain) qui sont identiques. 0 si aucun n'est connu."""
    egaux = connus = 0
    for x, y in ((a_ch, b_ch), (a_sdb, b_sdb)):
        if pd.notna(x) and pd.notna(y):
            connus += 1
            egaux += int(x == y)
    return egaux / connus if connus else 0.0


def calculer_paires(df: pd.DataFrame, params: dict = RAPPROCHEMENT) -> pd.DataFrame:
    """Calcule le score de toutes les paires d'un même bloc. Renvoie TOUTES les paires (pas seulement les retenues).

    Garder tous les scores permet de justifier le seuil (histogramme) et de tester le détecteur.
    """
    comparables = df[
        (df["surface_m2"] > 0) & (df["montant"] > 0)
        & df["ville"].notna() & df["type_bien"].notna() & df["type_transaction"].notna()
        & df["id_bien"].notna()
    ].copy()
    comparables["_date"] = pd.to_datetime(comparables["date_collecte"], errors="coerce")
    w = params["poids"]
    lignes = []
    for cle, bloc in comparables.groupby(COLONNES_BLOC):
        if len(bloc) < 2:
            continue
        for (_, a), (_, b) in combinations(bloc.iterrows(), 2):
            s_surf = _similarite_relative(a["surface_m2"], b["surface_m2"], params["tolerance_surface"])
            s_prix = _similarite_relative(a["montant"], b["montant"], params["tolerance_prix"])
            s_pieces = _similarite_pieces(a["chambres"], b["chambres"], a["salles_bain"], b["salles_bain"])
            s_date = _similarite_date(a["_date"], b["_date"], params)
            score = w["surface"] * s_surf + w["prix"] * s_prix + w["pieces"] * s_pieces + w["date"] * s_date
            lignes.append({
                "id_a": a["id_bien"], "id_b": b["id_bien"], "source_a": a["source"], "source_b": b["source"],
                "ville": cle[0], "type_bien": cle[1], "type_transaction": cle[2],
                "surface_a": a["surface_m2"], "surface_b": b["surface_m2"],
                "montant_a": a["montant"], "montant_b": b["montant"],
                "chambres_a": a["chambres"], "chambres_b": b["chambres"],
                "sdb_a": a["salles_bain"], "sdb_b": b["salles_bain"],
                "sim_surface": round(s_surf, 3), "sim_prix": round(s_prix, 3),
                "sim_pieces": round(s_pieces, 3), "sim_date": round(s_date, 3), "score": round(score, 3),
                "ecart_prix_rel": abs(a["montant"] - b["montant"]) / max(a["montant"], b["montant"]),
            })
    colonnes = ["id_a", "id_b", "source_a", "source_b", "ville", "type_bien", "type_transaction",
                "surface_a", "surface_b", "montant_a", "montant_b", "chambres_a", "chambres_b",
                "sdb_a", "sdb_b", "sim_surface", "sim_prix", "sim_pieces", "sim_date", "score", "ecart_prix_rel"]
    return pd.DataFrame(lignes, columns=colonnes)


def _champs_en_conflit(paire: pd.Series) -> list[str]:
    """Liste les attributs qui se CONTREDISENT dans une paire déjà jugée « même bien »."""
    conflits = []
    if paire["ecart_prix_rel"] > 0.02:                      # prix : au-delà de 2 %
        conflits.append("prix")
    for champ, a, b in (("chambres", paire["chambres_a"], paire["chambres_b"]),
                        ("salles_bain", paire["sdb_a"], paire["sdb_b"])):
        if pd.notna(a) and pd.notna(b) and a != b:
            conflits.append(champ)
    return conflits


def classer_paires(paires: pd.DataFrame, params: dict = RAPPROCHEMENT) -> pd.DataFrame:
    """Garde les paires au-dessus du seuil et les classe : doublon_probable ou conflit."""
    retenues = paires[
        (paires["score"] >= params["seuil_doublon_probable"])
        & (paires["sim_surface"] >= params["sim_surface_min"])      # conditions nécessaires :
        & (paires["sim_prix"] >= params["sim_prix_min"])            # surface ET prix proches
    ].copy()
    retenues["champs_en_conflit"] = retenues.apply(lambda p: ",".join(_champs_en_conflit(p)), axis=1)
    retenues["type_lien"] = np.where(retenues["champs_en_conflit"] == "", "doublon_probable", "conflit")
    return retenues.reset_index(drop=True)


def marquer_rapprochements(df: pd.DataFrame, retenues: pd.DataFrame) -> pd.DataFrame:
    """Ajoute à chaque ligne : `lien_rapprochement` et `id_groupe_rapprochement` (groupes de lignes liées)."""
    df = df.copy()
    parent = {}                                                  # union-find : regroupe les lignes liées

    def trouver(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _, p in retenues.iterrows():
        parent[trouver(p["id_a"])] = trouver(p["id_b"])

    lien = {}
    for _, p in retenues.iterrows():                             # « conflit » l'emporte sur « doublon_probable »
        for identifiant in (p["id_a"], p["id_b"]):
            if lien.get(identifiant) != "conflit":
                lien[identifiant] = p["type_lien"]
    racines = {identifiant: trouver(identifiant) for identifiant in lien}
    numeros = {r: f"G{i:03d}" for i, r in enumerate(sorted(set(racines.values())), start=1)}

    df["lien_rapprochement"] = df["id_bien"].map(lien)
    df["id_groupe_rapprochement"] = df["id_bien"].map(lambda i: numeros[racines[i]] if i in racines else None)
    return df


def estimer_coincidences(df: pd.DataFrame, params: dict = RAPPROCHEMENT, graine: int = 0) -> dict:
    """Estime combien de « doublons probables » le HASARD produirait avec ces critères.

    MÉTHODE (test par permutation) : dans chaque bloc (même ville, type, transaction), on MÉLANGE les
    prix entre les biens. Ça casse le lien prix <-> bien tout en gardant les mêmes surfaces et blocs.
    Toute paire retenue après mélange est une pure coïncidence. On répète N fois et on fait la moyenne.
    Si le nombre observé est proche de la moyenne du hasard, les paires retenues sont des SIGNAUX à
    vérifier à la main, pas des preuves : c'est ce que le rapport affiche.
    """
    rng = np.random.default_rng(graine)
    comptes = []
    for _ in range(params["simulations_hasard"]):
        melange = df.copy()
        melange["montant"] = melange.groupby(COLONNES_BLOC)["montant"].transform(
            lambda s: rng.permutation(s.to_numpy())
        )
        comptes.append(len(classer_paires(calculer_paires(melange, params), params)))
    return {"moyenne": float(np.mean(comptes)), "min": int(np.min(comptes)), "max": int(np.max(comptes)),
            "tirages": params["simulations_hasard"]}


def detecter_rapprochements(df: pd.DataFrame, params: dict = RAPPROCHEMENT):
    """Enchaîne calcul, classement et marquage. Renvoie (df marqué, toutes les paires, paires retenues)."""
    paires = calculer_paires(df, params)
    retenues = classer_paires(paires, params)
    return marquer_rapprochements(df, retenues), paires, retenues
