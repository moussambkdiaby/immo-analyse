"""Configuration centrale du pipeline ImmoAnalyse.

POURQUOI UN FICHIER DE CONFIGURATION ?
Le cahier des charges (§ 6.2) impose que les seuils ne soient pas codés « en dur » au milieu
des fonctions. Toutes les hypothèses métier sont donc regroupées ici : si une règle change,
on modifie ce fichier et AUCUNE fonction de traitement.

Les seuils sont des hypothèses pédagogiques (cahier § 6), pas des normes du marché.
"""
from pathlib import Path

# --------------------------------------------------------------------------- chemins
RACINE = Path(__file__).resolve().parent.parent          # dossier immo-analyse/
RAW = RACINE / "data" / "raw"                            # données brutes : LECTURE SEULE
SOURCES = RAW / "sources"
REFERENTIELS = RAW / "referentiels"
PROCESSED = RACINE / "data" / "processed"                # données propres
QUARANTINE = RACINE / "data" / "quarantine"              # lignes rejetées + motifs
REPORTS = RACINE / "reports"                             # rapports de qualité et analyses

# --------------------------------------------------------------------------- sources
# Format de chaque flux (cahier § 5.2). Le « volume attendu » vient de fiche_conception_dataset.md
# et sert à réconcilier ce qu'on reçoit avec ce qui est annoncé.
SOURCES_CONFIG = {
    "plateforme": {"fichier": "plateforme_immo_sn.csv", "format": "csv", "sep": ";", "encodage": "utf-8", "volume_attendu": 875},
    "agence": {"fichier": "agence_teranga.xlsx", "format": "excel", "feuille": "Annonces", "volume_attendu": 680},
    "particuliers": {"fichier": "particuliers.json", "format": "json", "volume_attendu": 731},
    "notaires": {"fichier": "notaires.csv", "format": "csv", "sep": ",", "encodage": "utf-8", "volume_attendu": 410},
    "historique": {"fichier": "import_historique.csv", "format": "csv", "sep": ";", "encodage": "latin-1", "volume_attendu": 528},
}
# Préfixe de l'identifiant global : id_bien = "<source>:<id_local>"
# (un identifiant local n'est PAS une clé fiable, cahier § 5.3).

# --------------------------------------------------------------------------- transactions
TRANSACTIONS = ("vente", "location")
PERIODICITES = ("mensuel", "trimestriel", "semestriel", "annuel")

# Certaines sources n'ont pas de colonne « vente / location ».
# - notaires (actes) et historique (DateVente) ne contiennent que des ventes, par nature.
# - agence : on déduit la transaction du statut (voir STATUT_VERS_TRANSACTION).
TRANSACTION_PAR_NATURE = {"notaires": "vente", "historique": "vente"}

# Preuve de cette table : dans la plateforme et chez les particuliers (où la transaction est écrite),
# « Disponible » et « Loué » correspondent à 100 % à des locations (214 + 168 cas, 0 contre-exemple).
# Les statuts de vente (Vendu, En vente, Sous offre, Retiré, À confirmer) correspondent à des ventes.
STATUT_VERS_TRANSACTION = {
    "Disponible": "location", "Loué": "location",
    "En vente": "vente", "Vendu": "vente", "Sous offre": "vente", "Retiré": "vente", "À confirmer": "vente",
}

# Alias connus d'un nom de ville (cahier § 5.3 cite « Dkr »). Ajouter ici, jamais dans le code.
ALIAS_VILLES = {"dkr": "Dakar"}

# --------------------------------------------------------------------------- seuils de plausibilité
SEUILS = {
    "vente_prix_min": 100_000,          # FCFA : en dessous -> prix atypique à vérifier
    "vente_prix_max": 2_000_000_000,    # FCFA : au-dessus -> prix atypique à vérifier
    "loyer_mensuel_min": 25_000,        # FCFA / mois
    "loyer_mensuel_max": 5_000_000,     # FCFA / mois
    "surface_min": 5,                   # m²
    "surface_max": 2_000,               # m²
    "chambres_max_studio_appart": 10,   # au-dessus : atypique pour un appartement ou un studio
    "sdb_surplus_max": 2,               # sdb > chambres + 2 -> atypique
    "iqr_k": 1.5,                       # facteur de la règle de Tukey sur le prix au m²
}

# --------------------------------------------------------------------------- rapprochement de doublons
# Le seuil est une hypothèse DOCUMENTÉE et calibrée sur les données (voir README, section doublons).
RAPPROCHEMENT = {
    "tolerance_surface": 0.05,      # écart relatif de surface à partir duquel la similarité tombe à 0
    "tolerance_prix": 0.15,         # idem pour le prix (prix demandé et prix d'acte peuvent différer)
    "jours_pleine_similarite": 30,  # écart de dates toléré sans pénalité
    "jours_similarite_nulle": 365,  # au-delà : similarité de date nulle
    "poids": {"surface": 0.4, "prix": 0.4, "pieces": 0.1, "date": 0.1},
    "seuil_doublon_probable": 0.75,  # score minimal pour dire « même bien » (voir rapprochement.py)
    # Conditions NÉCESSAIRES en plus du score : la surface (1 décimale sur 20 à 1 500 m²) est l'attribut
    # le plus discriminant ; deux biens différents ont rarement la même à 0,5 % près ET le même prix.
    "sim_surface_min": 0.90,         # surface identique à 0,5 % près
    "sim_prix_min": 0.60,            # prix à 6 % près
    "simulations_hasard": 10,        # nb de tirages pour estimer les « faux doublons » dus au hasard
}

# Un même jour partagé par autant d'annonces d'UNE source = lot importé en masse (valeurs par défaut ?)
SEUIL_LOT_MEME_DATE = 20

# --------------------------------------------------------------------------- statuts
STATUTS_FINAUX = ("conforme", "corrige", "conserve_avertissement", "quarantaine", "doublon_exact_ecarte")
