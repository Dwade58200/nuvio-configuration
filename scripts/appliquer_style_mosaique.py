#!/usr/bin/env python3
"""
appliquer_style_mosaique.py
=============================

Applique dans `scripts/mosaique.py` les valeurs choisies avec l'outil
visuel `outils/reglage-style-mosaique.html` (bouton « Copier en JSON »).

Usage :
    python3 scripts/appliquer_style_mosaique.py --json valeurs.json
    python3 scripts/appliquer_style_mosaique.py --json-inline '{"tuile_largeur": 340, "inclinaison_deg": 8}'
    python3 scripts/appliquer_style_mosaique.py --json valeurs.json --dry-run

Format JSON attendu (exactement ce que produit le bouton « Copier en
JSON » de l'outil) -- toutes les clés sont optionnelles, seules celles
présentes sont appliquées :
    {
      "tuile_largeur": 372, "tuile_hauteur": 210, "ecart": 9,
      "rayon_coin": 9, "decalage_ligne": 0.5, "inclinaison_deg": 10,
      "intensite_ombre": 1.0, "flou_lueur": 24,
      "accent": "#7f77dd", "lueur_active": true
    }

"accent" et "lueur_active" sont affichés à titre indicatif (couleur
d'accent réelle calculée automatiquement par affiche dans le vrai
pipeline, voir `calculer_couleur_accent` -- ces deux clés ne modifient
aucune constante).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# clé JSON -> (nom de constante Python dans mosaique.py, formatteur de valeur)
CONSTANTES: dict[str, tuple[str, Callable[[Any], str]]] = {
    "tuile_largeur": ("TUILE_LARGEUR", lambda v: str(int(v))),
    "tuile_hauteur": ("TUILE_HAUTEUR", lambda v: str(int(v))),
    "ecart": ("ECART", lambda v: str(int(v))),
    "rayon_coin": ("RAYON_COIN", lambda v: str(int(v))),
    "decalage_ligne": ("DECALAGE_LIGNE", lambda v: str(round(float(v), 2))),
    "inclinaison_deg": ("INCLINAISON_DEG", lambda v: str(int(v))),
    "intensite_ombre": ("INTENSITE_OMBRE", lambda v: str(round(float(v), 2))),
    "flou_lueur": ("RAYON_FLOU_LUEUR_MIN", lambda v: str(int(v))),
}

# Clés reconnues mais qui ne correspondent à aucune constante à modifier
# (informatif seulement -- voir docstring).
CLES_INFORMATIVES = {"accent", "lueur_active"}


def construire_remplacements(valeurs: dict[str, Any]) -> dict[str, str]:
    remplacements = {}
    for cle_json, (nom_constante, formatter) in CONSTANTES.items():
        if cle_json in valeurs and valeurs[cle_json] is not None:
            remplacements[nom_constante] = formatter(valeurs[cle_json])
    return remplacements


def appliquer(contenu: str, remplacements: dict[str, str]) -> tuple[str, list[str], list[str]]:
    """Fonction pure (aucune I/O) : retourne (nouveau_contenu,
    constantes_modifiees, constantes_introuvables)."""
    modifiees: list[str] = []
    introuvables: list[str] = []
    nouveau = contenu
    for nom, valeur in remplacements.items():
        # Capture séparément la valeur et un éventuel commentaire de fin de
        # ligne, pour ne PAS coller la nouvelle valeur contre le "#" (le
        # commentaire, lui, est préservé tel quel).
        motif = re.compile(rf"^({re.escape(nom)}\s*=\s*)[^\n#]+?(\s*)(#.*)?$", re.MULTILINE)
        if not motif.search(nouveau):
            introuvables.append(nom)
            continue
        avant = nouveau

        def _remplacer(m: re.Match[str], valeur: str = valeur) -> str:
            commentaire = m.group(3)
            if commentaire:
                return f"{m.group(1)}{valeur}       {commentaire}"
            return f"{m.group(1)}{valeur}"

        nouveau = motif.sub(_remplacer, nouveau, count=1)
        if nouveau != avant:
            modifiees.append(nom)
    return nouveau, modifiees, introuvables


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Applique dans scripts/mosaique.py les valeurs exportées par outils/reglage-style-mosaique.html"
    )
    parser.add_argument("--json", default=None, help="Fichier JSON exporté par l'outil (bouton 'Copier en JSON')")
    parser.add_argument("--json-inline", default=None, help="JSON directement en argument, alternative à --json")
    parser.add_argument("--mosaique", default="scripts/mosaique.py")
    parser.add_argument("--dry-run", action="store_true", help="Affiche les changements sans écrire le fichier")
    args = parser.parse_args()

    if not args.json and not args.json_inline:
        parser.error("précise --json fichier.json ou --json-inline '{...}'")

    if args.json_inline:
        valeurs = json.loads(args.json_inline)
    else:
        valeurs = json.loads(Path(args.json).read_text(encoding="utf-8"))

    if not isinstance(valeurs, dict):
        print("Erreur : le JSON doit être un objet {clé: valeur}.", file=sys.stderr)
        return 1

    cles_inconnues = set(valeurs) - set(CONSTANTES) - CLES_INFORMATIVES
    for cle in sorted(cles_inconnues):
        print(f"⚠️  Clé {cle!r} non reconnue -- ignorée.", file=sys.stderr)

    remplacements = construire_remplacements(valeurs)
    if not remplacements:
        print("Aucune clé applicable dans le JSON fourni -- rien à changer.")
        return 0

    chemin_mosaique = Path(args.mosaique)
    contenu = chemin_mosaique.read_text(encoding="utf-8")
    nouveau_contenu, modifiees, introuvables = appliquer(contenu, remplacements)

    for nom in introuvables:
        print(
            f"⚠️  Constante {nom!r} introuvable dans {chemin_mosaique} -- ignorée.",
            file=sys.stderr,
        )

    if not modifiees:
        print("Rien à changer (valeurs déjà identiques, ou aucune constante applicable).")
        return 0

    prefixe = "[dry-run] " if args.dry_run else ""
    print(f"{prefixe}Constantes modifiées dans {chemin_mosaique} :")
    for nom in modifiees:
        print(f"  - {nom} = {remplacements[nom]}")

    if args.dry_run:
        print("\n(dry-run : rien n'a été écrit sur disque)")
        return 0

    chemin_mosaique.write_text(nouveau_contenu, encoding="utf-8")
    print(
        f"\n✅ {chemin_mosaique} mis à jour. "
        "Lance `pytest tests/test_mosaique.py tests/test_mosaique_integration.py` "
        "puis un run réel (`generer_backdrops.py --dry-run`) pour confirmer le rendu."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
