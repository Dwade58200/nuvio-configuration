# -*- coding: utf-8 -*-
"""
Test d'intégration du mode --mosaique : simule des réponses TMDB
paginées (discover) avec 12 résultats distincts, vérifie que le pipeline
complet (résolution multiple -> téléchargement -> mosaïque -> sauvegarde)
produit bien une image composite exploitant plusieurs sources, sans appel
réseau réel.
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generer_backdrops import GenerateurBackdrops, GROUPE_GENRES  # noqa: E402


def _image_bytes(couleur):
    img = Image.new("RGB", (780, 439), color=couleur)
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


def test_mosaique_bout_en_bout(tmp_path):
    dossier = {
        "title": "Action",
        "sources": [
            {
                "provider": "tmdb",
                "tmdbSourceType": "DISCOVER",
                "mediaType": "MOVIE",
                "sortBy": "popularity.desc",
                "filters": {"withGenres": "28"},
            }
        ],
    }

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart=None,
        repertoire_sortie=tmp_path,
        profil="compresse",
        mosaique=True,
    )

    # 12 résultats distincts (chacun avec un backdrop_path unique) sur 1 page
    resultats_discover = {
        "results": [
            {"id": i, "backdrop_path": f"/faux{i}.jpg", "popularity": 100 - i}
            for i in range(12)
        ]
    }

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "discover/movie" in url:
            return FausseReponse(resultats_discover)
        if "image.tmdb.org" in url:
            # extraire la couleur à partir du chemin pour varier les images
            index = int(url.split("faux")[1].split(".")[0])
            couleur = ((index * 20) % 255, 80, 180)
            return FausseReponse(content=_image_bytes(couleur))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    dossier_titre = dossier["title"]
    from generer_backdrops import construire_requetes

    requetes, _ = construire_requetes(GROUPE_GENRES, dossier)
    chemin_sortie = tmp_path / "genres" / "backdrop" / "action.jpg"

    resultat = generateur.traiter_dossier_mosaique(GROUPE_GENRES, dossier_titre, requetes, chemin_sortie)

    assert resultat is not None
    assert resultat.statut == "genere"
    assert "mosaïque" in resultat.detail
    assert chemin_sortie.exists()

    with Image.open(chemin_sortie) as img:
        assert img.format == "JPEG"
        couleurs = set(img.convert("RGB").resize((100, 100)).getdata())
        # la mosaïque doit contenir un vrai éventail de couleurs (pas un aplat unique)
        assert len(couleurs) > 20


def test_mosaique_repli_si_pas_assez_de_resultats(tmp_path):
    """Si TMDB ne retourne que 2 résultats avec backdrop, pas de mosaïque
    possible -> traiter_dossier_mosaique doit retourner None (signal de
    repli pour traiter_dossier)."""
    dossier = {
        "title": "Micro-genre",
        "sources": [
            {
                "provider": "tmdb",
                "tmdbSourceType": "DISCOVER",
                "mediaType": "MOVIE",
                "sortBy": "popularity.desc",
                "filters": {"withGenres": "99999"},
            }
        ],
    }

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle", cle_fanart=None, repertoire_sortie=tmp_path, mosaique=True
    )

    resultats_discover = {
        "results": [
            {"id": 1, "backdrop_path": "/a.jpg", "popularity": 10},
            {"id": 2, "backdrop_path": "/b.jpg", "popularity": 5},
        ]
    }

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "discover/movie" in url:
            return FausseReponse(resultats_discover)
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    from generer_backdrops import construire_requetes

    requetes, _ = construire_requetes(GROUPE_GENRES, dossier)
    resultat = generateur.traiter_dossier_mosaique(
        GROUPE_GENRES, dossier["title"], requetes, tmp_path / "x.jpg"
    )
    assert resultat is None


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
