"""Indicateurs de qualité des données (cahier § 7).

DÉFINITIONS (écrites ici ET dans le rapport, car un chiffre sans définition ne veut rien dire) :
  - enregistrements REÇUS      : toutes les lignes lues dans les 5 sources
  - enregistrements ÉVALUÉS    : reçus - copies exactes (la copie n'ajoute aucune information)
  - taux de conformité d'une règle = conformes / ÉVALUABLES x 100
        Le DÉNOMINATEUR est toujours indiqué. Les non évaluables (règle sans objet pour la ligne,
        ex. « loyer plausible » pour une vente) sont comptés À PART, jamais comme conformes.
  - statut final : 5 statuts mutuellement exclusifs, dont la somme = enregistrements reçus
        (donc aucun enregistrement n'est compté deux fois dans le taux global)
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from src.config import STATUTS_FINAUX
from src.processing.normalisation import est_vide
from src.processing.pipeline import Resultats
from src.validation.regles import BLOQUANTE

# champ -> (colonne de statut de conversion, statuts qui sont de VRAIES erreurs de conversion)
CHAMPS_CONVERSION = {
    "date": ("date_statut", {"impossible", "ambigu", "non_interpretable"}),
    "transaction": ("transaction_statut", {"non_interpretable"}),
    "categorie": ("categorie_statut", {"hors_referentiel"}),
    "region": ("region_statut", {"hors_referentiel"}),
    "ville": ("ville_statut", {"hors_referentiel"}),
    "montant": ("montant_statut", {"non_numerique", "ambigu", "negatif"}),
    "surface": ("surface_statut", {"non_numerique", "ambigu", "negatif"}),
    "chambres": ("chambres_statut", {"non_numerique"}),
    "sdb": ("sdb_statut", {"non_numerique"}),
    "statut": ("statut_statut", {"non_interpretable"}),
}
COLONNES_BRUTES = ["date_brute", "transaction_brute", "categorie_brute", "region_brute", "ville_brute",
                   "quartier_brute", "montant_brut", "devise_brute", "surface_brute", "chambres_brute",
                   "sdb_brute", "statut_brut", "description"]


def _pct(a, b):
    return round(100 * a / b, 1) if b else None


def valeurs_manquantes(R: Resultats) -> pd.DataFrame:
    """Manquants par (source, colonne brute). Une colonne ABSENTE d'une source n'est pas « 100 % manquante »."""
    d = R.donnees[~R.donnees["est_copie_exacte"]]
    lignes = []
    for source, g in d.groupby("source"):
        for colonne in COLONNES_BRUTES:
            absente = bool(g[colonne].isna().all())
            manquants = 0 if absente else int(g[colonne].map(est_vide).sum())
            lignes.append({"source": source, "colonne": colonne, "colonne_absente": absente,
                           "manquants": manquants, "evalues": len(g), "taux_manquant_pct": None if absente else _pct(manquants, len(g))})
    return pd.DataFrame(lignes)


def erreurs_conversion(R: Resultats) -> pd.DataFrame:
    d = R.donnees[~R.donnees["est_copie_exacte"]]
    lignes = []
    for champ, (colonne, erreurs) in CHAMPS_CONVERSION.items():
        for source, g in d.groupby("source"):
            lignes.append({"champ": champ, "source": source, "erreurs": int(g[colonne].isin(erreurs).sum()),
                           "evalues": len(g)})
    return pd.DataFrame(lignes)


def tableau_regles(R: Resultats) -> pd.DataFrame:
    lignes = []
    for r in R.regles:
        s = R.matrice[r.code]
        conformes, non_conformes = int((s == True).sum()), int((s == False).sum())   # noqa: E712
        evaluables = conformes + non_conformes
        lignes.append({
            "code": r.code, "regle": r.nom, "gravite": r.gravite, "description": r.description,
            "conformes": conformes, "non_conformes": non_conformes, "non_evaluables": int(s.isna().sum()) - int(R.donnees["est_copie_exacte"].sum()),
            "evaluables": evaluables, "taux_conformite_pct": _pct(conformes, evaluables),
            "denominateur": f"{evaluables} enregistrements évaluables",
        })
    return pd.DataFrame(lignes)


def construire_rapport(R: Resultats) -> dict:
    d = R.donnees
    recus = len(d)
    copies = int(d["est_copie_exacte"].sum())
    evalues = recus - copies
    statuts = d["statut_final"].value_counts().reindex(STATUTS_FINAUX, fill_value=0)
    exploitables = int(statuts[["conforme", "corrige", "conserve_avertissement"]].sum())

    par_source = d.groupby("source")["statut_final"].value_counts().unstack(1).reindex(columns=STATUTS_FINAUX).fillna(0).astype(int)
    tab_regles = tableau_regles(R)
    manquants = valeurs_manquantes(R)
    conversions = erreurs_conversion(R)

    actifs = d[~d["est_copie_exacte"]]
    corrections_par_champ = {champ: int((actifs[col] == "corrige").sum()) for champ, (col, _) in CHAMPS_CONVERSION.items()}
    quarantaine = d[d["statut_final"] == "quarantaine"]
    motifs_quarantaine = R.anomalies[(R.anomalies["gravite"] == BLOQUANTE) & R.anomalies["id_bien"].isin(quarantaine["id_bien"])]
    avert = R.anomalies[R.anomalies["gravite"] != BLOQUANTE]

    return {
        "genere_le": datetime.now().isoformat(timespec="seconds"),
        "date_reference": R.date_reference.isoformat(),
        "definitions": {
            "recus": "toutes les lignes lues dans les 5 sources",
            "evalues": "recus - copies exactes",
            "taux_conformite_regle": "conformes / evaluables x 100 (denominateur indique ; non evaluables comptes a part)",
            "statuts_finaux": "5 statuts mutuellement exclusifs dont la somme = recus",
            "taux_exploitable": "(conforme + corrige + conserve_avertissement) / recus x 100",
            "taux_conforme_strict": "conforme / recus x 100 (aucune correction, aucun avertissement)",
        },
        "volumes": {
            "total_recus": recus, "total_annonces": int(sum(R.volumes_attendus.values())),
            "par_source": {s: {"recus": R.volumes_recus[s], "annonces": R.volumes_attendus[s],
                               "ecart": R.volumes_recus[s] - R.volumes_attendus[s]} for s in R.volumes_recus},
        },
        "doublons_exacts": {"nombre": copies, "taux_pct_des_recus": _pct(copies, recus),
                            "par_source": {k: int(v) for k, v in d[d["est_copie_exacte"]].groupby("source").size().items()}},
        "statuts_finaux": {
            "nombres": {k: int(v) for k, v in statuts.items()},
            "taux_pct_des_recus": {k: _pct(int(v), recus) for k, v in statuts.items()},
            "enregistrements_exploitables": exploitables,
            "taux_exploitable_pct": _pct(exploitables, recus),
            "taux_conforme_strict_pct": _pct(int(statuts["conforme"]), recus),
            "par_source": {s: {k: int(v) for k, v in ligne.items()} for s, ligne in par_source.iterrows()},
        },
        "enregistrements_avec_au_moins_une_correction": int((actifs["champs_corriges"] > 0).sum()),
        "corrections_par_champ": corrections_par_champ,
        "champs_completes_par_deduction": {
            "transaction_deduite_nature_source": int((actifs["transaction_origine"] == "nature_source").sum()),
            "transaction_deduite_statut": int((actifs["transaction_origine"] == "statut").sum()),
            "periodicite_lue_dans_devise": int((actifs["periodicite_statut"] == "extrait_devise").sum()),
        },
        "valeurs_manquantes": manquants.to_dict(orient="records"),
        "erreurs_de_conversion": conversions.to_dict(orient="records"),
        "regles": tab_regles.to_dict(orient="records"),
        "quarantaine": {
            "nombre": int(len(quarantaine)),
            "motifs_par_regle": {k: int(v) for k, v in motifs_quarantaine.groupby("regle").size().sort_values(ascending=False).items()},
            "note": "Un enregistrement peut cumuler plusieurs motifs : la somme des motifs peut dépasser le nombre d'enregistrements.",
        },
        "avertissements": {
            "enregistrements_conserves_avec_avertissement": int(statuts["conserve_avertissement"]),
            "occurrences_par_regle": {k: int(v) for k, v in avert.groupby("regle").size().sort_values(ascending=False).items()},
        },
        "rapprochement": {
            "paires_comparees": int(len(R.paires)), "paires_retenues": int(len(R.rapprochements)),
            "doublons_probables": int((R.rapprochements["type_lien"] == "doublon_probable").sum()),
            "conflits": int((R.rapprochements["type_lien"] == "conflit").sum()),
            "faux_doublons_attendus_par_hasard": R.coincidences,
            "paires": R.rapprochements[["id_a", "id_b", "ville", "type_bien", "score", "type_lien", "champs_en_conflit"]].to_dict(orient="records"),
        },
        "integrite_sources": {"fichiers_bruts_intacts": R.sources_intactes, "sha256_avant_apres": R.empreintes_avant},
    }


def resume_csv(rapport: dict) -> pd.DataFrame:
    """Version « plate » du rapport : une ligne par indicateur (facile à ouvrir dans un tableur)."""
    lignes = []

    def ajouter(section, indicateur, valeur, denominateur=None, source="toutes"):
        taux = _pct(valeur, denominateur) if denominateur else None
        lignes.append({"section": section, "indicateur": indicateur, "source": source, "valeur": valeur,
                       "denominateur": denominateur, "taux_pct": taux})

    v = rapport["volumes"]
    ajouter("volumes", "enregistrements_recus", v["total_recus"])
    for s, x in v["par_source"].items():
        ajouter("volumes", "recus", x["recus"], x["annonces"], s)
    ajouter("doublons", "doublons_exacts", rapport["doublons_exacts"]["nombre"], v["total_recus"])
    for k, n in rapport["statuts_finaux"]["nombres"].items():
        ajouter("statuts_finaux", k, n, v["total_recus"])
    ajouter("statuts_finaux", "exploitables", rapport["statuts_finaux"]["enregistrements_exploitables"], v["total_recus"])
    ajouter("corrections", "enregistrements_avec_au_moins_une_correction", rapport["enregistrements_avec_au_moins_une_correction"], v["total_recus"])
    for champ, n in rapport["corrections_par_champ"].items():
        ajouter("corrections", f"valeurs_corrigees_{champ}", n)
    for e in rapport["erreurs_de_conversion"]:
        ajouter("erreurs_conversion", e["champ"], e["erreurs"], e["evalues"], e["source"])
    for m in rapport["valeurs_manquantes"]:
        if not m["colonne_absente"]:
            ajouter("valeurs_manquantes", m["colonne"], m["manquants"], m["evalues"], m["source"])
    for r in rapport["regles"]:
        ajouter(f"regle_{r['gravite']}", f"{r['code']} {r['regle']} (conformes)", r["conformes"], r["evaluables"])
        ajouter(f"regle_{r['gravite']}", f"{r['code']} {r['regle']} (non evaluables)", r["non_evaluables"])
    ajouter("rapprochement", "paires_retenues", rapport["rapprochement"]["paires_retenues"], rapport["rapprochement"]["paires_comparees"])
    return pd.DataFrame(lignes)


def _table_md(df: pd.DataFrame) -> str:
    """Convertit un tableau Pandas en tableau Markdown (sans dépendance supplémentaire)."""
    colonnes = list(df.columns)
    lignes = ["| " + " | ".join(map(str, colonnes)) + " |", "|" + "|".join("---" for _ in colonnes) + "|"]
    for _, ligne in df.iterrows():
        lignes.append("| " + " | ".join("" if pd.isna(x) else str(x) for x in ligne) + " |")
    return "\n".join(lignes)


def rapport_markdown(rapport: dict, R: Resultats) -> str:
    v, sf = rapport["volumes"], rapport["statuts_finaux"]
    reg = pd.DataFrame(rapport["regles"])
    manq = pd.DataFrame(rapport["valeurs_manquantes"])
    conv = pd.DataFrame(rapport["erreurs_de_conversion"])

    volumes = pd.DataFrame([{"source": s, "annoncées": x["annonces"], "reçues": x["recus"], "écart": x["ecart"]}
                            for s, x in v["par_source"].items()])
    statuts = pd.DataFrame([{"statut final": k, "enregistrements": n, "% des reçus": sf["taux_pct_des_recus"][k]}
                            for k, n in sf["nombres"].items()])
    par_source = pd.DataFrame(sf["par_source"]).T.reset_index().rename(columns={"index": "source"})

    manq_pivot = manq[~manq["colonne_absente"]].pivot(index="colonne", columns="source", values="taux_manquant_pct").fillna("-").reset_index()
    conv_pivot = conv.pivot(index="champ", columns="source", values="erreurs").reset_index()
    conv_pivot["total"] = conv.groupby("champ")["erreurs"].sum().reindex(conv_pivot["champ"]).to_numpy()

    def regles(gravite):
        sous = reg[reg["gravite"] == gravite][["code", "regle", "conformes", "non_conformes", "non_evaluables", "evaluables", "taux_conformite_pct"]]
        return _table_md(sous.rename(columns={"taux_conformite_pct": "taux % (conformes / évaluables)"}))

    q = rapport["quarantaine"]
    motifs_q = pd.DataFrame([{"règle bloquante violée": k, "enregistrements": n} for k, n in q["motifs_par_regle"].items()])
    avert = pd.DataFrame([{"règle (avertissement)": k, "occurrences": n} for k, n in rapport["avertissements"]["occurrences_par_regle"].items()])
    rap = rapport["rapprochement"]
    paires = pd.DataFrame(rap["paires"])
    hasard = rap["faux_doublons_attendus_par_hasard"]
    intact = "OUI" if rapport["integrite_sources"]["fichiers_bruts_intacts"] else "NON — à investiguer"
    m2 = R.profil["nom"] == "module2"
    texte_type_bien = ("- **Type de bien hors référentiel** : avertissement (`regles_metier.md` : conserver, signaler). Aucun cas dans ces données."
                       if m2 else "- **Type de bien hors référentiel** : le cahier dit quarantaine, `regles_metier.md` dit avertissement. On applique le cahier. Aucun cas dans ces données.")
    futures = R.donnees[(R.donnees["date_collecte"] > R.date_reference.isoformat()) & ~R.donnees["est_copie_exacte"]]
    texte_date_future = (f"- **Date future** : bloquante seulement pour une transaction déclarée vendue (`regles_metier.md`). {len(futures)} annonces de la plateforme sont datées après la date d'exécution ; "
                         f"{int((futures['statut_source'] == 'Vendu').sum())} sont « Vendu » (quarantaine), les {int((futures['statut_source'] != 'Vendu').sum())} autres sont signalées (A23)."
                         if m2 else f"- **Date future** : quarantaine (cahier § 6.1). {len(futures)} annonces de la plateforme (2028-12-01).")

    return f"""# Rapport de qualité des données — ImmoAnalyse

Généré le {rapport['genere_le']} · date d'exécution de référence : **{rapport['date_reference']}**

## 1. Résumé

- **{v['total_recus']} enregistrements reçus** (annoncés : {v['total_annonces']}), dont **{rapport['doublons_exacts']['nombre']} copies exactes** écartées.
- **{sf['enregistrements_exploitables']} enregistrements exploitables** ({sf['taux_exploitable_pct']} % des reçus) : conformes, corrigés ou conservés avec avertissement.
- **{sf['nombres']['quarantaine']} enregistrements en quarantaine** ({sf['taux_pct_des_recus']['quarantaine']} %), chacun avec son motif.
- **{sf['nombres']['conforme']} enregistrements entièrement conformes** ({sf['taux_conforme_strict_pct']} %) : aucune correction, aucun avertissement.
- Fichiers bruts préservés (empreintes SHA-256 identiques avant/après) : **{intact}**.

## 2. Définitions (pour lire les chiffres)

- **Reçus** : toutes les lignes lues. **Évalués** : reçus moins les copies exactes.
- **Taux de conformité d'une règle** = conformes ÷ **évaluables** × 100. Le dénominateur est toujours indiqué.
  Les **non évaluables** (règle sans objet pour la ligne, ou donnée nécessaire absente) sont comptés **à part** et ne sont **jamais** considérés comme conformes.
- **5 statuts finaux, mutuellement exclusifs**, par ordre de priorité : `doublon_exact_ecarte` > `quarantaine` > `conserve_avertissement` > `corrige` > `conforme`.
  Leur somme est exactement le nombre d'enregistrements reçus : **aucun enregistrement n'est compté deux fois**.
- **Taux exploitable** = (conforme + corrigé + conservé avec avertissement) ÷ reçus. **Taux conforme strict** = conforme ÷ reçus.

## 3. Volumes par source

{_table_md(volumes)}

Pour ce jeu de données, l'écart de l'agence (−40) vient du fichier : la feuille « Annonces » contient 640 lignes (sans ligne masquée ni vide) alors que la fiche de conception en annonce 680. La feuille « Params » (métadonnées) n'est pas une donnée et n'est pas lue.

## 4. Statuts finaux

{_table_md(statuts)}

Par source :

{_table_md(par_source)}

## 5. Valeurs manquantes (en % des enregistrements évalués, par colonne et par source)

Une colonne **absente** d'une source (ex. pas de statut dans l'historique) n'est pas comptée comme « manquante » : elle est omise. Un « vide déguisé » (`None FCFA`) est compté manquant.

{_table_md(manq_pivot)}

## 6. Erreurs de conversion par champ (nombre d'enregistrements)

Une erreur de conversion = une valeur présente mais impossible à convertir de façon fiable (texte à la place d'un nombre, valeur négative, date impossible, valeur hors référentiel). Une case vide n'est pas une erreur de conversion (elle est comptée en §5).

{_table_md(conv_pivot)}

## 7. Corrections réalisées

- **{rapport['enregistrements_avec_au_moins_une_correction']} enregistrements** ont au moins une valeur corrigée par une règle sûre (un enregistrement peut avoir plusieurs corrections).
- Valeurs corrigées par champ : {', '.join(f"{k} = {n}" for k, n in rapport['corrections_par_champ'].items() if n)}.
- Champs **complétés** (information déduite, pas valeur modifiée) : {rapport['champs_completes_par_deduction']['transaction_deduite_nature_source']} transactions déduites de la nature de la source (notaires, historique), {rapport['champs_completes_par_deduction']['transaction_deduite_statut']} déduites du statut (agence), {rapport['champs_completes_par_deduction']['periodicite_lue_dans_devise']} périodicités lues dans la devise (« FCFA/mois »).

## 8. Règles métier : conformité et dénominateurs

### Règles bloquantes (violation = quarantaine)

{regles('bloquante')}

### Règles d'avertissement (violation = conservé et signalé)

{regles('avertissement')}

## 9. Quarantaine : motifs

{q['nombre']} enregistrements. {q['note']}

{_table_md(motifs_q)}

Le fichier `data/quarantine/quarantaine.csv` donne, pour chaque ligne, sa source, sa ligne dans le fichier d'origine, ses valeurs brutes et son motif.

## 10. Avertissements : conservés et signalés

{_table_md(avert)}

**Erreur ou valeur légitime ?** Les avertissements sont des *signaux*, pas des verdicts : seuils et fourchettes sont des hypothèses pédagogiques (cahier § 6). Exemples : une villa de 1 250 m² ou un appartement à 340 M FCFA est atypique pour sa catégorie mais cohérent au m² ; on le signale sans le supprimer. Seules les règles bloquantes écartent un enregistrement.

## 11. Doublons et conflits

- **{rapport['doublons_exacts']['nombre']} doublons exacts** ({rapport['doublons_exacts']['taux_pct_des_recus']} % des reçus), répartis ainsi : {', '.join(f'{k} = {n}' for k, n in rapport['doublons_exacts']['par_source'].items())} : copies identiques sur tous les champs, placées en fin de fichier. On garde la première occurrence.
- **Rapprochement entre enregistrements** sur attributs métier (ville, type, transaction en bloc ; surface, prix, pièces, date en score) : **{rap['paires_comparees']} paires comparées, {rap['paires_retenues']} retenues** ({rap['doublons_probables']} doublons probables, {rap['conflits']} conflits).
- **Lecture prudente** : le test par permutation estime à **{hasard['moyenne']} faux doublons en moyenne** (entre {hasard['min']} et {hasard['max']} sur {hasard['tirages']} tirages) ce que le hasard produirait avec ces critères. Les paires retenues sont donc des **signaux à vérifier à la main**, pas des preuves. Rien n'est fusionné ni supprimé.

{_table_md(paires) if len(paires) else '_Aucune paire retenue._'}

## 12. Décisions et limites (constats propres à ce jeu de données)

- **On ne devine pas** : `1,250` (ambigu), date `03/04/2024` sans convention prouvée, périodicité d'un loyer non écrite, prix sans unité restent non convertis ou signalés.
- **Dates `JJ/MM/AAAA`** : la convention est déduite *par source* à partir de preuves (un premier nombre > 12 prouve un jour, un deuxième nombre > 12 prouverait un mois). Agence, particuliers et historique : JJ/MM. Notaires : les seules dates à barres sont impossibles (32/13/2024) → quarantaine.
- **Ventes et locations** sont séparées dans tout le pipeline. Les prix de vente sont des prix *demandés* (annonces), pas des prix de transaction conclue ; les actes notariés et l'historique sont des ventes.
- **Agence** : pas de colonne vente/location ; la transaction est déduite du statut (Disponible, Loué → location ; En vente, Vendu → vente), règle prouvée sur les sources où la transaction est écrite (0 contre-exemple).
{texte_type_bien}
{texte_date_future}
- **Lot suspect** : 40 annonces de la plateforme (PLT-02602 à PLT-02680, toutes du 2024-03-01, toutes « En vente », 0 chambre et 0 salle de bain) ressemblent à un import en masse avec valeurs par défaut. Conservées avec avertissement, à vérifier à la source.
- **Données synthétiques** : elles ne permettent pas d'estimer le marché réel (cahier § 5.7).
"""
