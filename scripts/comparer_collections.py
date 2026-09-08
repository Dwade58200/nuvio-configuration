#!/usr/bin/env python3
"""
comparer_collections.py
========================

Compare deux versions du JSON de collections Nuvio et affiche un rapport
clair des groupes/dossiers ajoutés ou supprimés -- pour relire en un coup
d'oeil ce qui a changé avant de committer un nouvel export Nuvio.

Ceci est un outil de RELECTURE, pas une dépendance du pipeline de
génération : generer_backdrops.py n'a besoin de rien de tout ça pour
fonctionner (voir BACKDROPS_SETUP.md, section « Ajout/suppression d'une
collection dans Nuvio » -- l'auto-inclusion des nouveaux groupes/dossiers
est déjà gérée nativement par le pipeline). Ce script sert seulement à
VOIR ce qui a changé, notamment pour repérer un renommage (qui, lui,
n'est pas deviné automatiquement -- voir « Résilience aux renommages »).

Usage :
    # Comparer le fichier actuel à la dernière version commitée (Git)
    python3 scripts/comparer_collections.py

    # Comparer à un commit/branche précis
    python3 scripts/comparer_collections.py --ref HEAD~3

    # Comparer deux fichiers explicites (sans Git)
    python3 scripts/comparer_collections.py --ancien old.json --nouveau new.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generer_backdrops import normaliser  # noqa: E402


def _titres_dossiers(groupe: dict[str, Any]) -> set[str]:
    return {d.get("title", "") for d in groupe.get("folders", [])}


def _index_par_groupe(collections: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index {titre_groupe_normalisé: groupe}. En cas de doublon de titre
    normalisé (ne devrait pas arriver), le dernier groupe rencontré gagne."""
    return {normaliser(g.get("title", "")): g for g in collections}


def comparer(ancien: list[dict[str, Any]], nouveau: list[dict[str, Any]]) -> str:
    """Construit le rapport texte des différences entre deux exports."""
    index_ancien = _index_par_groupe(ancien)
    index_nouveau = _index_par_groupe(nouveau)

    cles_ancien = set(index_ancien)
    cles_nouveau = set(index_nouveau)

    lignes: list[str] = []

    groupes_ajoutes = cles_nouveau - cles_ancien
    groupes_supprimes = cles_ancien - cles_nouveau
    groupes_communs = cles_ancien & cles_nouveau

    if groupes_ajoutes:
        lignes.append(f"🆕 {len(groupes_ajoutes)} groupe(s) ajouté(s) :")
        for cle in sorted(groupes_ajoutes):
            groupe = index_nouveau[cle]
            nb = len(groupe.get("folders", []))
            lignes.append(f"  + {groupe.get('title', cle)!r} ({nb} dossier(s))")

    if groupes_supprimes:
        lignes.append(f"🗑️  {len(groupes_supprimes)} groupe(s) supprimé(s) :")
        for cle in sorted(groupes_supprimes):
            groupe = index_ancien[cle]
            nb = len(groupe.get("folders", []))
            lignes.append(f"  - {groupe.get('title', cle)!r} ({nb} dossier(s))")

    for cle in sorted(groupes_communs):
        titre_ancien = index_ancien[cle].get("title", cle)
        titre_nouveau = index_nouveau[cle].get("title", cle)
        dossiers_ancien = _titres_dossiers(index_ancien[cle])
        dossiers_nouveau = _titres_dossiers(index_nouveau[cle])

        ajoutes = dossiers_nouveau - dossiers_ancien
        supprimes = dossiers_ancien - dossiers_nouveau

        if not ajoutes and not supprimes:
            continue

        entete = titre_nouveau if titre_ancien == titre_nouveau else f"{titre_ancien!r} -> {titre_nouveau!r}"
        lignes.append(f"\n📁 {entete} :")
        for titre in sorted(ajoutes):
            lignes.append(f"  + {titre!r}")
        for titre in sorted(supprimes):
            lignes.append(f"  - {titre!r}")

    if not lignes:
        return "✅ Aucun changement de structure (groupes/dossiers identiques)."

    return "\n".join(lignes)


def charger_depuis_git(chemin: Path, ref: str) -> list[dict[str, Any]]:
    resultat = subprocess.run(
        ["git", "show", f"{ref}:{chemin.as_posix()}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(resultat.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare deux versions du JSON de collections Nuvio (groupes/dossiers ajoutés ou supprimés)."
    )
    parser.add_argument(
        "--collections",
        default="Templates/Nuvio-Collections-Dwade58200.json",
        help="Fichier actuel, utilisé comme 'nouveau' sauf si --nouveau est précisé",
    )
    parser.add_argument(
        "--ref",
        default="HEAD",
        help="Référence Git pour la version 'ancienne' (défaut: HEAD), ignoré si --ancien est précisé",
    )
    parser.add_argument("--ancien", default=None, help="Fichier JSON explicite pour la version ancienne (sans Git)")
    parser.add_argument("--nouveau", default=None, help="Fichier JSON explicite pour la version nouvelle (sans Git)")
    args = parser.parse_args()

    chemin_nouveau = Path(args.nouveau) if args.nouveau else Path(args.collections)
    with chemin_nouveau.open(encoding="utf-8") as f:
        nouveau = json.load(f)

    if args.ancien:
        with Path(args.ancien).open(encoding="utf-8") as f:
            ancien = json.load(f)
    else:
        try:
            ancien = charger_depuis_git(Path(args.collections), args.ref)
        except subprocess.CalledProcessError as exc:
            print(
                f"Erreur : impossible de lire {args.collections!r} depuis Git à la référence {args.ref!r}.",
                file=sys.stderr,
            )
            print(f"  ({exc.stderr.strip() if exc.stderr else exc})", file=sys.stderr)
            print("Utilise --ancien fichier.json pour comparer deux fichiers explicites sans Git.", file=sys.stderr)
            return 1

    print(comparer(ancien, nouveau))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
