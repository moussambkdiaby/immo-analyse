# Plan de travail — Module 2 (préparation des données pour le Machine Learning)

**Règle d'or du module** : chaque décision a une **preuve chiffrée**, écrite dans `docs/justifications.md` **au moment où elle est prise**.
**Ordre imposé** : les 9 compétences se font dans l'ordre (le guide interdit de sauter une compétence).
**Date limite** : à compléter → `____`  ·  **Individuel / groupe** : `____`

## Livrables et critères éliminatoires (0 à la note si absent)

| Livrable | Critère éliminatoire | État |
|---|---|---|
| `models/pipeline_preparation.joblib` | présent et **rechargeable** | ⏳ |
| `notebooks/02_preparation_analyse.ipynb` | exécutable de bout en bout, **sans intervention** | ⏳ |
| `docs/justifications.md` | au moins une entrée **par décision** | 🟡 comp 3 faite (J-01 à J-15) |
| `sources/` et `referentiels/` | **non modifiés** | ✅ (SHA-256 avant / après) |
| `sortie/` | 3 fichiers : propres, quarantaine, avertissements (+ rapport) | ✅ |
| `reports/dictionnaire_features.csv` | toutes les features documentées | ⏳ |

## Avancement par compétence

| # | Compétence | Poids indicatif | Livrable principal | État |
|---|---|---|---|---|
| 3 | Nettoyage (manquants, doublons, aberrants) | 12 % | `sortie/*`, 6 mesures, J-01…J-15 | ✅ **fait** (Phase 0) |
| 1 | Types, distributions, statistiques | — | types par source, asymétrie de `prix` avant / après log, choix de la cible | ⏳ Phase 1 |
| 2 | EDA + visualisations diagnostiques par source | — | manquants (mécanisme), Simpson, tendance (Mann-Kendall) | ⏳ Phase 1 |
| 4 | Visualisations de restitution | — | V1 à V6 titrées, axes avec unités, conclusion chiffrée | ⏳ Phase 2 |
| 5 | Encodage + normalisation | — | encodeurs par variable, `handle_unknown`, scaler | ⏳ Phase 3 |
| 6 | Feature engineering | — | variables candidates, gain mesuré en validation croisée | ⏳ Phase 3 |
| 7 | Split train / validation / test | — | stratifié, vérification par source, dédoublonnage **avant** le split | ⏳ Phase 4 |
| 8 | Data leakage | — | audit `prix_m2`, `statut`, `source`, indicateurs de manque | ⏳ Phase 4 |
| 9 | Pipeline reproductible | — | `joblib`, 6 vérifications, une ligne de chaque source | ⏳ Phase 5 |
| — | Rapport final, dictionnaire de features, soutenance | 10 % + 15 % + 10 % | `rapport`, `dictionnaire_features.csv` | ⏳ Phase 6 |

(Barème : compétences techniques 55 %, documentation 15 %, conformité du rendu 10 %, rapport 10 %, soutenance 10 %.)

## Phases (ordre de travail)

| Phase | Contenu | Durée estimée (guidé) |
|---|---|---|
| 0 | Mise en place + nettoyage aligné sur `regles_metier.md` | 2 à 3 h — **fait** |
| 1 | Comp 1 et 2 : types, stats, EDA, diagnostics | 4 à 5 h |
| 2 | Comp 4 : V1 à V6 | 2 à 3 h |
| 3 | Comp 5 et 6 : encodage, normalisation, features | 4 à 5 h |
| 4 | Comp 7 et 8 : split, fuites | 3 à 4 h |
| 5 | Comp 9 : pipeline sérialisé et 6 vérifications | 2 h |
| 6 | Rapport, dictionnaire, relecture, soutenance | 4 à 5 h |

## Pièges qui coûtent le plus de points

| Piège | Coût | Parade |
|---|---|---|
| Notebook non exécutable | −10 | `Restart` + `Run All` avant chaque commit |
| Décision sans preuve chiffrée | jusqu'à −15 | une entrée dans `justifications.md` par décision |
| `prix_m2` gardé comme variable du modèle | −6 | c'est `prix / surface` : la cible est dedans (fuite) |
| Pipeline non sérialisé | −4 | `joblib.dump` puis rechargement testé |
| Imputer avant le split | fuite | imputer **dans** le pipeline, ajusté sur train seul |
| Dédoublonner après le split | fuite | dédoublonner **avant** (déjà fait en Phase 0) |
| Imputer la moyenne sur `prix` | interdit | `prix` est la cible |

## Commandes utiles

```bash
cd MODULE02
python -m src.preparation.nettoyage --date-ref 2026-11-03   # régénère sortie/ (profil module2)
pytest                                                      # 109 tests
# depuis la racine du dépôt : python executer_project.py --module 2
```
