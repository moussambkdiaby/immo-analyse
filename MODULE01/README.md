# ImmoAnalyse — pipeline de qualité de données immobilières

Projet fil rouge du **Module 1 : Python pour l'IA et le Machine Learning** (DEV DATA P8, Sonatel Academy).

> Ce dossier est le **MODULE01** du dépôt `immo-analyse` : il est autonome. Toutes les commandes ci-dessous s'exécutent **depuis `MODULE01/`** (`cd MODULE01`). Le projet complet et les autres modules sont décrits dans le `README.md` à la racine du dépôt.

Application Python modulaire et reproductible qui **importe 5 sources immobilières hétérogènes** (CSV, Excel, JSON), **contrôle leur qualité** avec des règles métier explicites, **corrige** ce qui peut l'être sans ambiguïté, **met en quarantaine** ce qui ne peut pas être exploité de façon fiable, mesure la qualité avec des **indicateurs chiffrés**, analyse les données retenues et **exporte** des fichiers propres accompagnés d'un rapport.

> Les données sont **synthétiques** (inspirées du contexte sénégalais) : elles illustrent la méthode et ne doivent pas servir à estimer le marché réel. Les prix de vente sont des prix **demandés** (annonces), pas des prix de transaction conclue.

## 1. Résultats en un coup d'œil

| Indicateur | Valeur |
|---|---|
| Enregistrements reçus (5 sources) | **3 184** (3 224 annoncés : 40 lignes de l'agence sont absentes du fichier) |
| Copies exactes écartées | **15** (0,5 %) — toutes dans la plateforme |
| Entièrement conformes | **1 393** (43,8 %) |
| Corrigés (valeur normalisée par une règle sûre) | **932** (29,3 %) |
| Conservés avec avertissement | **658** (20,7 %) |
| Mis en quarantaine (avec motif) | **186** (5,8 %) |
| **Exploitables** (conformes + corrigés + avertissements) | **2 983** (93,7 %) |
| Règles de validation | 29 (7 bloquantes, 22 avertissements) |
| Fichiers bruts préservés | oui (empreintes SHA-256 identiques avant et après) |

Le détail complet (dénominateurs, taux par règle, valeurs manquantes, erreurs de conversion, motifs de quarantaine) est dans `reports/rapport_qualite.md`.

## 2. Installation

Prérequis : **Python 3.10 ou plus récent** (testé avec 3.12).

```bash
git clone https://github.com/<utilisateur>/immo-analyse.git
cd immo-analyse
python3 -m venv .venv      # environnement virtuel unique, à la racine du dépôt
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt   # requirements.txt est à la racine du dépôt
cd MODULE01
```

Les données brutes (`data/raw/sources/` et `data/raw/referentiels/`) sont **fournies dans le dépôt** : rien d'autre à télécharger.

## 3. Exécution

```bash
python -m src.main                         # pipeline complet (≈ 15 secondes)
python -m src.main --date-ref 2026-10-29   # fixe la « date d'exécution » : résultats reproductibles
python -m src.main --sans-simulation       # saute l'estimation des faux doublons (plus rapide)
pytest                                     # 104 tests automatisés
```

Le notebook d'analyse (`notebooks/01_exploration.ipynb`) s'ouvre dans VS Code (noyau : `.venv`) ; il s'exécute de haut en bas avec `Restart` puis `Run All`.

**Sorties produites** (écrasées à chaque exécution : relancer ne crée aucun doublon) :

| Fichier | Contenu |
|---|---|
| `data/processed/donnees_propres.csv` / `.json` | enregistrements exploitables, valeurs propres **et** valeurs brutes d'origine |
| `data/quarantine/quarantaine.csv` / `.json` | enregistrements rejetés avec leur **motif**, leur source et leur ligne d'origine |
| `data/quarantine/doublons_exacts_ecartes.csv` | copies exactes écartées et l'original dont elles sont issues |
| `reports/quality_report.json` | rapport de qualité chiffré (complet, lisible par un programme) |
| `reports/quality_summary.csv` | indicateurs « à plat » (un tableur suffit) |
| `reports/rapport_qualite.md` | rapport lisible : définitions, tableaux, décisions, limites |
| `reports/anomalies.csv` | journal : une ligne par violation de règle (valeur fautive, motif) |
| `reports/rapprochements.csv` | doublons probables et conflits entre enregistrements |
| `reports/catalogue_regles.csv` | les 29 règles, leur gravité et leur justification |
| `reports/analyse_*.csv` | statistiques descriptives (prix au m², loyers, surfaces) |

## 3 bis. Structure du projet

```
MODULE01/
├── data/
│   ├── raw/                  # sources et référentiels fournis : JAMAIS modifiés
│   ├── processed/            # données propres
│   └── quarantine/           # données rejetées + motifs
├── reports/                  # rapports de qualité et analyses
├── notebooks/
│   ├── 00_profilage.ipynb    # exploration de la plateforme (démarche pas à pas)
│   └── 01_exploration.ipynb  # résultats du pipeline : distributions, anomalies, conformité
├── src/
│   ├── config.py             # chemins, SEUILS, tables de correspondance (aucun seuil « en dur » ailleurs)
│   ├── loaders/sources.py    # lecture des 5 sources vers un schéma commun + provenance
│   ├── processing/
│   │   ├── normalisation.py  # fonctions pures : prix, surface, dates, catégories... -> (valeur, statut)
│   │   ├── referentiels.py   # classe Referentiels (géographie, catégories)
│   │   ├── traitement.py     # combinaison, normalisation en colonnes, doublons exacts
│   │   ├── rapprochement.py  # doublons probables et conflits entre sources
│   │   └── pipeline.py       # orchestration : executer_pipeline()
│   ├── validation/
│   │   ├── regles.py         # classe Regle + catalogue des 29 règles
│   │   └── controle.py       # application des règles, journal, statut final
│   ├── analysis/
│   │   ├── qualite.py        # indicateurs de qualité, rapport JSON / CSV / Markdown
│   │   ├── stats.py          # statistiques descriptives (NumPy, Pandas)
│   │   └── export.py         # exports + vérification des fichiers produits
│   └── main.py               # point d'entrée
├── tests/                    # 104 tests : conformes, invalides, cas limites, intégration
├── requirements.txt
└── README.md
```

## 4. Le pipeline, étape par étape

1. **Chargement** (`loaders`) : chaque source est lue **sans aucune conversion** (tout en texte) avec ses propres options (séparateur, encodage `latin-1` pour l'historique, feuille `Annonces` de l'Excel, JSON imbriqué aplati). Toutes produisent le **même schéma de colonnes brutes** et gardent leur **provenance** (`source`, `id_local`, `ligne_source`).
2. **Combinaison** : les 5 sources sont empilées. L'identifiant global est `id_bien = source:id_local` : un identifiant local n'est **pas** une clé fiable (deux sources réutilisent les mêmes numéros pour des biens différents).
3. **Doublons exacts** : deux lignes d'une même source identiques sur tous les champs. On garde la première, les copies sont écartées et comptées à part.
4. **Normalisation** : chaque champ est converti par une fonction pure qui renvoie `(valeur, statut)`. La valeur brute n'est **jamais écrasée** (colonne `*_brut` conservée) : la normalisation est réversible et chaque correction est comptable.
5. **Rapprochement** : doublons probables et conflits entre enregistrements (section 6).
6. **Validation** : 29 règles (`Regle`) appliquées à chaque ligne ; chacune renvoie *conforme*, *non conforme* ou *non évaluable*.
7. **Décision** : un statut final unique par enregistrement (section 7).
8. **Indicateurs, analyse, exports** et vérification des fichiers écrits.

## 5. Règles métier

Les seuils sont des **hypothèses pédagogiques** (cahier § 6), pas des normes du marché. Ils sont tous dans `src/config.py` (`SEUILS`) : on les modifie sans toucher aux fonctions de traitement.

### Règles bloquantes → quarantaine

| Code | Règle | Ce qui est vérifié | Source de la règle |
|---|---|---|---|
| B01 | `identifiant_present` | L'identifiant local est renseigné | Cahier § 6.1 : obligatoire dans chaque source, quarantaine si absent |
| B02 | `transaction_valide` | Vente ou location après normalisation | Cahier § 6.1 : quarantaine si non interprétable |
| B03 | `prix_ou_loyer_positif` | Prix (vente) ou loyer (location) numérique strictement positif | regles_metier.md : prix absent, non numérique ou <= 0 -> quarantaine |
| B04 | `surface_positive` | Surface numérique strictement positive | regles_metier.md : surface absente, non numérique ou <= 0 -> quarantaine |
| B05 | `date_interpretable` | Date lisible et possible (pas 32/13/2024) | regles_metier.md : date non interprétable ou impossible -> quarantaine |
| B06 | `date_non_future` | Date non postérieure à la date d'exécution | Cahier § 6.1 : non future par rapport à la date d'exécution |
| B07 | `type_bien_valide` | Type de bien parmi les 7 catégories du référentiel | Cahier § 6.1 : quarantaine si hors référentiel (regles_metier.md dit « avertissement » : on suit le cahier) |

### Règles d'avertissement → conservé et signalé

| Code | Règle | Ce qui est vérifié | Source de la règle |
|---|---|---|---|
| A01 | `periodicite_connue` | Un loyer a une périodicité reconnue (mensuel, trimestriel...) | Cahier § 6.1 : signaler, ne pas deviner |
| A02 | `prix_vente_plausible` | Prix de vente entre les seuils généraux | regles_metier.md : prix < 100 000 ou > 2 milliards FCFA = atypique |
| A03 | `loyer_mensuel_plausible` | Loyer mensuel entre 25 000 et 5 000 000 FCFA | Cahier § 6.2 (évalué seulement si la périodicité est mensuelle) |
| A04 | `prix_dans_fourchette_categorie` | Prix de vente dans la fourchette de sa catégorie | referentiel_categories.csv : fourchettes indicatives (hypothèses pédagogiques) |
| A05 | `surface_plausible` | Surface entre 5 et 2 000 m² | regles_metier.md : atypique, pas nécessairement faux |
| A06 | `surface_dans_fourchette_categorie` | Surface dans la fourchette de sa catégorie | referentiel_categories.csv : surfaces typiques |
| A07 | `prix_m2_dans_plage_referentiel` | Prix au m² dans la plage déduite du référentiel | Cahier § 6.2 (plage déduite : prix min / surface max -> prix max / surface min) |
| A08 | `prix_m2_non_atypique` | Prix au m² hors valeurs extrêmes de sa catégorie (règle de l'IQR) | Complément statistique : la plage du référentiel est trop large pour détecter |
| A09 | `chambres_valides` | Nombre de chambres : entier >= 0 | Cahier § 6.1 |
| A10 | `salles_bain_valides` | Nombre de salles de bain : entier >= 0 | Cahier § 6.1 |
| A11 | `chambres_non_atypiques` | Pas plus de 10 chambres pour un appartement ou un studio | Cahier § 6.2 |
| A12 | `salles_bain_coherentes` | Salles de bain <= chambres + 2 | Cahier § 6.2 |
| A13 | `pieces_coherentes_type` | Terrain sans pièce ; maison, villa, appartement avec au moins 1 chambre | Cahier § 6.1 : cohérent avec le type de bien |
| A14 | `ville_reconnue` | Ville renseignée et présente dans le référentiel géographique | Cahier § 6.1 : signaler, ne pas corriger sans preuve |
| A15 | `region_reconnue` | Région renseignée et présente dans le référentiel | Cahier § 6.1 |
| A16 | `region_ville_coherentes` | La ville appartient bien à la région indiquée | regles_metier.md : signaler, ne pas corriger sans preuve |
| A17 | `statut_coherent_transaction` | Le statut est compatible avec la transaction écrite dans la source | Cohérence interne (évaluée seulement quand la transaction est écrite, pas déduite du statut) |
| A18 | `dates_coherentes` | La date d'expiration n'est pas antérieure à la mise en ligne | Cahier § 6.1 : date_mise_a_jour >= date_collecte -> signaler |
| A19 | `date_non_concentree` | Pas 20 annonces ou plus de la même source le même jour | Détection d'un import en masse (valeurs par défaut probables) |
| A20 | `pas_de_doublon_probable` | Aucun doublon probable dans les autres enregistrements | Cahier § 6.1 : distinguer doublon exact, doublon probable et conflit |
| A21 | `pas_de_conflit_entre_enregistrements` | Aucun conflit (même bien, valeurs contradictoires) | Cahier § 6.1 / Axe 1 : les conflits sont signalés, pas résolus arbitrairement |
| A22 | `identifiant_unique` | L'identifiant global n'apparaît qu'une fois | Cahier § 5.3 : un identifiant local n'est pas une clé fiable |

## 6. Doublons et conflits : stratégie documentée

| Cas | Définition | Traitement |
|---|---|---|
| **Doublon exact** | toutes les valeurs brutes identiques, même source | on garde la première occurrence ; la copie est écartée et tracée dans `doublons_exacts_ecartes.csv` |
| **Doublon probable** | deux enregistrements décrivent *probablement* le même bien, tous attributs concordants | conservés tous les deux, avertissement `A20`, identifiant de groupe |
| **Conflit** | même bien probable mais un attribut se contredit (prix > 2 % d'écart, chambres, salles de bain) | conservés tous les deux, avertissement `A21`, champs en conflit listés. **Aucune valeur n'est choisie arbitrairement** |

**Méthode.** Blocage (même ville, type de bien, transaction), puis score de similarité sur **plusieurs attributs** : surface (0,4), prix (0,4), pièces (0,1), date (0,1) ; seuil **0,75**, avec en plus une surface identique à 0,5 % près et un prix à 6 % près. La date pèse peu : un bien est annoncé, vendu, réannoncé à des mois d'écart.

**Justification du seuil.** Sur les 12 622 paires comparables, les scores forment un continuum jusqu'à ≈ 0,70 (coïncidences), puis un vide avant les paires réellement suspectes. Un **test par permutation** (prix mélangés dans chaque bloc) estime à ≈ 4,9 faux doublons dus au hasard contre 3 paires retenues : ces paires sont des **signaux à vérifier à la main**, pas des preuves. C'est écrit dans le rapport. La paire `PRT-01461` / `PRT-02191` (même surface, mêmes pièces, prix exactement ×0,95) porte la signature la plus nette d'une variante volontaire.

## 7. Décisions de nettoyage (y compris celles de ne PAS corriger)

**Statuts finaux** (mutuellement exclusifs, par ordre de priorité) : `doublon_exact_ecarte` > `quarantaine` > `conserve_avertissement` > `corrige` > `conforme`. Leur somme est exactement le nombre d'enregistrements reçus : aucun enregistrement n'est compté deux fois.

| Situation | Décision | Pourquoi |
|---|---|---|
| `438 746 000` (espaces) | **corrigé** → 438746000 | les espaces sont des séparateurs de milliers, sans autre lecture possible |
| `57.62 millions` | **corrigé** → 57 620 000 | l'unité est écrite dans la valeur |
| `92,4` (surface) | **corrigé** → 92,4 | virgule suivie de 1 ou 2 chiffres : décimale |
| `quatre-vingt` (surface) | **corrigé** → 80 | nombre en lettres sans ambiguïté |
| `appart`, `MAISON`, `Thiès`/`THIES` | **corrigé** (synonyme, casse, accents) | le référentiel donne les synonymes admis |
| `1,250` | **non converti** (ambigu) | 1 250 ou 1,25 ? Le texte ne contient pas la preuve |
| `à négocier` | **quarantaine** | aucun nombre, on n'invente rien |
| `None FCFA` | **manquant** | un `None` Python converti en texte : vide déguisé |
| surface `-30` | **quarantaine** | un signe moins est peut-être une erreur de saisie : on ne fait pas `abs()` |
| prix ou surface `0` | **quarantaine** | règle bloquante (strictement positif) |
| date `32/13/2024` | **quarantaine** | impossible ; aucun des deux nombres ne peut être un mois |
| date `JJ/MM/AAAA` | **convertie** si la convention est **prouvée** | déduite par source : un 1er nombre > 12 prouve un jour. Agence, particuliers, historique : JJ/MM. Notaires : aucune date à barres valide → quarantaine |
| date `2028-12-01` | **quarantaine** | postérieure à la date d'exécution (cahier § 6.1) |
| loyer sans périodicité | **conservé, signalé** (A01) | on ne devine pas ; le plafond de loyer devient *non évaluable* |
| ville et région incompatibles | **conservé, signalé** (A16) | « ne pas corriger sans preuve » |
| prix hors fourchette de sa catégorie | **conservé, signalé** | fourchettes indicatives ; au m² le bien est souvent ordinaire |
| type de bien hors référentiel | **quarantaine** | le cahier dit quarantaine, `regles_metier.md` dit avertissement : on suit le cahier (aucun cas ici) |
| transaction absente (agence) | **déduite du statut** (Loué, Disponible → location) | règle prouvée : dans les sources où la transaction est écrite, 0 contre-exemple |
| transaction absente (notaires, historique) | **déduite de la nature de la source** | actes de vente / ventes historiques |

**Ventes et locations** sont séparées dans tout le pipeline (`prix_vente` / `loyer` / `loyer_mensuel`) avant toute statistique : un loyer mensuel n'est pas comparable à un prix de vente.

**Particularité repérée** : 40 annonces de la plateforme (`PLT-02602` à `PLT-02680`) partagent la même date, le même statut et 0 chambre / 0 salle de bain, y compris des villas : signature d'un import en masse avec valeurs par défaut. Elles sont conservées avec l'avertissement `A19`, à vérifier à la source.

## 8. Indicateurs de qualité (définitions)

- **Taux de conformité d'une règle** = conformes ÷ **évaluables** × 100. Le dénominateur est toujours indiqué. Les **non évaluables** sont comptés à part et ne sont **jamais** considérés comme conformes.
- **Erreur de conversion** = valeur présente mais impossible à convertir de façon fiable ; une case vide est comptée dans les valeurs manquantes, pas dans les erreurs.
- **Taux exploitable** = (conforme + corrigé + conservé avec avertissement) ÷ reçus. **Taux conforme strict** = conforme ÷ reçus.
- Une colonne **absente** d'une source (pas de statut dans l'historique) n'est pas comptée « manquante ».

## 9. Tests

`pytest` lance **104 tests** : normalisation (cas conformes, invalides, **cas limites** comme `1,250` ou `03/04/2024`), règles de validation et décision finale, rapprochement (doublon, conflit, seuil modifiable), et un **test d'intégration** sur les vraies données (les statuts s'additionnent à 3 184, les 6 dates impossibles et les 5 dates futures sont en quarantaine, les fichiers bruts restent intacts, deux exécutions donnent les mêmes résultats, les exports sont cohérents et idempotents).

## 10. Reproductibilité et intégrité

- `--date-ref` fixe la date d'exécution (utile pour « date future » ou « hier ») ; la simulation du hasard est initialisée avec une graine fixe.
- Les empreintes SHA-256 des 5 fichiers bruts sont calculées avant et après l'exécution et comparées (résultat dans le rapport).
- Les exports vérifient leur propre cohérence (somme des fichiers = lignes reçues, identifiants uniques, motif présent sur chaque ligne en quarantaine, aucun prix ou surface ≤ 0 dans les données propres).

## 11. Limites

- Données synthétiques ; seuils et fourchettes = hypothèses pédagogiques.
- Prix de vente = prix **demandés**.
- Le rapprochement entre sources est peu discriminant sur ce jeu : les paires retenues sont indistinguables du hasard.
- 40 annonces de l'agence sont annoncées mais absentes du fichier fourni.
- Non réalisé (hors périmètre obligatoire) : export Parquet, registre de sources YAML, API locale, modèle de Machine Learning.
