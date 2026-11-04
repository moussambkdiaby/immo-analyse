"""Orchestration du pipeline : enchaîne toutes les étapes et renvoie un objet `Resultats`.

Séparer l'ORCHESTRATION (ce fichier) de l'EXPORT (src/analysis/export.py) permet au notebook
d'appeler `executer_pipeline()` et d'analyser les résultats sans rien écrire sur le disque.

Enchaînement :
  1. empreintes des fichiers bruts (avant)           6. règles de validation
  2. chargement des 5 sources (schéma commun)        7. journal des anomalies
  3. combinaison + identifiant global                8. statut final par enregistrement
  4. doublons exacts (copies)                        9. empreintes des fichiers bruts (après) = preuve
  5. normalisation, puis rapprochement entre sources
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from src.config import PROFIL_MODULE1, SOURCES, SOURCES_CONFIG
from src.loaders.sources import charger_toutes_les_sources, empreintes_sources
from src.processing.rapprochement import detecter_rapprochements, estimer_coincidences
from src.processing.referentiels import Referentiels
from src.processing.traitement import combiner_sources, marquer_doublons_exacts, normaliser_donnees
from src.validation.controle import appliquer_regles_sur_actifs, journal_anomalies, motifs_par_enregistrement, statut_final
from src.validation.regles import AVERTISSEMENT, BLOQUANTE, Regle, construire_regles

journal = logging.getLogger("immoanalyse")


@dataclass
class Resultats:
    date_reference: date
    ref: Referentiels
    regles: list[Regle]
    donnees: pd.DataFrame                  # TOUTES les lignes reçues, normalisées + statut final
    matrice: pd.DataFrame                  # résultat de chaque règle (True / False / <NA>)
    anomalies: pd.DataFrame                # une ligne par violation
    paires: pd.DataFrame                   # toutes les paires comparées (pour justifier le seuil)
    rapprochements: pd.DataFrame           # paires retenues (doublons probables et conflits)
    coincidences: dict                     # estimation des faux doublons dus au hasard
    volumes_recus: dict
    volumes_attendus: dict
    empreintes_avant: dict
    empreintes_apres: dict
    profil: dict = field(default_factory=lambda: dict(PROFIL_MODULE1))
    notes: list[str] = field(default_factory=list)

    @property
    def sources_intactes(self) -> bool:
        return self.empreintes_avant == self.empreintes_apres


def executer_pipeline(date_ref: date | None = None, simuler_hasard: bool = True, profil: dict = PROFIL_MODULE1) -> Resultats:
    """Exécute le pipeline complet. `date_ref` fixe la « date d'exécution » (reproductibilité).

    `profil` : jeu de règles appliqué (PROFIL_MODULE1 par défaut, PROFIL_MODULE2 pour la préparation ML).
    """
    date_ref = date_ref or date.today()
    journal.info("Date de référence : %s | profil de règles : %s", date_ref, profil["nom"])

    empreintes_avant = empreintes_sources()
    ref = Referentiels.charger()

    sources = charger_toutes_les_sources()
    volumes_recus = {nom: len(df) for nom, df in sources.items()}
    for nom, recu in volumes_recus.items():
        attendu = SOURCES_CONFIG[nom]["volume_attendu"]
        niveau = logging.INFO if recu == attendu else logging.WARNING
        journal.log(niveau, "Source %-12s : %4d lignes reçues, %4d annoncées", nom, recu, attendu)

    # On NETTOIE CHAQUE SOURCE AVANT de les concaténer (consigne du Module 2) : conventions de date,
    # doublons exacts et normalisation sont calculés source par source, puis les résultats sont empilés.
    morceaux = []
    for nom, brute in sources.items():
        propre = marquer_doublons_exacts(combiner_sources({nom: brute}))
        morceaux.append(normaliser_donnees(propre, ref, date_ref, profil))
    donnees = pd.concat(morceaux, ignore_index=True)
    journal.info("Normalisation faite : %d lignes, dont %d copies exactes", len(donnees), donnees["est_copie_exacte"].sum())

    # Les copies exactes sont écartées AVANT le rapprochement et la validation :
    # elles ne portent aucune information nouvelle (l'original est évalué).
    actifs = donnees[~donnees["est_copie_exacte"]]
    marques, paires, retenues = detecter_rapprochements(actifs)
    donnees["lien_rapprochement"] = None
    donnees["id_groupe_rapprochement"] = None
    donnees.loc[marques.index, "lien_rapprochement"] = marques["lien_rapprochement"]
    donnees.loc[marques.index, "id_groupe_rapprochement"] = marques["id_groupe_rapprochement"]
    coincidences = estimer_coincidences(actifs) if simuler_hasard else {"moyenne": None, "min": None, "max": None, "tirages": 0}
    journal.info("Rapprochement : %d paires retenues (hasard estimé : %s)", len(retenues), coincidences["moyenne"])

    regles = construire_regles(ref, date_ref, profil=profil)
    matrice = appliquer_regles_sur_actifs(donnees, regles)                  # copies : lignes <NA>
    actifs = donnees[~donnees["est_copie_exacte"]]
    anomalies = journal_anomalies(actifs, matrice.loc[actifs.index], regles)

    donnees["statut_final"] = statut_final(donnees, matrice, regles)
    donnees["motifs_bloquants"] = donnees["id_bien"].map(motifs_par_enregistrement(anomalies, BLOQUANTE))
    donnees["avertissements"] = donnees["id_bien"].map(motifs_par_enregistrement(anomalies, AVERTISSEMENT))
    # Les copies partagent leur id_bien avec l'original : on ne leur recopie pas ses motifs.
    donnees.loc[donnees["est_copie_exacte"], ["motifs_bloquants", "avertissements"]] = None
    journal.info("Statuts finaux : %s", donnees["statut_final"].value_counts().to_dict())

    empreintes_apres = empreintes_sources()
    if empreintes_avant != empreintes_apres:
        journal.error("ATTENTION : un fichier brut a été modifié pendant l'exécution !")

    return Resultats(
        date_reference=date_ref, ref=ref, regles=regles, donnees=donnees, matrice=matrice, anomalies=anomalies,
        paires=paires, rapprochements=retenues, coincidences=coincidences, volumes_recus=volumes_recus,
        volumes_attendus={n: c["volume_attendu"] for n, c in SOURCES_CONFIG.items()},
        empreintes_avant=empreintes_avant, empreintes_apres=empreintes_apres, profil=dict(profil),
    )
