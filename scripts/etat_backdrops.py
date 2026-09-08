#!/usr/bin/env python3
"""
etat_backdrops.py
===================

Tableau de bord (lecture seule, aucune écriture) de l'état de tous les
backdrops : pour chaque dossier du JSON de collections, indique s'il a une
image manuelle, un backdrop déjà généré sur disque, s'il manque encore, ou
s'il est ignoré (groupe/filtre désactivé) -- plus la liste des fichiers
orphelins. Donne une vue d'ensemble en un coup d'oeil, sans attendre un
run complet de generer_backdrops.py.

Rassemble en une seule commande ce que les autres scripts font
séparément : comparer_collections.py (ce qui a changé), images-manuelles.json
(les surcharges), et detecter_backdrops_orphelins (les fichiers en trop).

Usage :
    python3 scripts/etat_backdrops.py
    python3 scripts/etat_backdrops.py --groupe Genres
    python3 scripts/etat_backdrops.py --seulement-manquants
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config_collections  # noqa: E402
from generer_backdrops import (  # noqa: E402
    GROUPE_SLUGS,
    NOM_DOSSIER_BACKDROPS,
    charger_collections,
    charger_images_manuelles,
    detecter_backdrops_orphelins,
    dossier_actif,
    nom_fichier_backdrop,
    normaliser,
    slugifier,
)


def etat_dossier(
    groupe_titre: str,
    dossier_titre: str,
    images_manuelles: dict[str, str],
    repertoire_sortie: Path,
) -> tuple[str, Path]:
    """Détermine le statut d'un dossier et le chemin de fichier attendu."""
    slug_groupe = GROUPE_SLUGS.get(normaliser(groupe_titre), slugifier(groupe_titre))
    chemin = repertoire_sortie / slug_groupe / NOM_DOSSIER_BACKDROPS / f"{nom_fichier_backdrop(dossier_titre)}.jpg"

    if dossier_titre in images_manuelles:
        return ("image manuelle" if chemin.exists() else "image manuelle (pas encore générée)"), chemin
    if not dossier_actif(groupe_titre, dossier_titre):
        return "ignoré (groupe/filtre désactivé)", chemin
    if chemin.exists():
        return "généré", chemin
    return "manquant", chemin


def main() -> int:
    parser = argparse.ArgumentParser(
        description="État de tous les backdrops (généré / manquant / image manuelle / ignoré)."
    )
    parser.add_argument("--collections", default="Templates/Nuvio-Collections-Dwade58200.json")
    parser.add_argument("--sortie", default="Collections")
    parser.add_argument("--images-manuelles", default="Templates/images-manuelles.json")
    parser.add_argument("--config-groupes", default="Templates/groupes-config.json")
    parser.add_argument("--groupe", default=None, help="Ne montrer qu'un groupe précis (sous-chaîne, insensible à la casse)")
    parser.add_argument("--seulement-manquants", action="store_true", help="N'afficher que les dossiers au statut 'manquant'")
    args = parser.parse_args()

    config_collections.appliquer_config_externe(
        Path(args.config_groupes) if args.config_groupes else None
    )

    collections: list[dict[str, Any]] = charger_collections(Path(args.collections))
    images_manuelles = charger_images_manuelles(Path(args.images_manuelles))
    repertoire_sortie = Path(args.sortie)

    compteurs: dict[str, int] = {}
    for groupe in collections:
        titre_groupe = groupe.get("title", "")
        if args.groupe and args.groupe.lower() not in titre_groupe.lower():
            continue

        lignes = []
        for dossier in groupe.get("folders", []):
            titre_dossier = dossier.get("title", "")
            statut, _chemin = etat_dossier(titre_groupe, titre_dossier, images_manuelles, repertoire_sortie)
            compteurs[statut] = compteurs.get(statut, 0) + 1
            if args.seulement_manquants and statut != "manquant":
                continue
            lignes.append(f"  [{statut}] {titre_dossier}")

        if lignes:
            print(f"\n📁 {titre_groupe}")
            print("\n".join(lignes))

    orphelins = detecter_backdrops_orphelins(collections, repertoire_sortie)

    print("\n" + "=" * 60)
    print("Résumé :")
    for statut, nb in sorted(compteurs.items(), key=lambda kv: -kv[1]):
        print(f"  {statut} : {nb}")
    if orphelins:
        print(f"  fichiers orphelins sur disque : {len(orphelins)} (voir --signaler-orphelins de generer_backdrops.py pour le détail)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
