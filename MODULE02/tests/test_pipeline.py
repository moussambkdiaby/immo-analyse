"""Test d'intégration : le pipeline complet sur les VRAIES données du projet.

Ces tests vérifient les propriétés qui comptent pour la validation (cahier § 12) : les chiffres
s'additionnent, les fichiers bruts restent intacts, le pipeline est reproductible, les exports sont cohérents.
"""
import json
from datetime import date

import pandas as pd
import pytest

from src import config
from src.analysis import export
from src.processing.pipeline import executer_pipeline

pytestmark = pytest.mark.skipif(not (config.SOURCES / "notaires.csv").exists(), reason="données brutes absentes")
DATE_REF = date(2026, 10, 29)


@pytest.fixture(scope="module")
def resultats():
    return executer_pipeline(DATE_REF, simuler_hasard=False)


def test_les_5_sources_sont_lues(resultats):
    assert set(resultats.volumes_recus) == {"plateforme", "agence", "particuliers", "notaires", "historique"}
    assert resultats.volumes_recus["plateforme"] == 875 and resultats.volumes_recus["historique"] == 528


def test_les_statuts_s_additionnent_exactement_au_nombre_de_lignes(resultats):
    d = resultats.donnees
    assert d["statut_final"].notna().all()
    assert d["statut_final"].value_counts().sum() == len(d) == sum(resultats.volumes_recus.values())


def test_les_15_copies_exactes_de_la_plateforme_sont_detectees(resultats):
    copies = resultats.donnees[resultats.donnees["est_copie_exacte"]]
    assert len(copies) == 15 and set(copies["source"]) == {"plateforme"}
    assert (copies["statut_final"] == "doublon_exact_ecarte").all()


def test_anomalies_attendues_detectees(resultats):
    q = resultats.donnees[resultats.donnees["statut_final"] == "quarantaine"]
    # 6 dates impossibles (notaires) et 5 dates futures (plateforme) doivent être en quarantaine
    assert q["motifs_bloquants"].str.contains("date_interpretable").sum() == 6
    assert q["motifs_bloquants"].str.contains("date_non_future").sum() == 5
    # prix « à négocier » : jamais converti, mis en quarantaine
    assert (q["montant_brut"] == "à négocier").sum() >= 5


def test_valeurs_ambigues_ou_en_lettres_traitees_comme_prevu(resultats):
    d = resultats.donnees
    assert (d["surface_brute"] == "quatre-vingt").sum() == 4
    assert (d.loc[d["surface_brute"] == "quatre-vingt", "surface_m2"] == 80).all()          # corrigé sans ambiguïté
    assert (d.loc[d["montant_brut"] == "57.62 millions", "montant"] == 57620000).all()


def test_aucune_donnee_propre_ne_viole_une_regle_bloquante(resultats):
    d = resultats.donnees
    propres = d[d["statut_final"].isin(["conforme", "corrige", "conserve_avertissement"])]
    assert (propres["prix_vente"].dropna() > 0).all() and (propres["surface_m2"].dropna() > 0).all()
    assert (pd.to_datetime(propres["date_collecte"]).dropna() <= pd.Timestamp(DATE_REF)).all()


def test_ventes_et_locations_sont_separees(resultats):
    d = resultats.donnees
    assert d.loc[d["type_transaction"] == "location", "prix_vente"].isna().all()
    assert d.loc[d["type_transaction"] == "vente", "loyer"].isna().all()


def test_les_fichiers_bruts_sont_preserves(resultats):
    assert resultats.sources_intactes


def test_le_pipeline_est_reproductible(resultats):
    de_nouveau = executer_pipeline(DATE_REF, simuler_hasard=False)
    assert de_nouveau.donnees["statut_final"].value_counts().to_dict() == resultats.donnees["statut_final"].value_counts().to_dict()
    pd.testing.assert_series_equal(de_nouveau.donnees["id_bien"], resultats.donnees["id_bien"])


def test_exports_coherents_et_idempotents(resultats, tmp_path, monkeypatch):
    monkeypatch.setattr(export, "PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(export, "QUARANTINE", tmp_path / "quarantine")
    monkeypatch.setattr(export, "REPORTS", tmp_path / "reports")
    export.exporter(resultats)
    premier = len(pd.read_csv(tmp_path / "processed" / "donnees_propres.csv", encoding="utf-8-sig"))
    export.exporter(resultats)                                     # 2e exécution : ne doit RIEN ajouter
    second = len(pd.read_csv(tmp_path / "processed" / "donnees_propres.csv", encoding="utf-8-sig"))
    assert premier == second
    assert all(export.verifier_exports(resultats).values())
    rapport = json.loads((tmp_path / "reports" / "quality_report.json").read_text(encoding="utf-8"))
    assert rapport["volumes"]["total_recus"] == 3184
    assert sum(rapport["statuts_finaux"]["nombres"].values()) == 3184


def test_module2_profil_et_livrables_de_sortie(tmp_path):
    """Le nettoyage du Module 2 écrit les 4 livrables de sortie/ et reste cohérent avec le profil regles_metier.md."""
    from src.config import PROFIL_MODULE2
    from src.preparation.nettoyage import produire_sortie
    R = executer_pipeline(DATE_REF, simuler_hasard=False, profil=PROFIL_MODULE2)
    d = R.donnees
    assert d["statut_final"].value_counts().sum() == 3184
    assert (d.loc[d["surface_brute"] == "quatre-vingt", "statut_final"] == "quarantaine").all()
    futures = d[(d["date_collecte"] > DATE_REF.isoformat()) & ~d["est_copie_exacte"]]
    assert len(futures) == 5 and (futures.loc[futures["statut_source"] == "Vendu", "statut_final"] == "quarantaine").all()
    assert (futures.loc[futures["statut_source"] != "Vendu", "statut_final"] == "conserve_avertissement").all()
    produire_sortie(R, tmp_path)
    for nom in ("donnees_propres.csv", "quarantine.csv", "avertissements.csv", "rapport_qualite.md"):
        assert (tmp_path / nom).exists()
    q = pd.read_csv(tmp_path / "quarantine.csv", encoding="utf-8-sig")
    assert q["raison"].notna().all()
    rapport = (tmp_path / "rapport_qualite.md").read_text(encoding="utf-8")
    assert all(f"## Mesure {i}" in rapport for i in range(1, 7))
