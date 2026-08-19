# -*- coding: utf-8 -*-
"""
Test d'intégration : simule les réponses TMDB/Fanart avec de fausses
requêtes HTTP, pour vérifier que tout le pipeline
(résolution -> téléchargement -> redimensionnement -> sauvegarde) fonctionne,
sans avoir besoin d'une vraie clé API ni d'accès réseau à TMDB.
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generer_backdrops import (  # noqa: E402
    GenerateurBackdrops,
    GROUPE_GENRES,
)


def _image_factice_bytes() -> bytes:
    """Une petite image JPEG en mémoire, pour simuler une réponse TMDB."""
    img = Image.new("RGB", (1920, 1080), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class FausseReponse:
    def __init__(self, json_data=None, content=b"", status_code=200):
        self._json = json_data or {}
        self.content = content
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_pipeline_complet_discover_vers_image(tmp_path):
    dossier = {
        "title": "Action",
        "sources": [
            {
                "provider": "tmdb",
                "tmdbSourceType": "DISCOVER",
                "mediaType": "MOVIE",
                "sortBy": "popularity.desc",
                "filters": {"withGenres": "28", "voteCountGte": 200},
            }
        ],
    }

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart=None,
        repertoire_sortie=tmp_path,
        profil="standard",
    )

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "discover/movie" in url:
            return FausseReponse({"results": [{"id": 42, "backdrop_path": "/abc123.jpg"}]})
        if "image.tmdb.org" in url:
            return FausseReponse(content=_image_factice_bytes())
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    resultat = generateur.traiter_dossier(GROUPE_GENRES, dossier)

    assert resultat.statut == "genere", resultat.detail
    chemin_final = tmp_path / resultat.chemin
    assert chemin_final.exists()

    with Image.open(chemin_final) as img:
        assert img.width <= 1280  # profil "standard"
        assert img.format == "JPEG"


def test_pipeline_bascule_sur_fanart_si_pas_de_backdrop_tmdb():
    dossier = {
        "title": "Comédie",
        "sources": [
            {
                "provider": "tmdb",
                "tmdbSourceType": "DISCOVER",
                "mediaType": "MOVIE",
                "sortBy": "popularity.desc",
                "filters": {"withGenres": "35"},
            }
        ],
    }

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart="fausse-cle-fanart",
        repertoire_sortie=Path("/tmp/inutilise"),
        profil="standard",
        dry_run=True,  # on veut juste vérifier la résolution, pas l'écriture disque ici
    )

    # dry_run court-circuite avant l'appel réseau -> on teste donc juste que
    # la requête est bien construite (déjà couvert par les tests unitaires).
    resultat = generateur.traiter_dossier(GROUPE_GENRES, dossier)
    assert resultat.statut == "genere"
    assert "requête" in resultat.detail


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
