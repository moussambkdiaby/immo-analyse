"""Règles métier de validation (cahier § 6) — implémentées avec une CLASSE `Regle`.

POURQUOI UNE CLASSE ?
Une règle n'est pas qu'une fonction : elle a un NOM, une GRAVITÉ, une description, une justification.
En les regroupant dans un objet `Regle`, le pipeline peut appliquer la MÊME boucle à toutes les règles
et en tirer des chiffres (conformes / non conformes / non évaluables) sans écrire un `if` par règle.
Ajouter une règle = ajouter UNE `Regle` à la liste, sans toucher au reste du code.

Gravités (regles_metier.md) :
  - "bloquante"     : l'enregistrement ne peut pas être exploité de façon fiable -> QUARANTAINE
  - "avertissement" : valeur atypique ou incohérente -> on CONSERVE et on SIGNALE

Résultat d'une règle sur une ligne (colonne de type « boolean » de Pandas) :
  True  = conforme        False = non conforme        <NA> = NON ÉVALUABLE
  Les non-évaluables sont comptés à part : ils ne sont JAMAIS considérés comme conformes (cahier § 7).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

import pandas as pd

from src.config import PERIODICITES, SEUIL_LOT_MEME_DATE, SEUILS, STATUT_VERS_TRANSACTION, TRANSACTIONS
from src.processing.normalisation import est_vide
from src.processing.referentiels import Referentiels

BLOQUANTE = "bloquante"
AVERTISSEMENT = "avertissement"


@dataclass(frozen=True)
class Regle:
    code: str                                   # identifiant court (B01, A02...)
    nom: str                                    # nom lisible
    champ: str                                  # champ concerné
    gravite: str                                # BLOQUANTE ou AVERTISSEMENT
    description: str                            # ce qui est vérifié
    justification: str                          # pourquoi cette règle / d'où elle vient
    test: Callable[[pd.DataFrame], pd.Series]   # df -> Series booléenne (True / False / <NA>)
    colonne_valeur: str = ""                    # colonne affichée dans le journal des anomalies
    colonne_detail: str = ""                    # colonne de statut de conversion (ex. montant_statut)

    def evaluer(self, df: pd.DataFrame) -> pd.Series:
        """Applique la règle à tout le tableau. Renvoie True / False / <NA> pour chaque ligne."""
        return self.test(df).astype("boolean")


def _resultat(df: pd.DataFrame, evaluable: pd.Series, conforme: pd.Series) -> pd.Series:
    """Assemble le résultat : <NA> là où la règle n'est pas évaluable, sinon conforme True/False."""
    conforme = conforme.fillna(False).astype(bool)
    return conforme.astype("boolean").where(evaluable.fillna(False).astype(bool))


def _toujours(df: pd.DataFrame) -> pd.Series:
    return pd.Series(True, index=df.index)


def construire_regles(ref: Referentiels, date_ref: date, seuils: dict = SEUILS) -> list[Regle]:
    """Construit le catalogue de règles. Les seuils viennent de config.py (jamais codés ici)."""
    fourchettes = ref.fourchettes()
    types_connus = set(fourchettes.index)
    aujourdhui = pd.Timestamp(date_ref)

    # ------------------------------------------------------------------ fonctions de test
    def t_id(df):
        return _resultat(df, _toujours(df), ~df["id_local"].map(est_vide))

    def t_transaction(df):
        return _resultat(df, _toujours(df), df["type_transaction"].isin(TRANSACTIONS))

    def t_montant(df):
        return _resultat(df, _toujours(df), df["montant"] > 0)

    def t_surface(df):
        return _resultat(df, _toujours(df), df["surface_m2"] > 0)

    def t_date_interpretable(df):
        return _resultat(df, _toujours(df), df["date_collecte"].notna())

    def t_date_non_future(df):
        d = pd.to_datetime(df["date_collecte"], errors="coerce")
        return _resultat(df, d.notna(), d <= aujourdhui)

    def t_type_bien(df):
        return _resultat(df, _toujours(df), df["type_bien"].isin(types_connus))

    def t_periodicite(df):
        return _resultat(df, df["type_transaction"] == "location", df["periodicite"].isin(PERIODICITES))

    def t_prix_vente(df):
        ev = (df["type_transaction"] == "vente") & (df["montant"] > 0)
        return _resultat(df, ev, df["montant"].between(seuils["vente_prix_min"], seuils["vente_prix_max"]))

    def t_loyer(df):
        ev = (df["type_transaction"] == "location") & (df["montant"] > 0) & (df["periodicite"] == "mensuel")
        return _resultat(df, ev, df["montant"].between(seuils["loyer_mensuel_min"], seuils["loyer_mensuel_max"]))

    def _bornes(df, colonne_min, colonne_max):
        """Rapproche chaque ligne des bornes de SA catégorie (index aligné sur df)."""
        # .to_dict() : un mapping par dictionnaire reste robuste même si toute la colonne type_bien est vide
        return (df["type_bien"].map(fourchettes[colonne_min].to_dict()).astype(float),
                df["type_bien"].map(fourchettes[colonne_max].to_dict()).astype(float))

    def t_prix_categorie(df):
        mini, maxi = _bornes(df, "prix_min_indicatif", "prix_max_indicatif")
        ev = (df["type_transaction"] == "vente") & (df["montant"] > 0) & mini.notna()
        return _resultat(df, ev, (df["montant"] >= mini) & (df["montant"] <= maxi))

    def t_surface_plausible(df):
        return _resultat(df, df["surface_m2"] > 0, df["surface_m2"].between(seuils["surface_min"], seuils["surface_max"]))

    def t_surface_categorie(df):
        mini, maxi = _bornes(df, "surface_min_typique", "surface_max_typique")
        ev = (df["surface_m2"] > 0) & mini.notna()
        return _resultat(df, ev, (df["surface_m2"] >= mini) & (df["surface_m2"] <= maxi))

    def t_pm2_plage(df):
        # Le référentiel n'a pas de prix/m² : on déduit la plage extrême possible d'une catégorie
        # (prix min / surface max  ->  prix max / surface min). Contrôle large, cohérent avec le cahier § 6.2.
        pmin, pmax = _bornes(df, "prix_min_indicatif", "prix_max_indicatif")
        smin, smax = _bornes(df, "surface_min_typique", "surface_max_typique")
        ev = df["prix_m2"].notna() & pmin.notna()
        return _resultat(df, ev, (df["prix_m2"] >= pmin / smax) & (df["prix_m2"] <= pmax / smin))

    def t_pm2_iqr(df):
        # Règle de Tukey PAR CATÉGORIE : atypique si hors [Q1 - k*IQR ; Q3 + k*IQR].
        ev = df["prix_m2"].notna() & df["type_bien"].isin(types_connus)
        valeurs = df["prix_m2"].where(ev)
        # Quartiles par catégorie, recopiés sur chaque ligne via un dict (robuste si aucune catégorie n'est valide).
        par_type = valeurs.groupby(df["type_bien"])
        q1 = df["type_bien"].map(par_type.quantile(0.25).to_dict()).astype(float)
        q3 = df["type_bien"].map(par_type.quantile(0.75).to_dict()).astype(float)
        iqr, k = q3 - q1, seuils["iqr_k"]
        return _resultat(df, ev, (df["prix_m2"] >= q1 - k * iqr) & (df["prix_m2"] <= q3 + k * iqr))

    def t_chambres_valides(df):
        return _resultat(df, ~df["chambres_brute"].map(est_vide), df["chambres"].notna() & (df["chambres"] >= 0))

    def t_sdb_valides(df):
        return _resultat(df, ~df["sdb_brute"].map(est_vide), df["salles_bain"].notna() & (df["salles_bain"] >= 0))

    def t_chambres_atypiques(df):
        ev = df["chambres"].notna() & df["type_bien"].isin(["Appartement", "Studio"])
        return _resultat(df, ev, df["chambres"] <= seuils["chambres_max_studio_appart"])

    def t_sdb_chambres(df):
        ev = df["chambres"].notna() & df["salles_bain"].notna()
        return _resultat(df, ev, df["salles_bain"] <= df["chambres"] + seuils["sdb_surplus_max"])

    def t_pieces_type(df):
        # Un terrain n'a ni chambre ni salle de bain ; une maison, une villa ou un appartement a au moins une chambre.
        bati = df["type_bien"].isin(["Maison", "Villa", "Appartement"])
        terrain = df["type_bien"] == "Terrain"
        ev = df["chambres"].notna() & (bati | terrain)
        conforme = (terrain & (df["chambres"] == 0) & (df["salles_bain"].fillna(0) == 0)) | (bati & (df["chambres"] >= 1))
        return _resultat(df, ev, conforme)

    def t_ville(df):
        return _resultat(df, _toujours(df), df["ville"].notna())

    def t_region(df):
        return _resultat(df, _toujours(df), df["region"].notna())

    def t_region_ville(df):
        ev = df["ville"].notna() & df["region"].notna()
        return _resultat(df, ev, df["ville"].map(ref.region_de_ville) == df["region"])

    def t_statut_transaction(df):
        ev = (df["transaction_origine"] == "source") & df["statut_source"].notna() & df["type_transaction"].notna()
        return _resultat(df, ev, df["statut_source"].map(STATUT_VERS_TRANSACTION) == df["type_transaction"])

    def t_dates_coherentes(df):
        debut = pd.to_datetime(df["date_collecte"], errors="coerce")
        fin = pd.to_datetime(df["date_expiration"], errors="coerce")
        return _resultat(df, debut.notna() & fin.notna(), fin >= debut)

    def t_lot(df):
        taille = df.groupby(["source", "date_collecte"])["id_bien"].transform("size")
        return _resultat(df, df["date_collecte"].notna(), taille < SEUIL_LOT_MEME_DATE)

    def t_doublon(df):
        return _resultat(df, _toujours(df), df["lien_rapprochement"] != "doublon_probable")

    def t_conflit(df):
        return _resultat(df, _toujours(df), df["lien_rapprochement"] != "conflit")

    def t_id_unique(df):
        return _resultat(df, df["id_bien"].notna(), ~df["id_bien"].duplicated(keep=False))

    B, A = BLOQUANTE, AVERTISSEMENT
    return [
        # ------------------------------------------------------------- bloquantes -> quarantaine
        Regle("B01", "identifiant_present", "id_local", B, "L'identifiant local est renseigné",
              "Cahier § 6.1 : obligatoire dans chaque source, quarantaine si absent", t_id, "id_local"),
        Regle("B02", "transaction_valide", "type_transaction", B, "Vente ou location après normalisation",
              "Cahier § 6.1 : quarantaine si non interprétable", t_transaction, "transaction_brute", "transaction_statut"),
        Regle("B03", "prix_ou_loyer_positif", "montant", B, "Prix (vente) ou loyer (location) numérique strictement positif",
              "regles_metier.md : prix absent, non numérique ou <= 0 -> quarantaine", t_montant, "montant_brut", "montant_statut"),
        Regle("B04", "surface_positive", "surface_m2", B, "Surface numérique strictement positive",
              "regles_metier.md : surface absente, non numérique ou <= 0 -> quarantaine", t_surface, "surface_brute", "surface_statut"),
        Regle("B05", "date_interpretable", "date_collecte", B, "Date lisible et possible (pas 32/13/2024)",
              "regles_metier.md : date non interprétable ou impossible -> quarantaine", t_date_interpretable, "date_brute", "date_statut"),
        Regle("B06", "date_non_future", "date_collecte", B, "Date non postérieure à la date d'exécution",
              "Cahier § 6.1 : non future par rapport à la date d'exécution", t_date_non_future, "date_brute"),
        Regle("B07", "type_bien_valide", "type_bien", B, "Type de bien parmi les 7 catégories du référentiel",
              "Cahier § 6.1 : quarantaine si hors référentiel (regles_metier.md dit « avertissement » : on suit le cahier)",
              t_type_bien, "categorie_brute", "categorie_statut"),
        # ------------------------------------------------------------- avertissements -> conservé et signalé
        Regle("A01", "periodicite_connue", "periodicite", A, "Un loyer a une périodicité reconnue (mensuel, trimestriel...)",
              "Cahier § 6.1 : signaler, ne pas deviner", t_periodicite, "devise_brute"),
        Regle("A02", "prix_vente_plausible", "montant", A, "Prix de vente entre les seuils généraux",
              "regles_metier.md : prix < 100 000 ou > 2 milliards FCFA = atypique", t_prix_vente, "montant_brut"),
        Regle("A03", "loyer_mensuel_plausible", "montant", A, "Loyer mensuel entre 25 000 et 5 000 000 FCFA",
              "Cahier § 6.2 (évalué seulement si la périodicité est mensuelle)", t_loyer, "montant_brut"),
        Regle("A04", "prix_dans_fourchette_categorie", "montant", A, "Prix de vente dans la fourchette de sa catégorie",
              "referentiel_categories.csv : fourchettes indicatives (hypothèses pédagogiques)", t_prix_categorie, "montant_brut"),
        Regle("A05", "surface_plausible", "surface_m2", A, "Surface entre 5 et 2 000 m²",
              "regles_metier.md : atypique, pas nécessairement faux", t_surface_plausible, "surface_brute"),
        Regle("A06", "surface_dans_fourchette_categorie", "surface_m2", A, "Surface dans la fourchette de sa catégorie",
              "referentiel_categories.csv : surfaces typiques", t_surface_categorie, "surface_brute"),
        Regle("A07", "prix_m2_dans_plage_referentiel", "prix_m2", A, "Prix au m² dans la plage déduite du référentiel",
              "Cahier § 6.2 (plage déduite : prix min / surface max -> prix max / surface min)", t_pm2_plage, "prix_m2"),
        Regle("A08", "prix_m2_non_atypique", "prix_m2", A, "Prix au m² hors valeurs extrêmes de sa catégorie (règle de l'IQR)",
              "Complément statistique : la plage du référentiel est trop large pour détecter", t_pm2_iqr, "prix_m2"),
        Regle("A09", "chambres_valides", "chambres", A, "Nombre de chambres : entier >= 0",
              "Cahier § 6.1", t_chambres_valides, "chambres_brute", "chambres_statut"),
        Regle("A10", "salles_bain_valides", "salles_bain", A, "Nombre de salles de bain : entier >= 0",
              "Cahier § 6.1", t_sdb_valides, "sdb_brute", "sdb_statut"),
        Regle("A11", "chambres_non_atypiques", "chambres", A, "Pas plus de 10 chambres pour un appartement ou un studio",
              "Cahier § 6.2", t_chambres_atypiques, "chambres_brute"),
        Regle("A12", "salles_bain_coherentes", "salles_bain", A, "Salles de bain <= chambres + 2",
              "Cahier § 6.2", t_sdb_chambres, "sdb_brute"),
        Regle("A13", "pieces_coherentes_type", "chambres", A, "Terrain sans pièce ; maison, villa, appartement avec au moins 1 chambre",
              "Cahier § 6.1 : cohérent avec le type de bien", t_pieces_type, "chambres_brute"),
        Regle("A14", "ville_reconnue", "ville", A, "Ville renseignée et présente dans le référentiel géographique",
              "Cahier § 6.1 : signaler, ne pas corriger sans preuve", t_ville, "ville_brute", "ville_statut"),
        Regle("A15", "region_reconnue", "region", A, "Région renseignée et présente dans le référentiel",
              "Cahier § 6.1", t_region, "region_brute", "region_statut"),
        Regle("A16", "region_ville_coherentes", "region", A, "La ville appartient bien à la région indiquée",
              "regles_metier.md : signaler, ne pas corriger sans preuve", t_region_ville, "region_brute"),
        Regle("A17", "statut_coherent_transaction", "statut_source", A, "Le statut est compatible avec la transaction écrite dans la source",
              "Cohérence interne (évaluée seulement quand la transaction est écrite, pas déduite du statut)",
              t_statut_transaction, "statut_brut"),
        Regle("A18", "dates_coherentes", "date_expiration", A, "La date d'expiration n'est pas antérieure à la mise en ligne",
              "Cahier § 6.1 : date_mise_a_jour >= date_collecte -> signaler", t_dates_coherentes, "date_fin_brute"),
        Regle("A19", "date_non_concentree", "date_collecte", A, f"Pas {SEUIL_LOT_MEME_DATE} annonces ou plus de la même source le même jour",
              "Détection d'un import en masse (valeurs par défaut probables)", t_lot, "date_brute"),
        Regle("A20", "pas_de_doublon_probable", "id_bien", A, "Aucun doublon probable dans les autres enregistrements",
              "Cahier § 6.1 : distinguer doublon exact, doublon probable et conflit", t_doublon, "id_bien"),
        Regle("A21", "pas_de_conflit_entre_enregistrements", "id_bien", A, "Aucun conflit (même bien, valeurs contradictoires)",
              "Cahier § 6.1 / Axe 1 : les conflits sont signalés, pas résolus arbitrairement", t_conflit, "id_bien"),
        Regle("A22", "identifiant_unique", "id_bien", A, "L'identifiant global n'apparaît qu'une fois",
              "Cahier § 5.3 : un identifiant local n'est pas une clé fiable", t_id_unique, "id_bien"),
    ]
