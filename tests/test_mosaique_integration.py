"""
Tests de la cascade de résolution d'image pour une tuile de mosaïque.

Ordre attendu, pour un candidat (film/série) :
  1. backdrop TMDB tagué français (pays FR ou non renseigné -- jamais un
     backdrop langue "fr" mais pays "CA", cf. cas réel "From"/"Supernatural")
  2. Fanart "thumb" anglais UNIQUEMENT (plus de background ni clearart)
  3. backdrop TMDB tagué anglais
  4. backdrop TMDB tagué avec la langue ORIGINALE du titre (si différente
     de fr/en)
  5. backdrop TMDB générique non tagué (sans texte)
  6. dernier recours silencieux : backdrop_path brut déjà connu (aucune
     requête supplémentaire)

Le type "banner" n'est JAMAIS utilisé (hors format pour nos tuiles paysage).

Tout est simulé via un faux `session.get` -- aucun appel réseau réel.
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generer_backdrops import GROUPE_GENRES, GenerateurBackdrops, construire_requetes  # noqa: E402


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
# Pool de connexions HTTP (mosaïque + parallélisme = beaucoup de requêtes
# concurrentes vers les mêmes hôtes)
# ---------------------------------------------------------------------------

def test_pool_de_connexions_agrandi_au_dela_du_defaut_requests():
    """Régression : avec le pool par défaut de `requests` (10), le mode
    mosaïque (jusqu'à 12 téléchargements en parallèle par dossier) plus
    `--parallelisme` déclenchait en boucle un warning urllib3 "Connection
    pool is full, discarding connection" sur TMDB/Fanart -- pas une erreur
    bloquante, mais un vrai gâchis de connexions TCP à chaque run réel."""
    generateur = _generateur()
    adaptateur_https = generateur.session.get_adapter("https://api.themoviedb.org")
    assert adaptateur_https._pool_maxsize > 10
    # Le même objet adaptateur doit être monté sur http:// et https:// (un
    # seul pool partagé pour TMDB, Fanart.tv, MDBList, et les CDN d'images).
    assert generateur.session.get_adapter("http://example.com") is adaptateur_https


# ---------------------------------------------------------------------------
# Palier 1 : backdrop TMDB tagué français (avant même Fanart)
# ---------------------------------------------------------------------------

def test_tmdb_backdrop_tague_francais_utilise_en_priorite_absolue():
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": [{"file_path": "/tmdb_fr.jpg", "iso_639_1": "fr", "iso_3166_1": "FR", "vote_average": 5}]})
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
# Palier 2 : Fanart "thumb" anglais uniquement
# ---------------------------------------------------------------------------

def test_fanart_thumb_anglais_utilise_si_pas_de_tmdb_fr():
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": []})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({"moviethumb": [{"url": "https://fanart.example/thumb_en.jpg", "lang": "en", "likes": "1"}]})
        if "thumb_en.jpg" in url:
            return FausseReponse(content=_image_bytes((5, 5, 5)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(CANDIDAT_FILM) is not None


def test_fanart_background_jamais_interroge():
    """Le type 'background' Fanart n'est plus utilisé du tout dans la
    cascade -- seul 'thumb' anglais compte désormais."""
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": []})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({
                "moviebackground": [{"url": "https://fanart.example/fond_en.jpg", "lang": "en", "likes": "999"}],
                "moviethumb": [{"url": "https://fanart.example/thumb_en.jpg", "lang": "en", "likes": "1"}],
            })
        if "fond_en.jpg" in url:
            raise AssertionError("le type 'background' Fanart ne doit plus jamais être interrogé")
        if "thumb_en.jpg" in url:
            return FausseReponse(content=_image_bytes((6, 6, 6)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(CANDIDAT_FILM) is not None


def test_fanart_francais_jamais_interroge():
    """Fanart n'est plus interrogé qu'en anglais -- un thumb FR présent ne
    doit jamais être choisi (et ne fait plus partie de la cascade)."""
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": [{"file_path": "/tmdb_en.jpg", "iso_639_1": "en", "vote_average": 5}]})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({"moviethumb": [{"url": "https://fanart.example/thumb_fr.jpg", "lang": "fr", "likes": "999"}]})
        if "thumb_fr.jpg" in url:
            raise AssertionError("un thumb Fanart en français ne doit plus jamais être choisi")
        if "tmdb_en.jpg" in url:
            return FausseReponse(content=_image_bytes((7, 7, 7)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(CANDIDAT_FILM) is not None


def test_fanart_thumb_anglais_priorite_sur_tmdb_anglais():
    """Le Fanart thumb anglais (palier 2) doit être choisi avant même un
    backdrop TMDB anglais valide (palier 3), dans cet ordre précis."""
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": [{"file_path": "/tmdb_en.jpg", "iso_639_1": "en", "vote_average": 9}]})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({"moviethumb": [{"url": "https://fanart.example/thumb_en.jpg", "lang": "en", "likes": "1"}]})
        if "thumb_en.jpg" in url:
            return FausseReponse(content=_image_bytes((8, 8, 8)))
        if "tmdb_en.jpg" in url:
            raise AssertionError("Fanart thumb anglais doit être choisi avant le backdrop TMDB anglais")
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
                "moviebanner": [{"url": "https://fanart.example/banner_en.jpg", "lang": "en", "likes": "9999"}],
                "moviethumb": [{"url": "https://fanart.example/thumb_en.jpg", "lang": "en", "likes": "1"}],
            })
        if "banner_en.jpg" in url:
            raise AssertionError("le type banner ne doit jamais être utilisé")
        if "thumb_en.jpg" in url:
            return FausseReponse(content=_image_bytes((7, 7, 7)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(CANDIDAT_FILM) is not None


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
    """Sans rien en fr/en/natif (ni TMDB ni Fanart), on retombe sur un
    backdrop TMDB générique non tagué -- Fanart n'est plus sollicité du
    tout à ce stade (contrairement à l'ancienne cascade)."""
    generateur = _generateur()
    candidat_sans_natif_distinct = ("/brut.jpg", 42, "movie", "fr")  # natif == préférée, pas de palier 4

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({"backdrops": [{"file_path": "/generique.jpg", "iso_639_1": None, "vote_average": 1}]})
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({"moviethumb": [{"url": "https://fanart.example/thumb_fr.jpg", "lang": "fr", "likes": "1"}]})
        if "thumb_fr.jpg" in url:
            raise AssertionError("Fanart FR ne doit plus jamais être interrogé/choisi")
        if "generique.jpg" in url:
            return FausseReponse(content=_image_bytes((100, 100, 100)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    assert generateur._resoudre_image_tuile(candidat_sans_natif_distinct) is not None


def test_fr_ca_jamais_confondu_avec_fr():
    """Un backdrop TMDB tagué langue='fr' MAIS pays='CA' (français
    canadien) ne doit JAMAIS être choisi pour le palier français."""
    generateur = _generateur()

    def fausse_get(url, params=None, timeout=None, **kwargs):
        if "/movie/42/images" in url:
            return FausseReponse({
                "backdrops": [
                    {"file_path": "/quebec.jpg", "iso_639_1": "fr", "iso_3166_1": "CA", "vote_average": 9},
                    {"file_path": "/tmdb_en.jpg", "iso_639_1": "en", "vote_average": 5},
                ]
            })
        if "webservice.fanart.tv/v3/movies/42" in url:
            return FausseReponse({})
        if "quebec.jpg" in url:
            raise AssertionError("un backdrop tagué langue=fr/pays=CA ne doit jamais être choisi pour le palier français")
        if "tmdb_en.jpg" in url:
            return FausseReponse(content=_image_bytes((50, 50, 50)))
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)
    image = generateur._resoudre_image_tuile(CANDIDAT_FILM)
    assert image is not None  # résolu via le palier anglais, pas via fr/CA


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
            return FausseReponse({"tvthumb": [{"url": "https://fanart.example/tv_thumb_en.jpg", "lang": "en", "likes": "1"}]})
        if "webservice.fanart.tv/v3/tv/77" in url:
            raise AssertionError("Fanart doit être interrogé avec le tvdb_id, pas le tmdb_id")
        if "tv_thumb_en.jpg" in url:
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
# ClientMDBList (clé API simple, pas d'OAuth)
# ---------------------------------------------------------------------------

def test_mdblist_recupere_les_items_d_une_liste_par_user_slug():
    from generer_backdrops import ClientMDBList

    client = ClientMDBList(api_key="fausse-cle-mdblist")

    def fausse_get(url, params=None, timeout=None, **kwargs):
        assert url == "https://api.mdblist.com/lists/dwade/james-bond/items"
        assert params["apikey"] == "fausse-cle-mdblist"
        return FausseReponse({
            "movies": [{"id": 100, "title": "A"}],
            "shows": [{"id": 200, "title": "B"}],
        })

    client.session.get = MagicMock(side_effect=fausse_get)
    items = client.recuperer_items_liste("dwade", "james-bond")
    assert items == [(100, "movie"), (200, "tv")]


def test_mdblist_recupere_les_items_d_une_liste_par_id():
    from generer_backdrops import ClientMDBList

    client = ClientMDBList(api_key="fausse-cle-mdblist")

    def fausse_get(url, params=None, timeout=None, **kwargs):
        assert url == "https://api.mdblist.com/lists/2194/items"
        return FausseReponse({"movies": [{"id": 550}], "shows": []})

    client.session.get = MagicMock(side_effect=fausse_get)
    assert client.recuperer_items_liste_par_id(2194) == [(550, "movie")]


def test_mdblist_par_id_sans_cle_retourne_liste_vide_sans_appel_reseau():
    from generer_backdrops import ClientMDBList

    client = ClientMDBList(api_key=None)

    def fausse_get(*args, **kwargs):
        raise AssertionError("ne devrait jamais être appelé sans clé MDBList")

    client.session.get = MagicMock(side_effect=fausse_get)
    assert client.recuperer_items_liste_par_id(2194) == []


def test_mdblist_par_user_slug_sans_cle_utilise_le_repli_json_public():
    """Sans clé API, la résolution par (user, slug) doit quand même
    fonctionner via l'export JSON public de la liste -- confirmé comme
    méthode d'accès légitime par le développeur de MDBList lui-même."""
    from generer_backdrops import ClientMDBList

    client = ClientMDBList(api_key=None)

    def fausse_get(url, params=None, timeout=None, **kwargs):
        assert url == "https://mdblist.com/lists/dwade/james-bond/json/"
        return FausseReponse({"movies": [{"id": 100}], "shows": []})

    client.session.get = MagicMock(side_effect=fausse_get)
    assert client.recuperer_items_liste("dwade", "james-bond") == [(100, "movie")]


def test_mdblist_repli_json_public_utilise_si_api_officielle_echoue():
    from generer_backdrops import ClientMDBList

    client = ClientMDBList(api_key="fausse-cle-mdblist")
    appels = []

    def fausse_get(url, params=None, timeout=None, **kwargs):
        appels.append(url)
        if "api.mdblist.com" in url:
            return FausseReponse(status_code=500)
        return FausseReponse({"movies": [{"id": 100}], "shows": []})

    client.session.get = MagicMock(side_effect=fausse_get)
    items = client.recuperer_items_liste("dwade", "james-bond")
    assert items == [(100, "movie")]
    assert len(appels) == 2  # API officielle tentée d'abord, puis repli JSON


def test_mdblist_resultats_mis_en_cache():
    from generer_backdrops import ClientMDBList

    client = ClientMDBList(api_key="fausse-cle-mdblist")
    compteur = {"n": 0}

    def fausse_get(*args, **kwargs):
        compteur["n"] += 1
        return FausseReponse({"movies": [{"id": 1}], "shows": []})

    client.session.get = MagicMock(side_effect=fausse_get)
    client.recuperer_items_liste("dwade", "james-bond")
    client.recuperer_items_liste("dwade", "james-bond")
    assert compteur["n"] == 1


def test_mdblist_rechercher_listes_trie_par_nombre_d_items():
    from generer_backdrops import ClientMDBList

    client = ClientMDBList(api_key="fausse-cle-mdblist")

    def fausse_get(url, params=None, timeout=None, **kwargs):
        assert url == "https://api.mdblist.com/lists/search"
        assert params == {"apikey": "fausse-cle-mdblist", "query": "james bond"}
        return FausseReponse([
            {"id": 1, "name": "Petite liste 007", "slug": "petite", "user_name": "a", "items": 5},
            {"id": 2, "name": "Grande liste 007", "slug": "grande", "user_name": "b", "items": 50},
        ])

    client.session.get = MagicMock(side_effect=fausse_get)
    resultats = client.rechercher_listes("james bond")
    assert [r["id"] for r in resultats] == [2, 1]


def test_mdblist_rechercher_listes_sans_cle_retourne_liste_vide():
    from generer_backdrops import ClientMDBList

    client = ClientMDBList(api_key=None)

    def fausse_get(*args, **kwargs):
        raise AssertionError("ne devrait jamais être appelé sans clé MDBList")

    client.session.get = MagicMock(side_effect=fausse_get)
    assert client.rechercher_listes("james bond") == []


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
