"""Point d'entrée unique du pipeline ImmoAnalyse.

    python -m src.main                      # exécution complète, date du jour
    python -m src.main --date-ref 2026-10-29  # fixe la « date d'exécution » : résultats reproductibles
    python -m src.main --sans-simulation    # saute l'estimation des faux doublons (plus rapide)

Le script charge, normalise, valide, rapproche, exporte et vérifie les exports.
Il s'exécute de bout en bout avec UNE commande (critère d'acceptation n°10).
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from src.analysis.export import exporter, verifier_exports
from src.processing.pipeline import executer_pipeline


def main(argv=None) -> int:
    parseur = argparse.ArgumentParser(description="Pipeline de qualité de données immobilières (ImmoAnalyse)")
    parseur.add_argument("--date-ref", type=date.fromisoformat, default=None,
                         help="date d'exécution de référence AAAA-MM-JJ (défaut : aujourd'hui)")
    parseur.add_argument("--sans-simulation", action="store_true", help="ne pas estimer les faux doublons dus au hasard")
    parseur.add_argument("--log", default="INFO", help="niveau de journalisation (DEBUG, INFO, WARNING)")
    args = parseur.parse_args(argv)

    logging.basicConfig(level=args.log.upper(), format="%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")
    log = logging.getLogger("immoanalyse")

    resultats = executer_pipeline(args.date_ref, simuler_hasard=not args.sans_simulation)
    rapport = exporter(resultats)
    controles = verifier_exports(resultats)

    sf = rapport["statuts_finaux"]
    log.info("RÉSUMÉ : %d reçus | exploitables %d (%s %%) | quarantaine %d | copies exactes %d",
             rapport["volumes"]["total_recus"], sf["enregistrements_exploitables"], sf["taux_exploitable_pct"],
             sf["nombres"]["quarantaine"], sf["nombres"]["doublon_exact_ecarte"])
    echecs = [nom for nom, ok in controles.items() if not ok]
    for nom, ok in controles.items():
        log.log(logging.INFO if ok else logging.ERROR, "[%s] %s", "OK" if ok else "ÉCHEC", nom)
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
