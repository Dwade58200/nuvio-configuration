"""
Tests unitaires pour scripts/appliquer_style_mosaique.py

Lancer avec : pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from appliquer_style_mosaique import appliquer, construire_remplacements  # noqa: E402

CONTENU_EXEMPLE = """\
TUILE_LARGEUR = 372       # commentaire existant
TUILE_HAUTEUR = 210
ECART = 9                 # espace entre tuiles
INTENSITE_OMBRE = 1.0
"""


def test_construire_remplacements_ignore_les_cles_absentes():
    remplacements = construire_remplacements({"tuile_largeur": 340})
    assert remplacements == {"TUILE_LARGEUR": "340"}


def test_construire_remplacements_arrondit_les_flottants():
    remplacements = construire_remplacements({"decalage_ligne": 0.456, "intensite_ombre": 1.234})
    assert remplacements == {"DECALAGE_LIGNE": "0.46", "INTENSITE_OMBRE": "1.23"}


def test_appliquer_remplace_une_valeur_simple():
    nouveau, modifiees, introuvables = appliquer(CONTENU_EXEMPLE, {"TUILE_HAUTEUR": "180"})
    assert "TUILE_HAUTEUR = 180" in nouveau
    assert modifiees == ["TUILE_HAUTEUR"]
    assert introuvables == []


def test_appliquer_preserve_le_commentaire_de_fin_de_ligne():
    nouveau, _, _ = appliquer(CONTENU_EXEMPLE, {"TUILE_LARGEUR": "340"})
    assert "TUILE_LARGEUR = 340       # commentaire existant" in nouveau
    # Pas de collage valeur/commentaire (bug corrigé : "340# commentaire").
    assert "340#" not in nouveau


def test_appliquer_signale_une_constante_introuvable():
    nouveau, modifiees, introuvables = appliquer(CONTENU_EXEMPLE, {"CONSTANTE_INEXISTANTE": "1"})
    assert nouveau == CONTENU_EXEMPLE
    assert modifiees == []
    assert introuvables == ["CONSTANTE_INEXISTANTE"]


def test_appliquer_plusieurs_constantes_a_la_fois():
    nouveau, modifiees, introuvables = appliquer(
        CONTENU_EXEMPLE, {"TUILE_LARGEUR": "340", "INTENSITE_OMBRE": "1.20"}
    )
    assert "TUILE_LARGEUR = 340" in nouveau
    assert "INTENSITE_OMBRE = 1.20" in nouveau
    assert set(modifiees) == {"TUILE_LARGEUR", "INTENSITE_OMBRE"}
    assert introuvables == []


def test_appliquer_ne_change_rien_si_valeur_deja_identique():
    _, modifiees, _ = appliquer(CONTENU_EXEMPLE, {"TUILE_HAUTEUR": "210"})
    # La substitution a bien lieu textuellement, mais le contenu final est
    # identique -- donc rien à signaler comme "modifié".
    assert modifiees == []
