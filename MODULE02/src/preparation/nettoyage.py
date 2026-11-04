"""Compétence 3 du Module 2 : nettoyage (manquants, doublons, aberrants) et livrables de `sortie/`.

Ce module RÉUTILISE le pipeline du Module 1 (chargement, normalisation, règles, quarantaine, doublons)
avec le profil de règles du Module 2 (`PROFIL_MODULE2`, aligné sur `regles_metier.md`), puis écrit :

    sortie/donnees_propres.csv    corpus nettoyé et concaténé (conforme + corrigé + conservé avec avertissement)
    sortie/quarantine.csv         lignes rejetées + raison
    sortie/avertissements.csv     lignes conservées avec l'anomalie signalée
    sortie/rapport_qualite.md     les 6 mesures imposées par regles_metier.md (+ détail)

Exécution :  python -m src.preparation.nettoyage [--date-ref AAAA-MM-JJ]
"""
from __future__ import annotations

import argparse
import logging
from datetime import date

import pandas as pd

from src.analysis.export import COLONNES_PROPRES, COLONNES_QUARANTAINE, ENCODAGE
from src.analysis.qualite import construire_rapport, rapport_markdown, valeurs_manquantes
from src.config import PROFIL_MODULE2, SORTIE
from src.processing.pipeline import Resultats, executer_pipeline

RETENUS = ["conforme", "corrige", "conserve_avertissement"]


def six_mesures(R: Resultats, rapport: dict) -> str:
    """Section « Les 6 mesures imposées par regles_metier.md » (en tête de sortie/rapport_qualite.md)."""
    m = valeurs_manquantes(R)
    m = m[~m["colonne_absente"]]
    # Taux global par colonne = manquants / évalués, sur les seules sources qui possèdent la colonne.
    par_colonne = (m.groupby("colonne").agg(manquants=("manquants", "sum"), evalues=("evalues", "sum")))
    par_colonne["taux_manquant_pct"] = (100 * par_colonne["manquants"] / par_colonne["evalues"]).round(1)
    lignes_m = "\n".join(f"| {c} | {int(r.manquants)} | {int(r.evalues)} | {r.taux_manquant_pct} % |" for c, r in par_colonne.iterrows())
    erreurs = pd.DataFrame(rapport["erreurs_de_conversion"]).groupby("champ")["erreurs"].sum()
    lignes_e = "\n".join(f"| {c} | {int(n)} |" for c, n in erreurs.items())
    sf, rap, v = rapport["statuts_finaux"], rapport["rapprochement"], rapport["volumes"]
    return f"""# Les 6 mesures imposées par `regles_metier.md`

Date d'exécution de référence : **{rapport['date_reference']}** · profil de règles : **{R.profil['nom']}** · enregistrements reçus : **{v['total_recus']}**

## Mesure 1 — Taux de valeurs manquantes par colonne

Une colonne **absente** d'une source n'est pas comptée « manquante ». Un vide déguisé (`None FCFA`) est compté manquant. Dénominateur : enregistrements évalués (copies exactes exclues) des sources qui possèdent la colonne.

| colonne | manquants | évalués | taux |
|---|---|---|---|
{lignes_m}

## Mesure 2 — Doublons exacts

**{rapport['doublons_exacts']['nombre']}** copies exactes ({rapport['doublons_exacts']['taux_pct_des_recus']} % des reçus), écartées avant validation ({', '.join(f'{k} : {n}' for k, n in rapport['doublons_exacts']['par_source'].items())}).

## Mesure 3 — Doublons probables entre enregistrements

**{rap['paires_retenues']}** paires retenues sur {rap['paires_comparees']} comparées ({rap['doublons_probables']} doublons probables, {rap['conflits']} conflits). Rien n'est fusionné (`regles_metier.md` : *ne pas fusionner sans justification*). Le hasard produirait en moyenne **{rap['faux_doublons_attendus_par_hasard']['moyenne']}** paires : ce sont des signaux à vérifier, pas des preuves.

## Mesure 4 — Erreurs de conversion par champ (nombre d'enregistrements)

| champ | erreurs |
|---|---|
{lignes_e}

## Mesure 5 — Enregistrements corrigés / mis en quarantaine / conservés avec avertissement

| statut | enregistrements | % des reçus |
|---|---|---|
| corrigés (valeur normalisée par une règle sûre) | {sf['nombres']['corrige']} | {sf['taux_pct_des_recus']['corrige']} % |
| mis en quarantaine | {sf['nombres']['quarantaine']} | {sf['taux_pct_des_recus']['quarantaine']} % |
| conservés avec avertissement | {sf['nombres']['conserve_avertissement']} | {sf['taux_pct_des_recus']['conserve_avertissement']} % |
| entièrement conformes | {sf['nombres']['conforme']} | {sf['taux_pct_des_recus']['conforme']} % |
| copies exactes écartées | {sf['nombres']['doublon_exact_ecarte']} | {sf['taux_pct_des_recus']['doublon_exact_ecarte']} % |

Statuts mutuellement exclusifs : leur somme est exactement le nombre d'enregistrements reçus.

## Mesure 6 — Taux d'enregistrements entièrement conformes

**{sf['taux_conforme_strict_pct']} %** (conformes ÷ reçus : aucune correction, aucun avertissement). Pour mémoire, le taux d'enregistrements **exploitables** (conformes + corrigés + avertissements) est de {sf['taux_exploitable_pct']} %.

---

# Détail complet du rapport de qualité

"""


def produire_sortie(R: Resultats, dossier=SORTIE) -> dict:
    """Écrit les 4 livrables de `sortie/` et renvoie le rapport (dictionnaire)."""
    dossier.mkdir(parents=True, exist_ok=True)
    d = R.donnees
    propres = d[d["statut_final"].isin(RETENUS)]
    quarantaine = d[d["statut_final"] == "quarantaine"].copy()
    averti = d[d["statut_final"] == "conserve_avertissement"].copy()

    propres[COLONNES_PROPRES].to_csv(dossier / "donnees_propres.csv", index=False, encoding=ENCODAGE)
    quarantaine["raison"] = quarantaine["motifs_bloquants"]
    quarantaine[["raison"] + COLONNES_QUARANTAINE].to_csv(dossier / "quarantine.csv", index=False, encoding=ENCODAGE)
    averti["nb_avertissements"] = averti["avertissements"].str.count(" ; ") + 1
    colonnes_av = ["id_bien", "source", "ligne_source", "avertissements", "nb_avertissements", "type_transaction",
                   "type_bien", "ville", "montant", "surface_m2", "prix_m2", "date_collecte", "lien_rapprochement"]
    averti[colonnes_av].to_csv(dossier / "avertissements.csv", index=False, encoding=ENCODAGE)

    rapport = construire_rapport(R)
    (dossier / "rapport_qualite.md").write_text(six_mesures(R, rapport) + rapport_markdown(rapport, R), encoding="utf-8")
    return rapport


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Module 2, compétence 3 : nettoyage et livrables de sortie/")
    p.add_argument("--date-ref", type=date.fromisoformat, default=None, help="date d'exécution AAAA-MM-JJ")
    p.add_argument("--sans-simulation", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level="INFO", format="%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")
    R = executer_pipeline(args.date_ref, simuler_hasard=not args.sans_simulation, profil=PROFIL_MODULE2)
    rapport = produire_sortie(R)
    logging.getLogger("immoanalyse").info("sortie/ écrit : %s", rapport["statuts_finaux"]["nombres"])
    return 0 if R.sources_intactes else 1


if __name__ == "__main__":
    raise SystemExit(main())
