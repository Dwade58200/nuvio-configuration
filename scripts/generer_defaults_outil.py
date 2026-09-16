#!/usr/bin/env python3
"""
generer_defaults_outil.py
============================

Garde les valeurs par défaut affichées dans `outils/reglage-style-mosaique.html`
(curseurs, champs numériques, objet JS `defaults`) synchronisées avec les
VRAIES constantes de `scripts/mosaique.py`.

Pourquoi : les deux fichiers étaient jusqu'ici indépendants -- si
`scripts/mosaique.py` change (édition manuelle, ou `appliquer_style_mosaique.py`
lancé depuis une session/machine différente de celle qui a ouvert l'outil
en dernier), les curseurs de l'outil repartent silencieusement d'un
instantané obsolète la prochaine fois qu'on l'ouvre -- aucune erreur,
juste un point de départ trompeur pour le prochain réglage. Ce script
élimine cette dérive : il est lancé automatiquement avant chaque
déploiement GitHub Pages de `outils/` (voir `deployer-outils.yml`), qui se
déclenche aussi sur un changement de `scripts/mosaique.py`.

N'affecte QUE les valeurs par défaut affichées à l'ouverture -- ne change
rien au comportement de l'outil (curseurs, ratio, génération réelle...).

Usage :
    python3 scripts/generer_defaults_outil.py
    python3 scripts/generer_defaults_outil.py --dry-run   # affiche sans écrire
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path

# nom de constante dans mosaique.py -> (id dans l'outil, conversion valeur mosaique.py -> valeur outil)
# DECALAGE_LIGNE (0.5) et INTENSITE_OMBRE (1.0) sont des fractions côté
# script, mais des pourcentages entiers côté outil (curseurs 0-100/0-200) --
# voir appliquer_style_mosaique.py pour la conversion inverse.
CONSTANTES: dict[str, tuple[str, Callable[[float], int]]] = {
    "TUILE_LARGEUR": ("tuileLargeur", lambda v: round(v)),
    "TUILE_HAUTEUR": ("tuileHauteur", lambda v: round(v)),
    "ECART": ("ecart", lambda v: round(v)),
    "RAYON_COIN": ("rayon", lambda v: round(v)),
    "DECALAGE_LIGNE": ("decalage", lambda v: round(v * 100)),
    "INCLINAISON_DEG": ("inclinaison", lambda v: round(v)),
    "INTENSITE_OMBRE": ("ombre", lambda v: round(v * 100)),
    "RAYON_FLOU_LUEUR_MIN": ("flou", lambda v: round(v)),
}


def extraire_constantes(contenu_mosaique: str) -> dict[str, float]:
    """Fonction pure : lit les constantes de style au format
    `NOM = valeur` (un float ou un int) dans le texte de mosaique.py."""
    valeurs: dict[str, float] = {}
    for nom in CONSTANTES:
        motif = re.compile(rf"^{re.escape(nom)}\s*=\s*(-?[0-9.]+)", re.MULTILINE)
        trouve = motif.search(contenu_mosaique)
        if trouve:
            valeurs[nom] = float(trouve.group(1))
    return valeurs


def valeurs_outil_depuis_constantes(constantes: dict[str, float]) -> dict[str, int]:
    """Fonction pure : convertit les constantes mosaique.py (fractions,
    pixels bruts) vers les unités affichées par l'outil (pourcentages
    entiers pour decalage/ombre, entiers directs pour le reste)."""
    return {id_outil: conversion(constantes[nom]) for nom, (id_outil, conversion) in CONSTANTES.items() if nom in constantes}


def mettre_a_jour_html(contenu_html: str, valeurs_outil: dict[str, int]) -> tuple[str, list[str], list[str]]:
    """Fonction pure (aucune I/O) : retourne (nouveau_contenu,
    ids_modifies, ids_introuvables). Met à jour à la fois les attributs
    `value="..."` des curseurs/champs numériques (`id="X"` et `id="XNum"`)
    et l'objet JS `var defaults = {X:..., ...}`."""
    modifies: list[str] = []
    introuvables: list[str] = []
    nouveau = contenu_html

    # Attributs HTML value="..." -- curseur ET champ numérique jumeau.
    for id_html, valeur in valeurs_outil.items():
        for cible in (id_html, f"{id_html}Num"):
            motif = re.compile(rf'(id="{re.escape(cible)}"[^>\n]*?value=")-?\d+(")')
            if not motif.search(nouveau):
                introuvables.append(cible)
                continue
            avant = nouveau

            def _remplacer_attribut(m: re.Match[str], v: int = valeur) -> str:
                return f"{m.group(1)}{v}{m.group(2)}"

            nouveau = motif.sub(_remplacer_attribut, nouveau, count=1)
            if nouveau != avant:
                modifies.append(cible)

    # Objet JS `var defaults = {tuileLargeur:372, ...}`.
    for cle, valeur in valeurs_outil.items():
        motif_js = re.compile(rf"(\b{re.escape(cle)}:)-?\d+")
        if not motif_js.search(nouveau):
            introuvables.append(f"defaults.{cle}")
            continue
        avant = nouveau

        def _remplacer_js(m: re.Match[str], v: int = valeur) -> str:
            return f"{m.group(1)}{v}"

        nouveau = motif_js.sub(_remplacer_js, nouveau, count=1)
        if nouveau != avant:
            modifies.append(f"defaults.{cle}")

    return nouveau, modifies, introuvables


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronise les valeurs par défaut de l'outil de style avec scripts/mosaique.py"
    )
    parser.add_argument("--mosaique", default="scripts/mosaique.py")
    parser.add_argument("--outil", default="outils/reglage-style-mosaique.html")
    parser.add_argument("--dry-run", action="store_true", help="Affiche les changements sans écrire le fichier")
    args = parser.parse_args()

    chemin_mosaique = Path(args.mosaique)
    chemin_outil = Path(args.outil)

    constantes = extraire_constantes(chemin_mosaique.read_text(encoding="utf-8"))
    manquantes = set(CONSTANTES) - set(constantes)
    for nom in sorted(manquantes):
        print(f"⚠️  Constante {nom!r} introuvable dans {chemin_mosaique} -- ignorée.", file=sys.stderr)

    valeurs_outil = valeurs_outil_depuis_constantes(constantes)
    contenu_outil = chemin_outil.read_text(encoding="utf-8")
    nouveau_contenu, modifies, introuvables = mettre_a_jour_html(contenu_outil, valeurs_outil)

    for cible in introuvables:
        print(f"⚠️  {cible!r} introuvable dans {chemin_outil} -- ignoré.", file=sys.stderr)

    if not modifies:
        print("Rien à changer (outil déjà synchronisé avec mosaique.py).")
        return 0

    prefixe = "[dry-run] " if args.dry_run else ""
    print(f"{prefixe}Valeurs par défaut synchronisées dans {chemin_outil} :")
    for cible in sorted(set(modifies)):
        print(f"  - {cible}")

    if args.dry_run:
        print("\n(dry-run : rien n'a été écrit sur disque)")
        return 0

    chemin_outil.write_text(nouveau_contenu, encoding="utf-8")
    print(f"\n✅ {chemin_outil} mis à jour.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
