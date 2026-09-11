#!/usr/bin/env python3
"""
mosaique.py
============

Génère un backdrop "mosaïque" à partir de plusieurs AFFICHES (posters)
d'un même dossier, disposées en grille inclinée façon cascade -- inspiré
du rendu de luckynumb3rs (stremio-perfect-setup) : les titres restent
lisibles car ils sont déjà incrustés dans les affiches TMDB elles-mêmes
(le script n'écrit aucun texte).

Toute la logique ici est indépendante du réseau et testable avec de
simples objets PIL.Image en mémoire (voir tests/test_mosaique.py).
"""

from __future__ import annotations

import colorsys
import io
import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# Réglages de la grille inclinée
# ---------------------------------------------------------------------------

TUILE_LARGEUR = 372       # taille de référence d'une tuile, avant mise à l'échelle canvas (paysage, ~16:9, comme le rendu luckynumb3rs)
TUILE_HAUTEUR = 210
ECART = 9                 # espace entre tuiles
RAYON_COIN = 9              # arrondi des coins de chaque tuile
DECALAGE_LIGNE = 0.5      # décalage horizontal d'une ligne à l'autre (cascade)
INCLINAISON_DEG = 10       # angle de rotation de la grille entière
MARGE_CASES = 3           # cases en trop (au-delà du canvas) pour couvrir les coins après rotation

INTENSITE_OMBRE = 1.0        # multiplie l'alpha des 3 dégradés de vignette (gauche/bas/coin) -- 1.0 = valeurs par défaut ci-dessous, inchangées
RAYON_FLOU_LUEUR_MIN = 24    # flou minimum (px, échelle canvas) de la lueur d'accent diffuse

MINIMUM_IMAGES_DISTINCTES = 3   # en dessous, pas assez de variété -> repli sur mode single-backdrop
TUILES_CIBLE = 12               # nombre de tuiles visées (on répète les images si besoin, comme luckynumb3rs)


def assez_d_images(nombre_images: int) -> bool:
    return nombre_images >= MINIMUM_IMAGES_DISTINCTES


def completer_jusqua(images: Sequence[Image.Image], minimum: int = TUILES_CIBLE) -> list[Image.Image]:
    """Répète les images disponibles (cycle) jusqu'à atteindre `minimum`,
    comme le fait luckynumb3rs (`ensure_minimum_tiles`) -- évite une
    mosaïque trop pauvre quand peu de titres sont disponibles."""
    if not images:
        return []
    resultat = list(images)
    cycle = itertools.cycle(images)
    while len(resultat) < minimum:
        resultat.append(next(cycle))
    return resultat


# Compatibilité : gardé pour ne pas casser d'éventuels appels existants qui
# testent juste "a-t-on assez d'images ?" (retourne un couple factice).
def choisir_grille(nombre_images: int) -> tuple[int, int] | None:
    return (1, 1) if assez_d_images(nombre_images) else None


# ---------------------------------------------------------------------------
# Couleur d'accent
# ---------------------------------------------------------------------------

def calculer_couleur_accent(image: Image.Image) -> tuple[int, int, int]:
    """Extrait une couleur d'accent 'vive' à partir d'une image, en
    prenant la couleur moyenne puis en boostant saturation/luminosité pour
    obtenir un ton exploitable en dégradé (jamais trop terne ni trop pâle).
    """
    petite = image.convert("RGB").resize((16, 16), Image.Resampling.BOX)
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

def aplatir_transparence(image: Image.Image, couleur_fond: tuple[int, int, int] = (14, 14, 16)) -> Image.Image:
    """Compose proprement une image avec canal alpha (ex: artworks
    'clearart' de Fanart, souvent détourés sur fond transparent) sur un
    fond uni sombre, plutôt que de simplement jeter le canal alpha (ce qui
    peut révéler des pixels noirs/blancs parasites sous la découpe).
    Filet de sécurité si aucun vrai fond n'a pu être composé en amont
    (voir `composer_sur_fond` pour le cas nominal avec un fond réel)."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        image = image.convert("RGBA")
        fond = Image.new("RGB", image.size, couleur_fond)
        fond.paste(image, mask=image.split()[-1])
        return fond
    return image.convert("RGB")


def composer_sur_fond(image_transparente: Image.Image, image_fond: Image.Image, proportion_max: float = 0.8) -> Image.Image:
    """Compose un artwork détouré (ex: 'clearart' Fanart) sur une VRAIE
    image de fond, plutôt que sur une couleur plate -- l'artwork est
    redimensionné pour tenir dans `proportion_max` du fond (en conservant
    son ratio) et centré."""
    image_fond = image_fond.convert("RGBA")
    image_transparente = image_transparente.convert("RGBA")

    ratio = min(
        (image_fond.width * proportion_max) / max(1, image_transparente.width),
        (image_fond.height * proportion_max) / max(1, image_transparente.height),
        1.0,  # ne jamais agrandir l'artwork au-delà de sa taille d'origine
    )
    nouvelle_taille = (max(1, int(image_transparente.width * ratio)), max(1, int(image_transparente.height * ratio)))
    artwork_redim = image_transparente.resize(nouvelle_taille, Image.Resampling.LANCZOS)

    x = (image_fond.width - artwork_redim.width) // 2
    y = (image_fond.height - artwork_redim.height) // 2
    resultat = image_fond.copy()
    resultat.alpha_composite(artwork_redim, (x, y))
    return resultat.convert("RGB")


def recadrer_pour_tuile(image: Image.Image, largeur: int, hauteur: int) -> Image.Image:
    """Recadre (crop centré) + redimensionne une image pour remplir
    exactement (largeur, hauteur), comme un CSS `object-fit: cover`."""
    image = aplatir_transparence(image)
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

    return image.resize((largeur, hauteur), Image.Resampling.LANCZOS)


def arrondir_coins(image: Image.Image, rayon: int) -> Image.Image:
    """Applique un masque de coins arrondis à une image RGB -> RGBA."""
    image = image.convert("RGBA")
    masque = Image.new("L", image.size, 0)
    dessin = ImageDraw.Draw(masque)
    dessin.rounded_rectangle([(0, 0), (image.width - 1, image.height - 1)], radius=rayon, fill=255)
    image.putalpha(masque)
    return image


def preparer_tuile(image: Image.Image, largeur: int, hauteur: int) -> Image.Image:
    return arrondir_coins(recadrer_pour_tuile(image, largeur, hauteur), max(4, int(RAYON_COIN * largeur / TUILE_LARGEUR)))


# ---------------------------------------------------------------------------
# Grille inclinée en cascade
# ---------------------------------------------------------------------------

def dimensions_grille(largeur_canvas: int, hauteur_canvas: int, echelle: float = 1.0) -> tuple[int, int]:
    """Retourne (colonnes, lignes) de la grille pour un canvas donné --
    factorisé pour pouvoir calculer le nombre de cases à remplir AVANT de
    télécharger les images (et ainsi récupérer assez d'images distinctes
    pour éviter les répétitions rapprochées)."""
    tuile_largeur = max(1, int(TUILE_LARGEUR * echelle))
    tuile_hauteur = max(1, int(TUILE_HAUTEUR * echelle))
    ecart = max(1, int(ECART * echelle))
    colonnes = math.ceil(largeur_canvas / (tuile_largeur + ecart)) + MARGE_CASES
    lignes = math.ceil(hauteur_canvas / (tuile_hauteur + ecart)) + MARGE_CASES
    return colonnes, lignes


def nombre_cellules_grille(largeur_canvas: int, hauteur_canvas: int, echelle: float = 1.0) -> int:
    colonnes, lignes = dimensions_grille(largeur_canvas, hauteur_canvas, echelle)
    return colonnes * lignes


def construire_grille_inclinee(
    images: Sequence[Image.Image],
    largeur_canvas: int,
    hauteur_canvas: int,
    echelle: float = 1.0,
) -> Image.Image:
    """Construit une grille de tuiles décalées ligne par ligne (cascade),
    puis la fait pivoter légèrement avant de la centrer sur le canvas
    final -- même principe que le rendu de luckynumb3rs, en implémentation
    propre.
    """
    if not images:
        raise ValueError("Aucune image fournie pour construire la grille.")

    tuile_largeur = max(1, int(TUILE_LARGEUR * echelle))
    tuile_hauteur = max(1, int(TUILE_HAUTEUR * echelle))
    ecart = max(1, int(ECART * echelle))

    colonnes, lignes = dimensions_grille(largeur_canvas, hauteur_canvas, echelle)
    decalage_px = int(DECALAGE_LIGNE * (tuile_largeur + ecart))

    grille_largeur = colonnes * (tuile_largeur + ecart) + lignes * decalage_px
    grille_hauteur = lignes * (tuile_hauteur + ecart)
    grille = Image.new("RGBA", (grille_largeur, grille_hauteur), (0, 0, 0, 0))

    cycle_images = itertools.cycle(images)
    for ligne in range(lignes):
        for colonne in range(colonnes):
            source = next(cycle_images)
            tuile = preparer_tuile(source, tuile_largeur, tuile_hauteur)
            x = ligne * decalage_px + colonne * (tuile_largeur + ecart)
            y = ligne * (tuile_hauteur + ecart)
            grille.alpha_composite(tuile, (x, y))

    pivotee = grille.rotate(INCLINAISON_DEG, expand=True, resample=Image.Resampling.BICUBIC)

    canvas = Image.new("RGBA", (largeur_canvas, hauteur_canvas), (10, 10, 12, 255))
    x_centre = (largeur_canvas - pivotee.width) // 2
    y_centre = (hauteur_canvas - pivotee.height) // 2
    canvas.alpha_composite(pivotee, (x_centre, y_centre))

    return canvas


# ---------------------------------------------------------------------------
# Dégradé multi-couches teinté par la couleur d'accent
# ---------------------------------------------------------------------------

def _degrade_lineaire(
    largeur: int, hauteur: int, direction: str, couleur: tuple[int, int, int] = (6, 6, 8), intensite: float = 1.0
) -> Image.Image:
    """Dégradé calculé à basse résolution puis mis à l'échelle (rapide),
    même technique que le script de référence. `intensite` multiplie
    l'alpha calculé (1.0 = comportement historique inchangé) -- utilisé
    pour le réglage INTENSITE_OMBRE, jamais pour la lueur d'accent."""
    petite_largeur = max(1, largeur // 4)
    petite_hauteur = max(1, hauteur // 4)
    image = Image.new("RGBA", (petite_largeur, petite_hauteur), (0, 0, 0, 0))
    pixels = image.load()
    assert pixels is not None  # toujours vrai pour une image fraîchement créée avec Image.new()

    if direction == "gauche":
        for x in range(petite_largeur):
            proportion = max(0.0, 1.0 - x / (petite_largeur * 0.5))
            alpha = min(255, int(190 * proportion**1.6 * intensite))
            if alpha:
                for y in range(petite_hauteur):
                    pixels[x, y] = (*couleur, alpha)

    elif direction == "bas":
        for y in range(petite_hauteur):
            proportion = max(0.0, (y - petite_hauteur * 0.45) / (petite_hauteur * 0.55))
            alpha = min(255, int(200 * proportion**1.4 * intensite))
            if alpha:
                for x in range(petite_largeur):
                    pixels[x, y] = (*couleur, alpha)

    elif direction == "coin_bas_gauche":
        diagonale_max = math.hypot(petite_largeur, petite_hauteur)
        for x in range(petite_largeur):
            for y in range(petite_hauteur):
                distance = math.hypot(x, petite_hauteur - y)
                base = max(0.0, 1.0 - (distance / diagonale_max) / 0.6)
                alpha = int(220 * base**2.0 * intensite)
                if alpha:
                    pixels[x, y] = (*couleur, min(255, alpha))

    return image.resize((largeur, hauteur), Image.Resampling.BILINEAR)


def appliquer_degrade(canvas: Image.Image, accent: tuple[int, int, int]) -> Image.Image:
    """Superpose plusieurs dégradés pour un rendu 'vignette' proche de
    luckynumb3rs : assombrissement bas + gauche + coin bas-gauche, et une
    lueur diffuse de la couleur d'accent en haut-droite."""
    largeur, hauteur = canvas.size

    degrade_gauche = _degrade_lineaire(largeur, hauteur, "gauche", intensite=INTENSITE_OMBRE)
    degrade_bas = _degrade_lineaire(largeur, hauteur, "bas", intensite=INTENSITE_OMBRE)
    degrade_coin = _degrade_lineaire(largeur, hauteur, "coin_bas_gauche", intensite=INTENSITE_OMBRE)

    resultat = Image.alpha_composite(canvas, degrade_coin)
    resultat = Image.alpha_composite(resultat, degrade_gauche)
    resultat = Image.alpha_composite(resultat, degrade_bas)

    # Lueur d'accent diffuse, coin haut-droite -- intensité NON affectée par
    # INTENSITE_OMBRE (réglage séparé, voir outils/reglage-style-mosaique.html)
    petite_lueur = _degrade_lineaire(largeur // 4, hauteur // 4, "coin_bas_gauche", couleur=accent)
    lueur = petite_lueur.rotate(180).resize((largeur, hauteur), Image.Resampling.BILINEAR)
    lueur = lueur.filter(ImageFilter.GaussianBlur(radius=max(RAYON_FLOU_LUEUR_MIN, largeur // 70)))
    resultat = Image.alpha_composite(resultat, lueur)

    return resultat


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
    (l'appelant doit alors retomber sur le mode "un seul backdrop").
    Complète (cycle) jusqu'à couvrir TOUTES les cases de la grille -- si
    `images_sources` contient déjà assez d'images distinctes pour ça,
    aucune répétition n'a lieu du tout."""
    if not assez_d_images(len(images_sources)):
        return None

    accent = calculer_couleur_accent(images_sources[0]) if images_sources else couleur_accent_deterministe(titre_repli)

    echelle = largeur_canvas / 1920  # les constantes de tuile sont calibrées pour un canvas 1920px
    cellules = nombre_cellules_grille(largeur_canvas, hauteur_canvas, echelle)
    images_completees = completer_jusqua(images_sources, cellules)

    canvas = construire_grille_inclinee(images_completees, largeur_canvas, hauteur_canvas, echelle=echelle)
    canvas = appliquer_degrade(canvas, accent)

    return ResultatMosaique(image=canvas.convert("RGB"), accent=accent, nb_tuiles=len(images_sources))


def image_depuis_bytes(donnees: bytes) -> Image.Image:
    return Image.open(io.BytesIO(donnees))


# ---------------------------------------------------------------------------
# Incrustation de titre sur un backdrop "nu" (sans texte)
# ---------------------------------------------------------------------------
# Utilisé pour les catalogues "champTitre" (ex: FanKai, voir
# generer_backdrops._resoudre_tuile_titre_sur_backdrop_nu) : le backdrop
# vient de TMDB sans aucun texte incrusté, et le SEUL titre disponible est
# celui du catalogue lui-même -- on l'écrit donc nous-mêmes, ici.

_POLICE_TAILLE_MIN = 16
_POLICE_TAILLE_RATIO = 0.11  # proportion de la hauteur du canvas
_MARGE_RATIO = 0.045


_UnePolice = ImageFont.ImageFont | ImageFont.FreeTypeFont


def _charger_police(taille: int, chemin_police: str | None) -> _UnePolice:
    """Charge la police TTF fournie (ex: la police bundlée du dépôt) à la
    taille demandée ; repli sur la police par défaut de Pillow (mise à
    l'échelle, disponible depuis Pillow 10.1) si le fichier est introuvable
    ou invalide -- jamais d'exception, un titre moche vaut mieux qu'un
    backdrop en erreur."""
    if chemin_police:
        try:
            return ImageFont.truetype(str(chemin_police), taille)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=taille)
    except TypeError:  # Pillow < 10.1 : load_default() ne prend pas `size`
        return ImageFont.load_default()


def _decouper_en_lignes(dessin: ImageDraw.ImageDraw, texte: str, police: _UnePolice, largeur_max: float) -> list[str]:
    """Découpe `texte` en lignes tenant chacune dans `largeur_max` px,
    en coupant sur les espaces (jamais au milieu d'un mot)."""
    mots = texte.split()
    if not mots:
        return [texte] if texte else []
    lignes: list[str] = []
    ligne_courante = mots[0]
    for mot in mots[1:]:
        essai = f"{ligne_courante} {mot}"
        if dessin.textlength(essai, font=police) <= largeur_max:
            ligne_courante = essai
        else:
            lignes.append(ligne_courante)
            ligne_courante = mot
    lignes.append(ligne_courante)
    return lignes


def incruster_titre(
    image: Image.Image,
    titre: str,
    largeur: int,
    hauteur: int,
    chemin_police: str | None = None,
) -> Image.Image:
    """Recadre `image` (cover) sur (largeur, hauteur), puis écrit `titre`
    en bas à gauche par-dessus un léger dégradé sombre (pour la
    lisibilité) -- pensé pour un backdrop TMDB "nu" (sans aucun texte
    d'origine). La taille de police est réduite automatiquement si le
    titre ne tient pas en 2 lignes. Ne lève jamais d'exception à cause du
    texte : un backdrop sans titre lisible reste préférable à un échec
    total (l'appelant a de toute façon un repli, voir
    generer_backdrops._resoudre_tuile_titre_sur_backdrop_nu)."""
    fond = recadrer_pour_tuile(image, largeur, hauteur).convert("RGBA")
    if not (titre or "").strip():
        return fond.convert("RGB")

    marge = max(12, int(largeur * _MARGE_RATIO))
    largeur_max_texte = max(1, largeur - marge * 2)
    taille_police = max(_POLICE_TAILLE_MIN, int(hauteur * _POLICE_TAILLE_RATIO))

    dessin_mesure = ImageDraw.Draw(fond)
    police = _charger_police(taille_police, chemin_police)
    lignes = _decouper_en_lignes(dessin_mesure, titre.strip(), police, largeur_max_texte)
    while len(lignes) > 2 and taille_police > _POLICE_TAILLE_MIN:
        taille_police -= 2
        police = _charger_police(taille_police, chemin_police)
        lignes = _decouper_en_lignes(dessin_mesure, titre.strip(), police, largeur_max_texte)

    interligne = int(taille_police * 1.2)
    hauteur_bloc_texte = interligne * len(lignes)

    # Dégradé sombre en bas (réutilise le dégradé "bas" du style mosaïque,
    # en plus prononcé) pour garantir la lisibilité du texte quel que soit
    # le contenu du backdrop dessous.
    scrim = _degrade_lineaire(largeur, hauteur, "bas", couleur=(4, 4, 6), intensite=1.4)
    resultat = Image.alpha_composite(fond, scrim)

    dessin = ImageDraw.Draw(resultat)
    y = max(marge, hauteur - marge - hauteur_bloc_texte)
    for ligne in lignes:
        # ombre portée légère puis texte blanc, pour rester lisible même
        # sur un fond clair localement.
        dessin.text((marge + 2, y + 2), ligne, font=police, fill=(0, 0, 0, 170))
        dessin.text((marge, y), ligne, font=police, fill=(255, 255, 255, 255))
        y += interligne

    return resultat.convert("RGB")
