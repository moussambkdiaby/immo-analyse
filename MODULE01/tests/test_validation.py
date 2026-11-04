"""Tests des règles métier et de la décision finale (conforme / corrigé / avertissement / quarantaine)."""
import pandas as pd

from tests.conftest import ligne, preparer, valider


def code_viole(matrice, code, i=0):
    return matrice[code].iloc[i] is False or matrice[code].iloc[i] == False  # noqa: E712


# ------------------------------------------------------------------ cas CONFORME
def test_enregistrement_propre_est_conforme(ref):
    _, matrice, statut = valider([ligne()], ref)
    assert statut.iloc[0] == "conforme"
    assert not matrice.iloc[0].eq(False).any()


def test_valeur_corrigee_donne_le_statut_corrige(ref):
    _, _, statut = valider([ligne(montant_brut="57.62 millions", categorie_brute="appart")], ref)
    assert statut.iloc[0] == "corrige"


# ------------------------------------------------------------------ règles BLOQUANTES -> quarantaine
def test_prix_nul_ou_non_numerique_va_en_quarantaine(ref):
    for brut in ("0", "à négocier", None, "-100"):
        df, matrice, statut = valider([ligne(montant_brut=brut)], ref)
        assert statut.iloc[0] == "quarantaine", brut
        assert matrice["B03"].iloc[0] == False  # noqa: E712


def test_surface_negative_ou_absente_va_en_quarantaine(ref):
    for brut in ("-30", None, "0"):
        _, _, statut = valider([ligne(surface_brute=brut)], ref)
        assert statut.iloc[0] == "quarantaine", brut


def test_date_future_va_en_quarantaine(ref):
    _, matrice, statut = valider([ligne(date_brute="2028-12-01")], ref)
    assert statut.iloc[0] == "quarantaine" and matrice["B06"].iloc[0] == False  # noqa: E712


def test_date_impossible_va_en_quarantaine_et_la_regle_future_est_non_evaluable(ref):
    _, matrice, statut = valider([ligne(date_brute="32/13/2024")], ref)
    assert statut.iloc[0] == "quarantaine"
    assert matrice["B05"].iloc[0] == False                  # noqa: E712
    assert pd.isna(matrice["B06"].iloc[0])                  # non évaluable : jamais compté comme conforme


def test_type_de_bien_hors_referentiel_va_en_quarantaine(ref):
    _, _, statut = valider([ligne(categorie_brute="Château")], ref)
    assert statut.iloc[0] == "quarantaine"


def test_identifiant_absent_va_en_quarantaine(ref):
    _, _, statut = valider([ligne(id_local=None)], ref)
    assert statut.iloc[0] == "quarantaine"


# ------------------------------------------------------------------ règles d'AVERTISSEMENT -> conservé
def test_prix_hors_fourchette_de_categorie_est_conserve_avec_avertissement(ref):
    # Un appartement à 200 M FCFA dépasse la fourchette indicative (25 à 120 M) mais reste plausible.
    df, matrice, statut = valider([ligne(montant_brut="200000000", surface_brute="150")], ref)
    assert statut.iloc[0] == "conserve_avertissement"
    assert matrice["A04"].iloc[0] == False and matrice["A02"].iloc[0] == True  # noqa: E712


def test_cas_limite_prix_pile_sur_la_borne_est_conforme(ref):
    _, matrice, _ = valider([ligne(montant_brut="120000000", surface_brute="100")], ref)   # max Appartement = 120 M
    assert matrice["A04"].iloc[0] == True                                                   # noqa: E712


def test_region_et_ville_incompatibles_sont_signalees_pas_corrigees(ref):
    df, matrice, statut = valider([ligne(region_brute="Ziguinchor", ville_brute="Dakar")], ref)
    assert matrice["A16"].iloc[0] == False                                                  # noqa: E712
    assert statut.iloc[0] == "conserve_avertissement"
    assert df["region"].iloc[0] == "Ziguinchor"                                             # rien n'est « corrigé »


def test_loyer_sans_periodicite_est_signale_et_non_evalue_sur_le_plafond(ref):
    df, matrice, statut = valider([ligne(transaction_brute="location", statut_brut="Disponible",
                                         montant_brut="400000", devise_brute=None)], ref)
    assert matrice["A01"].iloc[0] == False                  # périodicité inconnue : signalée, jamais devinée
    assert pd.isna(matrice["A03"].iloc[0])                  # plafond de loyer : non évaluable sans périodicité


def test_loyer_mensuel_est_evalue(ref):
    _, matrice, _ = valider([ligne(transaction_brute="location", statut_brut="Disponible",
                                   montant_brut="400000", devise_brute="FCFA/mois")], ref)
    assert matrice["A01"].iloc[0] == True and matrice["A03"].iloc[0] == True               # noqa: E712


def test_regles_de_vente_sont_non_evaluables_pour_une_location(ref):
    _, matrice, _ = valider([ligne(transaction_brute="location", statut_brut="Disponible",
                                   montant_brut="400000", devise_brute="FCFA/mois")], ref)
    assert pd.isna(matrice["A02"].iloc[0]) and pd.isna(matrice["A04"].iloc[0])


def test_terrain_avec_chambres_est_signale(ref):
    _, matrice, _ = valider([ligne(categorie_brute="Terrain", montant_brut="30000000", surface_brute="500",
                                   chambres_brute="3", sdb_brute="0")], ref)
    assert matrice["A13"].iloc[0] == False                                                  # noqa: E712


def test_salles_de_bain_superieures_aux_chambres_plus_deux(ref):
    _, matrice, _ = valider([ligne(chambres_brute="1", sdb_brute="4")], ref)
    assert matrice["A12"].iloc[0] == False                                                  # noqa: E712


# ------------------------------------------------------------------ lot importé en masse
def test_lot_de_20_annonces_du_meme_jour_est_signale(ref):
    lignes = [ligne(id_local=f"L-{i:03d}", date_brute="2024-03-01", surface_brute=str(80 + i)) for i in range(20)]
    lignes.append(ligne(id_local="L-solo", date_brute="2023-01-01"))
    _, matrice, _ = valider(lignes, ref)
    assert (matrice["A19"].iloc[:20] == False).all() and matrice["A19"].iloc[20] == True    # noqa: E712


# ------------------------------------------------------------------ doublons EXACTS
def test_copie_exacte_est_ecartee_et_l_original_conserve(ref):
    lignes = [ligne(), ligne()]                              # deux lignes identiques (sauf leur position)
    df, _, statut = valider(lignes, ref)
    assert list(df["est_copie_exacte"]) == [False, True]
    assert list(statut) == ["conforme", "doublon_exact_ecarte"]
    assert df["copie_de"].iloc[1] == df["id_bien"].iloc[0]


def test_deux_lignes_de_sources_differentes_ne_sont_pas_des_copies(ref):
    df = preparer([ligne(), ligne(source="agence")], ref)
    assert not df["est_copie_exacte"].any()


# ------------------------------------------------------------------ propriétés générales
def test_les_statuts_sont_mutuellement_exclusifs_et_exhaustifs(ref):
    lignes = [ligne(id_local=f"X{i}", montant_brut=m) for i, m in enumerate(["60000000", "57.62 millions", "0", "200000000"])]
    _, _, statut = valider(lignes, ref)
    assert len(statut) == 4 and statut.notna().all()
    assert set(statut) <= {"conforme", "corrige", "conserve_avertissement", "quarantaine", "doublon_exact_ecarte"}


def test_la_valeur_brute_est_conservee_a_cote_de_la_valeur_propre(ref):
    df, _, _ = valider([ligne(montant_brut="438 746 000")], ref)
    assert df["montant_brut"].iloc[0] == "438 746 000" and df["montant"].iloc[0] == 438746000.0
