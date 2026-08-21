# -*- coding: utf-8 -*-
"""
Test d'intégration du mode --mosaique : simule des réponses TMDB paginées
(discover, avec backdrop_path) et, quand une clé Fanart est fournie, des
réponses Fanart.tv (thumb avec titre incrusté) -- vérifie que le pipeline
complet (résolution multiple -> Fanart puis repli TMDB -> grille inclinée
-> sauvegarde) fonctionne, sans appel réseau réel.
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generer_backdrops import GenerateurBackdrops, GROUPE_GENRES, construire_requetes  # noqa: E402


def _image_bytes(couleur, taille=(1280, 720)):
    img = Image.new("RGB", taille, color=couleur)
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


def _dossier_action():
    return {
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


def _resultats_discover(n=12, media_type="movie", debut_id=1):
    return {
        "results": [
            {
                "id": debut_id + i,
                "backdrop_path": f"/faux{debut_id + i}.jpg",
                "popularity": 100 - i,
                "original_language": "en",
            }
            for i in range(n)
        ]
    }


def test_mosaique_bout_en_bout_repli_tmdb_sans_fanart(tmp_path):
    """Sans clé Fanart, doit retomber directement sur les backdrops TMDB bruts."""
    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle", cle_fanart=None, repertoire_sortie=tmp_path, profil="compresse", mosaique=True
    )

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "discover/movie" in url:
            return FausseReponse(_resultats_discover())
        if "image.tmdb.org" in url:
            assert "/w1280/" in url, f"devrait demander un backdrop TMDB (w1280), pas: {url}"
            index = int(url.split("faux")[1].split(".")[0])
            return FausseReponse(content=_image_bytes(((index * 20) % 255, 80, 180)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    requetes, _ = construire_requetes(GROUPE_GENRES, _dossier_action())
    chemin_sortie = tmp_path / "genres" / "backdrop" / "action.jpg"
    resultat = generateur.traiter_dossier_mosaique(GROUPE_GENRES, "Action", requetes, chemin_sortie)

    assert resultat is not None
    assert resultat.statut == "genere"
    assert chemin_sortie.exists()
    with Image.open(chemin_sortie) as img:
        assert img.format == "JPEG"


def test_mosaique_utilise_fanart_thumb_en_priorite_pour_un_film(tmp_path):
    """Avec une clé Fanart, un film doit utiliser l'image 'moviethumb' (avec
    titre incrusté) plutôt que le backdrop TMDB brut."""
    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart="fausse-cle-fanart",
        repertoire_sortie=tmp_path,
        profil="compresse",
        mosaique=True,
        langue_preferee="fr",
    )

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "discover/movie" in url:
            return FausseReponse(_resultats_discover())
        if "webservice.fanart.tv/v3/movies/" in url:
            index = int(url.rstrip("/").split("/")[-1])
            return FausseReponse({
                "moviethumb": [{"url": f"https://fanart.example/thumb{index}.jpg", "lang": "fr", "likes": "5"}]
            })
        if "fanart.example" in url:
            index = int(url.split("thumb")[1].split(".")[0])
            return FausseReponse(content=_image_bytes(((index * 15) % 255, 40, 200)))
        if "image.tmdb.org" in url:
            raise AssertionError("ne devrait pas retomber sur TMDB alors que Fanart a répondu")
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    requetes, _ = construire_requetes(GROUPE_GENRES, _dossier_action())
    chemin_sortie = tmp_path / "genres" / "backdrop" / "action.jpg"
    resultat = generateur.traiter_dossier_mosaique(GROUPE_GENRES, "Action", requetes, chemin_sortie)

    assert resultat is not None
    assert resultat.statut == "genere"
    assert chemin_sortie.exists()


def test_mosaique_serie_passe_par_external_ids_pour_fanart(tmp_path):
    """Une série doit d'abord résoudre son tvdb_id (Fanart indexe les séries
    par TheTVDB, pas par TMDB) avant d'interroger Fanart."""
    dossier = {
        "title": "Séries populaires",
        "sources": [
            {
                "provider": "tmdb",
                "tmdbSourceType": "DISCOVER",
                "mediaType": "TV",
                "sortBy": "popularity.desc",
                "filters": {},
            }
        ],
    }

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart="fausse-cle-fanart",
        repertoire_sortie=tmp_path,
        profil="compresse",
        mosaique=True,
    )

    appels_external_ids = []

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "discover/tv" in url:
            return FausseReponse(_resultats_discover(media_type="tv"))
        if "/tv/" in url and "external_ids" in url:
            tmdb_id = int(url.split("/tv/")[1].split("/")[0])
            appels_external_ids.append(tmdb_id)
            return FausseReponse({"tvdb_id": 9000 + tmdb_id})
        if "webservice.fanart.tv/v3/tv/" in url:
            tvdb_id = int(url.rstrip("/").split("/")[-1])
            return FausseReponse({
                "tvthumb": [{"url": f"https://fanart.example/tv{tvdb_id}.jpg", "lang": "fr", "likes": "3"}]
            })
        if "fanart.example" in url:
            return FausseReponse(content=_image_bytes((90, 90, 200)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    requetes, _ = construire_requetes(GROUPE_GENRES, dossier)
    chemin_sortie = tmp_path / "genres" / "backdrop" / "series.jpg"
    resultat = generateur.traiter_dossier_mosaique(GROUPE_GENRES, "Séries populaires", requetes, chemin_sortie)

    assert resultat is not None
    assert resultat.statut == "genere"
    assert len(appels_external_ids) == 12  # un appel external_ids par candidat série


def test_mosaique_repli_si_pas_assez_de_resultats(tmp_path):
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

    generateur = GenerateurBackdrops(cle_tmdb="fausse-cle", cle_fanart=None, repertoire_sortie=tmp_path, mosaique=True)

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "discover/movie" in url:
            return FausseReponse(_resultats_discover(n=2))  # sous le seuil minimum (3)
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    requetes, _ = construire_requetes(GROUPE_GENRES, dossier)
    resultat = generateur.traiter_dossier_mosaique(GROUPE_GENRES, dossier["title"], requetes, tmp_path / "x.jpg")
    assert resultat is None


def test_mosaique_complete_si_peu_de_resultats(tmp_path):
    """4 résultats (>= seuil de 3, < 12) : doit générer en répétant les
    images plutôt que d'abandonner."""
    dossier = {
        "title": "Petit genre",
        "sources": [
            {
                "provider": "tmdb",
                "tmdbSourceType": "DISCOVER",
                "mediaType": "MOVIE",
                "sortBy": "popularity.desc",
                "filters": {"withGenres": "1"},
            }
        ],
    }

    generateur = GenerateurBackdrops(cle_tmdb="fausse-cle", cle_fanart=None, repertoire_sortie=tmp_path, mosaique=True)

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "discover/movie" in url:
            return FausseReponse(_resultats_discover(n=4))
        if "image.tmdb.org" in url:
            index = int(url.split("faux")[1].split(".")[0])
            return FausseReponse(content=_image_bytes(((index * 60) % 255, 90, 150)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    requetes, _ = construire_requetes(GROUPE_GENRES, dossier)
    chemin_sortie = tmp_path / "genres" / "backdrop" / "petit.jpg"
    resultat = generateur.traiter_dossier_mosaique(GROUPE_GENRES, dossier["title"], requetes, chemin_sortie)

    assert resultat is not None
    assert resultat.statut == "genere"
    assert chemin_sortie.exists()


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
