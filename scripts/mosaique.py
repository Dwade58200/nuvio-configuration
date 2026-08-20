#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mosaique.py
============

Génère un backdrop "mosaïque" à partir de plusieurs affiches/backdrops
d'un même dossier (plusieurs films/séries), avec un dégradé teinté par une
couleur d'accent extraite automatiquement -- inspiré du rendu de
luckynumb3rs (stremio-perfect-setup), en version simplifiée (grille droite,
pas de tuiles inclinées).

Toute la logique ici est indépendante du réseau et testable avec de
simples objets PIL.Image en mémoire (voir tests/test_mosaique.py).
"""

from __future__ import annotations

import colorsys
import io
from dataclasses import dataclass
from typing import Sequence

from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------------------
# Réglages de grille
# ---------------------------------------------------------------------------

GAP = 6           # espace entre les tuiles, en pixels (à l'échelle 1920x1080)
RAYON_COIN = 10    # arrondi des coins de chaque tuile

# Nombre d'images disponibles -> (colonnes, lignes). Du plus dense au plus
# clairsemé ; en dessous du minimum, on ne fait pas de mosaïque.
PALIERS_GRILLE: list[tuple[int, tuple[int, int]]] = [
    (12, (4, 3)),
    (9, (3, 3)),
    (6, (3, 2)),
]
MINIMUM_TUILES = 6


def choisir_grille(nombre_images: int) -> tuple[int, int] | None:
    """Retourne (colonnes, lignes) selon le nombre d'images dispo, ou None
    si on n'en a pas assez pour une mosaïque cohérente."""
    for seuil, dims in PALIERS_GRILLE:
        if nombre_images >= seuil:
            return dims
    return None


# ---------------------------------------------------------------------------
# Couleur d'accent
# ---------------------------------------------------------------------------

def calculer_couleur_accent(image: Image.Image) -> tuple[int, int, int]:
    """Extrait une couleur d'accent 'vive' à partir d'une image, en
    prenant la couleur moyenne puis en boostant saturation/luminosité pour
    obtenir un ton exploitable en dégradé (jamais trop terne ni trop pâle).
    """
    petite = image.convert("RGB").resize((16, 16), Image.BOX)
    pixels = list(petite.getdata())
    r = sum(p[0] for p in pixels) / len(pixels)
    g = sum(p[1] for p in pixels) / len(pixels)
    b = sum(p[2] for p in pixels) / len(pixels)

    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    s = min(1.0, max(s, 0.55))   # jamais trop désaturé
    v = min(0.85, max(v, 0.45))  # ni trop sombre, ni trop clair
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return (int(r2 * 255), int(g2 * 255), int(b2 * 255))


def couleur_accent_deterministe(texte: str) -> tuple[int, int, int]:
    """Repli : accent dérivé du titre du dossier (déterministe, pas
    aléatoire), utilisé si aucune image n'est disponible pour l'extraction."""
    graine = sum((i + 1) * ord(c) for i, c in enumerate(texte or "backdrop"))
    h = (graine % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.6, 0.85)
    return (int(r * 255), int(g * 255), int(b * 255))


# ---------------------------------------------------------------------------
# Découpe / arrondi des tuiles
# ---------------------------------------------------------------------------

def recadrer_pour_tuile(image: Image.Image, largeur: int, hauteur: int) -> Image.Image:
    """Recadre (crop centré) + redimensionne une image pour remplir
    exactement (largeur, hauteur), comme un CSS `object-fit: cover`."""
    image = image.convert("RGB")
    ratio_cible = largeur / hauteur
    ratio_source = image.width / image.height

    if ratio_source > ratio_cible:
        nouvelle_largeur = int(image.height * ratio_cible)
        offset = (image.width - nouvelle_largeur) // 2
        image = image.crop((offset, 0, offset + nouvelle_largeur, image.height))
    else:
        nouvelle_hauteur = int(image.width / ratio_cible)
        offset = (image.height - nouvelle_hauteur) // 2
        image = image.crop((0, offset, image.width, offset + nouvelle_hauteur))

    return image.resize((largeur, hauteur), Image.LANCZOS)


def arrondir_coins(image: Image.Image, rayon: int) -> Image.Image:
    """Applique un masque de coins arrondis à une image RGB -> RGBA."""
    image = image.convert("RGBA")
    masque = Image.new("L", image.size, 0)
    dessin = ImageDraw.Draw(masque)
    dessin.rounded_rectangle([(0, 0), (image.width - 1, image.height - 1)], radius=rayon, fill=255)
    image.putalpha(masque)
    return image


# ---------------------------------------------------------------------------
# Composition de la grille
# ---------------------------------------------------------------------------

def construire_grille(
    images: Sequence[Image.Image],
    largeur_canvas: int,
    hauteur_canvas: int,
) -> Image.Image:
    """Compose une grille de tuiles recadrées/arrondies sur un canvas RGBA.

    Le nombre d'images utilisées est déterminé par `choisir_grille`;
    les images en trop sont ignorées, celles en trop peu font échouer
    l'appel (vérifier `choisir_grille` avant d'appeler cette fonction).
    """
    grille = choisir_grille(len(images))
    if grille is None:
        raise ValueError(f"Pas assez d'images pour une mosaïque ({len(images)} < {MINIMUM_TUILES}).")
    colonnes, lignes = grille
    n_tuiles = colonnes * lignes

    tuile_largeur = (largeur_canvas - GAP * (colonnes + 1)) // colonnes
    tuile_hauteur = (hauteur_canvas - GAP * (lignes + 1)) // lignes

    canvas = Image.new("RGBA", (largeur_canvas, hauteur_canvas), (12, 12, 14, 255))

    for index in range(n_tuiles):
        image_source = images[index % len(images)]
        tuile = recadrer_pour_tuile(image_source, tuile_largeur, tuile_hauteur)
        tuile = arrondir_coins(tuile, RAYON_COIN)

        col = index % colonnes
        ligne = index // colonnes
        x = GAP + col * (tuile_largeur + GAP)
        y = GAP + ligne * (tuile_hauteur + GAP)
        canvas.alpha_composite(tuile, (x, y))

    return canvas


# ---------------------------------------------------------------------------
# Dégradé teinté par la couleur d'accent
# ---------------------------------------------------------------------------

def appliquer_degrade(canvas: Image.Image, accent: tuple[int, int, int]) -> Image.Image:
    """Applique par-dessus le canvas :
    - un dégradé sombre du bas vers le haut (lisibilité d'un futur titre) ;
    - une teinte diffuse de la couleur d'accent en bas à gauche.
    """
    largeur, hauteur = canvas.size
    overlay = Image.new("RGBA", (largeur, hauteur), (0, 0, 0, 0))

    # Dégradé sombre bas -> haut
    degrade_sombre = Image.new("L", (1, hauteur), color=0)
    for y in range(hauteur):
        proportion = y / max(1, hauteur - 1)  # 0 en haut, 1 en bas
        degrade_sombre.putpixel((0, y), int(210 * (proportion ** 1.6)))
    degrade_sombre = degrade_sombre.resize((largeur, hauteur))
    overlay_sombre = Image.new("RGBA", (largeur, hauteur), (5, 5, 8, 255))
    overlay_sombre.putalpha(degrade_sombre)
    overlay = Image.alpha_composite(overlay, overlay_sombre)

    # Teinte accent diffuse, coin bas-gauche
    teinte = Image.new("RGBA", (largeur, hauteur), (0, 0, 0, 0))
    rayon = int(largeur * 0.55)
    cercle = Image.new("L", (rayon * 2, rayon * 2), 0)
    dessin = ImageDraw.Draw(cercle)
    dessin.ellipse([(0, 0), (rayon * 2, rayon * 2)], fill=140)
    cercle = cercle.filter(ImageFilter.GaussianBlur(rayon // 3))
    bloc_couleur = Image.new("RGBA", cercle.size, (*accent, 255))
    bloc_couleur.putalpha(cercle)
    teinte.alpha_composite(bloc_couleur, (-rayon // 2, hauteur - rayon))
    overlay = Image.alpha_composite(overlay, teinte)

    return Image.alpha_composite(canvas, overlay)


# ---------------------------------------------------------------------------
# Point d'entrée haut niveau
# ---------------------------------------------------------------------------

@dataclass
class ResultatMosaique:
    image: Image.Image
    accent: tuple[int, int, int]
    nb_tuiles: int


def generer_mosaique(
    images_sources: Sequence[Image.Image],
    largeur_canvas: int,
    hauteur_canvas: int,
    titre_repli: str = "",
) -> ResultatMosaique | None:
    """Retourne None si pas assez d'images pour composer une mosaïque
    (l'appelant doit alors retomber sur le mode "un seul backdrop")."""
    grille = choisir_grille(len(images_sources))
    if grille is None:
        return None

    if images_sources:
        accent = calculer_couleur_accent(images_sources[0])
    else:
        accent = couleur_accent_deterministe(titre_repli)

    canvas = construire_grille(images_sources, largeur_canvas, hauteur_canvas)
    canvas = appliquer_degrade(canvas, accent)

    return ResultatMosaique(image=canvas.convert("RGB"), accent=accent, nb_tuiles=grille[0] * grille[1])


def image_depuis_bytes(donnees: bytes) -> Image.Image:
    return Image.open(io.BytesIO(donnees))
