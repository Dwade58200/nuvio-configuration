# -*- coding: utf-8 -*-
"""Tests pour scripts/mettre_a_jour_urls.py (aucun appel réseau)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from mettre_a_jour_urls import construire_url_cdn, mettre_a_jour  # noqa: E402


def test_construire_url_cdn():
    url = construire_url_cdn("Dwade58200/nuvio-configuration", "feature/backdrops-automation", Path("genres/backdrop/action.jpg"))
    assert url == (
        "https://cdn.jsdelivr.net/gh/Dwade58200/nuvio-configuration"
        "@feature/backdrops-automation/collections/genres/backdrop/action.jpg"
    )


def test_mettre_a_jour_seulement_les_fichiers_existants(tmp_path):
    sortie = tmp_path / "collections"
    (sortie / "genres" / "backdrop").mkdir(parents=True)
    (sortie / "genres" / "backdrop" / "action.jpg").write_bytes(b"fake")
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
    assert collections[0]["folders"][1]["heroBackdropUrl"] == "https://ancien-cdn.example/aventure.webp"


def test_groupe_desactive_franchises_jamais_touche(tmp_path):
    sortie = tmp_path / "collections"
    # Même si, hypothétiquement, un fichier existait sur disque pour une
    # franchise, le groupe "Franchises" n'a pas de slug -> jamais modifié.
    (sortie / "franchises" / "backdrop").mkdir(parents=True)
    (sortie / "franchises" / "backdrop" / "007.jpg").write_bytes(b"fake")

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
    sortie = tmp_path / "collections"
    (sortie / "genres" / "backdrop").mkdir(parents=True)
    (sortie / "genres" / "backdrop" / "action.jpg").write_bytes(b"fake")

    url_deja_bonne = construire_url_cdn(
        "Dwade58200/nuvio-configuration", "feature/backdrops-automation", Path("genres/backdrop/action.jpg")
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
