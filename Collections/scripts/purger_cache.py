#!/usr/bin/env python3
"""
purger_cache.py
=================

Purge le cache CDN jsDelivr pour tous les backdrops générés, afin que les
nouvelles images soient servies immédiatement (jsDelivr cache sinon les
fichiers pendant ~7 jours).

Usage :
    python3 scripts/purger_cache.py --depot Dwade58200/nuvio-configuration \
        --branche feature/backdrops-automation --sortie Collections
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests


def purger_cdn(depot: str, branche: str, repertoire_sortie: Path, delai: float = 0.3) -> None:
    fichiers = sorted(repertoire_sortie.rglob("*.jpg"))

    if not fichiers:
        print(f"Aucun fichier .jpg trouvé dans {repertoire_sortie}, rien à purger.")
        return

    reussis, echoues = 0, 0
    for fichier in fichiers:
        # chemin tel qu'il apparaît dans le dépôt (ex: Collections/Genres/Backdrops/Action_Backdrop.jpg)
        chemin_depot = f"{repertoire_sortie.name}/{fichier.relative_to(repertoire_sortie)}"
        # chaque segment est encodé séparément (ex: l'espace dans
        # "Services de Streaming"), pour que l'URL de purge reste valide.
        chemin_encode = "/".join(quote(segment) for segment in Path(chemin_depot).parts)
        url_purge = f"https://purge.jsdelivr.net/gh/{depot}@{branche}/{chemin_encode}"
        try:
            r = requests.get(url_purge, timeout=10)
            if r.status_code == 200:
                reussis += 1
                print(f"✅ Purgé : {chemin_depot}")
            else:
                echoues += 1
                print(f"⚠️  Échec ({r.status_code}) : {chemin_depot}", file=sys.stderr)
        except requests.RequestException as exc:
            echoues += 1
            print(f"⚠️  Erreur réseau pour {chemin_depot} : {exc}", file=sys.stderr)
        time.sleep(delai)  # éviter de spammer l'API de purge

    print(f"\nRésumé purge CDN : {reussis} réussi(s), {echoues} échoué(s), sur {len(fichiers)} fichier(s).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge le cache jsDelivr pour les backdrops générés.")
    parser.add_argument("--depot", default="Dwade58200/nuvio-configuration", help="owner/repo GitHub")
    parser.add_argument("--branche", default="feature/backdrops-automation")
    parser.add_argument("--sortie", default="Collections", help="Répertoire contenant les backdrops générés")
    parser.add_argument("--delai", type=float, default=0.3, help="Délai (s) entre chaque requête de purge")
    args = parser.parse_args()

    purger_cdn(args.depot, args.branche, Path(args.sortie), args.delai)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
