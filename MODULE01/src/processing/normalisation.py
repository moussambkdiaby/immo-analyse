"""Fonctions de normalisation : convertir une valeur brute (texte) en valeur propre.

PRINCIPES (à retenir) :
1. Chaque fonction traite UNE valeur et renvoie un couple (valeur, statut). Elle est « pure » :
   mêmes entrées -> mêmes sorties, aucun effet de bord. C'est ce qui la rend testable.
2. Le statut dit ce qui s'est passé :
      "conforme"  : la valeur était déjà propre
      "corrige"   : une règle SÛRE a été appliquée (espaces, virgule décimale, « millions »...)
      "manquant"  : case vide (ou vide déguisé : "None", "null"...)
      autre       : échec de conversion (non_numerique, ambigu, negatif, impossible...)
3. On NE DEVINE JAMAIS. Quand le texte ne contient pas la preuve de la bonne valeur
   (« 1,250 », « 03/04/2024 » sans convention connue), on renvoie None + un statut explicite.
4. La valeur brute n'est jamais écrasée : le pipeline la conserve dans une colonne *_brut
   (la normalisation est donc réversible).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

import pandas as pd

# --------------------------------------------------------------------------- utilitaires

_VIDES_DEGUISES = {"", "none", "null", "nan", "n/a", "na", "nc", "-", "--"}


def est_vide(valeur) -> bool:
    """Vrai si la valeur est vide (None, NaN, texte vide) ou un « vide déguisé » ("None", "null"...).

    POURQUOI : dans particuliers.json, un None Python a été converti en texte « None FCFA ».
    isna() ne le voit pas : il faut le chercher explicitement.
    """
    if valeur is None:
        return True
    if isinstance(valeur, float) and pd.isna(valeur):
        return True
    if valeur is pd.NA or valeur is pd.NaT:
        return True
    return str(valeur).strip().lower() in _VIDES_DEGUISES


def cle_texte(texte) -> str | None:
    """Forme « clé » d'un texte : sans accents, minuscules, ponctuation -> espace.

    POURQUOI : « Thiès », « THIES » et « thies » doivent se comparer comme égaux, sans que
    l'on modifie la valeur affichée. On compare les CLÉS, on affiche les noms OFFICIELS.
    """
    if est_vide(texte):
        return None
    t = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return t or None


# --------------------------------------------------------------------------- nombres en lettres

_UNITES = {
    "zero": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
    "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14,
    "quinze": 15, "seize": 16,
}
_DIZAINES = {"vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60}


def mots_vers_nombre(texte: str) -> int | None:
    """Convertit un nombre écrit en français (1 à 999) : « quatre-vingt » -> 80.

    POURQUOI : le cahier cite « quatre-vingt » parmi les formats rencontrés. C'est un cas
    SANS ambiguïté, donc corrigeable. Toute suite de mots invraisemblable (« deux trois »)
    ou inconnue renvoie None : on ne devine pas.
    """
    t = cle_texte(texte)
    if not t:
        return None
    mots = [m for m in t.split() if m != "et"]
    mots = [m[:-1] if m in ("vingts", "cents") else m for m in mots]   # pluriels -> singuliers
    total, courant, precedent = 0, 0, None
    for m in mots:
        if m == "vingt" and precedent == "quatre" and courant == 4:
            courant = 80                                  # « quatre vingt » = 4 x 20
        elif m in _DIZAINES:
            if courant != 0:
                return None                               # « deux trente » n'existe pas
            courant = _DIZAINES[m]
        elif m in _UNITES:
            if courant % 10 != 0 and not (m == "quatre" and courant == 0):
                return None                               # « deux trois » n'existe pas
            courant += _UNITES[m]
        elif m == "cent":
            if courant >= 10:
                return None
            total, courant = total + (courant or 1) * 100, 0
        else:
            return None
        precedent = m
    resultat = total + courant
    return resultat if 1 <= resultat <= 999 else None


# --------------------------------------------------------------------------- nombres (prix, surface)

def _en_nombre(valeur):
    """Si la valeur est déjà un nombre Python (int / float), le renvoie ; sinon None."""
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    return None


def normaliser_prix(texte):
    """Convertit un prix en FCFA. Renvoie (nombre, statut).

    Règles (cahier § 6.3 et regles_metier.md) :
      - chiffres seuls (éventuellement un point décimal)    -> "conforme"
      - séparateurs de milliers (espace, espace insécable, virgule en groupes de 3) -> "corrige"
      - suffixe FCFA explicite                               -> "corrige"
      - « 57.62 millions » (unité EXPLICITE)                 -> "corrige" (x 1 000 000)
      - « 1,250 » seul : milliers ou décimale ? AMBIGU       -> (None, "ambigu")
      - texte sans nombre (« à négocier »)                   -> (None, "non_numerique")
      - négatif                                              -> (None, "negatif")
      - vide ou vide déguisé                                 -> (None, "manquant")
    """
    nombre = _en_nombre(texte)
    if nombre is not None:
        return (None, "manquant") if pd.isna(nombre) else (nombre, "conforme")
    if est_vide(texte):
        return None, "manquant"

    brut = str(texte).strip()
    # Suffixe de devise explicite (« 438 746 000 FCFA ») : on le retire, ce qui est une correction.
    sans_devise = re.sub(r"\s*(?:f\s?cfa|xof|cfa|francs?)\s*$", "", brut, flags=re.IGNORECASE).strip()
    devise_retiree = sans_devise != brut
    if est_vide(sans_devise):          # « None FCFA » : vide déguisé
        return None, "manquant"

    # Nombre négatif : on ne le « répare » pas (le signe est peut-être une erreur de saisie).
    if re.fullmatch(r"-\s*\d[\d\s.,]*", sans_devise):
        return None, "negatif"

    # Chiffres seuls, avec ou sans point décimal
    if re.fullmatch(r"\d+(\.\d+)?", sans_devise):
        return float(sans_devise), ("corrige" if devise_retiree else "conforme")

    # Espaces (normaux ou insécables) comme séparateurs de milliers : « 438 746 000 »
    if re.fullmatch(r"\d{1,3}([\s\u00a0\u202f]\d{3})+", sans_devise):
        return float(re.sub(r"[\s\u00a0\u202f]", "", sans_devise)), "corrige"

    # Virgule comme séparateur de milliers : au moins DEUX groupes (« 1,250,000 »)
    if re.fullmatch(r"\d{1,3}(,\d{3}){2,}", sans_devise):
        return float(sans_devise.replace(",", "")), "corrige"
    # Un seul groupe (« 1,250 ») : 1 250 ou 1,25 ? On ne devine pas.
    if re.fullmatch(r"\d+,\d{1,3}", sans_devise):
        return None, "ambigu"

    # « 57.62 millions » / « 1,5 million » : l'unité est écrite, donc la règle est sûre
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*millions?", sans_devise, flags=re.IGNORECASE)
    if m:
        # round() : 57.62 * 1_000_000 donne 57619999.99999999 en virgule flottante
        return float(round(float(m.group(1).replace(",", ".")) * 1_000_000)), "corrige"

    return None, "non_numerique"


def normaliser_surface(texte):
    """Convertit une surface en m². Renvoie (nombre, statut).

    Règles :
      - entier ou point décimal                      -> "conforme"
      - virgule décimale à 1 ou 2 chiffres (« 92,4 ») -> "corrige"
      - virgule + 3 chiffres (« 1,250 »)             -> (None, "ambigu")  : 1 250 m² ou 1,25 m² ?
      - nombre en lettres (« quatre-vingt »)         -> "corrige"
      - négatif                                      -> (None, "negatif")
      - autre texte                                  -> (None, "non_numerique")
      - vide                                         -> (None, "manquant")
    """
    nombre = _en_nombre(texte)
    if nombre is not None:
        if pd.isna(nombre):
            return None, "manquant"
        return (None, "negatif") if nombre < 0 else (nombre, "conforme")
    if est_vide(texte):
        return None, "manquant"

    brut = str(texte).strip()
    sans_unite = re.sub(r"\s*(?:m2|m²|mètres? carrés?|metres? carres?)\s*$", "", brut, flags=re.IGNORECASE).strip()
    unite_retiree = sans_unite != brut

    if re.fullmatch(r"-\s*\d+([.,]\d+)?", sans_unite):
        return None, "negatif"
    if re.fullmatch(r"\d+(\.\d+)?", sans_unite):
        return float(sans_unite), ("corrige" if unite_retiree else "conforme")
    # Ordre important : l'exception (ambigu) AVANT la règle générale (virgule décimale)
    if re.fullmatch(r"\d+,\d{3}", sans_unite):
        return None, "ambigu"
    if re.fullmatch(r"\d+,\d{1,2}", sans_unite):
        return float(sans_unite.replace(",", ".")), "corrige"

    en_chiffres = mots_vers_nombre(sans_unite)
    if en_chiffres is not None:
        return float(en_chiffres), "corrige"
    return None, "non_numerique"


def normaliser_entier(valeur):
    """Convertit un compte (chambres, salles de bain) en entier. Renvoie (entier, statut).

    Les négatifs sont conservés tels quels : c'est la RÈGLE de validation qui les signale
    (entier >= 0), pas la normalisation.
    """
    nombre = _en_nombre(valeur)
    if nombre is not None:
        if pd.isna(nombre):
            return None, "manquant"
        if nombre == int(nombre):
            return int(nombre), "conforme"
        return None, "non_numerique"
    if est_vide(valeur):
        return None, "manquant"
    brut = str(valeur).strip()
    if re.fullmatch(r"-?\d+", brut):
        return int(brut), "conforme"
    if re.fullmatch(r"-?\d+\.0+", brut):
        return int(float(brut)), "corrige"
    en_chiffres = mots_vers_nombre(brut)
    if en_chiffres is not None:
        return en_chiffres, "corrige"
    return None, "non_numerique"


# --------------------------------------------------------------------------- dates

_MOIS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}


def inferer_convention_date(textes) -> str:
    """Devine la convention des dates « xx/xx/aaaa » d'UNE source, à partir de PREUVES.

    Raisonnement : un jour ne dépasse jamais 31, un mois ne dépasse jamais 12.
      - si le 1er nombre dépasse parfois 12 et le 2e jamais  -> JJ/MM (le 1er est un jour)
      - si le 2e nombre dépasse parfois 12 et le 1er jamais  -> MM/JJ
      - sinon (aucune preuve, ou preuves contradictoires)    -> "ambigu"
    Les dates où les DEUX nombres dépassent 12 (32/13/2024) sont impossibles : elles ne prouvent rien.
    """
    premier_gt12 = deuxieme_gt12 = 0
    for t in textes:
        if est_vide(t):
            continue
        m = re.fullmatch(r"\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s*", str(t))
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 and b > 12:
            continue
        premier_gt12 += a > 12
        deuxieme_gt12 += b > 12
    if premier_gt12 and not deuxieme_gt12:
        return "JJ/MM"
    if deuxieme_gt12 and not premier_gt12:
        return "MM/JJ"
    return "ambigu"


def _date_valide(annee: int, mois: int, jour: int) -> date | None:
    try:
        return date(annee, mois, jour)
    except ValueError:
        return None


def normaliser_date(texte, convention: str = "ambigu", date_ref: date | None = None):
    """Convertit une date en ISO (AAAA-MM-JJ). Renvoie (texte_iso, statut).

    statuts : conforme (déjà ISO) | corrige | manquant | impossible | ambigu | non_interpretable
    - convention : "JJ/MM", "MM/JJ" ou "ambigu" (voir inferer_convention_date)
    - date_ref   : date de référence pour « hier », « aujourd'hui » (rend le résultat REPRODUCTIBLE)

    On ne convertit jamais une date ambiguë sans justification : « 03/04/2024 » avec une
    convention inconnue reste (None, "ambigu").
    """
    if est_vide(texte):
        return None, "manquant"
    if isinstance(texte, (pd.Timestamp, date)):
        return pd.Timestamp(texte).date().isoformat(), "conforme"

    brut = str(texte).strip()
    cle = cle_texte(brut) or ""

    # 1. ISO : AAAA-MM-JJ
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", brut)
    if m:
        d = _date_valide(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return (d.isoformat(), "conforme") if d else (None, "impossible")

    # 2. xx/xx/aaaa
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", brut)
    if m:
        a, b, annee = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12 and b > 12:
            return None, "impossible"                    # aucun des deux ne peut être un mois
        if convention == "JJ/MM":
            jour, mois = a, b
        elif convention == "MM/JJ":
            mois, jour = a, b
        else:                                            # convention inconnue : seule la preuve LOCALE compte
            if a > 12:
                jour, mois = a, b                        # a ne peut pas être un mois
            elif b > 12:
                mois, jour = a, b
            elif a == b:
                jour, mois = a, b                        # identique dans les deux lectures
            else:
                return None, "ambigu"
        d = _date_valide(annee, mois, jour)
        return (d.isoformat(), "corrige") if d else (None, "impossible")

    # 3. dates relatives : « hier », « aujourd'hui », « avant-hier »
    ref = date_ref or date.today()
    relatives = {"aujourd hui": 0, "hier": 1, "avant hier": 2}
    if cle in relatives:
        return (ref - timedelta(days=relatives[cle])).isoformat(), "corrige"

    # 4. mois en lettres : « 12 mars 2024 »
    m = re.fullmatch(r"(\d{1,2}) ([a-z]+) (\d{4})", cle)
    if m and m.group(2) in _MOIS:
        d = _date_valide(int(m.group(3)), _MOIS[m.group(2)], int(m.group(1)))
        return (d.isoformat(), "corrige") if d else (None, "impossible")

    return None, "non_interpretable"


# --------------------------------------------------------------------------- périodicité, transaction, statut

_PERIODICITES_SYNONYMES = {
    "mensuel": ("mois", "mensuel", "mensuelle", "mens", "monthly"),
    "trimestriel": ("trimestre", "trimestriel", "trimestrielle", "trim", "trimestres"),
    "semestriel": ("semestre", "semestriel", "semestrielle", "sem", "semestres"),
    "annuel": ("an", "annee", "annuel", "annuelle", "ans", "annees", "yearly"),
}


def normaliser_periodicite(texte):
    """Reconnaît une périodicité de loyer : « /mois », « par mois », « mens. » -> "mensuel".

    Cherche des MOTS ENTIERS (« mois » ne doit pas être trouvé dans « promotion »).
    Renvoie (periodicite, statut) ; statut "inconnu" si rien n'est reconnu (on ne devine pas).
    """
    if est_vide(texte):
        return None, "manquant"
    mots = (cle_texte(texte) or "").split()
    for forme, synonymes in _PERIODICITES_SYNONYMES.items():
        if any(mot in synonymes for mot in mots):
            return forme, ("conforme" if (cle_texte(texte) == forme) else "corrige")
    return None, "inconnu"


_TRANSACTIONS_SYNONYMES = {
    "vente": ("vente", "vendre", "a vendre", "vendu", "achat"),
    "location": ("location", "louer", "a louer", "loue", "loc", "bail"),
}


def normaliser_transaction(texte):
    """Ramène un type de transaction à "vente" ou "location". Renvoie (valeur, statut)."""
    if est_vide(texte):
        return None, "manquant"
    cle = cle_texte(texte)
    for forme, synonymes in _TRANSACTIONS_SYNONYMES.items():
        if cle in synonymes:
            return forme, ("conforme" if str(texte).strip() == forme else "corrige")
    return None, "non_interpretable"


STATUTS_CANONIQUES = {
    "vendu": "Vendu", "vente conclue": "Vendu", "acte signe": "Vendu",
    "en vente": "En vente", "disponible": "Disponible", "loue": "Loué",
    "sous offre": "Sous offre", "retire": "Retiré", "a confirmer": "À confirmer",
}


def normaliser_statut(texte):
    """Ramène un statut d'annonce à sa forme canonique (« VENDU », « Vente conclue » -> « Vendu »)."""
    if est_vide(texte):
        return None, "manquant"
    canonique = STATUTS_CANONIQUES.get(cle_texte(texte))
    if canonique is None:
        return None, "non_interpretable"
    return canonique, ("conforme" if str(texte).strip() == canonique else "corrige")


# --------------------------------------------------------------------------- catégorie de bien

def normaliser_categorie(valeur, synonymes, officielles):
    """Ramène un type de bien à son nom officiel, sans jamais deviner.

    synonymes   : dict {clé_texte du synonyme : nom officiel}, construit depuis le référentiel
    officielles : ensemble des 7 noms officiels
    Renvoie (nom officiel, statut) :
      (nom, "conforme")          : déjà écrit exactement comme le nom officiel
      (nom, "corrige")           : casse, espaces, accents ou synonyme du référentiel
      (None, "hors_referentiel") : valeur inconnue -> on ne devine pas
      (None, "manquant")         : case vide
    """
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return None, "manquant"
    brut = str(valeur)
    if brut in officielles:
        return brut, "conforme"
    cle = cle_texte(brut)
    if cle and cle in synonymes:
        return synonymes[cle], "corrige"
    return None, "hors_referentiel"
