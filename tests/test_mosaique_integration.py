# -*- coding: utf-8 -*-
"""
Tests de la cascade de résolution d'image pour une tuile de mosaïque.

Ordre attendu, pour chaque candidat (film/série) :
  Pour langue en (français, anglais) :
    1. backdrop TMDB tagué EXACTEMENT cette langue (/images)
    2. Fanart "background" dans cette langue
    3. Fanart "thumb" dans cette langue
    4. Fanart "clearart"/"hdclearart" dans cette langue, composé sur un
       VRAI fond (jamais une couleur plate)
  Puis, en tout dernier recours (aucune langue n'a rien donné) :
    Fanart background/thumb/clearart SANS TEXTE, puis backdrop TMDB
    générique non tagué, puis le backdrop_path brut déjà connu.

Le type "banner" n'est JAMAIS utilisé (hors format pour nos tuiles paysage).

Tout est simulé via un faux `session.get` -- aucun appel réseau réel.
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


def _image_bytes_png_transparent(couleur_opaque=(255, 200, 0)):
    img = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    for x in range(100, 200):
        for y in range(100, 200):
            img.putpixel((x, y), (*couleur_opaque, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
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


def _generateur(cle_fanart="fausse-cle-fanart", langue_preferee="fr"):
    return GenerateurBackdrops(
        cle_tmdb="fausse-cle-tmdb",
        cle_fanart=cle_fanart,
        repertoire_sortie=Path("/tmp/inutilise"),
        profil="compresse",
        mosaique=True,
        langue_preferee=langue_preferee,
    )


CANDIDAT_FILM = ("/brut.jpg", 42, "movie", "en")


# ---------------------------------------------------------------------------
# Palier 1 : backdrop TMDB tagué langue (avant même Fanart)
# ---------------------------------------------------------------------------

def test_tmdb_backdrop_tague_francais_utilise_en_priorite_absolue():
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": [{"file_path": "/tmdb_fr.jpg", "iso_639_1": "fr", "vote_average": 5}]})
        if "webservice.fanart.tv" in url:
            raise AssertionError("Fanart ne devrait pas être interrogé si TMDB a déjà un backdrop FR")
        if "image.tmdb.org/t/p/w1280/tmdb_fr.jpg" in url:
            return FausseReponse(content=_image_bytes((10, 10, 10)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    image = generateur._resoudre_image_tuile(CANDIDAT_FILM)
    assert image is not None


def test_tmdb_backdrop_langue_choisit_le_mieux_note():
    generateur = _generateur(cle_fanart=None)

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({
                "backdrops": [
                    {"file_path": "/moins_bon.jpg", "iso_639_1": "fr", "vote_average": 1},
                    {"file_path": "/meilleur.jpg", "iso_639_1": "fr", "vote_average": 9},
                ]
            })
        if "image.tmdb.org" in url:
            assert "meilleur.jpg" in url
            return FausseReponse(content=_image_bytes((1, 2, 3)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(CANDIDAT_FILM) is not None


# ---------------------------------------------------------------------------
# Palier 2/3 : Fanart background puis thumb, dans la langue courante
# ---------------------------------------------------------------------------

def test_fanart_background_francais_utilise_si_pas_de_tmdb_fr():
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": []})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({
                "moviebackground": [{"url": "https://fanart.example/fond_fr.jpg", "lang": "fr", "likes": "1"}],
                "moviethumb": [{"url": "https://fanart.example/thumb_fr.jpg", "lang": "fr", "likes": "999"}],
            })
        if "fond_fr.jpg" in url:
            return FausseReponse(content=_image_bytes((5, 5, 5)))
        if "thumb_fr.jpg" in url:
            raise AssertionError("le background doit être choisi avant le thumb, même moins populaire")
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(CANDIDAT_FILM) is not None


def test_fanart_thumb_francais_si_pas_de_background_francais():
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": []})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({
                "moviebackground": [{"url": "https://fanart.example/fond_en.jpg", "lang": "en", "likes": "1"}],
                "moviethumb": [{"url": "https://fanart.example/thumb_fr.jpg", "lang": "fr", "likes": "1"}],
            })
        if "thumb_fr.jpg" in url:
            return FausseReponse(content=_image_bytes((6, 6, 6)))
        if "fond_en.jpg" in url:
            raise AssertionError("un background EN ne doit pas être choisi avant un thumb FR (mauvaise langue)")
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(CANDIDAT_FILM) is not None


def test_banner_jamais_utilise_meme_si_present_et_bien_note():
    """Le type 'banner' est explicitement exclu (hors format)."""
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": []})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({
                "moviebanner": [{"url": "https://fanart.example/banner_fr.jpg", "lang": "fr", "likes": "9999"}],
                "moviethumb": [{"url": "https://fanart.example/thumb_fr.jpg", "lang": "fr", "likes": "1"}],
            })
        if "banner_fr.jpg" in url:
            raise AssertionError("le type banner ne doit jamais être utilisé")
        if "thumb_fr.jpg" in url:
            return FausseReponse(content=_image_bytes((7, 7, 7)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(CANDIDAT_FILM) is not None


# ---------------------------------------------------------------------------
# Palier 4 : clearart composé sur un vrai fond
# ---------------------------------------------------------------------------

def test_clearart_francais_compose_sur_fond_fanart():
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": []})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({
                "hdmovieclearart": [{"url": "https://fanart.example/clearart_fr.png", "lang": "fr", "likes": "1"}],
                "moviebackground": [{"url": "https://fanart.example/fond_quelconque.jpg", "lang": "en", "likes": "1"}],
            })
        if "clearart_fr.png" in url:
            return FausseReponse(content=_image_bytes_png_transparent())
        if "fond_quelconque.jpg" in url:
            return FausseReponse(content=_image_bytes((40, 60, 90)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    image = generateur._resoudre_image_tuile(CANDIDAT_FILM)
    assert image is not None
    assert image.mode == "RGB"  # composé, plus de transparence résiduelle
    # le pixel central doit porter la couleur du clearart (composé par-dessus)
    assert image.getpixel((image.width // 2, image.height // 2))[0] > 200


def test_clearart_sans_fond_fanart_retombe_sur_backdrop_path_connu():
    """Si aucun 'background' Fanart n'existe, le clearart est composé sur
    le backdrop_path déjà connu du candidat plutôt que d'être abandonné."""
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": []})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({"hdmovieclearart": [{"url": "https://fanart.example/clearart_fr.png", "lang": "fr", "likes": "1"}]})
        if "clearart_fr.png" in url:
            return FausseReponse(content=_image_bytes_png_transparent())
        if "image.tmdb.org/t/p/w1280/brut.jpg" in url:
            return FausseReponse(content=_image_bytes((20, 30, 40)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    image = generateur._resoudre_image_tuile(CANDIDAT_FILM)
    assert image is not None
    assert image.mode == "RGB"


# ---------------------------------------------------------------------------
# Bascule français -> anglais
# ---------------------------------------------------------------------------

def test_bascule_sur_anglais_si_rien_en_francais():
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": [{"file_path": "/tmdb_en.jpg", "iso_639_1": "en", "vote_average": 5}]})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({})  # rien du tout côté Fanart
        if "tmdb_en.jpg" in url:
            return FausseReponse(content=_image_bytes((80, 80, 80)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(CANDIDAT_FILM) is not None


# ---------------------------------------------------------------------------
# Dernier recours : sans texte
# ---------------------------------------------------------------------------

def test_sans_texte_seulement_si_ni_francais_ni_anglais():
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": [{"file_path": "/generique.jpg", "iso_639_1": None, "vote_average": 1}]})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({"moviebackground": [{"url": "https://fanart.example/fond_sans_texte.jpg", "lang": None, "likes": "1"}]})
        if "fond_sans_texte.jpg" in url:
            return FausseReponse(content=_image_bytes((100, 100, 100)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(CANDIDAT_FILM) is not None


def test_fr_ca_jamais_confondu_avec_fr():
    """Un backdrop TMDB ou artwork Fanart tagué 'fr-CA' (français canadien)
    ne doit JAMAIS être choisi pour le palier 'fr' -- seul le tag exact
    'fr' est accepté."""
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            # aucun backdrop taggé "fr" strict, seulement une variante fr-CA
            return FausseReponse({"backdrops": [{"file_path": "/quebec.jpg", "iso_639_1": "fr-CA", "vote_average": 9}]})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({
                "moviethumb": [
                    {"url": "https://fanart.example/thumb_fr_ca.jpg", "lang": "fr-CA", "likes": "999"},
                    {"url": "https://fanart.example/thumb_en.jpg", "lang": "en", "likes": "1"},
                ]
            })
        if "quebec.jpg" in url:
            raise AssertionError("un backdrop tagué fr-CA ne doit jamais être choisi pour le palier français")
        if "thumb_fr_ca.jpg" in url:
            raise AssertionError("un artwork Fanart tagué fr-CA ne doit jamais être choisi pour le palier français")
        if "thumb_en.jpg" in url:
            # normal : comme rien n'existe en fr strict, on bascule sur le palier anglais
            return FausseReponse(content=_image_bytes((50, 50, 50)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    image = generateur._resoudre_image_tuile(CANDIDAT_FILM)
    assert image is not None  # résolu via le palier anglais, pas via fr-CA


def test_repli_final_sur_backdrop_path_brut_sans_cle_fanart():
    generateur = _generateur(cle_fanart=None)

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": []})
        if "image.tmdb.org/t/p/w1280/brut.jpg" in url:
            return FausseReponse(content=_image_bytes((1, 1, 1)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(CANDIDAT_FILM) is not None


# ---------------------------------------------------------------------------
# Séries : passage par tvdb_id pour Fanart
# ---------------------------------------------------------------------------

def test_serie_utilise_tvdb_id_pour_interroger_fanart():
    generateur = _generateur()
    candidat_serie = ("/brut_serie.jpg", 77, "tv", "en")

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/tv/77/images" in url:
            return FausseReponse({"backdrops": []})
        if "/tv/77/external_ids" in url:
            return FausseReponse({"tvdb_id": 12345})
        if "webservice.fanart.tv/v3/tv/12345" in url:
            return FausseReponse({"tvthumb": [{"url": "https://fanart.example/tv_thumb_fr.jpg", "lang": "fr", "likes": "1"}]})
        if "webservice.fanart.tv/v3/tv/77" in url:
            raise AssertionError("Fanart doit être interrogé avec le tvdb_id, pas le tmdb_id")
        if "tv_thumb_fr.jpg" in url:
            return FausseReponse(content=_image_bytes((9, 9, 9)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(candidat_serie) is not None


# ---------------------------------------------------------------------------
# Test bout-en-bout (discover -> résolution -> mosaïque -> sauvegarde)
# ---------------------------------------------------------------------------

def test_mosaique_bout_en_bout_sans_fanart(tmp_path):
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

    generateur = _generateur(cle_fanart=None)
    generateur.repertoire_sortie = tmp_path

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "discover/movie" in url:
            return FausseReponse({
                "results": [
                    {"id": i, "backdrop_path": f"/faux{i}.jpg", "popularity": 100 - i, "original_language": "en"}
                    for i in range(1, 10)
                ]
            })
        if "/images" in url:
            return FausseReponse({"backdrops": []})
        if "image.tmdb.org" in url:
            index = int(url.split("faux")[1].split(".")[0])
            return FausseReponse(content=_image_bytes(((index * 25) % 255, 80, 180)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    requetes, _ = construire_requetes(GROUPE_GENRES, dossier)
    chemin_sortie = tmp_path / "genres" / "backdrop" / "action.jpg"
    resultat = generateur.traiter_dossier_mosaique(GROUPE_GENRES, "Action", requetes, chemin_sortie)

    assert resultat is not None
    assert resultat.statut == "genere"
    assert chemin_sortie.exists()
    with Image.open(chemin_sortie) as img:
        assert img.format == "JPEG"


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

    generateur = _generateur(cle_fanart=None)
    generateur.repertoire_sortie = tmp_path

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "discover/movie" in url:
            return FausseReponse({
                "results": [
                    {"id": i, "backdrop_path": f"/faux{i}.jpg", "popularity": 10 - i, "original_language": "en"}
                    for i in range(1, 3)  # seulement 2 -> sous le seuil minimum (3)
                ]
            })
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    requetes, _ = construire_requetes(GROUPE_GENRES, dossier)
    resultat = generateur.traiter_dossier_mosaique(GROUPE_GENRES, dossier["title"], requetes, tmp_path / "x.jpg")
    assert resultat is None


def test_deduplique_un_film_present_via_collection_et_discover(tmp_path):
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

    generateur = _generateur(cle_fanart=None)
    generateur.repertoire_sortie = tmp_path

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
        if "/images" in url:
            return FausseReponse({"backdrops": []})
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


# ---------------------------------------------------------------------------
# Cache TMDB/Fanart (le même titre revient dans plusieurs dossiers)
# ---------------------------------------------------------------------------

def test_recuperer_images_est_mis_en_cache():
    generateur = _generateur(cle_fanart=None)
    compteur_appels = {"n": 0}

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            compteur_appels["n"] += 1
            return FausseReponse({"backdrops": [{"file_path": "/x.jpg", "iso_639_1": "fr", "vote_average": 5}]})
        if "x.jpg" in url:
            return FausseReponse(content=_image_bytes((1, 1, 1)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    generateur._resoudre_image_tuile(CANDIDAT_FILM)
    generateur._resoudre_image_tuile(CANDIDAT_FILM)  # même film, ex: présent dans un 2e dossier
    generateur._resoudre_image_tuile(CANDIDAT_FILM)

    assert compteur_appels["n"] == 1, "recuperer_images aurait dû être appelé une seule fois (mis en cache)"


def test_fanart_donnees_est_mis_en_cache():
    generateur = _generateur()
    compteur_appels = {"n": 0}

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": []})
        if "webservice.fanart.tv/v3/movies/42" in url:
            compteur_appels["n"] += 1
            return FausseReponse({"moviethumb": [{"url": "https://fanart.example/thumb.jpg", "lang": "fr", "likes": "1"}]})
        if "thumb.jpg" in url:
            return FausseReponse(content=_image_bytes((1, 1, 1)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    generateur._resoudre_image_tuile(CANDIDAT_FILM)
    generateur._resoudre_image_tuile(CANDIDAT_FILM)

    assert compteur_appels["n"] == 1, "Fanart aurait dû être interrogé une seule fois (mis en cache)"


# ---------------------------------------------------------------------------
# Budget d'appels TMDB /images -> bascule Fanart uniquement
# ---------------------------------------------------------------------------

def test_budget_tmdb_images_epuise_bascule_sur_fanart():
    generateur = _generateur(langue_preferee="fr")
    generateur.tmdb.limite_appels_images = 1  # budget volontairement minuscule pour le test

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/images" in url:
            return FausseReponse({"backdrops": [{"file_path": "/depuis_tmdb.jpg", "iso_639_1": "fr", "vote_average": 5}]})
        if "depuis_tmdb.jpg" in url:
            return FausseReponse(content=_image_bytes((1, 1, 1)))
        if "webservice.fanart.tv/v3/movies/2" in url:
            return FausseReponse({"moviethumb": [{"url": "https://fanart.example/thumb2.jpg", "lang": "fr", "likes": "1"}]})
        if "thumb2.jpg" in url:
            return FausseReponse(content=_image_bytes((2, 2, 2)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    # 1er candidat : le budget (1) permet encore l'appel /images -> consommé ici
    assert generateur._resoudre_image_tuile(("/brut1.jpg", 1, "movie", "en")) is not None
    assert generateur.tmdb.budget_images_epuise is False
    assert generateur.tmdb.compteur_appels_images == 1

    # 2e candidat : budget épuisé -> /images ne doit PLUS être appelé, bascule Fanart directe
    image = generateur._resoudre_image_tuile(("/brut2.jpg", 2, "movie", "en"))
    assert image is not None
    assert generateur.tmdb.budget_images_epuise is True
    assert generateur.tmdb.compteur_appels_images == 1  # inchangé : pas de second appel /images


def test_recuperer_images_sans_reseau_une_fois_budget_epuise():
    """Vérifie qu'aucun appel réseau n'est fait du tout une fois le budget
    atteint (pas juste ignoré après coup)."""
    from generer_backdrops import ClientTMDB

    client = ClientTMDB(cle_api="x", limite_appels_images=0)
    appelé = {"valeur": False}

    def fausse_get(*args, **kwargs):
        appelé["valeur"] = True
        raise AssertionError("ne devrait jamais être appelé, budget déjà à 0")

    client.session.get = MagicMock(side_effect=fausse_get)
    resultat = client.recuperer_images(123, "movie")
    assert resultat == {}
    assert appelé["valeur"] is False
    assert client.budget_images_epuise is True


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
