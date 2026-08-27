#!/usr/bin/env python3
"""
valider_collections.py
========================

Valide `Templates/Nuvio-Collections-Dwade58200.json` contre le schéma
`schema/nuvio-collections.schema.json`, pour attraper une erreur de
structure (champ manquant, mauvais type, provider inconnu...) avant
qu'elle ne casse l'import dans Nuvio ou le pipeline de backdrops.

Usage :
    python3 scripts/valider_collections.py
    python3 scripts/valider_collections.py --collections chemin/vers/fichier.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover
    print("Le paquet 'jsonschema' est requis : pip install jsonschema", file=sys.stderr)
    raise


def valider(chemin_collections: Path, chemin_schema: Path) -> list[str]:
    """Retourne la liste des erreurs trouvées (vide si le fichier est valide)."""
    with chemin_schema.open(encoding="utf-8") as f:
        schema = json.load(f)

    with chemin_collections.open(encoding="utf-8") as f:
        collections = json.load(f)

    validateur = jsonschema.Draft7Validator(schema)
    erreurs = sorted(validateur.iter_errors(collections), key=lambda e: list(e.path))

    messages: list[str] = []
    for erreur in erreurs:
        chemin = " -> ".join(str(p) for p in erreur.path) or "(racine)"
        messages.append(f"[{chemin}] {erreur.message}")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Valide le JSON de collections Nuvio contre son schéma.")
    parser.add_argument("--collections", default="Templates/Nuvio-Collections-Dwade58200.json")
    parser.add_argument("--schema", default="schema/nuvio-collections.schema.json")
    args = parser.parse_args()

    erreurs = valider(Path(args.collections), Path(args.schema))

    if erreurs:
        print(f"❌ {len(erreurs)} erreur(s) de structure trouvée(s) dans {args.collections} :\n")
        for message in erreurs:
            print(f"  - {message}")
        return 1

    print(f"✅ {args.collections} est conforme au schéma.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
