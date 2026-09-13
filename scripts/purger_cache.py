#!/usr/bin/env python3
"""
purger_cache.py
=================

Purge le cache CDN jsDelivr pour les backdrops générés, afin que les
nouvelles images soient servies immédiatement (jsDelivr cache sinon les
fichiers pendant ~7 jours).

Par défaut (sans --fichiers-modifies), purge TOUS les `.jpg` présents
dans `--sortie` -- pratique pour un run manuel/standalone où on ne sait
pas ce qui a changé. Dans le workflow GitHub Actions, seuls les fichiers
RÉELLEMENT modifiés par le dernier commit sont passés via
--fichiers-modifies (voir generer-backdrops.yml) : un run mensuel normal
ne touche qu'une poignée de dossiers sur 200+, purger tout le reste à
chaque fois n'a aucun effet utile (leur contenu sur le CDN n'a pas
changé) et ne fait que ralentir le workflow de plusieurs minutes pour
rien (0.3s de délai entre chaque requête, volontaire -- voir plus bas).

Usage :
    # Purge sélective (utilisée par le workflow) : uniquement les fichiers
    # listés (un chemin par ligne, relatif à la racine du dépôt -- typiquement
    # produit par `git diff --cached --name-only`)
    python3 scripts/purger_cache.py --depot Dwade58200/nuvio-configuration \
        --branche main --sortie Collections --fichiers-modifies fichiers_modifies.txt

    # Purge complète (run manuel, comportement historique)
    python3 scripts/purger_cache.py --depot Dwade58200/nuvio-configuration \
        --branche main --sortie Collections
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests


def charger_fichiers_modifies(chemin: Path) -> list[Path] | None:
    """Charge la liste explicite de fichiers à purger (un chemin par
    ligne, relatif à la racine du dépôt -- typiquement produite par `git
    diff --cached --name-only` dans le workflow, AVANT le commit).
    Retourne None si le fichier n'existe pas (repli sur "tout purger",
    voir purger_cdn) -- une liste VIDE (fichier présent mais sans ligne,
    ex: seul un JSON a changé, aucun backdrop) est un résultat valide et
    distinct, qui signifie "rien à purger", pas "purge tout"."""
    if not chemin.exists():
        return None
    return [Path(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines() if ligne.strip()]


def purger_cdn(
    depot: str,
    branche: str,
    repertoire_sortie: Path,
    delai: float = 0.3,
    fichiers: list[Path] | None = None,
) -> None:
    """Si `fichiers` est fourni (voir --fichiers-modifies), ne purge QUE
    ces fichiers-là -- sinon (repli), tous les `.jpg` présents sous
    `repertoire_sortie`."""
    if fichiers is not None:
        fichiers_a_purger = sorted(fichiers)
    else:
        fichiers_a_purger = sorted(repertoire_sortie.rglob("*.jpg"))

    if not fichiers_a_purger:
        if fichiers is not None:
            print("Aucun fichier modifié à purger (0 backdrop dans la liste fournie).")
        else:
            print(f"Aucun fichier .jpg trouvé dans {repertoire_sortie}, rien à purger.")
        return

    reussis, echoues = 0, 0
    for fichier in fichiers_a_purger:
        try:
            chemin_relatif = fichier.relative_to(repertoire_sortie)
        except ValueError:
            # ex: --fichiers-modifies avec un --sortie qui ne correspond pas
            # au préfixe des chemins listés -- ignoré plutôt que de planter
            # tout le run pour une seule entrée mal formée.
            echoues += 1
            print(f"⚠️  Chemin hors de {repertoire_sortie}, ignoré : {fichier}", file=sys.stderr)
            continue
        # chemin tel qu'il apparaît dans le dépôt (ex: Collections/Genres/Backdrops/Action_Backdrop.jpg)
        chemin_depot = f"{repertoire_sortie.name}/{chemin_relatif}"
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

    print(f"\nRésumé purge CDN : {reussis} réussi(s), {echoues} échoué(s), sur {len(fichiers_a_purger)} fichier(s).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge le cache jsDelivr pour les backdrops générés.")
    parser.add_argument("--depot", default="Dwade58200/nuvio-configuration", help="owner/repo GitHub")
    parser.add_argument("--branche", default="main")
    parser.add_argument("--sortie", default="Collections", help="Répertoire contenant les backdrops générés")
    parser.add_argument("--delai", type=float, default=0.3, help="Délai (s) entre chaque requête de purge")
    parser.add_argument(
        "--fichiers-modifies",
        default=None,
        help="Fichier texte (un chemin par ligne, relatif à la racine du dépôt) listant les backdrops "
        "réellement modifiés -- limite la purge à ceux-ci au lieu de tout le contenu de --sortie",
    )
    args = parser.parse_args()

    fichiers = charger_fichiers_modifies(Path(args.fichiers_modifies)) if args.fichiers_modifies else None
    purger_cdn(args.depot, args.branche, Path(args.sortie), args.delai, fichiers=fichiers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
