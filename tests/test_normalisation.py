"""Tests des fonctions de normalisation : cas CONFORMES, INVALIDES et LIMITES (cahier § 12).

Un test vérifie une règle précise. Les cas limites sont les plus importants : ils prouvent que la
fonction REFUSE de deviner quand le texte est ambigu.
"""
from datetime import date

import pytest

from src.processing.normalisation import (
    cle_texte, est_vide, inferer_convention_date, mots_vers_nombre, normaliser_categorie, normaliser_date,
    normaliser_entier, normaliser_periodicite, normaliser_prix, normaliser_statut, normaliser_surface,
    normaliser_transaction,
)

REF = date(2026, 10, 29)


# ------------------------------------------------------------------ prix
@pytest.mark.parametrize("texte, attendu", [
    ("60581000", (60581000.0, "conforme")),                      # conforme
    (18152000, (18152000.0, "conforme")),                        # nombre déjà numérique
    ("320860000.0", (320860000.0, "conforme")),                  # flottant écrit en texte (notaires)
    ("438 746 000", (438746000.0, "corrige")),                   # espaces = milliers
    ("438\u00a0746\u00a0000", (438746000.0, "corrige")),         # espace insécable, invisible à l'œil
    ("57.62 millions", (57620000.0, "corrige")),                 # unité explicite
    ("57.62 Millions", (57620000.0, "corrige")),                 # casse du mot
    ("123456000 FCFA", (123456000.0, "corrige")),                # suffixe de devise explicite
    ("1,250,000", (1250000.0, "corrige")),                       # virgule en milliers (2 groupes)
])
def test_prix_conformes_ou_normalisables(texte, attendu):
    assert normaliser_prix(texte) == attendu


@pytest.mark.parametrize("texte, attendu", [
    ("à négocier", (None, "non_numerique")),                     # texte sans nombre
    ("None FCFA", (None, "manquant")),                           # vide déguisé (None Python converti en texte)
    (None, (None, "manquant")),
    ("", (None, "manquant")),
    ("-5000", (None, "negatif")),                                # on ne « répare » pas un signe
])
def test_prix_invalides(texte, attendu):
    assert normaliser_prix(texte) == attendu


@pytest.mark.parametrize("texte", ["1,250", "1,5"])
def test_prix_ambigu_n_est_jamais_devine(texte):
    assert normaliser_prix(texte) == (None, "ambigu")


def test_prix_zero_est_converti_mais_sera_refuse_par_la_regle():
    # La normalisation convertit ; c'est la RÈGLE « prix > 0 » qui rejette (séparation des responsabilités).
    assert normaliser_prix("0") == (0.0, "conforme")


# ------------------------------------------------------------------ surface
@pytest.mark.parametrize("texte, attendu", [
    ("173.3", (173.3, "conforme")), (150, (150.0, "conforme")), ("92,4", (92.4, "corrige")),
    (" 92,4 ", (92.4, "corrige")), ("80 m²", (80.0, "corrige")), ("quatre-vingt", (80.0, "corrige")),
    ("1,25", (1.25, "corrige")),                                 # format valide ; la plausibilité est jugée ailleurs
])
def test_surface_valides(texte, attendu):
    assert normaliser_surface(texte) == attendu


@pytest.mark.parametrize("texte, attendu", [
    ("1,250", (None, "ambigu")),                                 # 1 250 m² ou 1,25 m² ? on ne devine pas
    ("-30", (None, "negatif")), ("grande", (None, "non_numerique")), (None, (None, "manquant")),
])
def test_surface_invalides_ou_ambigues(texte, attendu):
    assert normaliser_surface(texte) == attendu


# ------------------------------------------------------------------ nombres en lettres et entiers
@pytest.mark.parametrize("texte, attendu", [
    ("quatre-vingt", 80), ("quatre vingt dix sept", 97), ("vingt et un", 21), ("soixante-et-onze", 71),
    ("deux cent trente", 230), ("cent", 100), ("deux trois", None), ("abc", None), ("", None),
])
def test_mots_vers_nombre(texte, attendu):
    assert mots_vers_nombre(texte) == attendu


@pytest.mark.parametrize("valeur, attendu", [
    ("4", (4, "conforme")), (4.0, (4, "conforme")), ("4.0", (4, "corrige")), (None, (None, "manquant")),
    ("abc", (None, "non_numerique")), (2.5, (None, "non_numerique")),
])
def test_entier(valeur, attendu):
    assert normaliser_entier(valeur) == attendu


# ------------------------------------------------------------------ dates
def test_date_iso_conforme():
    assert normaliser_date("2024-03-01") == ("2024-03-01", "conforme")


def test_date_jj_mm_avec_convention_prouvee():
    assert normaliser_date("11/05/2022", "JJ/MM") == ("2022-05-11", "corrige")


def test_date_ambigue_sans_convention_n_est_pas_convertie():
    assert normaliser_date("03/04/2024") == (None, "ambigu")


def test_date_non_ambigue_grace_a_la_preuve_locale():
    assert normaliser_date("18/08/2025") == ("2025-08-18", "corrige")     # 18 ne peut pas être un mois


@pytest.mark.parametrize("texte", ["32/13/2024", "31/02/2024", "2024-13-45"])
def test_dates_impossibles(texte):
    assert normaliser_date(texte, "JJ/MM")[1] == "impossible"


def test_dates_relatives_utilisent_la_date_de_reference():
    assert normaliser_date("hier", date_ref=REF) == ("2026-10-28", "corrige")
    assert normaliser_date("aujourd'hui", date_ref=REF) == ("2026-10-29", "corrige")


def test_date_mois_en_lettres():
    assert normaliser_date("12 mars 2024") == ("2024-03-12", "corrige")
    assert normaliser_date("5 février 2023") == ("2023-02-05", "corrige")


def test_date_vide_ou_illisible():
    assert normaliser_date(None) == (None, "manquant")
    assert normaliser_date("bientôt") == (None, "non_interpretable")


def test_convention_deduite_des_preuves():
    assert inferer_convention_date(["25/12/2020", "05/06/2018"]) == "JJ/MM"      # 25 > 12 : un jour
    assert inferer_convention_date(["12/25/2020", "06/05/2018"]) == "MM/JJ"      # 25 en 2e position : un jour
    assert inferer_convention_date(["03/04/2024", "05/06/2018"]) == "ambigu"     # aucune preuve
    assert inferer_convention_date(["32/13/2024"]) == "ambigu"                   # impossible : ne prouve rien


# ------------------------------------------------------------------ périodicité, transaction, statut, catégorie
@pytest.mark.parametrize("texte, attendu", [
    ("FCFA/mois", "mensuel"), ("par mois", "mensuel"), ("mens.", "mensuel"), ("mensuel", "mensuel"),
    ("/an", "annuel"), ("trimestriel", "trimestriel"),
])
def test_periodicite_reconnue(texte, attendu):
    assert normaliser_periodicite(texte)[0] == attendu


def test_periodicite_cherche_des_mots_entiers():
    assert normaliser_periodicite("promotion") == (None, "inconnu")             # « mois » n'est pas dans « promotion »


def test_transaction_et_statut():
    assert normaliser_transaction("vente") == ("vente", "conforme")
    assert normaliser_transaction("À louer") == ("location", "corrige")
    assert normaliser_transaction("échange") == (None, "non_interpretable")
    assert normaliser_statut("VENDU") == ("Vendu", "corrige")
    assert normaliser_statut("Acte signé") == ("Vendu", "corrige")
    assert normaliser_statut("Loué") == ("Loué", "conforme")


def test_categorie(ref):
    f = lambda v: normaliser_categorie(v, ref.synonymes, ref.officielles)
    assert f("Appartement") == ("Appartement", "conforme")
    assert f("appart") == ("Appartement", "corrige")
    assert f("  VILLA ") == ("Villa", "corrige")
    assert f("LOCAL COMMERCIAL") == ("Local commercial", "corrige")
    assert f("Château") == (None, "hors_referentiel")
    assert f(None) == (None, "manquant")


def test_lieux(ref):
    assert ref.normaliser_ville("THIÈS") == ("Thiès", "corrige")
    assert ref.normaliser_ville("Dkr") == ("Dakar", "corrige")                   # alias connu
    assert ref.normaliser_ville("Atlantide") == (None, "hors_referentiel")
    assert ref.region_de_ville("Mbour") == "Thiès"


def test_utilitaires():
    assert est_vide(None) and est_vide("") and est_vide("None") and est_vide(float("nan"))
    assert not est_vide("0")
    assert cle_texte("  Guédiawaye ") == "guediawaye"
