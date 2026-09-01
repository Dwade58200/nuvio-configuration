"""
Tests unitaires pour scripts/generer_backdrops.py

Aucun de ces tests n'appelle le réseau : on teste uniquement la logique de
résolution/mapping, qui est la partie la plus fragile (et celle qui
contenait le bug initial sur les titres de groupes).

Lancer avec : pytest tests/ -v
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generer_backdrops import (  # noqa: E402
    GROUPE_DECOUVRIR,
    GROUPE_FRANCHISES,
    GROUPE_GENRES,
    GROUPE_SPORTS,
    GROUPE_STREAMING,
    GROUPE_THEMATIQUES,
    GROUPE_VIBES,
    ClientMDBList,
    ClientTMDB,
    _extraire_slug_thematique,
    _mapper_filtres_discover,
    _resoudre_genre_depuis_texte,
    analyser_url_mdblist,
    charger_catalogues_aiometadata,
    charger_collections,
    construire_requetes,
    dossier_actif,
    meilleur_backdrop_tmdb_langue,
    normaliser,
    slugifier,
)

# ---------------------------------------------------------------------------
# Le bug historique : mapping des titres de groupes
# ---------------------------------------------------------------------------

def test_titres_groupes_reconnus_quelle_que_soit_la_variante_emoji():
    """Historique : le JSON Nuvio a changé les emojis/espaces des titres de
    groupes à deux reprises déjà (ex: "🎭Genres" -> "🎭 Genres",
    "Vibe" -> "🎭 Vibe", "Franchises" -> "🎞️ Franchises",
    "Sports" -> "🏃‍♂️ Sports"). Les constantes GROUPE_* sont des clés
    NORMALISÉES : ce test vérifie que toutes les variantes connues
    (anciennes et nouvelles) normalisent bien vers la même clé, pour ne
    plus jamais se faire surprendre par un simple changement d'emoji."""
    variantes_genres = ["🎭Genres", "🎭 Genres", "genres", "Genres"]
    variantes_streaming = ["🎬Services de Streaming", "🎬 Services de Streaming"]
    variantes_vibes = ["Vibe", "🎭 Vibe", "✨ Vibe"]
    variantes_franchises = ["Franchises", "🎞️ Franchises"]
    variantes_sports = ["Sports", "🏃‍♂️ Sports"]

    for variante in variantes_genres:
        assert normaliser(variante) == GROUPE_GENRES, variante
    for variante in variantes_streaming:
        assert normaliser(variante) == GROUPE_STREAMING, variante
    for variante in variantes_vibes:
        assert normaliser(variante) == GROUPE_VIBES, variante
    for variante in variantes_franchises:
        assert normaliser(variante) == GROUPE_FRANCHISES, variante
    for variante in variantes_sports:
        assert normaliser(variante) == GROUPE_SPORTS, variante


def test_groupe_inconnu_normalise_vers_une_cle_absente_de_criteres_groupes():
    """Un titre de groupe complètement différent (pas juste un emoji en
    plus) doit rester non reconnu -- la normalisation ne doit pas
    'deviner' au-delà de emoji/accents/espaces."""
    from generer_backdrops import CRITERES_GROUPES

    assert normaliser("Un Groupe Totalement Inconnu") not in CRITERES_GROUPES


def test_sports_et_franchises_sont_desactives():
    assert dossier_actif(GROUPE_SPORTS, "Football") is False
    assert dossier_actif(GROUPE_FRANCHISES, "007") is False
    assert dossier_actif(GROUPE_FRANCHISES, "28 Jours Collection") is False


def test_streaming_est_maintenant_actif():
    """Certains catalogues Streaming sont désormais résolubles via TMDB
    (réseaux TF1/M6, ou repli popularité générique) -> le groupe est actif."""
    assert dossier_actif(GROUPE_STREAMING, "Netflix") is True


def test_genres_tous_actifs():
    assert dossier_actif(GROUPE_GENRES, "Action") is True
    assert dossier_actif(GROUPE_GENRES, "Comédie") is True


def test_decouvrir_filtre_inclusion_exclusion():
    assert dossier_actif(GROUPE_DECOUVRIR, "Tendance") is True
    assert dossier_actif(GROUPE_DECOUVRIR, "Populaire") is True
    assert dossier_actif(GROUPE_DECOUVRIR, "Tendance TV") is False  # exclu
    assert dossier_actif(GROUPE_DECOUVRIR, "Autre chose") is False  # pas dans inclure


# ---------------------------------------------------------------------------
# Slugs
# ---------------------------------------------------------------------------

def test_slugifier_accents_et_espaces():
    assert slugifier("Comédie") == "comedie"
    assert slugifier("28 Jours Collection") == "28-jours-collection"
    assert slugifier("Chasse au trésor") == "chasse-au-tresor"
    assert slugifier("") == "sans-titre"


def test_normaliser_est_stable_sur_emoji():
    assert normaliser("🎭Genres") == "genres"


# ---------------------------------------------------------------------------
# Mapping des filtres discover (camelCase JSON -> paramètres TMDB)
# ---------------------------------------------------------------------------

def test_mapper_filtres_discover_movie():
    filtres = {
        "withGenres": "35,10749",
        "voteCountGte": 500,
        "releaseDateGte": "2020-01-01",
        "releaseDateLte": "2029-12-31",
        "voteAverageGte": 5,
        "voteAverageLte": 9,
    }
    params = _mapper_filtres_discover(filtres, "movie")
    assert params["with_genres"] == "35,10749"
    assert params["vote_count.gte"] == 500
    assert params["primary_release_date.gte"] == "2020-01-01"
    assert params["primary_release_date.lte"] == "2029-12-31"
    assert params["vote_average.gte"] == 5
    assert params["vote_average.lte"] == 9


def test_mapper_filtres_discover_tv_utilise_first_air_date():
    filtres = {"releaseDateGte": "2020-01-01"}
    params = _mapper_filtres_discover(filtres, "tv")
    assert params["first_air_date.gte"] == "2020-01-01"
    assert "primary_release_date.gte" not in params


def test_mapper_filtres_ignore_les_valeurs_none():
    filtres = {"withGenres": None, "voteCountGte": None, "year": None}
    params = _mapper_filtres_discover(filtres, "movie")
    assert params == {}


# ---------------------------------------------------------------------------
# Extraction du mot-clé thématique depuis un catalogId
# ---------------------------------------------------------------------------

def test_extraire_slug_thematique():
    assert _extraire_slug_thematique("tmdb.discover.movie.theme.coming-of-age") == "coming of age"
    assert _extraire_slug_thematique("tmdb.discover.series.theme.martial-arts") == "martial arts"
    assert _extraire_slug_thematique("tmdb.trending_movie") is None


def test_resoudre_genre_depuis_texte():
    assert _resoudre_genre_depuis_texte("tmdb.discover.movie.genre_action.global") == (28, 10759)
    assert _resoudre_genre_depuis_texte("Comédie") == (35, 35)
    assert _resoudre_genre_depuis_texte("catalogue-inconnu-xyz") is None


# ---------------------------------------------------------------------------
# construire_requetes : cas réels tirés du JSON de l'utilisateur
# ---------------------------------------------------------------------------

def test_source_tmdb_collection():
    dossier = {
        "title": "28 Jours Collection",
        "sources": [
            {"provider": "tmdb", "tmdbSourceType": "COLLECTION", "tmdbId": 1565, "mediaType": "MOVIE"}
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_FRANCHISES, dossier)
    assert len(requetes) == 1
    assert requetes[0].kind == "collection"
    assert requetes[0].tmdb_id == 1565
    assert ignorees == []


def test_source_tmdb_discover():
    dossier = {
        "title": "Réconfort",
        "sources": [
            {
                "provider": "tmdb",
                "tmdbSourceType": "DISCOVER",
                "mediaType": "MOVIE",
                "sortBy": "popularity.desc",
                "filters": {"withGenres": "35,10749", "voteCountGte": 500},
            }
        ],
    }
    requetes, ignorees = construire_requetes("Vibe", dossier)
    assert len(requetes) == 1
    assert requetes[0].kind == "discover"
    assert requetes[0].params["with_genres"] == "35,10749"


def test_source_francaise_exclue_seul_le_catalogue_global_est_garde():
    """Cas réel : 'Populaire' a deux sources DISCOVER par media type, une
    globale et une filtrée withOriginalLanguage=fr -> seule la globale
    doit produire une requête."""
    dossier = {
        "title": "Populaire",
        "sources": [
            {
                "provider": "tmdb",
                "tmdbSourceType": "DISCOVER",
                "mediaType": "MOVIE",
                "sortBy": "popularity.desc",
                "filters": {},  # catalogue global (pas de withOriginalLanguage)
            },
            {
                "provider": "tmdb",
                "tmdbSourceType": "DISCOVER",
                "mediaType": "MOVIE",
                "sortBy": "popularity.desc",
                "filters": {"withOriginalLanguage": "fr"},  # variante France -> à exclure
            },
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_DECOUVRIR, dossier)
    assert len(requetes) == 1
    assert "with_original_language" not in requetes[0].params
    assert any("langue-spécifique exclue" in raison for raison in ignorees)


def test_source_francaise_seule_ne_laisse_aucune_requete_tmdb():
    """Si un dossier n'a QUE une source française (pas de globale), elle est
    quand même exclue -- même s'il ne reste alors plus de requête TMDB pour
    cette source (d'autres sources du dossier, ex: addon, peuvent compenser)."""
    dossier = {
        "title": "Top",
        "sources": [
            {
                "provider": "tmdb",
                "tmdbSourceType": "DISCOVER",
                "mediaType": "MOVIE",
                "sortBy": "popularity.desc",
                "filters": {"withOriginalLanguage": "fr"},
            }
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_DECOUVRIR, dossier)
    assert requetes == []
    assert any("langue-spécifique exclue" in raison for raison in ignorees)


def test_source_trakt_est_toujours_explicitement_ignoree():
    """Trakt n'est pas pris en charge (abonnement VIP requis pour créer une
    application) -- toute source `provider: "trakt"` doit rester ignorée,
    avec une raison explicite, jamais une tentative de résolution."""
    dossier = {
        "title": "007",
        "sources": [{"provider": "trakt", "traktListId": 11754060, "mediaType": "MOVIE"}],
    }
    requetes, ignorees = construire_requetes(GROUPE_FRANCHISES, dossier)
    assert requetes == []
    assert len(ignorees) == 1
    assert "trakt" in ignorees[0].lower()
    assert "non pris en charge" in ignorees[0]


# ---------------------------------------------------------------------------
# Passerelle MDBList (clé API simple sans OAuth)
# ---------------------------------------------------------------------------

def test_analyser_url_mdblist_formats_courants():
    assert analyser_url_mdblist("https://mdblist.com/lists/dwade/james-bond") == ("dwade", "james-bond")
    assert analyser_url_mdblist("https://www.mdblist.com/lists/dwade/james-bond/") == ("dwade", "james-bond")
    assert analyser_url_mdblist("mdblist.com/lists/dwade/james-bond/json/") == ("dwade", "james-bond")


def test_analyser_url_mdblist_url_invalide_retourne_none():
    assert analyser_url_mdblist("https://example.com/pas-une-liste") is None
    assert analyser_url_mdblist("") is None


def test_source_mdblist_avec_url_produit_une_requete_mdblist_liste():
    dossier = {
        "title": "007",
        "sources": [{"provider": "mdblist", "mdblistUrl": "https://mdblist.com/lists/dwade/james-bond"}],
    }
    requetes, ignorees = construire_requetes(GROUPE_FRANCHISES, dossier)
    assert len(requetes) == 1
    assert requetes[0].kind == "mdblist_liste"
    assert requetes[0].params == {"mdblist_user": "dwade", "mdblist_slug": "james-bond"}
    assert ignorees == []


def test_source_mdblist_avec_id_numerique_produit_une_requete_mdblist_liste():
    dossier = {"title": "X", "sources": [{"provider": "mdblist", "mdblistId": 2194}]}
    requetes, ignorees = construire_requetes(GROUPE_GENRES, dossier)
    assert len(requetes) == 1
    assert requetes[0].kind == "mdblist_liste"
    assert requetes[0].params == {"mdblist_id": 2194}


def test_source_mdblist_avec_user_et_slug_explicites():
    dossier = {
        "title": "X",
        "sources": [{"provider": "mdblist", "mdblistUser": "dwade", "mdblistSlug": "james-bond"}],
    }
    requetes, ignorees = construire_requetes(GROUPE_GENRES, dossier)
    assert len(requetes) == 1
    assert requetes[0].params == {"mdblist_user": "dwade", "mdblist_slug": "james-bond"}


def test_source_mdblist_sans_identifiant_est_ignoree():
    dossier = {"title": "Y", "sources": [{"provider": "mdblist"}]}
    requetes, ignorees = construire_requetes(GROUPE_DECOUVRIR, dossier)
    assert requetes == []
    assert "mdblist" in ignorees[0]


def test_mdblist_items_depuis_reponse_format_dict_movies_shows():
    reponse = {
        "movies": [{"id": 550, "title": "Fight Club"}],
        "shows": [{"id": 1396, "title": "Breaking Bad"}],
    }
    assert ClientMDBList._items_depuis_reponse(reponse) == [(550, "movie"), (1396, "tv")]


def test_mdblist_items_depuis_reponse_format_liste_plate():
    reponse = [{"id": 550, "mediatype": "movie"}, {"id": 1396, "mediatype": "show"}]
    assert ClientMDBList._items_depuis_reponse(reponse) == [(550, "movie"), (1396, "tv")]


def test_mdblist_items_depuis_reponse_ignore_items_sans_id():
    reponse = {"movies": [{"title": "Sans id TMDB"}], "shows": []}
    assert ClientMDBList._items_depuis_reponse(reponse) == []


def test_mdblist_sans_cle_api_par_id_retourne_liste_vide_sans_exception():
    """Sans clé API, la résolution par id numérique ne peut pas fonctionner
    (l'export JSON public nécessite de connaître user+slug) -- doit
    échouer proprement, jamais lever d'exception."""
    client = ClientMDBList(api_key=None)
    assert client.recuperer_items_liste_par_id(2194) == []


def test_genre_sans_source_directe_utilise_repli_titre():
    """Cas réel : le dossier 'Action' n'a QUE des sources addon non résolues,
    mais on doit quand même réussir via le repli sur le titre."""
    dossier = {
        "title": "Action",
        "sources": [
            {"provider": "addon", "addonId": "aio-metadata", "catalogId": "trakt.list.33123064", "type": "movie"},
            {
                "provider": "addon",
                "addonId": "aio-metadata",
                "catalogId": "tmdb.discover.movie.action_copy.mokbfuip",
                "type": "movie",
            },
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_GENRES, dossier)
    assert len(requetes) >= 1
    assert requetes[0].kind == "discover"
    assert requetes[0].params.get("with_genres") == 28  # Action (film)


def test_thematique_extrait_mot_cle():
    dossier = {
        "title": "Arts martiaux",
        "sources": [
            {
                "provider": "addon",
                "addonId": "aio-metadata",
                "catalogId": "tmdb.discover.movie.theme.martial-arts",
                "type": "movie",
            }
        ],
    }
    requetes, ignorees = construire_requetes("🎨 Thématiques", dossier)
    assert len(requetes) == 1
    assert requetes[0].params["__keyword_search__"] == "martial arts"


def test_catalogid_statique_trending():
    dossier = {
        "title": "Tendance",
        "sources": [
            {"provider": "addon", "addonId": "aio-metadata", "catalogId": "tmdb.trending_movie", "type": "movie"}
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_DECOUVRIR, dossier)
    assert len(requetes) == 1
    assert requetes[0].kind == "endpoint"
    assert requetes[0].endpoint == "/trending/movie/week"


def test_source_sitcom_reelle_fournie_par_utilisateur():
    """Cas réel : source TMDB DISCOVER avec un mot-clé (Sitcom, keyword
    193171), fournie telle quelle par l'utilisateur en remplacement d'une
    source Trakt indisponible."""
    dossier = {
        "title": "Sitcom",
        "sources": [
            {
                "title": "Sitcom",
                "sortBy": "popularity.desc",
                "tmdbId": None,
                "filters": {"voteCountGte": 50, "withKeywords": "193171"},
                "provider": "tmdb",
                "mediaType": "TV",
                "tmdbSourceType": "DISCOVER",
            }
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_THEMATIQUES, dossier)
    assert len(requetes) == 1
    assert requetes[0].kind == "discover"
    assert requetes[0].media_type == "tv"
    assert requetes[0].params["with_keywords"] == "193171"
    assert requetes[0].params["vote_count.gte"] == 50
    assert ignorees == []


def test_catalogid_reseau_tf1_m6_resolu_via_with_networks():
    dossier = {
        "title": "TF1",
        "sources": [
            {
                "provider": "addon",
                "addonId": "aio-metadata",
                "catalogId": "tmdb.discover.series.m6_et_tf1.mofqqcct",
                "type": "series",
            }
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_STREAMING, dossier)
    assert len(requetes) == 1
    assert requetes[0].kind == "discover"
    assert requetes[0].media_type == "tv"
    ids = set(requetes[0].params["with_networks"].split(","))
    assert ids == {"290", "712"}  # TF1 et M6


def test_catalogid_streaming_generique_replie_sur_popularite():
    """Cas réel : 'Netflix' a un catalogue tmdb.discover.* dont le nom
    ('global', 'populaire_copy...') ne porte plus l'info de plateforme ->
    repli sur popularité globale plutôt que rien."""
    dossier = {
        "title": "Netflix",
        "sources": [
            {
                "provider": "addon",
                "addonId": "aio-metadata",
                "catalogId": "tmdb.discover.movie.global_copy.mt49lz6m",
                "type": "movie",
            }
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_STREAMING, dossier)
    assert len(requetes) == 1
    assert requetes[0].kind == "discover"
    assert requetes[0].media_type == "movie"
    assert requetes[0].params == {"sort_by": "popularity.desc"}


def test_catalogid_non_tmdb_reste_ignore():
    """Un catalogue FlixPatrol (pas de préfixe tmdb.discover.) doit rester
    non résolu -- le repli générique ne doit pas tout accepter."""
    dossier = {
        "title": "Netflix",
        "sources": [
            {"provider": "addon", "addonId": "aio-metadata", "catalogId": "flixpatrol.netflix.fr.movie", "type": "movie"}
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_STREAMING, dossier)
    assert requetes == []
    assert "non résolu" in ignorees[0]


# ---------------------------------------------------------------------------
# Export AIOMetadata : résolution avec les VRAIS filtres TMDB
# ---------------------------------------------------------------------------

FIXTURE_AIOMETADATA = Path(__file__).resolve().parent / "fixtures" / "aiometadata-exemple.json"
FIXTURE_AIOMETADATA_LEGACY = Path(__file__).resolve().parent / "fixtures" / "aiometadata-exemple-legacy-plat.json"


def test_charger_catalogues_aiometadata():
    """Régression du bug réel : le vrai export AIOMetadata (version 2.15.0)
    range ses catalogues sous `config.catalogs`, pas à la racine du JSON --
    l'ancien code (`data.get("catalogs")`) y lisait silencieusement un
    index VIDE. Cette fixture reproduit la structure réelle."""
    catalogues = charger_catalogues_aiometadata(FIXTURE_AIOMETADATA)
    # catalogues avec une config "discover" exacte -> indexés en kind="discover"
    assert "tmdb.discover.movie.global.mt49lr48" in catalogues
    assert catalogues["tmdb.discover.movie.global.mt49lr48"]["kind"] == "discover"
    assert catalogues["tmdb.discover.movie.global.mt49lr48"]["media_type"] == "movie"
    assert catalogues["tmdb.discover.movie.global_copy.mt49lz6m"]["media_type"] == "tv"  # "series" normalisé en "tv"
    # catalogues sans config discover ET sans source mdblist exploitable -> exclus
    assert "trakt.watchlist" not in catalogues
    assert "tmdb.top" not in catalogues
    # mdblist.102554 n'a pas de metadata.url exportée -> pas résolvable, donc exclu
    assert "mdblist.102554" not in catalogues
    # mdblist "recommandation" personnalisée : jamais d'URL publique -> exclu
    assert "mdblist.recommended.recommended.movies" not in catalogues


def test_charger_catalogues_aiometadata_indexe_les_listes_mdblist_avec_url():
    """Cas réel corrigé : un catalogue `source: "mdblist"` AVEC une URL de
    liste publique exportée (ex: "Sitcom" -> mdblist.37087) doit être
    indexé en kind="mdblist", exploitable ensuite par construire_requetes."""
    catalogues = charger_catalogues_aiometadata(FIXTURE_AIOMETADATA)
    assert "mdblist.37087" in catalogues
    assert catalogues["mdblist.37087"] == {
        "kind": "mdblist",
        "media_type": "tv",
        "mdblist_url": "https://mdblist.com/lists/polynomialproton/top-sitcoms",
    }


def test_charger_catalogues_aiometadata_accepte_aussi_l_ancien_format_a_plat():
    """Compatibilité ascendante : un export où `catalogs` est à la racine
    (sans niveau `config`) doit continuer à fonctionner."""
    catalogues = charger_catalogues_aiometadata(FIXTURE_AIOMETADATA_LEGACY)
    assert "tmdb.discover.movie.genre_horreur.global" in catalogues
    assert catalogues["tmdb.discover.movie.genre_horreur.global"]["params"]["with_genres"] == "27"


def test_charger_catalogues_aiometadata_fichier_absent():
    assert charger_catalogues_aiometadata(None) == {}
    assert charger_catalogues_aiometadata(Path("/chemin/inexistant.json")) == {}


def test_catalogue_aiometadata_prime_sur_repli_generique():
    """Cas réel : Netflix a un catalogueId opaque ('global.mt49lr48') --
    sans export, on retombe en générique ; AVEC l'export, on doit obtenir
    le VRAI filtre with_watch_providers=8 (Netflix), pas un repli."""
    catalogues = charger_catalogues_aiometadata(FIXTURE_AIOMETADATA)
    dossier = {
        "title": "Netflix",
        "sources": [
            {"provider": "addon", "addonId": "aio-metadata", "catalogId": "tmdb.discover.movie.global.mt49lr48", "type": "movie"}
        ],
    }

    # Sans export : repli générique (aucun filtre plateforme)
    requetes_sans, _ = construire_requetes(GROUPE_STREAMING, dossier)
    assert requetes_sans[0].params == {"sort_by": "popularity.desc"}

    # Avec export : le vrai filtre Netflix (watch_providers=8)
    requetes_avec, ignorees_avec = construire_requetes(GROUPE_STREAMING, dossier, catalogues)
    assert len(requetes_avec) == 1
    assert requetes_avec[0].media_type == "movie"
    assert requetes_avec[0].params["with_watch_providers"] == "8"
    assert requetes_avec[0].params["watch_region"] == "FR"
    assert ignorees_avec == []


def test_catalogue_aiometadata_tf1_avec_genre_et_provider():
    catalogues = charger_catalogues_aiometadata(FIXTURE_AIOMETADATA)
    dossier = {
        "title": "TF1",
        "sources": [
            {"provider": "addon", "addonId": "aio-metadata", "catalogId": "tmdb.discover.series.m6_et_tf1.mofqqcct", "type": "series"}
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_STREAMING, dossier, catalogues)
    assert len(requetes) == 1
    assert requetes[0].media_type == "tv"
    assert requetes[0].params["with_watch_providers"] == "1754"
    assert requetes[0].params["with_genres"] == "10764"


def test_catalogue_aiometadata_resout_placeholder_date():
    catalogues = charger_catalogues_aiometadata(FIXTURE_AIOMETADATA)
    dossier = {
        "title": "Action",
        "sources": [
            {"provider": "addon", "addonId": "aio-metadata", "catalogId": "tmdb.discover.movie.genre_action.global", "type": "movie"}
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_GENRES, dossier, catalogues)
    assert len(requetes) == 1
    valeur_date = requetes[0].params["release_date.lte"]
    assert valeur_date == date.today().isoformat()  # résolu à l'exécution, pas figé dans l'export


def test_catalogue_absent_de_l_export_retombe_sur_heuristique():
    """Un catalogId qui n'est PAS dans l'export doit continuer à utiliser
    les replis heuristiques existants (genre/thème/générique), sans planter."""
    catalogues = charger_catalogues_aiometadata(FIXTURE_AIOMETADATA)
    dossier = {
        "title": "Comédie",
        "sources": [
            {"provider": "addon", "addonId": "aio-metadata", "catalogId": "tmdb.discover.movie.genre_comedie.absent_de_export", "type": "movie"}
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_GENRES, dossier, catalogues)
    assert len(requetes) == 1
    assert requetes[0].params.get("with_genres") == 35  # repli heuristique par genre, toujours actif


def test_catalogue_mdblist_de_l_export_produit_une_requete_mdblist_liste():
    """Cas réel corrigé : "Sitcom" (catalogId mdblist.37087, ajouté via
    l'addon aio-metadata, PAS via une source provider="mdblist" manuelle)
    doit maintenant se résoudre grâce à l'URL publique de l'export."""
    catalogues = charger_catalogues_aiometadata(FIXTURE_AIOMETADATA)
    dossier = {
        "title": "Sitcom",
        "sources": [{"provider": "addon", "addonId": "aio-metadata", "catalogId": "mdblist.37087", "type": "series"}],
    }
    requetes, ignorees = construire_requetes(GROUPE_THEMATIQUES, dossier, catalogues)
    assert len(requetes) == 1
    assert requetes[0].kind == "mdblist_liste"
    assert requetes[0].media_type == "tv"
    assert requetes[0].params == {"mdblist_user": "polynomialproton", "mdblist_slug": "top-sitcoms"}
    assert ignorees == []


def test_catalogue_mdblist_sans_export_reste_ignore():
    """Sans export fourni (ou catalogue absent de l'export), un catalogId
    'mdblist.<id>' opaque ne peut pas être deviné par heuristique -> reste
    explicitement ignoré, jamais une exception."""
    dossier = {
        "title": "Sitcom",
        "sources": [{"provider": "addon", "addonId": "aio-metadata", "catalogId": "mdblist.37087", "type": "series"}],
    }
    requetes, ignorees = construire_requetes(GROUPE_THEMATIQUES, dossier)
    assert requetes == []
    assert "non résolu" in ignorees[0]


def test_catalogue_mdblist_recommandation_personnalisee_reste_ignoree_avec_raison_claire():
    """"Recommandation" (mdblist.recommended.*) n'a jamais d'URL publique
    exportée (liste personnalisée liée au compte) -- doit rester ignoré,
    mais avec un message explicite plutôt que le générique "non résolu"."""
    catalogues = charger_catalogues_aiometadata(FIXTURE_AIOMETADATA)
    dossier = {
        "title": "Recommandation",
        "sources": [
            {
                "provider": "addon",
                "addonId": "aio-metadata",
                "catalogId": "mdblist.recommended.recommended.movies",
                "type": "movie",
            }
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_DECOUVRIR, dossier, catalogues)
    assert requetes == []
    assert "personnalisée" in ignorees[0]


def test_trakt_recommendations_ne_sont_plus_reconnues():
    """Retiré à la demande de l'utilisateur (compte secondaire sans
    historique -> recommandations non pertinentes). Doit rester ignoré,
    comme n'importe quel autre catalogue addon non résolu."""
    dossier = {
        "title": "Recommandation",
        "sources": [
            {"provider": "addon", "addonId": "aio-metadata", "catalogId": "trakt.recommendations.movies", "type": "movie"},
            {"provider": "addon", "addonId": "aio-metadata", "catalogId": "trakt.recommendations.shows", "type": "series"},
        ],
    }
    requetes, ignorees = construire_requetes(GROUPE_DECOUVRIR, dossier)
    assert requetes == []
    assert len(ignorees) == 2
    assert all("non résolu" in raison for raison in ignorees)


# ---------------------------------------------------------------------------
# Architecture de sortie : dossiers français + noms de fichiers personnalisés
# ---------------------------------------------------------------------------

def test_groupe_slugs_sont_en_francais():
    from generer_backdrops import GROUPE_SLUGS, NOM_DOSSIER_BACKDROPS, NOM_DOSSIER_RACINE

    assert NOM_DOSSIER_RACINE == "Collections"
    assert NOM_DOSSIER_BACKDROPS == "Backdrops"
    assert GROUPE_SLUGS[GROUPE_GENRES] == "Genres"
    assert GROUPE_SLUGS[GROUPE_STREAMING] == "Services de Streaming"
    assert GROUPE_SLUGS[GROUPE_THEMATIQUES] == "Thematiques"
    assert GROUPE_SLUGS[GROUPE_VIBES] == "Vibes"
    assert GROUPE_SLUGS[GROUPE_FRANCHISES] == "Franchises"
    assert GROUPE_SLUGS[GROUPE_SPORTS] == "Sports"
    assert GROUPE_SLUGS[GROUPE_DECOUVRIR] == "Decouvertes"


def test_noms_backdrop_personnalises_exacts():
    """Vérifie exactement les 15 correspondances demandées."""
    from generer_backdrops import nom_fichier_backdrop

    correspondances = {
        "Sci-Fi": "Sci-Fi_Backdrop",
        "Apple TV+": "Apple_TV_Backdrop",
        "Canal+": "Canal+_Backdrop",
        "TF1": "TF1_Backdrop",
        "HBO Max": "HBO_Max_Backdrop",
        "Prime Video": "Prime_Video_Backdrop",
        "Disney+": "Disney+_Backdrop",
        "Arts martiaux": "Arts_Martiaux_Backdrop",
        "Chasse au trésor": "Chasse_au_Tresor_Backdrop",
        "Comédie Romantique": "Comedie_Romantique_Backdrop",
        "Grands réalisateurs du cinéma": "Grands_Realisateurs_Backdrop",
        "Inspiré de faits réels": "Faits_Reels_Backdrop",
        "Super-Héros": "Super-Heros_Backdrop",
        "Voyage Temporel": "Voyage_Temporel_Backdrop",
        "Retournent le cerveau": "Retournent_Cerveau_Backdrop",
    }
    for titre, attendu in correspondances.items():
        assert nom_fichier_backdrop(titre) == attendu, titre


def test_nom_fichier_backdrop_generique_pour_titre_non_liste():
    """Un titre qui n'est PAS dans la table personnalisée doit quand même
    produire un nom raisonnable automatiquement."""
    from generer_backdrops import nom_fichier_backdrop

    assert nom_fichier_backdrop("Action") == "Action_Backdrop"
    assert nom_fichier_backdrop("Comédie") == "Comedie_Backdrop"  # accent retiré
    assert nom_fichier_backdrop("Guerre") == "Guerre_Backdrop"


def test_nom_fichier_backdrop_generique_met_les_sigles_connus_en_majuscules():
    from generer_backdrops import nom_fichier_backdrop

    # Un futur titre contenant "TV" ou "M6" non listé explicitement doit
    # quand même avoir le sigle en majuscules automatiquement.
    assert nom_fichier_backdrop("Nouvelle Chaine M6") == "Nouvelle_Chaine_M6_Backdrop"


def test_chemin_backdrop_complet_utilise_la_nouvelle_arborescence():
    """Test d'intégration léger : vérifie le chemin complet généré pour un
    dossier réel, avec la nouvelle arborescence française."""
    from generer_backdrops import GenerateurBackdrops

    generateur = GenerateurBackdrops(
        cle_tmdb="x", cle_fanart=None, repertoire_sortie=Path("/tmp/inutilise"), dry_run=True
    )
    resultat = generateur.traiter_dossier(
        GROUPE_GENRES,
        {
            "title": "Sci-Fi",
            "sources": [
                {
                    "provider": "tmdb",
                    "tmdbSourceType": "DISCOVER",
                    "mediaType": "MOVIE",
                    "sortBy": "popularity.desc",
                    "filters": {"withGenres": "878"},
                }
            ],
        },
    )
    assert resultat.chemin == "Genres/Backdrops/Sci-Fi_Backdrop.jpg"


# ---------------------------------------------------------------------------
# meilleur_backdrop_tmdb_langue (fonction pure, cascade de résolution TMDB)
# ---------------------------------------------------------------------------

def test_meilleur_backdrop_tmdb_langue_retourne_le_mieux_note_pour_la_langue_demandee():
    images_data = {
        "backdrops": [
            {"iso_639_1": "fr", "vote_average": 5.0, "file_path": "/moins-bon-fr.jpg"},
            {"iso_639_1": "fr", "vote_average": 8.2, "file_path": "/meilleur-fr.jpg"},
            {"iso_639_1": "en", "vote_average": 9.9, "file_path": "/meilleur-en.jpg"},
        ]
    }
    assert meilleur_backdrop_tmdb_langue(images_data, "fr") == "/meilleur-fr.jpg"
    assert meilleur_backdrop_tmdb_langue(images_data, "en") == "/meilleur-en.jpg"


def test_meilleur_backdrop_tmdb_langue_untagged_correspond_a_langue_none():
    images_data = {"backdrops": [{"iso_639_1": None, "vote_average": 3.0, "file_path": "/sans-langue.jpg"}]}
    assert meilleur_backdrop_tmdb_langue(images_data, None) == "/sans-langue.jpg"


def test_meilleur_backdrop_tmdb_langue_aucun_candidat_retourne_none():
    images_data = {"backdrops": [{"iso_639_1": "en", "vote_average": 9.0, "file_path": "/x.jpg"}]}
    assert meilleur_backdrop_tmdb_langue(images_data, "de") is None
    assert meilleur_backdrop_tmdb_langue(None, "fr") is None
    assert meilleur_backdrop_tmdb_langue({}, "fr") is None


def test_meilleur_backdrop_tmdb_langue_correspondance_stricte_jamais_de_variante_regionale():
    """À la demande explicite : "fr" ne doit JAMAIS matcher "fr-CA" (ni
    aucune autre variante régionale), dans aucune circonstance."""
    images_data = {"backdrops": [{"iso_639_1": "fr-CA", "vote_average": 7.0, "file_path": "/quebec.jpg"}]}
    assert meilleur_backdrop_tmdb_langue(images_data, "fr") is None
    assert meilleur_backdrop_tmdb_langue(images_data, None) is None


class _FausseReponseHTTP:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FausseSessionHTTP:
    """Capture les paramètres envoyés, sans jamais toucher au réseau."""

    def __init__(self, payload):
        self.derniers_params = None
        self._payload = payload

    def get(self, url, params=None, timeout=None):
        self.derniers_params = params
        return _FausseReponseHTTP(self._payload)


def test_recuperer_images_ne_demande_jamais_fr_ca_a_tmdb():
    """À la demande explicite : fr-CA ne doit plus jamais être demandé ni
    utilisé, dans aucune situation."""
    fausse_session = _FausseSessionHTTP({"backdrops": []})
    client = ClientTMDB(cle_api="fake", session=fausse_session)

    client.recuperer_images(124364, "tv", langue_originale="en")

    langues_demandees = fausse_session.derniers_params["include_image_language"].split(",")
    assert "fr-CA" not in langues_demandees
    assert "fr" in langues_demandees
    assert "en" in langues_demandees


def test_recuperer_images_ajoute_la_langue_originale_si_differente_de_fr_et_en():
    """Cas 'drama coréen' : la langue originale du titre doit être demandée
    explicitement à TMDB (sinon l'API la filtre côté serveur), pour pouvoir
    servir de repli texté après fr/en (palier "natif")."""
    fausse_session = _FausseSessionHTTP({"backdrops": []})
    client = ClientTMDB(cle_api="fake", session=fausse_session)

    client.recuperer_images(999, "tv", langue_originale="ko")

    langues_demandees = fausse_session.derniers_params["include_image_language"].split(",")
    assert "ko" in langues_demandees
    assert "fr" in langues_demandees
    assert "en" in langues_demandees


def test_recuperer_images_n_ajoute_pas_de_doublon_si_langue_originale_est_fr_ou_en():
    fausse_session = _FausseSessionHTTP({"backdrops": []})
    client = ClientTMDB(cle_api="fake", session=fausse_session)

    client.recuperer_images(1622, "tv", langue_originale="en")

    langues_demandees = fausse_session.derniers_params["include_image_language"].split(",")
    assert langues_demandees.count("en") == 1


# ---------------------------------------------------------------------------
# charger_collections
# ---------------------------------------------------------------------------

def test_charger_collections_lit_le_json_des_groupes(tmp_path):
    chemin = tmp_path / "collections.json"
    donnees = [{"title": "🎭 Genres", "folders": [{"title": "Action", "sources": []}]}]
    chemin.write_text(json.dumps(donnees), encoding="utf-8")

    resultat = charger_collections(chemin)

    assert resultat == donnees


def test_charger_collections_fichier_absent_leve_une_erreur_claire(tmp_path):
    try:
        charger_collections(tmp_path / "inexistant.json")
        raise AssertionError("aurait dû lever FileNotFoundError")
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
