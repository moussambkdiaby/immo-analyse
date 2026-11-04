# Les 6 mesures imposées par `regles_metier.md`

Date d'exécution de référence : **2026-11-03** · profil de règles : **module2** · enregistrements reçus : **3184**

## Mesure 1 — Taux de valeurs manquantes par colonne

Une colonne **absente** d'une source n'est pas comptée « manquante ». Un vide déguisé (`None FCFA`) est compté manquant. Dénominateur : enregistrements évalués (copies exactes exclues) des sources qui possèdent la colonne.

| colonne | manquants | évalués | taux |
|---|---|---|---|
| categorie_brute | 0 | 3169 | 0.0 % |
| chambres_brute | 0 | 3169 | 0.0 % |
| date_brute | 0 | 3169 | 0.0 % |
| description | 163 | 860 | 19.0 % |
| devise_brute | 0 | 860 | 0.0 % |
| montant_brut | 85 | 3169 | 2.7 % |
| quartier_brute | 0 | 860 | 0.0 % |
| region_brute | 0 | 3169 | 0.0 % |
| sdb_brute | 0 | 2759 | 0.0 % |
| statut_brut | 0 | 2641 | 0.0 % |
| surface_brute | 80 | 3169 | 2.5 % |
| transaction_brute | 0 | 1591 | 0.0 % |
| ville_brute | 8 | 3169 | 0.3 % |

## Mesure 2 — Doublons exacts

**15** copies exactes (0.5 % des reçus), écartées avant validation (plateforme : 15).

## Mesure 3 — Doublons probables entre enregistrements

**3** paires retenues sur 12609 comparées (0 doublons probables, 3 conflits). Rien n'est fusionné (`regles_metier.md` : *ne pas fusionner sans justification*). Le hasard produirait en moyenne **4.9** paires : ce sont des signaux à vérifier, pas des preuves.

## Mesure 4 — Erreurs de conversion par champ (nombre d'enregistrements)

| champ | erreurs |
|---|---|
| categorie | 0 |
| chambres | 0 |
| date | 6 |
| montant | 5 |
| region | 0 |
| sdb | 0 |
| statut | 0 |
| surface | 8 |
| transaction | 0 |
| ville | 0 |

## Mesure 5 — Enregistrements corrigés / mis en quarantaine / conservés avec avertissement

| statut | enregistrements | % des reçus |
|---|---|---|
| corrigés (valeur normalisée par une règle sûre) | 932 | 29.3 % |
| mis en quarantaine | 186 | 5.8 % |
| conservés avec avertissement | 658 | 20.7 % |
| entièrement conformes | 1393 | 43.8 % |
| copies exactes écartées | 15 | 0.5 % |

Statuts mutuellement exclusifs : leur somme est exactement le nombre d'enregistrements reçus.

## Mesure 6 — Taux d'enregistrements entièrement conformes

**43.8 %** (conformes ÷ reçus : aucune correction, aucun avertissement). Pour mémoire, le taux d'enregistrements **exploitables** (conformes + corrigés + avertissements) est de 93.7 %.

---

# Détail complet du rapport de qualité

# Rapport de qualité des données — ImmoAnalyse

Généré le 2026-11-04T10:01:07 · date d'exécution de référence : **2026-11-03**

## 1. Résumé

- **3184 enregistrements reçus** (annoncés : 3224), dont **15 copies exactes** écartées.
- **2983 enregistrements exploitables** (93.7 % des reçus) : conformes, corrigés ou conservés avec avertissement.
- **186 enregistrements en quarantaine** (5.8 %), chacun avec son motif.
- **1393 enregistrements entièrement conformes** (43.8 %) : aucune correction, aucun avertissement.
- Fichiers bruts préservés (empreintes SHA-256 identiques avant/après) : **OUI**.

## 2. Définitions (pour lire les chiffres)

- **Reçus** : toutes les lignes lues. **Évalués** : reçus moins les copies exactes.
- **Taux de conformité d'une règle** = conformes ÷ **évaluables** × 100. Le dénominateur est toujours indiqué.
  Les **non évaluables** (règle sans objet pour la ligne, ou donnée nécessaire absente) sont comptés **à part** et ne sont **jamais** considérés comme conformes.
- **5 statuts finaux, mutuellement exclusifs**, par ordre de priorité : `doublon_exact_ecarte` > `quarantaine` > `conserve_avertissement` > `corrige` > `conforme`.
  Leur somme est exactement le nombre d'enregistrements reçus : **aucun enregistrement n'est compté deux fois**.
- **Taux exploitable** = (conforme + corrigé + conservé avec avertissement) ÷ reçus. **Taux conforme strict** = conforme ÷ reçus.

## 3. Volumes par source

| source | annoncées | reçues | écart |
|---|---|---|---|
| plateforme | 875 | 875 | 0 |
| agence | 680 | 640 | -40 |
| particuliers | 731 | 731 | 0 |
| notaires | 410 | 410 | 0 |
| historique | 528 | 528 | 0 |

Pour ce jeu de données, l'écart de l'agence (−40) vient du fichier : la feuille « Annonces » contient 640 lignes (sans ligne masquée ni vide) alors que la fiche de conception en annonce 680. La feuille « Params » (métadonnées) n'est pas une donnée et n'est pas lue.

## 4. Statuts finaux

| statut final | enregistrements | % des reçus |
|---|---|---|
| conforme | 1393 | 43.8 |
| corrige | 932 | 29.3 |
| conserve_avertissement | 658 | 20.7 |
| quarantaine | 186 | 5.8 |
| doublon_exact_ecarte | 15 | 0.5 |

Par source :

| source | conforme | corrige | conserve_avertissement | quarantaine | doublon_exact_ecarte |
|---|---|---|---|---|---|
| agence | 248 | 222 | 161 | 9 | 0 |
| historique | 137 | 282 | 99 | 10 | 0 |
| notaires | 244 | 118 | 28 | 20 | 0 |
| particuliers | 143 | 225 | 227 | 136 | 0 |
| plateforme | 621 | 85 | 143 | 11 | 15 |

## 5. Valeurs manquantes (en % des enregistrements évalués, par colonne et par source)

Une colonne **absente** d'une source (ex. pas de statut dans l'historique) n'est pas comptée comme « manquante » : elle est omise. Un « vide déguisé » (`None FCFA`) est compté manquant.

| colonne | agence | historique | notaires | particuliers | plateforme |
|---|---|---|---|---|---|
| categorie_brute | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| chambres_brute | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| date_brute | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| description | - | - | - | - | 19.0 |
| devise_brute | - | - | - | - | 0.0 |
| montant_brut | 0.0 | 1.9 | 3.4 | 8.3 | 0.0 |
| quartier_brute | - | - | - | - | 0.0 |
| region_brute | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| sdb_brute | 0.0 | 0.0 | - | 0.0 | 0.0 |
| statut_brut | 0.0 | - | 0.0 | 0.0 | 0.0 |
| surface_brute | 0.0 | 0.0 | 0.0 | 10.3 | 0.6 |
| transaction_brute | - | - | - | 0.0 | 0.0 |
| ville_brute | 0.0 | 1.5 | 0.0 | 0.0 | 0.0 |

## 6. Erreurs de conversion par champ (nombre d'enregistrements)

Une erreur de conversion = une valeur présente mais impossible à convertir de façon fiable (texte à la place d'un nombre, valeur négative, date impossible, valeur hors référentiel). Une case vide n'est pas une erreur de conversion (elle est comptée en §5).

| champ | agence | historique | notaires | particuliers | plateforme | total |
|---|---|---|---|---|---|---|
| categorie | 0 | 0 | 0 | 0 | 0 | 0 |
| chambres | 0 | 0 | 0 | 0 | 0 | 0 |
| date | 0 | 0 | 6 | 0 | 0 | 6 |
| montant | 0 | 0 | 0 | 0 | 5 | 5 |
| region | 0 | 0 | 0 | 0 | 0 | 0 |
| sdb | 0 | 0 | 0 | 0 | 0 | 0 |
| statut | 0 | 0 | 0 | 0 | 0 | 0 |
| surface | 4 | 0 | 0 | 4 | 0 | 8 |
| transaction | 0 | 0 | 0 | 0 | 0 | 0 |
| ville | 0 | 0 | 0 | 0 | 0 | 0 |

## 7. Corrections réalisées

- **1339 enregistrements** ont au moins une valeur corrigée par une règle sûre (un enregistrement peut avoir plusieurs corrections).
- Valeurs corrigées par champ : date = 959, categorie = 157, ville = 12, montant = 141, surface = 79, statut = 132.
- Champs **complétés** (information déduite, pas valeur modifiée) : 938 transactions déduites de la nature de la source (notaires, historique), 640 déduites du statut (agence), 173 périodicités lues dans la devise (« FCFA/mois »).

## 8. Règles métier : conformité et dénominateurs

### Règles bloquantes (violation = quarantaine)

| code | regle | conformes | non_conformes | non_evaluables | evaluables | taux % (conformes / évaluables) |
|---|---|---|---|---|---|---|
| B01 | identifiant_present | 3169 | 0 | 0 | 3169 | 100.0 |
| B02 | transaction_valide | 3169 | 0 | 0 | 3169 | 100.0 |
| B03 | prix_ou_loyer_positif | 3072 | 97 | 0 | 3169 | 96.9 |
| B04 | surface_positive | 3081 | 88 | 0 | 3169 | 97.2 |
| B05 | date_interpretable | 3163 | 6 | 0 | 3169 | 99.8 |
| B06 | date_non_future | 1315 | 1 | 1853 | 1316 | 99.9 |

### Règles d'avertissement (violation = conservé et signalé)

| code | regle | conformes | non_conformes | non_evaluables | evaluables | taux % (conformes / évaluables) |
|---|---|---|---|---|---|---|
| A24 | type_bien_valide | 3169 | 0 | 0 | 3169 | 100.0 |
| A01 | periodicite_connue | 173 | 327 | 2669 | 500 | 34.6 |
| A02 | prix_vente_plausible | 2598 | 0 | 571 | 2598 | 100.0 |
| A03 | loyer_mensuel_plausible | 173 | 0 | 2996 | 173 | 100.0 |
| A04 | prix_dans_fourchette_categorie | 2518 | 80 | 571 | 2598 | 96.9 |
| A05 | surface_plausible | 3081 | 0 | 88 | 3081 | 100.0 |
| A06 | surface_dans_fourchette_categorie | 3078 | 3 | 88 | 3081 | 99.9 |
| A07 | prix_m2_dans_plage_referentiel | 2537 | 4 | 628 | 2541 | 99.8 |
| A08 | prix_m2_non_atypique | 2431 | 110 | 628 | 2541 | 95.7 |
| A09 | chambres_valides | 3169 | 0 | 0 | 3169 | 100.0 |
| A10 | salles_bain_valides | 2759 | 0 | 410 | 2759 | 100.0 |
| A11 | chambres_non_atypiques | 1126 | 0 | 2043 | 1126 | 100.0 |
| A12 | salles_bain_coherentes | 2599 | 160 | 410 | 2759 | 94.2 |
| A13 | pieces_coherentes_type | 2420 | 14 | 735 | 2434 | 99.4 |
| A14 | ville_reconnue | 3161 | 8 | 0 | 3169 | 99.7 |
| A15 | region_reconnue | 3169 | 0 | 0 | 3169 | 100.0 |
| A16 | region_ville_coherentes | 3157 | 4 | 8 | 3161 | 99.9 |
| A17 | statut_coherent_transaction | 1578 | 13 | 1578 | 1591 | 99.2 |
| A18 | dates_coherentes | 855 | 5 | 2309 | 860 | 99.4 |
| A19 | date_non_concentree | 3123 | 40 | 6 | 3163 | 98.7 |
| A20 | pas_de_doublon_probable | 3169 | 0 | 0 | 3169 | 100.0 |
| A21 | pas_de_conflit_entre_enregistrements | 3163 | 6 | 0 | 3169 | 99.8 |
| A22 | identifiant_unique | 3169 | 0 | 0 | 3169 | 100.0 |
| A23 | date_non_future_annonce | 1843 | 4 | 1322 | 1847 | 99.8 |

## 9. Quarantaine : motifs

186 enregistrements. Un enregistrement peut cumuler plusieurs motifs : la somme des motifs peut dépasser le nombre d'enregistrements.

| règle bloquante violée | enregistrements |
|---|---|
| prix_ou_loyer_positif | 97 |
| surface_positive | 88 |
| date_interpretable | 6 |
| date_non_future | 1 |

Le fichier `data/quarantine/quarantaine.csv` donne, pour chaque ligne, sa source, sa ligne dans le fichier d'origine, ses valeurs brutes et son motif.

## 10. Avertissements : conservés et signalés

| règle (avertissement) | occurrences |
|---|---|
| periodicite_connue | 327 |
| salles_bain_coherentes | 160 |
| prix_m2_non_atypique | 110 |
| prix_dans_fourchette_categorie | 80 |
| date_non_concentree | 40 |
| pieces_coherentes_type | 14 |
| statut_coherent_transaction | 13 |
| ville_reconnue | 8 |
| pas_de_conflit_entre_enregistrements | 6 |
| dates_coherentes | 5 |
| date_non_future_annonce | 4 |
| prix_m2_dans_plage_referentiel | 4 |
| region_ville_coherentes | 4 |
| surface_dans_fourchette_categorie | 3 |

**Erreur ou valeur légitime ?** Les avertissements sont des *signaux*, pas des verdicts : seuils et fourchettes sont des hypothèses pédagogiques (cahier § 6). Exemples : une villa de 1 250 m² ou un appartement à 340 M FCFA est atypique pour sa catégorie mais cohérent au m² ; on le signale sans le supprimer. Seules les règles bloquantes écartent un enregistrement.

## 11. Doublons et conflits

- **15 doublons exacts** (0.5 % des reçus), répartis ainsi : plateforme = 15 : copies identiques sur tous les champs, placées en fin de fichier. On garde la première occurrence.
- **Rapprochement entre enregistrements** sur attributs métier (ville, type, transaction en bloc ; surface, prix, pièces, date en score) : **12609 paires comparées, 3 retenues** (0 doublons probables, 3 conflits).
- **Lecture prudente** : le test par permutation estime à **4.9 faux doublons en moyenne** (entre 3 et 8 sur 10 tirages) ce que le hasard produirait avec ces critères. Les paires retenues sont donc des **signaux à vérifier à la main**, pas des preuves. Rien n'est fusionné ni supprimé.

| id_a | id_b | ville | type_bien | score | type_lien | champs_en_conflit |
|---|---|---|---|---|---|---|
| particuliers:PRT-01461 | particuliers:PRT-02191 | Gossas | Studio | 0.767 | conflit | prix |
| plateforme:PLT-00314 | plateforme:PLT-00587 | Podor | Appartement | 0.797 | conflit | salles_bain |
| agence:AGT-01179 | historique:HIS-0071 | Vélingara | Appartement | 0.795 | conflit | chambres,salles_bain |

## 12. Décisions et limites (constats propres à ce jeu de données)

- **On ne devine pas** : `1,250` (ambigu), date `03/04/2024` sans convention prouvée, périodicité d'un loyer non écrite, prix sans unité restent non convertis ou signalés.
- **Dates `JJ/MM/AAAA`** : la convention est déduite *par source* à partir de preuves (un premier nombre > 12 prouve un jour, un deuxième nombre > 12 prouverait un mois). Agence, particuliers et historique : JJ/MM. Notaires : les seules dates à barres sont impossibles (32/13/2024) → quarantaine.
- **Ventes et locations** sont séparées dans tout le pipeline. Les prix de vente sont des prix *demandés* (annonces), pas des prix de transaction conclue ; les actes notariés et l'historique sont des ventes.
- **Agence** : pas de colonne vente/location ; la transaction est déduite du statut (Disponible, Loué → location ; En vente, Vendu → vente), règle prouvée sur les sources où la transaction est écrite (0 contre-exemple).
- **Type de bien hors référentiel** : avertissement (`regles_metier.md` : conserver, signaler). Aucun cas dans ces données.
- **Date future** : bloquante seulement pour une transaction déclarée vendue (`regles_metier.md`). 5 annonces de la plateforme sont datées après la date d'exécution ; 1 sont « Vendu » (quarantaine), les 4 autres sont signalées (A23).
- **Lot suspect** : 40 annonces de la plateforme (PLT-02602 à PLT-02680, toutes du 2024-03-01, toutes « En vente », 0 chambre et 0 salle de bain) ressemblent à un import en masse avec valeurs par défaut. Conservées avec avertissement, à vérifier à la source.
- **Données synthétiques** : elles ne permettent pas d'estimer le marché réel (cahier § 5.7).
