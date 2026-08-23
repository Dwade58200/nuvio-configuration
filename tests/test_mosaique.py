# -*- coding: utf-8 -*-
"""Tests pour scripts/mosaique.py (grille inclinée) -- entièrement hors-ligne."""

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mosaique import (  # noqa: E402
    MINIMUM_IMAGES_DISTINCTES,
    TUILES_CIBLE,
    aplatir_transparence,
    appliquer_degrade,
    assez_d_images,
    calculer_couleur_accent,
    completer_jusqua,
    construire_grille_inclinee,
    couleur_accent_deterministe,
    generer_mosaique,
    recadrer_pour_tuile,
)


def _image_couleur(couleur, taille=(1280, 720)):  # paysage, comme un thumb Fanart/backdrop TMDB
    return Image.new("RGB", taille, color=couleur)


# ---------------------------------------------------------------------------
# Seuil minimum d'images / complétion
# ---------------------------------------------------------------------------

def test_assez_d_images():
    assert assez_d_images(MINIMUM_IMAGES_DISTINCTES) is True
    assert assez_d_images(MINIMUM_IMAGES_DISTINCTES - 1) is False
    assert assez_d_images(20) is True


def test_completer_jusqua_repete_par_cycle():
    images = [_image_couleur((255, 0, 0)), _image_couleur((0, 255, 0)), _image_couleur((0, 0, 255))]
    completees = completer_jusqua(images, minimum=10)
    assert len(completees) == 10
    assert completees[:3] == images  # les originales d'abord
    assert completees[3] is images[0]  # puis ça recycle depuis le début


def test_completer_jusqua_ne_reduit_jamais():
    images = [_image_couleur((i, i, i)) for i in range(15)]
    completees = completer_jusqua(images, minimum=TUILES_CIBLE)
    assert len(completees) == 15  # déjà plus que le minimum -> inchangé


def test_completer_jusqua_liste_vide():
    assert completer_jusqua([], minimum=12) == []


# ---------------------------------------------------------------------------
# Recadrage (inchangé, toujours utilisé par preparer_tuile)
# ---------------------------------------------------------------------------

def test_recadrer_pour_tuile_dimensions_exactes():
    source = _image_couleur((255, 0, 0), (1000, 400))
    tuile = recadrer_pour_tuile(source, 372, 210)
    assert tuile.size == (372, 210)


def test_aplatir_transparence_image_opaque_inchangee():
    source = _image_couleur((10, 20, 30))  # déjà RGB, pas de canal alpha
    resultat = aplatir_transparence(source)
    assert resultat.mode == "RGB"
    assert resultat.getpixel((0, 0)) == (10, 20, 30)


def test_aplatir_transparence_composite_sur_fond_sombre():
    """Cas 'clearart' Fanart : PNG avec zones transparentes. Doit être
    composé sur un fond uni (pas de pixels noirs/blancs parasites)."""
    source = Image.new("RGBA", (100, 100), (0, 0, 0, 0))  # entièrement transparent
    for x in range(40, 60):
        for y in range(40, 60):
            source.putpixel((x, y), (255, 0, 0, 255))  # un petit carré opaque rouge au centre

    resultat = aplatir_transparence(source, couleur_fond=(20, 20, 25))
    assert resultat.mode == "RGB"
    assert resultat.getpixel((0, 0)) == (20, 20, 25)   # zone transparente -> couleur de fond choisie
    assert resultat.getpixel((50, 50)) == (255, 0, 0)  # zone opaque -> couleur d'origine préservée


def test_recadrer_pour_tuile_gere_une_image_transparente():
    """Vérifie que le pipeline complet (recadrage) ne plante pas et ne
    laisse pas de transparence résiduelle sur une image RGBA."""
    source = Image.new("RGBA", (800, 800), (0, 0, 0, 0))
    tuile = recadrer_pour_tuile(source, 372, 210)
    assert tuile.mode == "RGB"
    assert tuile.size == (372, 210)


# ---------------------------------------------------------------------------
# Couleur d'accent
# ---------------------------------------------------------------------------

def test_couleur_accent_extrait_une_teinte_plausible():
    image_bleue = _image_couleur((20, 40, 220))
    r, g, b = calculer_couleur_accent(image_bleue)
    assert b >= r and b >= g
    assert all(0 <= c <= 255 for c in (r, g, b))


def test_couleur_accent_deterministe_stable():
    a1 = couleur_accent_deterministe("Action")
    a2 = couleur_accent_deterministe("Action")
    a3 = couleur_accent_deterministe("Comédie")
    assert a1 == a2
    assert a1 != a3


# ---------------------------------------------------------------------------
# Grille inclinée
# ---------------------------------------------------------------------------

def test_construire_grille_inclinee_dimensions_canvas():
    images = [_image_couleur((i * 20, 100, 200)) for i in range(8)]
    canvas = construire_grille_inclinee(images, 1920, 1080)
    assert canvas.size == (1920, 1080)
    assert canvas.mode == "RGBA"


def test_construire_grille_inclinee_leve_erreur_si_liste_vide():
    try:
        construire_grille_inclinee([], 1920, 1080)
        assert False, "aurait dû lever ValueError"
    except ValueError:
        pass


def test_construire_grille_inclinee_utilise_plusieurs_images_distinctes():
    """La grille doit vraiment composer plusieurs affiches différentes
    (le cycle doit couvrir toute la grille, pas répéter la même partout)."""
    images = [
        _image_couleur((255, 0, 0)),
        _image_couleur((0, 255, 0)),
        _image_couleur((0, 0, 255)),
        _image_couleur((255, 255, 0)),
        _image_couleur((0, 255, 255)),
        _image_couleur((255, 0, 255)),
    ]
    canvas = construire_grille_inclinee(images, 1280, 720)
    couleurs_presentes = set(canvas.convert("RGB").resize((200, 120)).getdata())
    couleurs_de_base = {(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255)}
    # tolérance : la rotation/l'anti-aliasing modifie légèrement les teintes en bordure de tuile,
    # on vérifie juste qu'on trouve des pixels PROCHES d'au moins 4 couleurs de base différentes
    trouvees = set()
    for couleur in couleurs_presentes:
        for base in couleurs_de_base:
            if sum(abs(c - b) for c, b in zip(couleur, base)) < 40:
                trouvees.add(base)
    assert len(trouvees) >= 4


def test_grille_avec_une_seule_image_repetee_ne_plante_pas():
    """Cas limite : une seule image dispo (en dessous du seuil normalement,
    mais la fonction bas-niveau doit rester robuste si appelée directement)."""
    images = [_image_couleur((10, 20, 30))]
    canvas = construire_grille_inclinee(images, 800, 450)
    assert canvas.size == (800, 450)


# ---------------------------------------------------------------------------
# Dégradé
# ---------------------------------------------------------------------------

def test_degrade_assombrit_le_bas_et_la_gauche():
    canvas = Image.new("RGBA", (400, 400), (200, 200, 200, 255))
    resultat = appliquer_degrade(canvas, (255, 100, 50)).convert("RGB")

    lum = lambda p: sum(p) / 3  # noqa: E731
    centre_haut_droite = lum(resultat.getpixel((380, 10)))
    bas_gauche = lum(resultat.getpixel((10, 390)))

    assert bas_gauche < centre_haut_droite


# ---------------------------------------------------------------------------
# Point d'entrée haut niveau
# ---------------------------------------------------------------------------

def test_generer_mosaique_retourne_none_si_pas_assez_images():
    images = [_image_couleur((255, 0, 0))] * (MINIMUM_IMAGES_DISTINCTES - 1)
    assert generer_mosaique(images, 1920, 1080) is None


def test_generer_mosaique_cas_nominal():
    images = [_image_couleur((i * 15, 80, 180)) for i in range(12)]
    resultat = generer_mosaique(images, 1920, 1080, titre_repli="Action")
    assert resultat is not None
    assert resultat.image.size == (1920, 1080)
    assert resultat.image.mode == "RGB"
    assert resultat.nb_tuiles == 12
    assert len(resultat.accent) == 3


def test_nombre_cellules_grille_1920x1080():
    """Verrouille le nombre de cases réel de la grille (bug historique :
    seulement 12 images étaient récupérées pour ~72 cases, causant des
    répétitions visibles d'une même affiche toutes les ~2 rangées)."""
    from mosaique import nombre_cellules_grille

    cellules = nombre_cellules_grille(1920, 1080, echelle=1.0)
    assert cellules >= 60  # la grille a largement plus de 12 cases


def test_generer_mosaique_sans_repetition_si_assez_d_images_distinctes():
    """Avec autant d'images distinctes que de cases, AUCUNE tuile ne doit
    être répétée dans la grille finale."""
    from mosaique import nombre_cellules_grille

    cellules = nombre_cellules_grille(1920, 1080, echelle=1.0)
    # une couleur strictement unique par image, pour les repérer après coup
    images = [_image_couleur((i % 256, (i * 7) % 256, (i * 13) % 256)) for i in range(cellules)]
    resultat = generer_mosaique(images, 1920, 1080, titre_repli="Test")
    assert resultat is not None
    assert resultat.nb_tuiles == cellules  # toutes les images distinctes sont utilisées, aucune répétée pour compléter


def test_generer_mosaique_complete_si_peu_d_images():
    """Avec seulement 4 images distinctes (>= seuil minimum de 3, < 12),
    la mosaïque doit quand même se générer en répétant les images,
    comme luckynumb3rs (`ensure_minimum_tiles`)."""
    images = [_image_couleur((i * 40, 80, 180)) for i in range(4)]
    resultat = generer_mosaique(images, 1920, 1080, titre_repli="Micro-genre")
    assert resultat is not None
    assert resultat.nb_tuiles == 4  # nb_tuiles reflète les images SOURCES distinctes, pas la répétition


def test_generer_mosaique_echelle_avec_petit_canvas():
    """Un canvas plus petit (profil 'compresse') doit produire une image
    aux bonnes dimensions, sans erreur de tuiles trop grandes/trop petites."""
    images = [_image_couleur((i * 15, 80, 180)) for i in range(8)]
    resultat = generer_mosaique(images, 780, 439, titre_repli="Comédie")
    assert resultat is not None
    assert resultat.image.size == (780, 439)


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
