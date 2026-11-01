# Guide d'explication et de défense — ImmoAnalyse

Le cahier dit : *« les participants savent expliquer et défendre leurs choix techniques »*.
Ce guide te donne, **module par module**, ce que ça fait, **pourquoi** c'est fait ainsi, et les questions qu'on peut te poser.

## 0. L'idée en 30 secondes (à savoir dire sans notes)

> « J'ai reçu cinq sources immobilières qui décrivent les mêmes choses de cinq façons différentes : noms de colonnes, formats de prix, de dates, encodages. Mon pipeline les lit toutes **sans rien convertir**, les ramène à un **schéma commun** en gardant la **provenance**, puis **normalise** chaque champ. Chaque règle métier donne un résultat **chiffré** : conforme, non conforme ou non évaluable. Chaque enregistrement reçoit **un seul statut** : conforme, corrigé, conservé avec avertissement, en quarantaine, ou copie exacte. Je **corrige seulement quand le texte contient la preuve** de la bonne valeur, et **je ne devine jamais**. Je ne modifie jamais les données brutes, et je le **prouve** par des empreintes SHA-256. »

## 1. Les 5 principes qui expliquent presque tous les choix

| Principe | Où il apparaît | Pourquoi |
|---|---|---|
| **Ne jamais deviner** | `1,250` ambigu, date `03/04/2024` sans preuve, périodicité inconnue, surface `-30` non « réparée » | Une correction silencieuse fausse est pire qu'une valeur manquante : personne ne sait qu'elle est fausse |
| **Garder le brut à côté du propre** | colonnes `montant_brut` et `montant` | Réversible, vérifiable, et les corrections deviennent comptables |
| **Une règle = un objet chiffré** | classe `Regle`, matrice True / False / `<NA>` | On peut mesurer chaque règle et ajouter une règle sans toucher au reste |
| **Statuts mutuellement exclusifs** | 5 statuts dont la somme = 3 184 | Aucun enregistrement n'est compté deux fois (exigence du cahier § 7) |
| **Séparer ventes et locations** | `prix_vente` / `loyer` / `loyer_mensuel` | Un loyer mensuel n'est pas comparable à un prix de vente |

## 2. Module par module

### `config.py` — la configuration
- **Rôle** : chemins, seuils (`SEUILS`), alias de villes, table statut → transaction, paramètres du rapprochement.
- **Pourquoi** : le cahier interdit les seuils « codés en dur au milieu du pipeline ». Pour changer une règle, on modifie ce fichier et **aucune fonction**.
- **Preuve de la configurabilité** : le test `test_le_seuil_se_modifie_sans_toucher_au_code`.

### `loaders/sources.py` — le chargement
- **Rôle** : une fonction `charger_<source>` par source, toutes renvoient **les mêmes colonnes brutes**.
- **Choix clés** :
  - `dtype=str` : aucune conversion automatique. Sinon `57.62 millions` ou `à négocier` seraient transformés ou perdus sans qu'on le sache.
  - `encoding="latin-1"` pour l'historique : lu en UTF-8, « Thiès » deviendrait « Thi�s » et ne retrouverait plus le référentiel.
  - Excel : **seule la feuille `Annonces`** est lue. `Params` contient des métadonnées, pas des biens.
  - JSON : `json_normalize` aplatit la structure imbriquée.
  - `ligne_source` : permet de retrouver n'importe quelle ligne dans son fichier d'origine.
  - `empreintes_sources()` : SHA-256 avant et après → preuve que le brut n'a pas bougé.

### `processing/normalisation.py` — le cœur
- **Rôle** : fonctions **pures** `valeur → (valeur_propre, statut)`.
- **Pourquoi pures** : même entrée, même sortie, aucun effet de bord → faciles à tester (65 tests).
- **Statuts** : `conforme` (déjà propre), `corrige` (règle sûre), `manquant`, ou une erreur précise (`non_numerique`, `ambigu`, `negatif`, `impossible`, `hors_referentiel`).
- **Les cas à savoir expliquer** :
  - **`1,250`** : milliers (1 250) ou décimale (1,25) ? Le texte ne le dit pas → `ambigu`. L'exception est testée **avant** la règle générale « virgule décimale » : l'ordre des règles compte.
  - **Dates** : `inferer_convention_date` regarde si le 1er nombre dépasse 12 (c'est alors un jour) ou le 2ᵉ (un mois). C'est une **preuve**, pas une supposition. Une date où les deux dépassent 12 (`32/13/2024`) est impossible et ne prouve rien.
  - **`round()` sur « millions »** : `57.62 * 1_000_000` donne `57619999.99999999` en virgule flottante.
  - **`None FCFA`** : un `None` Python converti en texte. `isna()` ne le voit pas, `est_vide()` oui.
  - **`quatre-vingt`** : converti par un petit analyseur qui **refuse** les suites invraisemblables (`deux trois`).

### `processing/referentiels.py` — la classe `Referentiels`
- **Rôle** : charge géographie et catégories une fois, les range dans un objet passé en paramètre.
- **Pourquoi une classe** : plusieurs modules partagent ces données ; on évite les variables globales cachées.
- **Idée** : on compare des **clés** (`cle_texte` : sans accents, minuscules) et on **affiche les noms officiels**. `THIÈS`, `Thies` et `thiès` retombent tous sur « Thiès ».

### `processing/traitement.py` — combiner et normaliser
- `combiner_sources` : empile les 5 sources et crée `id_bien = source:id_local`. **Pas l'id local seul** : `HIS-0001` et `PLT-00001` partagent 528 numéros sans être les mêmes biens.
- `_normaliser_transactions` : la transaction est établie **avant** le prix. Ordre : écrite dans la source > nature de la source (notaires = ventes) > déduite du statut (agence : `Loué`, `Disponible` → location, règle **prouvée** sur les sources où elle est écrite).
- `marquer_doublons_exacts` : clé texte de tous les champs bruts, `duplicated(keep="first")`.
- **« corrigé » vs « complété »** : une valeur *modifiée* est une correction ; une information *déduite* (transaction de l'agence) est un complément, comptée à part. Sinon 1 578 lignes passeraient en « corrigées » sans que leurs données aient changé.

### `processing/rapprochement.py` — doublons probables et conflits
- **Problème** : aucun identifiant fiable → on rapproche sur des **attributs**.
- **Méthode** : blocage (même ville, type, transaction) → score de similarité multi-attributs → seuil → classement.
- **Pourquoi la surface est obligatoire** : 1 décimale sur 20 à 1 500 m², deux biens différents ont rarement la même à 0,5 % près.
- **Pourquoi la date pèse peu (0,1)** : une même annonce est republiée des mois plus tard.
- **Doublon probable vs conflit** : tout concorde = doublon probable ; un champ se contredit = conflit. **Jamais de fusion** : le cahier veut que les conflits soient signalés, pas résolus arbitrairement.
- **Honnêteté statistique** : le test par permutation estime ≈ 4,9 faux doublons dus au hasard, contre 3 retenus. Donc : **signaux, pas preuves**.

### `validation/regles.py` + `controle.py` — les règles (POO)
- **`Regle`** : dataclass avec `code`, `nom`, `gravite`, `description`, `justification` et une fonction `test(df)`.
- **Résultat** : `True` conforme, `False` non conforme, `<NA>` **non évaluable**. Les non évaluables ne sont **jamais** comptés comme conformes (cahier § 7).
- **Exemple de non évaluable** : « loyer mensuel plausible » pour une **vente**, ou pour un loyer **sans périodicité** (on ne devine pas).
- **Gravités** : bloquante → quarantaine ; avertissement → conservé et signalé.
- **Statut final** (`controle.statut_final`) : priorité copie exacte > quarantaine > avertissement > corrigé > conforme.
- **Les règles sont appliquées aux seules lignes qui ne sont pas des copies** : sinon l'original et sa copie violeraient « identifiant unique ».

### `analysis/qualite.py`, `stats.py`, `export.py`
- **`qualite.py`** : tous les indicateurs obligatoires, avec dénominateurs et définitions écrites.
- **`stats.py`** : statistiques avec NumPy (`np.median`, `np.percentile`), **médiane** plutôt que moyenne, prix au m² **par catégorie** (un terrain n'est pas un studio).
- **`export.py`** : exports idempotents (écrasés, pas ajoutés) et `verifier_exports()` qui relit les fichiers écrits.

## 3. Questions probables et réponses

**Q1. Pourquoi lire en `dtype=str` ?**
Pour ne rien perdre. Une conversion automatique transformerait ou ferait disparaître `57.62 millions` et `à négocier` sans que je sache combien de valeurs sont touchées. Je convertis moi-même, avec des règles explicites, et je **compte** les échecs.

**Q2. Pourquoi ne pas utiliser l'identifiant comme clé ?**
Le cahier l'interdit et les données le prouvent : `HIS-0001` et `PLT-00001` partagent 528 numéros sans être les mêmes biens. `id_bien = source:id_local` rend l'identifiant unique, et le rapprochement se fait sur des attributs métier.

**Q3. Pourquoi mettre en quarantaine `surface = -30` au lieu de prendre la valeur absolue ?**
Je ne sais pas si le signe est une faute de frappe ou si la valeur est fausse. Corriger sans preuve crée une fausse donnée que personne ne détecte. En quarantaine, l'enregistrement est tracé avec son motif et peut être réparé à la source.

**Q4. Comment décides-tu `JJ/MM` ou `MM/JJ` ?**
Par preuve, par source. Si le 1er nombre dépasse parfois 12 et jamais le 2ᵉ, la source est en JJ/MM. Pour les notaires, les seules dates à barres sont impossibles (`32/13/2024`) : aucune convention prouvée, aucune conversion hasardeuse, quarantaine.

**Q5. Pourquoi un statut « non évaluable » ?**
Parce qu'une règle n'a pas toujours d'objet. « Loyer plausible » n'a pas de sens pour une vente. Compter ces cas comme conformes gonflerait artificiellement le taux de conformité. Le taux est `conformes / évaluables`, avec le dénominateur affiché.

**Q6. Comment évites-tu de compter deux fois le même enregistrement ?**
Cinq statuts finaux mutuellement exclusifs avec une priorité fixe. Leur somme vaut exactement 3 184, et un test le vérifie.

**Q7. Pourquoi 93,7 % d'exploitables mais seulement 43,8 % de conformes ?**
« Exploitable » inclut les corrigés et les avertissements. Beaucoup de corrections sont bénignes (casse, accents, statuts de notaires). Les deux taux sont donnés avec leur définition.

**Q8. Pourquoi les prix hors fourchette ne sont-ils pas en quarantaine ?**
Les fourchettes sont des hypothèses pédagogiques, pas des normes. Un appartement à 340 M FCFA sort de sa fourchette mais son prix au m² est ordinaire (rang 69 % dans sa catégorie) : prix et surface vont ensemble. On le signale, on le garde.

**Q9. Ton contrôle « prix au m² dans la plage du référentiel » ne détecte rien. Pourquoi ?**
Le référentiel n'a pas de prix au m² ; je déduis la plage (prix min ÷ surface max → prix max ÷ surface min). Comme prix et surface sont déjà contrôlés, ce contrôle est une conséquence des deux autres. Je l'ai gardé parce que le cahier le demande, et je l'ai complété par la règle de l'IQR par catégorie, qui peut échouer : je l'ai testée en multipliant un prix par 10, et le détecteur le repère.

**Q10. Tes doublons probables sont-ils fiables ?**
Pas comme preuves. Un test par permutation estime à ≈ 4,9 le nombre de paires que le hasard produirait avec mes critères, contre 3 retenues. Ce sont des signaux à vérifier à la main. La paire `PRT-01461` / `PRT-02191` est la plus convaincante : même surface, mêmes pièces, prix exactement ×0,95.

**Q11. Pourquoi ne fusionnes-tu pas les doublons probables ?**
`regles_metier.md` dit « ne pas fusionner sans justification », et le cahier veut que les conflits soient signalés, pas résolus arbitrairement. Choisir quel prix est « le bon » serait une décision métier que je n'ai pas les moyens de prouver.

**Q12. Comment prouves-tu que les données brutes n'ont pas été modifiées ?**
Je calcule le SHA-256 de chaque fichier source avant et après l'exécution et je compare. Le résultat est dans le rapport, et un test l'impose.

**Q13. Le pipeline est-il reproductible ? Idempotent ?**
Reproductible : `--date-ref` fixe la date d'exécution (« date future » et « hier » en dépendent) et la simulation a une graine fixe. Idempotent : les exports écrasent les fichiers au lieu d'ajouter, un test relance deux fois et compare.

**Q14. Quelle est la différence entre « corrigé » et « complété » ?**
Corrigé : la valeur a été modifiée par une règle sûre (`438 746 000` → `438746000`). Complété : une information absente a été déduite (transaction de l'agence déduite du statut). Je les compte à part pour que « corrigés » ne gonfle pas artificiellement.

**Q15. Pourquoi une classe `Regle` plutôt que des fonctions ?**
Une règle a un nom, une gravité, une justification et un test. En les regroupant, le pipeline applique la même boucle à toutes, et on obtient des chiffres par règle. Ajouter une règle, c'est ajouter un objet à la liste.

**Q16. Pourquoi la médiane et non la moyenne ?**
La distribution des prix est asymétrique à droite : quelques valeurs élevées tirent la moyenne (105 M) au-dessus de la médiane (75 M). La médiane résume mieux le bien « typique ».

**Q17. Pourquoi ne pas calculer un prix au m² moyen pour tout le jeu ?**
Un terrain (≈ 65 000 FCFA/m²) et une villa (≈ 906 000 FCFA/m²) ne sont pas comparables : la moyenne globale ne représenterait aucun bien. On compare à l'intérieur d'une catégorie.

**Q18. Que fais-tu des 40 annonces `PLT-02602` à `PLT-02680` ?**
Elles partagent la même date, le même statut, et ont 0 chambre et 0 salle de bain, villas comprises : signature d'un import en masse avec valeurs par défaut. La règle `A19` les signale, je les conserve avec avertissement et j'indique qu'il faut vérifier à la source.

**Q19. Il manque 40 lignes à l'agence. Qu'as-tu fait ?**
Je les ai **signalées** : la fiche annonce 680 lignes, le fichier en contient 640 (sans ligne masquée ni vide). Un pipeline fiable réconcilie ce qu'il reçoit avec ce qui est annoncé, et ne l'ignore pas.

**Q20. Le cahier et `regles_metier.md` divergent sur le type de bien hors référentiel. Que fais-tu ?**
Le cahier dit quarantaine, `regles_metier.md` dit avertissement. J'applique le cahier (document de référence) et je le documente. Aucun cas ici, donc aucun effet sur les résultats ; le changement se ferait en une ligne de configuration.

**Q21. Que ferais-tu avec plus de temps ?**
Un registre de sources YAML (ajouter une source sans toucher au code), le format Parquet, un score global de qualité, et une revue manuelle des paires de doublons probables avec le formateur.

## 4. Plan de démonstration (≈ 8 minutes)

1. **Montrer l'état de départ** (1 min) : `ls data/raw/sources` ; ouvrir une ligne brute difficile (`57.62 millions`, `None FCFA`).
2. **Lancer le pipeline** (1 min) : `python -m src.main --date-ref 2026-10-29` → montrer le résumé et les 9 contrôles `[OK]`.
3. **Montrer les sorties** (2 min) : `data/processed/donnees_propres.csv` (valeur propre à côté de la valeur brute), `data/quarantine/quarantaine.csv` (ligne + motif), `reports/rapport_qualite.md`.
4. **Un cas expliqué de bout en bout** (2 min) : `PLT-00002` : `57.62 millions` → 57 620 000, statut « corrigé » ; puis un rejet : `PLT-00062` : `à négocier` → quarantaine, règle `prix_ou_loyer_positif`.
5. **Les tests** (1 min) : `pytest` → 104 tests ; montrer un cas limite (`1,250` ambigu).
6. **Le notebook** (1 min) : `01_exploration.ipynb`, graphique de conformité par règle et séparation ventes / locations.

**Vérifie avant la démo** : `Restart` + `Run All` du notebook, `pytest` vert, `git status` propre, README à jour.
