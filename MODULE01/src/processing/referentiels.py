"""Chargement des référentiels (géographie, catégories de biens).

POURQUOI UNE CLASSE ?
Les deux référentiels sont utilisés ensemble par plusieurs modules (normalisation, validation,
analyse). On les charge UNE fois, on les range dans un objet, et on le passe en paramètre :
les fonctions ne dépendent d'aucune variable globale cachée (donc elles se testent facilement).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.config import ALIAS_VILLES, REFERENTIELS
from src.processing.normalisation import cle_texte


@dataclass
class Referentiels:
    geo: pd.DataFrame                       # region, ville, lat_centre, lon_centre
    categories: pd.DataFrame                # categorie, synonymes, fourchettes prix et surface
    ville_vers_region: dict = field(default_factory=dict)    # clé(ville) -> (nom officiel ville, région officielle)
    region_officielle: dict = field(default_factory=dict)    # clé(région) -> nom officiel
    synonymes: dict = field(default_factory=dict)            # clé(synonyme) -> nom officiel de catégorie
    officielles: set = field(default_factory=set)            # les 7 noms officiels

    @classmethod
    def charger(cls, dossier=REFERENTIELS) -> "Referentiels":
        geo = pd.read_csv(dossier / "referentiel_geographique.csv")
        categories = pd.read_csv(dossier / "referentiel_categories.csv")

        ref = cls(geo=geo, categories=categories)
        for _, ligne in geo.iterrows():
            ref.ville_vers_region[cle_texte(ligne["ville"])] = (ligne["ville"], ligne["region"])
            ref.region_officielle[cle_texte(ligne["region"])] = ligne["region"]
        # Les synonymes viennent DU FICHIER (« appart|appartement|appt ») : les règles restent dans le référentiel.
        for _, ligne in categories.iterrows():
            ref.officielles.add(ligne["categorie"])
            ref.synonymes[cle_texte(ligne["categorie"])] = ligne["categorie"]
            for synonyme in str(ligne["synonymes"]).split("|"):
                ref.synonymes[cle_texte(synonyme)] = ligne["categorie"]
        return ref

    # ------------------------------------------------------------------ géographie
    def normaliser_ville(self, valeur):
        """Renvoie (nom officiel, statut). Statuts : conforme | corrige | manquant | hors_referentiel."""
        cle = cle_texte(valeur)
        if cle is None:
            return None, "manquant"
        if cle in ALIAS_VILLES:                          # alias connu (ex. « Dkr »)
            return ALIAS_VILLES[cle], "corrige"
        if cle in self.ville_vers_region:
            officiel = self.ville_vers_region[cle][0]
            return officiel, ("conforme" if str(valeur).strip() == officiel else "corrige")
        return None, "hors_referentiel"

    def normaliser_region(self, valeur):
        cle = cle_texte(valeur)
        if cle is None:
            return None, "manquant"
        if cle in self.region_officielle:
            officiel = self.region_officielle[cle]
            return officiel, ("conforme" if str(valeur).strip() == officiel else "corrige")
        return None, "hors_referentiel"

    def region_de_ville(self, ville_officielle):
        """Région officielle d'une ville du référentiel (None si ville inconnue)."""
        entree = self.ville_vers_region.get(cle_texte(ville_officielle))
        return entree[1] if entree else None

    # ------------------------------------------------------------------ catégories
    def fourchettes(self) -> pd.DataFrame:
        """Fourchettes indicatives par catégorie, indexées par nom officiel."""
        return self.categories.set_index("categorie")[
            ["prix_min_indicatif", "prix_max_indicatif", "surface_min_typique", "surface_max_typique"]
        ]
