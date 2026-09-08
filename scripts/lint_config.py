#!/usr/bin/env python3
"""
lint_config.py
================

Vérifie `scripts/config_collections.py` à la recherche d'erreurs de
cohérence classiques : incohérence entre CRITERES_GROUPES et GROUPE_SLUGS,
collision de noms de dossiers/fichiers de sortie, filtres inclure/exclure
qui se contredisent, entrées de NOMS_BACKDROP_PERSONNALISES devenues
obsolètes (dossier renommé/supprimé côté Nuvio).

Complète la validation du SCHÉMA JSON (`valider_collections.py`, qui
vérifie la STRUCTURE du fichier de collections) -- celui-ci vérifie la
CONFIGURATION Python elle-même. Outil de relecture pur : ne modifie rien,
code de sortie 1 s'il trouve au moins un avertissement (utilisable en CI).

Usage :
    python3 scripts/lint_config.py
    python3 scripts/lint_config.py --sans-collections   # sans le croisement avec le JSON actuel
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_collections import (  # noqa: E402
    CRITERES_GROUPES,
    GROUPE_SLUGS,
    NOMS_BACKDROP_PERSONNALISES,
)
from generer_backdrops import charger_collections, nom_fichier_backdrop  # noqa: E402


def verifier_coherence_groupes() -> list[str]:
    avertissements = []
    cles_criteres = set(CRITERES_GROUPES)
    cles_slugs = set(GROUPE_SLUGS)
    for cle in sorted(cles_criteres - cles_slugs):
        avertissements.append(
            f"Groupe {cle!r} présent dans CRITERES_GROUPES mais absent de GROUPE_SLUGS "
            "(nom de dossier de sortie généré automatiquement au lieu du nom voulu -- vérifie que c'est intentionnel)."
        )
    for cle in sorted(cles_slugs - cles_criteres):
        avertissements.append(
            f"Groupe {cle!r} présent dans GROUPE_SLUGS mais absent de CRITERES_GROUPES "
            "(traité actif par défaut, sans filtre -- vérifie que c'est voulu)."
        )
    return avertissements


def verifier_collisions_slugs() -> list[str]:
    avertissements = []
    compteur = Counter(GROUPE_SLUGS.values())
    for slug, nb in compteur.items():
        if nb > 1:
            groupes = sorted(cle for cle, s in GROUPE_SLUGS.items() if s == slug)
            avertissements.append(
                f"Le nom de dossier de sortie {slug!r} est utilisé par {nb} groupes différents ({groupes}) "
                "-- leurs backdrops vont se mélanger dans le même dossier."
            )
    return avertissements


def verifier_collisions_noms_fichiers() -> list[str]:
    avertissements = []
    noms: dict[str, list[str]] = {}
    for titre_dossier in NOMS_BACKDROP_PERSONNALISES:
        nom = nom_fichier_backdrop(titre_dossier)
        noms.setdefault(nom, []).append(titre_dossier)
    for nom, titres in sorted(noms.items()):
        if len(titres) > 1:
            avertissements.append(
                f"Les dossiers {titres} produisent le même nom de fichier {nom!r} -- "
                "collision si les deux se retrouvent dans le même groupe."
            )
    return avertissements


def verifier_filtres_contradictoires() -> list[str]:
    avertissements = []
    for cle, critere in sorted(CRITERES_GROUPES.items()):
        if critere.inclure and critere.exclure:
            inclure_normalise = {m.lower() for m in critere.inclure}
            exclure_normalise = {m.lower() for m in critere.exclure}
            commun = inclure_normalise & exclure_normalise
            if commun:
                avertissements.append(
                    f"Groupe {cle!r} : les mots {sorted(commun)} sont à la fois dans inclure ET exclure "
                    "(exclure gagne toujours -> ces dossiers ne seront JAMAIS actifs, entrée probablement erronée)."
                )
    return avertissements


def verifier_noms_personnalises_obsoletes(collections: list[dict[str, Any]] | None) -> list[str]:
    if collections is None:
        return []
    titres_reels = {d.get("title", "") for groupe in collections for d in groupe.get("folders", [])}
    avertissements = []
    for titre_dossier in sorted(NOMS_BACKDROP_PERSONNALISES):
        if titre_dossier not in titres_reels:
            avertissements.append(
                f"NOMS_BACKDROP_PERSONNALISES contient {titre_dossier!r}, absent du JSON de collections actuel "
                "-- entrée probablement obsolète (dossier renommé ou supprimé côté Nuvio)."
            )
    return avertissements


def executer_tous_les_controles(collections: list[dict[str, Any]] | None) -> list[str]:
    return [
        *verifier_coherence_groupes(),
        *verifier_collisions_slugs(),
        *verifier_collisions_noms_fichiers(),
        *verifier_filtres_contradictoires(),
        *verifier_noms_personnalises_obsoletes(collections),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Vérifie la cohérence de scripts/config_collections.py.")
    parser.add_argument(
        "--collections",
        default="Templates/Nuvio-Collections-Dwade58200.json",
        help="Utilisé pour détecter les entrées NOMS_BACKDROP_PERSONNALISES obsolètes (optionnel)",
    )
    parser.add_argument(
        "--sans-collections",
        action="store_true",
        help="Ne pas croiser avec le JSON de collections (saute la détection des entrées obsolètes)",
    )
    args = parser.parse_args()

    collections = None
    if not args.sans_collections:
        chemin = Path(args.collections)
        if chemin.exists():
            collections = charger_collections(chemin)

    avertissements = executer_tous_les_controles(collections)

    if not avertissements:
        print("✅ scripts/config_collections.py : aucune incohérence détectée.")
        return 0

    print(f"⚠️  {len(avertissements)} avertissement(s) :\n")
    for a in avertissements:
        print(f"  - {a}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
