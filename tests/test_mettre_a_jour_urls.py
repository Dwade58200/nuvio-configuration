"""Tests pour scripts/mettre_a_jour_urls.py (aucun appel réseau)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mettre_a_jour_urls import construire_url_cdn, mettre_a_jour  # noqa: E402


def test_construire_url_cdn():
    url = construire_url_cdn(
        "Dwade58200/nuvio-configuration", "feature/backdrops-automation", Path("Genres/Backdrops/Action_Backdrop.jpg")
    )
    assert url == (
        "https://cdn.jsdelivr.net/gh/Dwade58200/nuvio-configuration"
        "@feature/backdrops-automation/Collections/Genres/Backdrops/Action_Backdrop.jpg"
    )


def test_construire_url_cdn_encode_les_espaces():
    """Cas réel : le dossier 'Services de Streaming' contient des espaces
    -- l'URL générée doit être correctement encodée (%20), pas laissée
    telle quelle (ce qui casserait potentiellement le lien)."""
    url = construire_url_cdn(
        "Dwade58200/nuvio-configuration",
        "feature/backdrops-automation",
        Path("Services de Streaming/Backdrops/Netflix_Backdrop.jpg"),
    )
    assert "Services%20de%20Streaming" in url
    assert " " not in url


def test_mettre_a_jour_seulement_les_fichiers_existants(tmp_path):
    sortie = tmp_path / "Collections"
    (sortie / "Genres" / "Backdrops").mkdir(parents=True)
    (sortie / "Genres" / "Backdrops" / "Action_Backdrop.jpg").write_bytes(b"fake")
    # "Aventure" n'a volontairement PAS de fichier généré sur disque

    collections = [
        {
            "title": "🎭Genres",
            "folders": [
                {"title": "Action", "heroBackdropUrl": "https://ancien-cdn.example/action.webp"},
                {"title": "Aventure", "heroBackdropUrl": "https://ancien-cdn.example/aventure.webp"},
            ],
        }
    ]

    mis_a_jour, inchanges = mettre_a_jour(
        collections, sortie, "Dwade58200/nuvio-configuration", "feature/backdrops-automation"
    )

    assert mis_a_jour == 1
    assert inchanges == 1
    assert "cdn.jsdelivr.net/gh/Dwade58200" in collections[0]["folders"][0]["heroBackdropUrl"]
    assert "Action_Backdrop.jpg" in collections[0]["folders"][0]["heroBackdropUrl"]
    assert collections[0]["folders"][1]["heroBackdropUrl"] == "https://ancien-cdn.example/aventure.webp"


def test_utilise_le_nom_de_fichier_personnalise(tmp_path):
    """Cas réel : 'Sci-Fi' doit chercher/produire 'Sci-Fi_Backdrop.jpg',
    pas un slug générique comme 'sci-fi_backdrop.jpg'."""
    sortie = tmp_path / "Collections"
    (sortie / "Genres" / "Backdrops").mkdir(parents=True)
    (sortie / "Genres" / "Backdrops" / "Sci-Fi_Backdrop.jpg").write_bytes(b"fake")

    collections = [{"title": "🎭Genres", "folders": [{"title": "Sci-Fi", "heroBackdropUrl": ""}]}]
    mis_a_jour, _ = mettre_a_jour(
        collections, sortie, "Dwade58200/nuvio-configuration", "feature/backdrops-automation"
    )
    assert mis_a_jour == 1
    assert "Sci-Fi_Backdrop.jpg" in collections[0]["folders"][0]["heroBackdropUrl"]


def test_groupe_desactive_franchises_jamais_touche(tmp_path):
    sortie = tmp_path / "Collections"
    # Même si, hypothétiquement, un fichier existait sur disque pour une
    # franchise, le groupe "Franchises" est désactivé -> jamais modifié.
    (sortie / "Franchises" / "Backdrops").mkdir(parents=True)
    (sortie / "Franchises" / "Backdrops" / "007_Backdrop.jpg").write_bytes(b"fake")

    collections = [
        {
            "title": "Franchises",
            "folders": [{"title": "007", "heroBackdropUrl": "https://image.tmdb.org/original/x.jpg"}],
        }
    ]
    mis_a_jour, inchanges = mettre_a_jour(
        collections, sortie, "Dwade58200/nuvio-configuration", "feature/backdrops-automation"
    )
    assert mis_a_jour == 0
    assert collections[0]["folders"][0]["heroBackdropUrl"] == "https://image.tmdb.org/original/x.jpg"


def test_idempotent_si_deja_a_jour(tmp_path):
    sortie = tmp_path / "Collections"
    (sortie / "Genres" / "Backdrops").mkdir(parents=True)
    (sortie / "Genres" / "Backdrops" / "Action_Backdrop.jpg").write_bytes(b"fake")

    url_deja_bonne = construire_url_cdn(
        "Dwade58200/nuvio-configuration", "feature/backdrops-automation", Path("Genres/Backdrops/Action_Backdrop.jpg")
    )
    collections = [{"title": "🎭Genres", "folders": [{"title": "Action", "heroBackdropUrl": url_deja_bonne}]}]

    mis_a_jour, inchanges = mettre_a_jour(
        collections, sortie, "Dwade58200/nuvio-configuration", "feature/backdrops-automation"
    )
    assert mis_a_jour == 0
    assert inchanges == 1


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
