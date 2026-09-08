#!/usr/bin/env python3
"""
synchroniser_config.py
========================

Maintient à jour `Templates/groupes-config.json` -- un fichier de données
qui ÉTEND `scripts/config_collections.py` (CRITERES_GROUPES/GROUPE_SLUGS)
SANS toucher au code Python. Pour chaque groupe présent dans le JSON de
collections mais absent des deux sources (config_collections.py ET ce
fichier), une entrée par défaut est ajoutée automatiquement (actif=true,
sans filtre, slug dérivé du titre). Pour chaque groupe présent dans ce
fichier mais disparu du JSON de collections, un avertissement est affiché
(rien n'est supprimé automatiquement, sauf --purger-supprimes explicite).

C'est un COMPLÉMENT optionnel à l'auto-inclusion déjà native du pipeline
(voir BACKDROPS_SETUP.md, section « Ajout/suppression d'une collection »)
: sans ce fichier ni ce script, tout continue de fonctionner exactement
pareil -- un groupe inconnu est actif par défaut, silencieusement. Ce
script sert à PERSISTER cette information dans un fichier versionnable et
modifiable, plutôt que de la laisser purement implicite dans le
comportement par défaut de `dossier_actif`.

Un groupe déjà codé en dur dans `CRITERES_GROUPES` (scripts/config_collections.py)
reste sous le contrôle exclusif du code Python : ce script ne le touche
jamais, même s'il disparaît du JSON de collections (voir plutôt
`--signaler-orphelins` de generer_backdrops.py pour les dossiers
individuels, ou une vérification manuelle du groupe entier).

Usage :
    python3 scripts/synchroniser_config.py
    python3 scripts/synchroniser_config.py --purger-supprimes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_collections import CRITERES_GROUPES  # noqa: E402
from generer_backdrops import charger_collections, normaliser, slugifier  # noqa: E402


def charger_config_existante(chemin: Path) -> dict[str, dict[str, Any]]:
    if not chemin.exists():
        return {}
    with chemin.open(encoding="utf-8") as f:
        donnees = json.load(f)
    if not isinstance(donnees, dict):
        raise ValueError(f"{chemin} doit contenir un objet JSON {{titre_groupe: {{...}}}}")
    return donnees


def sauver_config(chemin: Path, donnees: dict[str, dict[str, Any]]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def synchroniser(
    collections: list[dict[str, Any]], config_existante: dict[str, dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    """Fonction pure (aucune I/O) : retourne (nouvelle_config,
    titres_groupes_ajoutes, cles_groupes_disparus)."""
    nouvelle = dict(config_existante)
    groupes_ajoutes: list[str] = []

    cles_vues = set()
    for groupe in collections:
        titre = groupe.get("title", "")
        cle = normaliser(titre)
        cles_vues.add(cle)
        deja_connu = cle in CRITERES_GROUPES or cle in config_existante
        if not deja_connu:
            nouvelle[cle] = {
                "titre_vu": titre,
                "actif": True,
                "slug": slugifier(titre),
                "inclure": None,
                "exclure": None,
            }
            groupes_ajoutes.append(titre)

    # Un groupe codé en dur dans CRITERES_GROUPES reste toujours sous
    # contrôle du code Python -- jamais signalé "disparu" par ce script.
    groupes_disparus = [cle for cle in config_existante if cle not in cles_vues and cle not in CRITERES_GROUPES]

    return nouvelle, groupes_ajoutes, groupes_disparus


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronise Templates/groupes-config.json avec le JSON de collections Nuvio actuel."
    )
    parser.add_argument("--collections", default="Templates/Nuvio-Collections-Dwade58200.json")
    parser.add_argument("--config-groupes", default="Templates/groupes-config.json")
    parser.add_argument(
        "--purger-supprimes",
        action="store_true",
        help="Retire du fichier les groupes disparus du JSON de collections (par défaut : rapport seul, rien n'est supprimé)",
    )
    args = parser.parse_args()

    collections = charger_collections(Path(args.collections))
    chemin_config = Path(args.config_groupes)
    config_existante = charger_config_existante(chemin_config)

    nouvelle_config, ajoutes, disparus = synchroniser(collections, config_existante)

    if args.purger_supprimes:
        for cle in disparus:
            nouvelle_config.pop(cle, None)

    if nouvelle_config != config_existante:
        sauver_config(chemin_config, nouvelle_config)

    if ajoutes:
        print(f"🆕 {len(ajoutes)} groupe(s) ajouté(s) à {chemin_config} avec les réglages par défaut :")
        for titre in ajoutes:
            print(f"  + {titre!r}")
    if disparus:
        verbe = "retiré(s) de" if args.purger_supprimes else "toujours présent(s) dans"
        print(f"🗑️  {len(disparus)} groupe(s) disparu(s) du JSON de collections mais {verbe} {chemin_config} :")
        for cle in disparus:
            suffixe = "" if args.purger_supprimes else " (relance avec --purger-supprimes pour nettoyer)"
            print(f"  - {cle!r}{suffixe}")
    if not ajoutes and not disparus:
        print("✅ Rien à synchroniser -- config déjà à jour.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
