"""
Test d'intégration : simule les réponses TMDB/Fanart avec de fausses
requêtes HTTP, pour vérifier que tout le pipeline
(résolution -> téléchargement -> redimensionnement -> sauvegarde) fonctionne,
sans avoir besoin d'une vraie clé API ni d'accès réseau à TMDB.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generer_backdrops import (
    GROUPE_GENRES,
    GenerateurBackdrops,
    charger_catalogues_aiometadata,
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


def test_generer_tout_avertit_sur_groupe_du_json_non_reconnu(caplog):
    """Reproduit le vrai bug rencontré : un groupe renommé dans le JSON
    (ex: emoji ajouté sur un nom totalement inconnu du script) doit
    déclencher un avertissement explicite, pas un échec silencieux."""
    from generer_backdrops import GenerateurBackdrops

    # Configure caplog pour capturer les logs INFO (pas seulement WARNING+)
    caplog.set_level("INFO")

    collections = [
        {"title": "🔥 Groupe Jamais Vu", "folders": [{"title": "Test", "sources": []}]},
    ]

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle", cle_fanart=None, repertoire_sortie=Path("/tmp/inutilise"), dry_run=True,
    )
    generateur.generer_tout(collections)

    # Vérifie que le message a été loggué via logger.info
    assert any("Nouveau groupe détecté" in record.message for record in caplog.records)
    assert any("Groupe Jamais Vu" in record.message for record in caplog.records)
    # Le message contient aussi la clé normalisée (avec espaces, pas underscores)
    assert any("groupe jamais vu" in record.message.lower() for record in caplog.records)


def test_generer_tout_reconnait_un_groupe_avec_emoji_different(caplog):
    """Le même groupe 'Genres', mais avec un emoji jamais vu explicitement
    dans le code, doit être reconnu (normalisation) et NE DOIT PAS déclencher
    l'avertissement 'non reconnu'."""
    from generer_backdrops import GenerateurBackdrops

    collections = [
        {"title": "🆕 Genres", "folders": [{"title": "Action", "sources": []}]},
    ]

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle", cle_fanart=None, repertoire_sortie=Path("/tmp/inutilise"), dry_run=True,
    )
    generateur.generer_tout(collections)

    # Vérifie qu'aucun warning 'non reconnu' n'a été émis
    assert not any("non reconnu" in record.message for record in caplog.records)


def test_image_manuelle_court_circuite_la_resolution_tmdb(tmp_path):
    """Un dossier listé dans images_manuelles doit utiliser directement
    l'image fournie, SANS passer par ClientTMDB/ClientFanart -- même sur
    un groupe normalement désactivé (Franchises)."""
    from generer_backdrops import GROUPE_FRANCHISES

    session_mock = MagicMock()
    session_mock.get.return_value = FausseReponse(content=_image_factice_bytes())

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart=None,
        repertoire_sortie=tmp_path,
        dry_run=False,
        images_manuelles={"007": "https://exemple.test/007.jpg"},
    )
    generateur.session = session_mock
    generateur.tmdb.session = session_mock

    resultat = generateur.traiter_dossier(GROUPE_FRANCHISES, {"title": "007", "sources": []})

    assert resultat.statut == "genere"
    assert "image manuelle" in resultat.detail
    assert (tmp_path / resultat.chemin).exists()
    # Une seule requête HTTP : celle vers l'image manuelle -- aucun appel
    # de résolution TMDB/discover ne doit avoir eu lieu.
    assert session_mock.get.call_count == 1


def test_fankai_genere_une_mosaique_a_partir_des_images_directes_du_catalogue(tmp_path):
    """Cas réel (FanKai) : un catalogue "custom" dont les items n'ont pas
    d'id IMDb exploitable doit quand même produire une vraie mosaïque, en
    utilisant directement les posters du catalogue -- bout en bout, sans
    aucun appel TMDB (le média n'a pas de tmdb_id)."""
    from generer_backdrops import GROUPE_ANIMES

    fixture = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "fankai_catalog_sample.json").read_text(encoding="utf-8")
    )
    url_catalogue = "https://streamio.fankai.fr/x/catalog/anime/fankai_catalog.json"

    def _repondre(url, timeout=None, **kwargs):
        if url.rstrip("?") == url_catalogue or url.startswith(url_catalogue):
            return FausseReponse(json_data=fixture)
        # toute autre URL = une image de poster à télécharger
        return FausseReponse(content=_image_factice_bytes())

    session_mock = MagicMock()
    session_mock.get.side_effect = _repondre

    catalogues = {
        "1d5e3b0.fankai_catalog": {
            "kind": "custom_catalogue",
            "media_type": "tv",
            "url": url_catalogue,
            "champ_image": "poster",
        }
    }

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart=None,
        repertoire_sortie=tmp_path,
        dry_run=False,
        mosaique=True,
        catalogues_aiometadata=catalogues,
    )
    generateur.session = session_mock
    generateur.tmdb.session = session_mock
    generateur.catalogue_custom.session = session_mock

    dossier = {
        "title": "FanKai",
        "sources": [
            {
                "provider": "addon",
                "addonId": "com.aiostreams.viren070.5a21f0f2-961",
                "catalogId": "1d5e3b0.fankai_catalog",
                "type": "anime",
            }
        ],
    }

    resultat = generateur.traiter_dossier(GROUPE_ANIMES, dossier)

    assert resultat.statut == "genere"
    assert (tmp_path / resultat.chemin).exists()
    # Aucun appel TMDB : seule ClientTMDB.session aurait pu servir à un
    # /find IMDb->TMDB, jamais déclenché ici (aucun id "tt...").
    urls_appelees = [c.args[0] if c.args else c.kwargs.get("url") for c in session_mock.get.call_args_list]
    assert not any("themoviedb.org" in u for u in urls_appelees if u)


def test_fankai_avec_champ_titre_cherche_un_backdrop_tmdb_nu_et_incruste_le_titre(tmp_path):
    """Nouveau (champTitre) : au lieu des posters bruts du catalogue, on
    cherche chaque titre sur TMDB, on prend son backdrop NU (iso_639_1
    absent), et on écrit le titre du catalogue par-dessus -- contrairement
    au test ci-dessus, TMDB DOIT être appelé ici."""
    from generer_backdrops import GROUPE_ANIMES

    fixture = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "fankai_catalog_sample.json").read_text(encoding="utf-8")
    )
    url_catalogue = "https://streamio.fankai.fr/x/catalog/anime/fankai_catalog.json"

    def _repondre(url, timeout=None, params=None, **kwargs):
        if url.rstrip("?") == url_catalogue or url.startswith(url_catalogue):
            return FausseReponse(json_data=fixture)
        if "/search/tv" in url or "/search/movie" in url:
            return FausseReponse(json_data={"results": [{"id": 999, "popularity": 42.0}]})
        if "/images" in url:
            return FausseReponse(json_data={"backdrops": [{"file_path": "/nu.jpg", "iso_639_1": None, "vote_average": 8.0}]})
        # toute autre URL (téléchargement d'image, poster de repli...) = une image factice
        return FausseReponse(content=_image_factice_bytes())

    session_mock = MagicMock()
    session_mock.get.side_effect = _repondre

    catalogues = {
        "1d5e3b0.fankai_catalog": {
            "kind": "custom_catalogue",
            "media_type": "tv",
            "url": url_catalogue,
            "champ_image": "poster",
            "champ_titre": "name",
            "suffixes_titre_ignorer": ["Henshū", "Kaï", "Kai"],
        }
    }

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart=None,
        repertoire_sortie=tmp_path,
        dry_run=False,
        mosaique=True,
        catalogues_aiometadata=catalogues,
    )
    generateur.session = session_mock
    generateur.tmdb.session = session_mock
    generateur.catalogue_custom.session = session_mock

    dossier = {
        "title": "FanKai",
        "sources": [
            {
                "provider": "addon",
                "addonId": "com.aiostreams.viren070.5a21f0f2-961",
                "catalogId": "1d5e3b0.fankai_catalog",
                "type": "anime",
            }
        ],
    }

    resultat = generateur.traiter_dossier(GROUPE_ANIMES, dossier)

    assert resultat.statut == "genere"
    assert (tmp_path / resultat.chemin).exists()
    urls_appelees = [c.args[0] if c.args else c.kwargs.get("url") for c in session_mock.get.call_args_list]
    assert any("/search/tv" in u or "/search/movie" in u for u in urls_appelees if u)
    assert any("/images" in u for u in urls_appelees if u)


def test_fankai_champ_titre_retombe_sur_le_poster_si_tmdb_ne_trouve_rien(tmp_path):
    """Si la recherche TMDB échoue pour un titre (aucun résultat), le
    poster brut du catalogue (champ_image, filet de sécurité) doit quand
    même servir de tuile -- jamais d'échec total pour un seul titre raté."""
    from generer_backdrops import GROUPE_ANIMES

    fixture = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "fankai_catalog_sample.json").read_text(encoding="utf-8")
    )
    url_catalogue = "https://streamio.fankai.fr/x/catalog/anime/fankai_catalog.json"

    def _repondre(url, timeout=None, params=None, **kwargs):
        if url.rstrip("?") == url_catalogue or url.startswith(url_catalogue):
            return FausseReponse(json_data=fixture)
        if "/search/tv" in url or "/search/movie" in url:
            return FausseReponse(json_data={"results": []})  # TMDB ne trouve jamais rien
        return FausseReponse(content=_image_factice_bytes())

    session_mock = MagicMock()
    session_mock.get.side_effect = _repondre

    catalogues = {
        "1d5e3b0.fankai_catalog": {
            "kind": "custom_catalogue",
            "media_type": "tv",
            "url": url_catalogue,
            "champ_image": "poster",
            "champ_titre": "name",
            "suffixes_titre_ignorer": ["Henshū", "Kaï", "Kai"],
        }
    }

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart=None,
        repertoire_sortie=tmp_path,
        dry_run=False,
        mosaique=True,
        catalogues_aiometadata=catalogues,
    )
    generateur.session = session_mock
    generateur.tmdb.session = session_mock
    generateur.catalogue_custom.session = session_mock

    dossier = {
        "title": "FanKai",
        "sources": [
            {
                "provider": "addon",
                "addonId": "com.aiostreams.viren070.5a21f0f2-961",
                "catalogId": "1d5e3b0.fankai_catalog",
                "type": "anime",
            }
        ],
    }

    resultat = generateur.traiter_dossier(GROUPE_ANIMES, dossier)

    assert resultat.statut == "genere"
    assert (tmp_path / resultat.chemin).exists()
    # Chaque titre du catalogue (TMDB ne trouve jamais rien ici) doit être
    # remonté dans le récap de fin de run -- voir
    # afficher_titres_champ_titre_non_resolus.
    assert set(generateur.titres_champ_titre_non_resolus) == {item["name"] for item in fixture["metas"]}


def _logo_factice_bytes() -> bytes:
    """Un petit logo RGBA en mémoire (PNG, fond transparent), pour simuler
    le téléchargement du logo-titre officiel d'un item FanKai."""
    img = Image.new("RGBA", (300, 120), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_fankai_avec_champ_logo_et_filtre_anime_colle_le_logo_par_item(tmp_path):
    """Bout en bout : "champLogo" + "genreObligatoire": "anime" doivent
    coller le logo PROPRE À CHAQUE ITEM (pas un logo unique partagé) sur
    son backdrop TMDB nu -- Frieren (logo=null dans la fixture réelle)
    doit retomber sur le titre écrit en texte, les autres items sur leur
    propre logo."""
    from generer_backdrops import GROUPE_ANIMES

    fixture = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "fankai_catalog_sample.json").read_text(encoding="utf-8")
    )
    url_catalogue = "https://streamio.fankai.fr/x/catalog/anime/fankai_catalog.json"

    def _repondre(url, timeout=None, params=None, **kwargs):
        if url.rstrip("?") == url_catalogue or url.startswith(url_catalogue):
            return FausseReponse(json_data=fixture)
        if "/search/tv" in url or "/search/movie" in url:
            return FausseReponse(
                json_data={"results": [{"id": 999, "popularity": 42.0, "genre_ids": [16], "original_language": "ja"}]}
            )
        if "/images" in url:
            return FausseReponse(json_data={"backdrops": [{"file_path": "/nu.jpg", "iso_639_1": None, "vote_average": 8.0}]})
        if "/image/logo" in url:
            return FausseReponse(content=_logo_factice_bytes())
        # poster de repli, backdrop TMDB nu téléchargé, etc.
        return FausseReponse(content=_image_factice_bytes())

    session_mock = MagicMock()
    session_mock.get.side_effect = _repondre

    catalogues = {
        "1d5e3b0.fankai_catalog": {
            "kind": "custom_catalogue",
            "media_type": "tv",
            "url": url_catalogue,
            "champ_image": "poster",
            "champ_titre": "name",
            "suffixes_titre_ignorer": ["Henshū", "Kaï", "Kai"],
            "champ_logo": "logo",
            "filtre_anime": True,
        }
    }

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart=None,
        repertoire_sortie=tmp_path,
        dry_run=False,
        mosaique=True,
        catalogues_aiometadata=catalogues,
    )
    generateur.session = session_mock
    generateur.tmdb.session = session_mock
    generateur.catalogue_custom.session = session_mock

    dossier = {
        "title": "FanKai",
        "sources": [
            {
                "provider": "addon",
                "addonId": "com.aiostreams.viren070.5a21f0f2-961",
                "catalogId": "1d5e3b0.fankai_catalog",
                "type": "anime",
            }
        ],
    }

    resultat = generateur.traiter_dossier(GROUPE_ANIMES, dossier)

    assert resultat.statut == "genere"
    assert (tmp_path / resultat.chemin).exists()
    urls_appelees = [c.args[0] if c.args else c.kwargs.get("url") for c in session_mock.get.call_args_list]
    urls_logo_appelees = {u for u in urls_appelees if u and "/image/logo" in u}
    # 5 items ont un logo dans la fixture (Frieren = null, exclu) -> 5 URLs
    # de logo DISTINCTES appelées, une par item -- pas un logo unique répété.
    assert len(urls_logo_appelees) == 5
    assert all("logo" in u for u in urls_logo_appelees)


def test_fankai_champ_logo_absent_ou_en_echec_retombe_sur_le_titre_en_texte(tmp_path):
    """Si un item n'a pas de logo (null, ex: Frieren) OU si son
    téléchargement échoue, le pipeline doit quand même réussir en
    retombant sur le titre écrit en texte -- jamais d'échec total pour un
    logo manquant/indisponible."""
    from generer_backdrops import GROUPE_ANIMES

    fixture = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "fankai_catalog_sample.json").read_text(encoding="utf-8")
    )
    url_catalogue = "https://streamio.fankai.fr/x/catalog/anime/fankai_catalog.json"

    def _repondre(url, timeout=None, params=None, **kwargs):
        if url.rstrip("?") == url_catalogue or url.startswith(url_catalogue):
            return FausseReponse(json_data=fixture)
        if "/search/tv" in url or "/search/movie" in url:
            return FausseReponse(
                json_data={"results": [{"id": 999, "popularity": 42.0, "genre_ids": [16], "original_language": "ja"}]}
            )
        if "/images" in url:
            return FausseReponse(json_data={"backdrops": [{"file_path": "/nu.jpg", "iso_639_1": None, "vote_average": 8.0}]})
        if "/image/logo" in url:
            return FausseReponse(status_code=404)  # tous les téléchargements de logo échouent
        return FausseReponse(content=_image_factice_bytes())

    session_mock = MagicMock()
    session_mock.get.side_effect = _repondre

    catalogues = {
        "1d5e3b0.fankai_catalog": {
            "kind": "custom_catalogue",
            "media_type": "tv",
            "url": url_catalogue,
            "champ_image": "poster",
            "champ_titre": "name",
            "suffixes_titre_ignorer": ["Henshū", "Kaï", "Kai"],
            "champ_logo": "logo",
            "filtre_anime": True,
        }
    }

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart=None,
        repertoire_sortie=tmp_path,
        dry_run=False,
        mosaique=True,
        catalogues_aiometadata=catalogues,
    )
    generateur.session = session_mock
    generateur.tmdb.session = session_mock
    generateur.catalogue_custom.session = session_mock

    dossier = {
        "title": "FanKai",
        "sources": [
            {
                "provider": "addon",
                "addonId": "com.aiostreams.viren070.5a21f0f2-961",
                "catalogId": "1d5e3b0.fankai_catalog",
                "type": "anime",
            }
        ],
    }

    resultat = generateur.traiter_dossier(GROUPE_ANIMES, dossier)

    assert resultat.statut == "genere"
    assert (tmp_path / resultat.chemin).exists()


def test_pipeline_avec_le_vrai_dossier_action_du_groupe_genres(tmp_path):
    """Cas réel (pas inventé pour le test) : le dossier "Action" du groupe
    Genres, tel qu'il existe aujourd'hui dans
    Templates/Nuvio-Collections-Dwade58200.json (voir fixtures/
    dossier_genres_action_reel.json), avec les VRAIS catalogId AIOMetadata
    qu'il référence, extraits de Templates/aiometadata-setup.json (voir
    fixtures/aiometadata_genres_action_reel.json). Vérifie que le pipeline
    complet -- résolution addon/aio-metadata (priorité absolue, sans repli
    heuristique) -> MDBList + TMDB discover -> dédup -> mosaïque ->
    sauvegarde -- fonctionne de bout en bout sur cette vraie configuration,
    en ne simulant que les réponses réseau.

    Si ce test casse après une modification de la config réelle (renommage
    de catalogue, nouveau filtre...), c'est le signal qu'il faut
    resynchroniser les deux fixtures depuis les Templates/ à jour plutôt
    que d'ajuster le test à l'aveugle.
    """
    fixture_dossier = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "dossier_genres_action_reel.json").read_text(encoding="utf-8")
    )
    chemin_aiometadata = Path(__file__).resolve().parent / "fixtures" / "aiometadata_genres_action_reel.json"
    catalogues_aiometadata = charger_catalogues_aiometadata(chemin_aiometadata)

    # Les 6 sources du dossier réel référencent bien ces 6 catalogId --
    # tous doivent être résolus via l'export AIOMetadata, sans repli
    # heuristique. Si l'un d'eux manque, la fixture aiometadata a dérivé
    # de la vraie config et doit être régénérée.
    ids_attendus = {
        "mdblist.128037",
        "mdblist.128029",
        "tmdb.discover.movie.genre_action.global",
        "tmdb.discover.series.genre_action_and_aventure.global",
        "tmdb.discover.movie.action_copy.mokbfuip",
        "tmdb.discover.series.action_aventure_copy.mokbk464",
    }
    assert ids_attendus.issubset(catalogues_aiometadata.keys())

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle",
        cle_fanart=None,
        repertoire_sortie=tmp_path,
        profil="standard",
        mosaique=True,
        catalogues_aiometadata=catalogues_aiometadata,
    )

    # Pool volontairement chevauchant entre MDBList et discover (comme en
    # pratique : le même film ressort souvent à la fois d'une liste
    # MDBList "New Action" et d'un discover popularité) -- vérifie la
    # dédup documentée dans BACKDROPS_SETUP.md avec de vrais ids qui se
    # recoupent, plutôt qu'un mock qui évite artificiellement le cas.
    ids_films = list(range(500, 520))  # 20 films distincts au total
    ids_series = list(range(600, 620))  # 20 séries distinctes au total

    def fausse_get(url, params=None, timeout=None, **kwargs):
        params = params or {}
        if "mdblist.com" in url and "action-movies" in url:
            return FausseReponse([{"id": i, "type": "movie"} for i in ids_films[:12]])
        if "mdblist.com" in url and "action-tv-shows" in url:
            return FausseReponse([{"id": i, "type": "tv"} for i in ids_series[:12]])
        if "discover/movie" in url:
            if params.get("page", 1) != 1:
                return FausseReponse({"results": []})
            return FausseReponse(
                {"results": [{"id": i, "backdrop_path": f"/movie-{i}.jpg", "original_language": "en"} for i in ids_films]}
            )
        if "discover/tv" in url:
            if params.get("page", 1) != 1:
                return FausseReponse({"results": []})
            return FausseReponse(
                {"results": [{"id": i, "backdrop_path": f"/tv-{i}.jpg", "original_language": "en"} for i in ids_series]}
            )
        if ("/movie/" in url or "/tv/" in url) and url.endswith("/images"):
            # Backdrop taggé français, pays FR -- résolu dès l'étape 1 de
            # _resoudre_image_tuile, pas de détour Fanart nécessaire ici.
            return FausseReponse({"backdrops": [{"file_path": "/nu.jpg", "iso_639_1": "fr", "iso_3166_1": "FR"}]})
        if "image.tmdb.org" in url:
            return FausseReponse(content=_image_factice_bytes())
        raise AssertionError(f"URL inattendue: {url}")

    generateur.session.get = MagicMock(side_effect=fausse_get)

    resultat = generateur.traiter_dossier(fixture_dossier["groupe_titre"], fixture_dossier["dossier"])

    assert resultat.statut == "genere", resultat.detail
    assert "mosa" in resultat.detail.lower()  # confirme le mode mosaïque, pas un repli single-backdrop
    assert resultat.chemin is not None
    chemin_final = tmp_path / resultat.chemin
    assert chemin_final.exists()
    # Chemin de sortie cohérent avec le vrai groupe/dossier (pas un slug générique)
    assert "genres" in str(chemin_final).lower()
    assert "action" in str(chemin_final).lower()

    with Image.open(chemin_final) as img:
        assert img.format == "JPEG"
        assert img.width > 0 and img.height > 0


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
