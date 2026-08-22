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


def test_fanart_priorite_langue_francais_devant_original():
    from generer_backdrops import ClientFanart

    client = ClientFanart(cle_api="x")
    data = {
        "moviethumb": [
            {"url": "https://example/original.jpg", "lang": "en", "likes": "50"},
            {"url": "https://example/fr.jpg", "lang": "fr", "likes": "1"},
        ]
    }
    url, bucket = client.choisir_url(data, "movie", langue_preferee="fr", langue_originale="en")
    assert bucket == "preferee"
    assert url == "https://example/fr.jpg"  # le français gagne même avec moins de likes


def test_fanart_autre_langue_avec_texte_prime_sur_sans_texte():
    """Priorité demandée : Français -> original -> N'IMPORTE QUELLE AUTRE
    langue avec titre -> sans texte SEULEMENT en tout dernier recours."""
    from generer_backdrops import ClientFanart

    client = ClientFanart(cle_api="x")
    data = {
        "moviethumb": [
            {"url": "https://example/allemand.jpg", "lang": "de", "likes": "10"},
            {"url": "https://example/sans_texte.jpg", "lang": None, "likes": "999"},
        ]
    }
    # ni fr ni en (original) disponibles -> doit prendre l'allemand (a du texte)
    # plutôt que la version sans texte, même beaucoup plus populaire
    url, bucket = client.choisir_url(data, "movie", langue_preferee="fr", langue_originale="en")
    assert bucket == "autre"
    assert url == "https://example/allemand.jpg"


def test_fanart_sans_texte_seulement_en_dernier_recours():
    from generer_backdrops import ClientFanart

    client = ClientFanart(cle_api="x")
    data = {"moviebackground": [{"url": "https://example/fond.jpg", "lang": None, "likes": "5"}]}
    url, bucket = client.choisir_url(data, "movie", langue_preferee="fr", langue_originale="en")
    assert bucket == "sans_texte"
    assert url == "https://example/fond.jpg"


def test_fanart_thumb_prime_sur_banner_a_langue_egale():
    from generer_backdrops import ClientFanart

    client = ClientFanart(cle_api="x")
    data = {
        "moviebanner": [{"url": "https://example/banner_fr.jpg", "lang": "fr", "likes": "100"}],
        "moviethumb": [{"url": "https://example/thumb_fr.jpg", "lang": "fr", "likes": "1"}],
    }
    url, bucket = client.choisir_url(data, "movie", langue_preferee="fr", langue_originale="en")
    assert bucket == "preferee"
    assert url == "https://example/thumb_fr.jpg"  # thumb préféré au banner, même moins populaire


def test_fanart_banner_utilise_si_pas_de_thumb_disponible():
    from generer_backdrops import ClientFanart

    client = ClientFanart(cle_api="x")
    data = {"moviebanner": [{"url": "https://example/banner_fr.jpg", "lang": "fr", "likes": "10"}]}
    url, bucket = client.choisir_url(data, "movie", langue_preferee="fr", langue_originale="en")
    assert bucket == "preferee"
    assert url == "https://example/banner_fr.jpg"


def test_fanart_clearart_utilise_en_repli_pour_serie():
    from generer_backdrops import ClientFanart

    client = ClientFanart(cle_api="x")
    data = {"hdclearart": [{"url": "https://example/clearart.png", "lang": None, "likes": "3"}]}
    url, bucket = client.choisir_url(data, "tv", langue_preferee="fr", langue_originale="ja")
    assert bucket == "sans_texte"
    assert url == "https://example/clearart.png"


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


def test_mosaique_deduplique_un_film_present_via_collection_et_discover(tmp_path):
    """Bug historique : un film présent à la fois dans une collection et
    dans les résultats discover était compté deux fois (médias types
    différents empêchaient la déduplication). Vérifie que le même id de
    film n'apparaît qu'une seule fois parmi les candidats retenus."""
    dossier = {
        "title": "Mixte",
        "sources": [
            {"provider": "tmdb", "tmdbSourceType": "COLLECTION", "tmdbId": 999, "mediaType": "MOVIE"},
            {
                "provider": "tmdb",
                "tmdbSourceType": "DISCOVER",
                "mediaType": "MOVIE",
                "sortBy": "popularity.desc",
                "filters": {"withGenres": "28"},
            },
        ],
    }

    generateur = GenerateurBackdrops(cle_tmdb="fausse-cle", cle_fanart=None, repertoire_sortie=tmp_path, mosaique=True)

    # Le film id=1 apparaît DANS LA COLLECTION *ET* dans les résultats discover.
    reponse_collection = {"parts": [{"id": 1, "backdrop_path": "/collection1.jpg", "popularity": 999}]}
    reponse_discover = {
        "results": [{"id": 1, "backdrop_path": "/discover1.jpg", "popularity": 90, "original_language": "en"}]
        + [{"id": i, "backdrop_path": f"/discover{i}.jpg", "popularity": 90 - i, "original_language": "en"} for i in range(2, 6)]
    }

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/collection/999" in url:
            return FausseReponse(reponse_collection)
        if "discover/movie" in url:
            return FausseReponse(reponse_discover)
        if "image.tmdb.org" in url:
            return FausseReponse(content=_image_bytes((100, 100, 100)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    requetes, _ = construire_requetes(GROUPE_GENRES, dossier)

    candidats: list = []
    vus: set = set()
    listes_par_requete = [generateur.tmdb.resoudre_backdrops_multiples(req, limite=12) for req in requetes]
    max_len = max((len(liste) for liste in listes_par_requete), default=0)
    for i in range(max_len):
        for liste in listes_par_requete:
            if i < len(liste):
                backdrop_path, tmdb_id, media_type, langue = liste[i]
                cle = (media_type, tmdb_id)
                if cle not in vus:
                    vus.add(cle)
                    candidats.append((backdrop_path, tmdb_id, media_type, langue))

    ids_films = [c[1] for c in candidats]
    assert ids_films.count(1) == 1, f"le film id=1 apparaît {ids_films.count(1)} fois, devrait être 1"


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
