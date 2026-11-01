"""Tests de la détection de doublons probables et de conflits entre enregistrements."""
from src.processing.rapprochement import calculer_paires, classer_paires, detecter_rapprochements
from tests.conftest import ligne, preparer


def deux_biens(ref, **b):
    """Deux biens de sources différentes, même ville / type / transaction ; `b` modifie le second."""
    a = ligne(id_local="A-1", source="agence", surface_brute="100.0", montant_brut="60000000", chambres_brute="3", sdb_brute="2")
    autre = ligne(id_local="B-1", source="historique", **{"surface_brute": "100.0", "montant_brut": "60000000",
                                                           "chambres_brute": "3", "sdb_brute": "2", **b})
    return preparer([a, autre], ref)


def test_biens_identiques_sont_un_doublon_probable(ref):
    df, paires, retenues = detecter_rapprochements(deux_biens(ref))
    assert len(retenues) == 1 and retenues["type_lien"].iloc[0] == "doublon_probable"
    assert set(df["lien_rapprochement"]) == {"doublon_probable"}
    assert df["id_groupe_rapprochement"].nunique() == 1


def test_meme_bien_avec_prix_different_est_un_conflit_pas_un_doublon(ref):
    _, _, retenues = detecter_rapprochements(deux_biens(ref, montant_brut="57000000"))   # -5 %
    assert len(retenues) == 1 and retenues["type_lien"].iloc[0] == "conflit"
    assert "prix" in retenues["champs_en_conflit"].iloc[0]


def test_conflit_sur_le_nombre_de_chambres(ref):
    _, _, retenues = detecter_rapprochements(deux_biens(ref, chambres_brute="5"))
    assert retenues["type_lien"].iloc[0] == "conflit" and "chambres" in retenues["champs_en_conflit"].iloc[0]


def test_surface_differente_n_est_pas_rapprochee(ref):
    _, _, retenues = detecter_rapprochements(deux_biens(ref, surface_brute="120.0"))
    assert retenues.empty                                   # même ville et même prix, mais 20 % d'écart de surface


def test_prix_tres_different_n_est_pas_rapproche(ref):
    _, _, retenues = detecter_rapprochements(deux_biens(ref, montant_brut="90000000"))
    assert retenues.empty


def test_villes_differentes_ne_sont_pas_comparees(ref):
    df = deux_biens(ref, ville_brute="Thiès", region_brute="Thiès")
    assert calculer_paires(df).empty                        # le blocage évite la comparaison


def test_une_vente_n_est_jamais_le_doublon_d_une_location(ref):
    df = deux_biens(ref, transaction_brute="location", statut_brut="Disponible")
    assert calculer_paires(df).empty


def test_le_seuil_se_modifie_sans_toucher_au_code(ref):
    paires = calculer_paires(deux_biens(ref, montant_brut="57000000"))
    assert len(classer_paires(paires, {**__import__("src.config", fromlist=["x"]).RAPPROCHEMENT, "seuil_doublon_probable": 0.99})) == 0
