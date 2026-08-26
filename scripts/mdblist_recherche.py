#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mdblist_recherche.py
=====================

Cherche une liste PUBLIQUE sur MDBList.com par titre, et affiche pour
chaque résultat le snippet JSON prêt à coller dans une source
`"provider": "mdblist"` du fichier de collections Nuvio.

À lancer en LOCAL (pas besoin dans GitHub Actions) pour trouver la bonne
liste de remplacement quand tu migres une source Trakt vers MDBList.

Usage :
--------
    export MDBLIST_API_KEY="ta_cle_ici"
    python3 scripts/mdblist_recherche.py "james bond"

    # ou en passant la clé directement :
    python3 scripts/mdblist_recherche.py --cle-api ta_cle "james bond"

Endpoint utilisé (confirmé par lecture du code source du client Go
officiel `mdblist-cli`, voir
github.com/luckylittle/mdblist-cli/blob/main/internal/client/mdblist.go) :
    GET https://api.mdblist.com/lists/search?apikey=...&query=...
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    import requests
except ImportError:  # pragma: no cover
    print("Le paquet 'requests' est requis : pip install requests", file=sys.stderr)
    raise

API_BASE = "https://api.mdblist.com"


def rechercher(cle_api: str, requete: str) -> list[dict]:
    r = requests.get(
        f"{API_BASE}/lists/search",
        params={"apikey": cle_api, "query": requete},
        timeout=15,
    )
    if r.status_code == 401:
        print("Erreur : clé API invalide ou manquante.", file=sys.stderr)
        sys.exit(1)
    r.raise_for_status()
    resultats = r.json()
    if not isinstance(resultats, list):
        print(f"Réponse inattendue de l'API MDBList : {resultats!r}", file=sys.stderr)
        return []
    return sorted(resultats, key=lambda l: -(l.get("items") or 0))


def afficher(resultats: list[dict]) -> None:
    if not resultats:
        print("Aucune liste trouvée.")
        return

    for i, liste in enumerate(resultats, start=1):
        nom = liste.get("name", "?")
        user = liste.get("user_name", "?")
        slug = liste.get("slug", "?")
        nb_items = liste.get("items", "?")
        likes = liste.get("likes", 0)
        media_type = liste.get("mediatype") or "mixte"
        prive = " 🔒 PRIVÉE (pas accessible sans être le propriétaire connecté)" if liste.get("private") else ""

        print(f"\n{i}. {nom}{prive}")
        print(f"   👤 {user}  ·  📦 {nb_items} items  ·  ❤️  {likes} likes  ·  🎬 {media_type}")
        print(f"   🔗 https://mdblist.com/lists/{user}/{slug}")
        print("   Snippet JSON à coller dans une source :")
        print(f'   {{ "provider": "mdblist", "mdblistUrl": "https://mdblist.com/lists/{user}/{slug}" }}')


def main() -> int:
    parser = argparse.ArgumentParser(description="Recherche une liste publique sur MDBList.com par titre.")
    parser.add_argument("requete", help="Terme(s) à rechercher (ex: \"james bond\")")
    parser.add_argument("--cle-api", default=None, help="Clé API MDBList (ou variable MDBLIST_API_KEY)")
    args = parser.parse_args()

    cle_api = args.cle_api or os.environ.get("MDBLIST_API_KEY")
    if not cle_api:
        print(
            "Erreur : clé API manquante (--cle-api ou MDBLIST_API_KEY).\n"
            "Génère-en une gratuitement sur https://mdblist.com/preferences/ "
            "(connexion via ton compte Trakt).",
            file=sys.stderr,
        )
        return 1

    resultats = rechercher(cle_api, args.requete)
    afficher(resultats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
