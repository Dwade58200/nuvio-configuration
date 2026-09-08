#!/usr/bin/env python3
"""
definir_image_manuelle.py
===========================

Petit outil pour ajouter/retirer une entrée dans
`Templates/images-manuelles.json` (voir BACKDROPS_SETUP.md, section
« Images manuelles ») et, par défaut, générer immédiatement le fichier
backdrop correspondant -- sans attendre un run complet de
generer_backdrops.py.

La "protection anti-écrasement" est déjà native au mécanisme : tant que
l'entrée reste dans images-manuelles.json, generer_backdrops.py la
consulte en PRIORITÉ ABSOLUE (avant toute résolution TMDB/Fanart/MDBList)
à chaque run, y compris les suivants -- ce script n'a donc qu'à écrire
cette entrée une fois, elle survit à tous les runs futurs sans manifeste
séparé.

Usage :
    # Enregistrer une image pour le dossier "Netflix" et la générer tout de suite
    python3 scripts/definir_image_manuelle.py "Netflix" https://exemple.com/image.jpg

    # Avec un fichier local
    python3 scripts/definir_image_manuelle.py "Noël" images/noel.jpg

    # Juste enregistrer l'entrée, sans générer maintenant (prise en compte
    # au prochain run complet de generer_backdrops.py)
    python3 scripts/definir_image_manuelle.py "Netflix" https://exemple.com/image.jpg --sans-generer

    # Retirer une surcharge manuelle existante (retour au comportement normal)
    python3 scripts/definir_image_manuelle.py "Netflix" --retirer
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests  # noqa: E402
from generer_backdrops import (  # noqa: E402
    GROUPE_SLUGS,
    NOM_DOSSIER_BACKDROPS,
    charger_collections,
    charger_images_manuelles,
    nom_fichier_backdrop,
    normaliser,
    slugifier,
    telecharger_et_traiter,
    traiter_image_locale,
)


def sauver_images_manuelles(chemin: Path, donnees: dict[str, str]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def trouver_groupe_du_dossier(collections: list[dict[str, Any]], dossier_titre: str) -> str | None:
    """Cherche le groupe auquel appartient un titre de dossier donné, pour
    déterminer le bon chemin de sortie. Retourne None si introuvable -- la
    surcharge est quand même enregistrée dans le JSON, elle sera prise en
    compte dès que ce dossier existera (ou au prochain run complet)."""
    for groupe in collections:
        for dossier in groupe.get("folders", []):
            if dossier.get("title") == dossier_titre:
                return str(groupe.get("title", ""))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ajoute/retire une surcharge d'image manuelle pour un dossier Nuvio."
    )
    parser.add_argument("dossier", help="Titre EXACT du dossier tel qu'il apparaît dans le JSON Nuvio")
    parser.add_argument("image", nargs="?", help="URL http(s) ou chemin de fichier local (absent avec --retirer)")
    parser.add_argument("--images-manuelles", default="Templates/images-manuelles.json")
    parser.add_argument("--collections", default="Templates/Nuvio-Collections-Dwade58200.json")
    parser.add_argument("--sortie", default="Collections", help="Répertoire racine de sortie (défaut: Collections)")
    parser.add_argument("--profil", default="standard", choices=["standard", "haute", "compresse"])
    parser.add_argument(
        "--sans-generer", action="store_true",
        help="N'enregistrer que l'entrée JSON, sans générer le fichier tout de suite",
    )
    parser.add_argument("--retirer", action="store_true", help="Retirer la surcharge existante pour ce dossier")
    args = parser.parse_args()

    chemin_images_manuelles = Path(args.images_manuelles)
    donnees = charger_images_manuelles(chemin_images_manuelles)

    if args.retirer:
        if args.dossier not in donnees:
            print(f"Aucune surcharge manuelle trouvée pour {args.dossier!r} -- rien à faire.")
            return 0
        del donnees[args.dossier]
        sauver_images_manuelles(chemin_images_manuelles, donnees)
        print(f"✅ Surcharge manuelle retirée pour {args.dossier!r}.")
        print("(le fichier backdrop déjà généré reste sur disque -- relance generer_backdrops.py pour le régénérer via TMDB si besoin)")
        return 0

    if not args.image:
        parser.error("l'argument 'image' est requis (sauf avec --retirer)")

    donnees[args.dossier] = args.image
    sauver_images_manuelles(chemin_images_manuelles, donnees)
    print(f"✅ Surcharge enregistrée : {args.dossier!r} -> {args.image!r} (dans {chemin_images_manuelles})")

    if args.sans_generer:
        print("(génération différée au prochain run de generer_backdrops.py)")
        return 0

    collections = charger_collections(Path(args.collections))
    groupe_titre = trouver_groupe_du_dossier(collections, args.dossier)
    if groupe_titre is None:
        print(
            f"⚠️  Dossier {args.dossier!r} introuvable dans {args.collections} -- "
            "surcharge enregistrée quand même, elle sera prise en compte dès que "
            "ce dossier existera dans le JSON (ou au prochain run complet).",
            file=sys.stderr,
        )
        return 0

    slug_groupe = GROUPE_SLUGS.get(normaliser(groupe_titre), slugifier(groupe_titre))
    chemin_relatif = Path(slug_groupe) / NOM_DOSSIER_BACKDROPS / f"{nom_fichier_backdrop(args.dossier)}.jpg"
    chemin_sortie = Path(args.sortie) / chemin_relatif

    try:
        if args.image.startswith("http://") or args.image.startswith("https://"):
            telecharger_et_traiter(args.image, chemin_sortie, requests.Session(), args.profil)
        else:
            traiter_image_locale(Path(args.image), chemin_sortie, args.profil)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Échec de la génération immédiate : {exc}", file=sys.stderr)
        print("La surcharge reste enregistrée -- elle sera retentée au prochain run complet.", file=sys.stderr)
        return 1

    print(f"✅ Image générée : {chemin_relatif}")
    print("Pense à lancer mettre_a_jour_urls.py pour répercuter le changement dans heroBackdropUrl.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
