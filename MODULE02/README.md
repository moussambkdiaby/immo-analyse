# MODULE02 — Préparation des données pour le Machine Learning

Suite d'ImmoAnalyse : on transforme les 5 sources brutes en un jeu de données **préparé, documenté et reproductible**, utilisable dans un pipeline de Machine Learning. Règle absolue du module : **chaque décision a une preuve chiffrée**, écrite dans `docs/justifications.md` au moment où elle est prise.

> Ce dossier est **autonome** : il contient ses données brutes (`sources/`, `referentiels/`, **en lecture seule**), son code, ses tests et ses livrables. Toutes les commandes s'exécutent **depuis `MODULE02/`**.

## Structure

```
MODULE02/
├── sources/                   # 5 sources brutes (JAMAIS modifiées)
├── referentiels/              # géographie, catégories, dictionnaire, règles métier (JAMAIS modifiés)
├── sortie/                    # livrables du nettoyage : donnees_propres.csv, quarantine.csv, avertissements.csv, rapport_qualite.md
├── notebooks/                 # 02_preparation_analyse.ipynb (exécutable de bout en bout)
├── models/                    # pipeline_preparation.joblib (pipeline sérialisé)
├── reports/                   # dictionnaire_features.csv
├── docs/                      # justifications.md (registre des décisions), PLAN_MODULE2.md (avancement)
├── src/                       # code : loaders, processing, validation, analysis, preparation
└── tests/                     # 109 tests automatisés
```

## Installation et exécution

L'environnement virtuel est unique et se trouve à la racine du dépôt (voir le `README.md` racine).

```bash
cd MODULE02
python -m src.preparation.nettoyage --date-ref 2026-11-03   # nettoyage -> sortie/
pytest                                                       # 109 tests
```

## Avancement

Voir `docs/PLAN_MODULE2.md` (critères éliminatoires, avancement par compétence, pièges) et `docs/justifications.md` (décisions J-01 à J-15 pour la compétence 3).

## Lien avec le Module 1

La compétence 3 (nettoyage) réutilise le pipeline du Module 1 avec le **profil de règles du Module 2**, aligné sur `referentiels/regles_metier.md` (`PROFIL_MODULE2` dans `src/config.py`). Le Module 1 reste intact dans `MODULE01/`.
