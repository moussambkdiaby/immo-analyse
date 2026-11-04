"""Outils de test partagés : fabriquer un mini-jeu de données brutes SANS toucher aux vrais fichiers."""
from datetime import date

import pandas as pd
import pytest

from src.loaders.sources import COLONNES_COMMUNES
from src.processing.referentiels import Referentiels
from src.processing.traitement import combiner_sources, marquer_doublons_exacts, normaliser_donnees
from src.validation.controle import appliquer_regles_sur_actifs, statut_final
from src.validation.regles import construire_regles

DATE_REF = date(2026, 10, 29)


@pytest.fixture(scope="session")
def ref():
    return Referentiels.charger()


def ligne(**champs):
    """Une ligne brute « saine » (vente d'un appartement à Dakar) que chaque test modifie à sa guise."""
    base = {
        "source": "plateforme", "id_local": "T-001", "ligne_source": 1, "date_brute": "2024-05-10",
        "date_fin_brute": None, "transaction_brute": "vente", "categorie_brute": "Appartement",
        "region_brute": "Dakar", "ville_brute": "Dakar", "quartier_brute": None, "montant_brut": "60000000",
        "devise_brute": "FCFA", "surface_brute": "100", "chambres_brute": "3", "sdb_brute": "2",
        "statut_brut": "En vente", "description": None,
    }
    base.update(champs)
    return base


def preparer(lignes, ref):
    """Brut -> données normalisées (avec les colonnes de rapprochement vides)."""
    brut = pd.DataFrame(lignes, columns=COLONNES_COMMUNES).reset_index(drop=True)
    brut["ligne_source"] = range(1, len(brut) + 1)
    df = marquer_doublons_exacts(combiner_sources({"test": brut}))
    df = normaliser_donnees(df, ref, DATE_REF)
    df["lien_rapprochement"] = None
    df["id_groupe_rapprochement"] = None
    return df


def valider(lignes, ref):
    """Brut -> (df, matrice des règles, statut final) pour vérifier une décision de bout en bout."""
    df = preparer(lignes, ref)
    regles = construire_regles(ref, DATE_REF)
    matrice = appliquer_regles_sur_actifs(df, regles)     # même logique que le pipeline : copies exclues
    return df, matrice, statut_final(df, matrice, regles)
