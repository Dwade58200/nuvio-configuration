"""
Tests unitaires pour scripts/etat_backdrops.py

Lancer avec : pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from etat_backdrops import etat_dossier  # noqa: E402


def test_etat_dossier_manquant_si_actif_et_aucun_fichier(tmp_path):
    statut, chemin = etat_dossier("🎭 Genres", "Action", {}, tmp_path)
    assert statut == "manquant"
    assert not chemin.exists()


def test_etat_dossier_genere_si_le_fichier_existe(tmp_path):
    statut, chemin = etat_dossier("🎭 Genres", "Action", {}, tmp_path)
    chemin.parent.mkdir(parents=True)
    chemin.write_bytes(b"fake-jpg")

    statut, chemin = etat_dossier("🎭 Genres", "Action", {}, tmp_path)
    assert statut == "généré"


def test_etat_dossier_ignore_si_groupe_desactive(tmp_path):
    from generer_backdrops import GROUPE_FRANCHISES

    statut, _ = etat_dossier(GROUPE_FRANCHISES, "007", {}, tmp_path)
    assert statut == "ignoré (groupe/filtre désactivé)"


def test_etat_dossier_image_manuelle_pas_encore_generee(tmp_path):
    statut, _ = etat_dossier("Genres", "Action", {"Action": "https://exemple.test/img.jpg"}, tmp_path)
    assert statut == "image manuelle (pas encore générée)"


def test_etat_dossier_image_manuelle_deja_generee(tmp_path):
    _, chemin = etat_dossier("Genres", "Action", {}, tmp_path)
    chemin.parent.mkdir(parents=True)
    chemin.write_bytes(b"fake-jpg")

    statut, _ = etat_dossier("Genres", "Action", {"Action": "https://exemple.test/img.jpg"}, tmp_path)
    assert statut == "image manuelle"


def test_etat_dossier_image_manuelle_prioritaire_sur_groupe_desactive(tmp_path):
    """Même sur un groupe désactivé (Franchises), une image manuelle
    change le statut -- cohérent avec la priorité absolue de
    traiter_dossier() dans generer_backdrops.py."""
    from generer_backdrops import GROUPE_FRANCHISES

    statut, _ = etat_dossier(GROUPE_FRANCHISES, "007", {"007": "https://exemple.test/007.jpg"}, tmp_path)
    assert statut == "image manuelle (pas encore générée)"
