#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mettre_a_jour_urls.py
========================

Met à jour le champ `heroBackdropUrl` de chaque dossier dans
`Templates/Nuvio-Collections-Dwade58200.json`, pour qu'il pointe vers le
backdrop généré sur CE dépôt (via le CDN jsDelivr), au lieu du placeholder
qui pointe encore vers le dépôt de luckynumb3rs.

Ne touche QUE les dossiers pour lesquels un fichier a réellement été
généré (vérifié sur disque) -- les autres `heroBackdropUrl` (Franchises,
Streaming, Sports, dossiers non résolus) sont laissés tels quels.

Réutilise volontairement les mêmes fonctions de slug que
`generer_backdrops.py`, pour que les deux scripts restent strictement
synchronisés sur les chemins de fichiers.

Usage :
    python3 scripts/mettre_a_jour_urls.py \
        --collections Templates/Nuvio-Collections-Dwade58200.json \
        --sortie collections \
        --depot Dwade58200/nuvio-configuration \
        --branche feature/backdrops-automation
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generer_backdrops import GROUPE_SLUGS, dossier_actif, slugifier  # noqa: E402


def construire_url_cdn(depot: str, branche: str, chemin_relatif: Path) -> str:
    return f"https://cdn.jsdelivr.net/gh/{depot}@{branche}/collections/{chemin_relatif.as_posix()}"


def mettre_a_jour(
    collections: list[dict[str, Any]],
    repertoire_sortie: Path,
    depot: str,
    branche: str,
) -> tuple[int, int]:
    """Retourne (nb_mis_a_jour, nb_inchanges)."""
    mis_a_jour = 0
    inchanges = 0

    for groupe in collections:
        titre_groupe = groupe.get("title", "")
        slug_groupe = GROUPE_SLUGS.get(titre_groupe)
        if not slug_groupe:
            continue  # groupe inconnu du générateur -> on ne touche à rien

        for dossier in groupe.get("folders", []):
            if not dossier_actif(titre_groupe, dossier.get("title", "")):
                inchanges += 1
                continue  # groupe/dossier désactivé (ex: Franchises) -> jamais touché

            slug_dossier = slugifier(dossier.get("title", ""))
            chemin_relatif = Path(slug_groupe) / "backdrop" / f"{slug_dossier}.jpg"
            chemin_disque = repertoire_sortie / chemin_relatif

            if not chemin_disque.exists():
                inchanges += 1
                continue

            nouvelle_url = construire_url_cdn(depot, branche, chemin_relatif)
            if dossier.get("heroBackdropUrl") != nouvelle_url:
                dossier["heroBackdropUrl"] = nouvelle_url
                mis_a_jour += 1
            else:
                inchanges += 1

    return mis_a_jour, inchanges


def main() -> int:
    parser = argparse.ArgumentParser(description="Met à jour heroBackdropUrl vers les backdrops générés.")
    parser.add_argument("--collections", default="Templates/Nuvio-Collections-Dwade58200.json")
    parser.add_argument("--sortie", default="collections")
    parser.add_argument("--depot", default="Dwade58200/nuvio-configuration")
    parser.add_argument("--branche", default="feature/backdrops-automation")
    parser.add_argument("--dry-run", action="store_true", help="N'écrit rien, affiche juste ce qui changerait")
    args = parser.parse_args()

    chemin_json = Path(args.collections)
    with chemin_json.open(encoding="utf-8") as f:
        collections = json.load(f)

    mis_a_jour, inchanges = mettre_a_jour(collections, Path(args.sortie), args.depot, args.branche)

    print(f"heroBackdropUrl mis à jour : {mis_a_jour}")
    print(f"heroBackdropUrl inchangés  : {inchanges}")

    if mis_a_jour and not args.dry_run:
        with chemin_json.open("w", encoding="utf-8") as f:
            json.dump(collections, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"\n✅ {chemin_json} mis à jour et sauvegardé.")
    elif mis_a_jour and args.dry_run:
        print("\n(dry-run) rien n'a été écrit sur disque.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
