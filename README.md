# ImmoAnalyse

Projet fil rouge de data science sur des annonces immobilières **synthétiques** inspirées du contexte sénégalais (DEV DATA P8, Sonatel Academy). Le but : suivre une chaîne complète et reproductible, des fichiers bruts jusqu'à un jeu de données préparé pour un futur modèle de Machine Learning.

> Les données sont synthétiques : elles ne représentent pas des transactions réelles et ne permettent pas d'estimer les prix du marché.

## Parcours du projet

Le dépôt contient des modules **autonomes** (chacun a son code, ses tests, ses données brutes en lecture seule et ses livrables). Un module rendu n'est jamais retouché par le suivant : il reste reproductible.

| Module | Sujet | Dossier | État |
|---|---|---|---|
| 1 | Python pour l'IA et le ML : contrôle de la qualité des données (5 sources CSV, Excel, JSON) | [`MODULE01/`](MODULE01/README.md) | terminé |
| 2 | Préparation des données pour le Machine Learning | [`MODULE02/`](MODULE02/README.md) | en cours (compétence 3 faite) |

## Installation (une seule fois, à la racine du dépôt)

Prérequis : **Python 3.10 ou plus récent** (testé avec 3.12).

```bash
git clone https://github.com/<utilisateur>/immo-analyse.git
cd immo-analyse
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Exécution

Depuis la racine du dépôt :

```bash
python executer_project.py                       # vérifie les données, lance les modules 1 et 2
python executer_project.py --module 2            # un seul module
python executer_project.py --tests               # lance les tests de chaque module (104 + 109)
python executer_project.py --date-ref 2026-11-03 # fixe la « date d'exécution » (résultats reproductibles)
```

On peut aussi travailler directement dans un module : `cd MODULE02` puis les commandes de son `README.md`.

## Données brutes

Les cinq sources (`agence_teranga.xlsx`, `import_historique.csv`, `notaires.csv`, `particuliers.json`, `plateforme_immo_sn.csv`) et les quatre référentiels sont **en lecture seule** : aucun module ne les modifie. Chaque module en possède une copie (`MODULE01/data/raw/` et `MODULE02/sources/`, `MODULE02/referentiels/`) et `executer_project.py` vérifie qu'elles sont **identiques octet pour octet**.

## Structure du dépôt

```
immo-analyse/
├── README.md               # ce fichier : parcours, installation, exécution
├── requirements.txt        # dépendances communes à tous les modules
├── executer_project.py     # lance un module (ou tous) depuis la racine
├── .gitignore
├── MODULE01/               # Module 1 : pipeline de qualité des données
└── MODULE02/               # Module 2 : préparation pour le Machine Learning
```
