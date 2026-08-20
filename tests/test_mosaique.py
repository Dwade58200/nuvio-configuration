# -*- coding: utf-8 -*-
"""Tests pour scripts/mosaique.py -- entièrement hors-ligne."""

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mosaique import (  # noqa: E402
    MINIMUM_TUILES,
    appliquer_degrade,
    calculer_couleur_accent,
    choisir_grille,
    construire_grille,
    couleur_accent_deterministe,
    generer_mosaique,
    recadrer_pour_tuile,
)


def _image_couleur(couleur, taille=(300, 169)):
    return Image.new("RGB", taille, color=couleur)


# ---------------------------------------------------------------------------
# Choix de la grille
# ---------------------------------------------------------------------------

def test_choisir_grille_paliers():
    assert choisir_grille(12) == (4, 3)
    assert choisir_grille(15) == (4, 3)  # plus d'images que nécessaire -> palier max
    assert choisir_grille(9) == (3, 3)
    assert choisir_grille(6) == (3, 2)
    assert choisir_grille(5) is None  # pas assez


def test_minimum_tuiles_coherent_avec_paliers():
    assert choisir_grille(MINIMUM_TUILES) is not None
    assert choisir_grille(MINIMUM_TUILES - 1) is None


# ---------------------------------------------------------------------------
# Recadrage
# ---------------------------------------------------------------------------

def test_recadrer_pour_tuile_dimensions_exactes():
    source = _image_couleur((255, 0, 0), (1000, 400))  # très large
    tuile = recadrer_pour_tuile(source, 400, 225)
    assert tuile.size == (400, 225)

    source2 = _image_couleur((0, 255, 0), (200, 800))  # très haut
    tuile2 = recadrer_pour_tuile(source2, 400, 225)
    assert tuile2.size == (400, 225)


# ---------------------------------------------------------------------------
# Couleur d'accent
# ---------------------------------------------------------------------------

def test_couleur_accent_extrait_une_teinte_plausible():
    image_bleue = _image_couleur((20, 40, 220))
    r, g, b = calculer_couleur_accent(image_bleue)
    # le canal bleu doit rester dominant après le boost saturation/luminosité
    assert b >= r and b >= g
    assert all(0 <= c <= 255 for c in (r, g, b))


def test_couleur_accent_deterministe_stable():
    a1 = couleur_accent_deterministe("Action")
    a2 = couleur_accent_deterministe("Action")
    a3 = couleur_accent_deterministe("Comédie")
    assert a1 == a2  # déterministe, pas aléatoire
    assert a1 != a3  # des titres différents donnent des teintes différentes


# ---------------------------------------------------------------------------
# Construction de la grille complète
# ---------------------------------------------------------------------------

def test_construire_grille_dimensions_canvas():
    images = [_image_couleur((i * 20, 100, 200)) for i in range(12)]
    canvas = construire_grille(images, 1920, 1080)
    assert canvas.size == (1920, 1080)
    assert canvas.mode == "RGBA"


def test_construire_grille_leve_erreur_si_pas_assez_images():
    images = [_image_couleur((255, 0, 0))] * 3
    try:
        construire_grille(images, 1920, 1080)
        assert False, "aurait dû lever ValueError"
    except ValueError:
        pass


def test_construire_grille_utilise_bien_plusieurs_images_distinctes():
    """Vérifie que la mosaïque contient VRAIMENT plusieurs images
    différentes, pas la même recopiée partout (sanity check visuel)."""
    images = [
        _image_couleur((255, 0, 0)),
        _image_couleur((0, 255, 0)),
        _image_couleur((0, 0, 255)),
        _image_couleur((255, 255, 0)),
        _image_couleur((0, 255, 255)),
        _image_couleur((255, 0, 255)),
    ]
    canvas = construire_grille(images, 900, 600)
    couleurs_presentes = set(canvas.convert("RGB").getdata())
    # au moins 5 couleurs de base distinctes doivent apparaître quelque part
    couleurs_de_base = {(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255)}
    trouvees = {c for c in couleurs_presentes if c in couleurs_de_base}
    assert len(trouvees) >= 5


# ---------------------------------------------------------------------------
# Dégradé
# ---------------------------------------------------------------------------

def test_degrade_assombrit_le_bas_plus_que_le_haut():
    canvas = Image.new("RGBA", (200, 200), (200, 200, 200, 255))
    resultat = appliquer_degrade(canvas, (255, 100, 50)).convert("RGB")

    pixel_haut = resultat.getpixel((100, 5))
    pixel_bas = resultat.getpixel((100, 195))
    luminosite_haut = sum(pixel_haut) / 3
    luminosite_bas = sum(pixel_bas) / 3
    assert luminosite_bas < luminosite_haut


# ---------------------------------------------------------------------------
# Point d'entrée haut niveau
# ---------------------------------------------------------------------------

def test_generer_mosaique_retourne_none_si_pas_assez_images():
    images = [_image_couleur((255, 0, 0))] * 2
    assert generer_mosaique(images, 1920, 1080) is None


def test_generer_mosaique_cas_nominal():
    images = [_image_couleur((i * 15, 80, 180)) for i in range(12)]
    resultat = generer_mosaique(images, 1920, 1080, titre_repli="Action")
    assert resultat is not None
    assert resultat.image.size == (1920, 1080)
    assert resultat.image.mode == "RGB"
    assert resultat.nb_tuiles == 12
    assert len(resultat.accent) == 3


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
