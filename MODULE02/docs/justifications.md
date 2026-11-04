# Registre des décisions — Module 2 ImmoAnalyse

**Règle du registre** : chaque décision est écrite **au moment où elle est prise**, avec une **preuve chiffrée**, la règle de référence et l'alternative écartée. Les chiffres viennent de `sortie/rapport_qualite.md` (exécution du 2026-11-03, profil de règles `module2`, 3 184 enregistrements reçus). Pour les recalculer, depuis `MODULE02/` : `python -m src.preparation.nettoyage --date-ref 2026-11-03`.

| Statut | Signification |
|---|---|
| ✅ fait | décision prise, preuve calculée |
| ⏳ à faire | prévue dans le plan (voir `docs/PLAN_MODULE2.md`) |

## Compétence 3 — Nettoyage (manquants, doublons, aberrants)

### J-01 · Lire `import_historique.csv` en `latin-1` (mojibake) · ✅
- **Décision** : lire le fichier avec `encoding="latin-1"` et non en UTF-8.
- **Preuve** : décodé en UTF-8, **141 villes sur 520 (27 %)** contiennent le caractère de remplacement `U+FFFD` (« Thi�s ») et **aucune** ne retrouve le référentiel ; décodé en `latin-1`, **0 ville sur 520** est inconnue du référentiel.
- **Pourquoi avant les jointures** : une ville corrompue ne correspond plus à `referentiel_geographique.csv` ; elle serait signalée à tort comme incohérente (faux positifs géographiques).
- **Référence** : guide du Module 2, tableau des pièges ; `src/loaders/sources.py`.
- **Alternative écartée** : décoder en UTF-8 avec remplacement puis « réparer » les villes à la main (corrections non fiables, non traçables).

### J-02 · Header dupliqué de `plateforme_immo_sn.csv` · ✅
- **Décision** : un filtre écarte toute ligne dont `ref_plateforme` vaut `ref_plateforme`, et on compte ce qu'il écarte.
- **Preuve** : `grep -c "^ref_plateforme"` sur le fichier fourni renvoie **1** (le header de la ligne 1). Le défaut décrit par le guide n'existe donc **pas** dans ce fichier : le filtre écarte **0 ligne**.
- **Référence** : guide du Module 2 (« header dupliqué en cours de fichier »).
- **Alternative écartée** : ne rien documenter (la grille note « header dupliqué filtré »).

### J-03 · Doublons exacts de la plateforme : garder la première occurrence · ✅
- **Décision** : écarter les copies exactes avant validation et avant tout découpage, en gardant la première occurrence.
- **Preuve** : **15 copies exactes** (0,5 % des reçus), toutes dans la plateforme, en fin de fichier : `PLT-00058, 00171, 00398, 00491, 00494, 00544, 00625, 00656, 00676, 00692, 00711, 00716, 00790, 00799, 00801`. Aucune référence répétée avec des valeurs différentes (**0 conflit d'identifiant**).
- **Pourquoi avant le split** : dédoublonner après le découpage laisserait une même annonce dans train et test (fuite silencieuse).
- **Référence** : guide du Module 2 (« dédoublonner après le split » = piège).
- **Alternative écartée** : garder les copies (surpondère 15 annonces).

### J-04 · Prix : normaliser les formats sûrs, rejeter le reste · ✅
- **Décision** : espaces/virgules de milliers et « millions » explicites sont **corrigés** ; `à négocier` et les prix absents ou ≤ 0 vont en **quarantaine**.
- **Preuve** : plateforme **804 conformes / 65 corrigés (50 espaces + 15 « millions ») / 6 non numériques** (875 lignes, copies comprises) ; sur les enregistrements évalués, 141 prix corrigés au total (plateforme 64, historique 72 avec espaces, particuliers 5). **97 enregistrements** violent la règle prix positif (63 particuliers, 14 notaires, 10 historique, 5 plateforme, 5 agence à 0) → quarantaine.
- **Référence** : `regles_metier.md` (bloquantes et normalisables).
- **Alternative écartée** : imputer la moyenne sur `prix` (interdit : il s'agit de la cible du futur modèle).

### J-05 · Surface : virgule décimale corrigée ; négatif et nombre en lettres rejetés · ✅
- **Décision** : virgule décimale (1 ou 2 chiffres) corrigée ; surface négative et `quatre-vingt` → **quarantaine** ; virgule + 3 chiffres refusée comme ambiguë.
- **Preuve** : **79 surfaces corrigées** (29 virgules dans la plateforme) ; **4 surfaces négatives** (agence) ; **4 `quatre-vingt`** (particuliers) ; **0 cas ambigu** de type `1,250`. **88 enregistrements** violent la règle surface positive.
- **Référence** : `regles_metier.md` (surface non numérique ou ≤ 0 = bloquante) ; guide : `quatre-vingt` non convertible de façon fiable.
- **Alternative écartée** : convertir `quatre-vingt` en 80 (choix du Module 1, écarté pour suivre le référentiel du Module 2) ; prendre la valeur absolue de `-30` (on ne sait pas si le signe est une faute de frappe).

### J-06 · Dates : convention JJ/MM déduite par source · ✅
- **Décision** : convertir `JJ/MM/AAAA` seulement quand la convention est **prouvée** pour la source ; sinon la date reste ambiguë.
- **Preuve** : convention **JJ/MM** prouvée pour agence, particuliers et historique (un premier nombre > 12 apparaît, jamais un second) ; **6 dates impossibles** chez les notaires (`32/13/2024`) : aucune convention prouvable → quarantaine. **959 dates corrigées** au total.
- **Référence** : `regles_metier.md` (date impossible = bloquante ; JJ/MM/AAAA ou ISO normalisables).
- **Alternative écartée** : supposer JJ/MM partout (risque d'inverser mois et jours sans le savoir).

### J-07 · Dates futures : bloquantes seulement si la vente est déclarée vendue · ✅
- **Décision** : quarantaine pour une date future sur une transaction `Vendu` ; avertissement (règle A23) pour les autres.
- **Preuve** : **5 annonces** de la plateforme datées 2028-12-01 : **1** est « Vendu » (`PLT-00077`, quarantaine) ; **4** sont « Retiré » ou « En vente » (`PLT-00014, 00395, 00572, 00753`, conservées avec avertissement).
- **Référence** : `regles_metier.md` (« date future pour une transaction déclarée vendue »).
- **Alternative écartée** : tout mettre en quarantaine (choix du Module 1, plus strict que le référentiel du Module 2).

### J-08 · Catégories, villes, statuts : normaliser la forme, jamais le fond · ✅
- **Décision** : casse, accents, espaces et synonymes du référentiel sont corrigés ; une incohérence ville / région est **signalée, pas corrigée**.
- **Preuve** : **157 catégories corrigées** (5 `appart`, 152 majuscules de l'historique) ; **12 villes** corrigées (casse) ; **132 statuts** harmonisés ; **0 valeur hors référentiel**. **4 incohérences ville / région** (particuliers) conservées avec avertissement ; **8 villes manquantes** (historique).
- **Référence** : `regles_metier.md` (« ne pas corriger sans preuve »).
- **Alternative écartée** : corriger la région à partir de la ville (bruit introduit si c'est la ville qui est fausse).

### J-09 · Transaction absente : déduite avec preuve · ✅
- **Décision** : notaires et historique = ventes par nature de la source ; agence : déduite du statut (Loué, Disponible → location ; En vente, Vendu → vente).
- **Preuve (répartition)** : sur **3 169** enregistrements, **1 591** transactions écrites dans la source, **938** déduites de la nature de la source, **640** déduites du statut (agence).
- **Preuve (la règle statut → transaction)** : dans les sources où la transaction est écrite, « Disponible » et « Loué » sont des locations dans **379 cas sur 379** (160 plateforme, 219 particuliers) ; les statuts Vendu, Sous offre, Retiré et À confirmer sont des ventes dans **730 cas sur 730** ; « En vente » est une vente dans 469 cas sur 482 (les 13 autres sont signalés par la règle A17).
- **Preuve (contrôle indépendant par le prix, agence)** : tous les prix non nuls de « Disponible » et « Loué » sont ≤ 1 445 000 FCFA (taille d'un loyer), tous ceux de « En vente » et « Vendu » sont ≥ 8 573 000 FCFA (taille d'une vente) : **aucun prix entre les deux**, donc 0 contradiction entre le statut et l'ordre de grandeur.
- **Alternative écartée** : mettre les 640 lignes de l'agence en quarantaine (perte de 20 % du corpus sans raison).

### J-10 · Périodicité des loyers : signaler sans deviner · ✅
- **Décision** : la périodicité n'est lue que si elle est écrite (devise `FCFA/mois`).
- **Preuve** : **327 locations sur 500** (agence et particuliers) n'ont aucune périodicité : avertissement A01 ; le plafond de loyer devient *non évaluable* pour elles.
- **Référence** : cahier § 6.1 (« signaler ; ne pas deviner »).
- **Alternative écartée** : supposer « mensuel » (les montants le suggèrent, mais ce serait une supposition).

### J-11 · Aberrants : juger sur la fourchette de la catégorie, signaler, ne pas supprimer · ✅
- **Décision** : un prix ou une surface hors fourchette est **conservé avec avertissement**.
- **Preuve** : **0** prix hors seuils généraux (100 000 à 2 milliards) ; **80 prix hors fourchette de leur catégorie** (sur 2 598 évaluables) ; **3 surfaces hors fourchette** (sur 3 081) ; **110 prix au m² atypiques** par la règle de l'IQR par catégorie (sur 2 541). Un bien extrême en prix peut être ordinaire au m² (ex. `PLT-00663` : 340 M FCFA, 389,7 m², rang 69 % dans sa catégorie).
- **Référence** : `regles_metier.md` (atypique, pas nécessairement faux) ; guide (jugement sur la fourchette de la catégorie, pas sur la fourchette globale : faux positifs pour les villas).
- **Alternative écartée** : supprimer les 80 prix hors fourchette (perte d'information sur des biens haut de gamme plausibles).

### J-12 · Doublons probables : signaler, ne pas fusionner · ✅
- **Décision** : rapprocher sur des attributs (ville, type, transaction, surface, prix, pièces, date), signaler, ne rien fusionner.
- **Preuve** : **3 paires** retenues sur **12 609** comparées (0 doublon probable, 3 conflits). Le test par permutation estime **4,9** paires dues au hasard : ce sont des signaux, pas des preuves.
- **Référence** : `regles_metier.md` (« ne pas fusionner sans justification »).
- **Alternative écartée** : fusionner (choisir arbitrairement un des deux prix).

### J-13 · Lot suspect de 40 annonces · ✅
- **Décision** : conserver avec avertissement (règle A19) et recommander une vérification à la source.
- **Preuve** : **40 annonces** de la plateforme (`PLT-02602` à `PLT-02680`), toutes du 2024-03-01, « En vente », **0 chambre et 0 salle de bain** (dont 14 maisons, villas ou appartements).
- **Conséquence pour la suite** : ces lignes porteront des chambres à 0 qui ne sont probablement pas réelles : à surveiller dans l'EDA (compétence 2) et à ne pas laisser dominer une variable.

### J-14 · Ordre : nettoyer chaque source avant de les concaténer · ✅
- **Décision** : conventions de date, doublons exacts et normalisation sont calculés **source par source** ; les résultats sont ensuite empilés (`executer_pipeline`).
- **Preuve** : mêmes totaux que le traitement groupé (1 393 conformes / 932 corrigés / 658 avertissements / 186 quarantaine / 15 copies = 3 184), avec une convention de date propre à chaque source.
- **Référence** : guide du Module 2 (« concaténer avant d'avoir nettoyé chaque source » = à ne pas faire).

### J-15 · Écart de volume de l'agence · ✅
- **Décision** : signaler l'écart, ne rien inventer.
- **Preuve** : **640 lignes** dans la feuille `Annonces` pour **680** annoncées par la fiche de conception (−40). La feuille `Params` (métadonnées) n'est pas lue comme une donnée.

## Compétences à venir (entrées à écrire au fil du travail) · ⏳

| Compétence | Décisions à documenter |
|---|---|
| 1 · Types et statistiques | types par source ; asymétrie de `prix` avant et après log ; cible retenue |
| 2 · EDA | mécanisme des manquants ; paradoxe de Simpson ; tendance temporelle |
| 4 · Visualisations | V1 à V6 avec conclusion chiffrée |
| 5 · Encodage et normalisation | one-hot / ordinal par variable ; `handle_unknown` ; choix du scaler |
| 6 · Feature engineering | chaque variable candidate avec son gain en validation croisée |
| 7 · Split | type de découpage, stratification, vérification par source |
| 8 · Fuite de données | audit de `prix_m2`, `statut`, `source`, indicateurs de manque |
| 9 · Pipeline | 6 vérifications de reproductibilité |
