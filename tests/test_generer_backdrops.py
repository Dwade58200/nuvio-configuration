# -*- coding: utf-8 -*-
"""
Tests unitaires pour scripts/generer_backdrops.py

Aucun de ces tests n'appelle le réseau : on teste uniquement la logique de
résolution/mapping, qui est la partie la plus fragile (et celle qui
contenait le bug initial sur les titres de groupes).

Lancer avec : pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generer_backdrops import (  # noqa: E402
    GROUPE_GENRES,
    GROUPE_SPORTS,
    GROUPE_STREAMING,
    GROUPE_DECOUVRIR,
    GROUPE_FRANCHISES,
    _mapper_filtres_discover,
    _extraire_slug_thematique,
    _resoudre_genre_depuis_texte,
    construire_requetes,
    dossier_actif,
    slugifier,
    normaliser,
)


# ---------------------------------------------------------------------------
# Le bug historique : mapping des titres de groupes
# ---------------------------------------------------------------------------

def test_titres_groupes_correspondent_au_vrai_json():
    """Ce sont les titres RÉELS observés dans Nuvio-Collections-Dwade58200.json.
    S'ils changent dans le JSON, ce test doit échouer pour qu'on le remarque."""
    assert GROUPE_GENRES == "🎭Genres"  # PAS d'espace après l'emoji
    assert GROUPE_STREAMING == "🎬Services de Streaming"  # PAS d'espace
    assert GROUPE_FRANCHISES == "Franchises"  # PAS d'emoji
    assert GROUPE_SPORTS == "Sports"  # PAS d'emoji


def test_sports_streaming_et_franchises_sont_desactives():
    assert dossier_actif(GROUPE_SPORTS, "Football") is False
    assert dossier_actif(GROUPE_STREAMING, "Netflix") is False
    assert dossier_actif(GROUPE_FRANCHISES, "007") is False
    assert dossier_actif(GROUPE_FRANCHISES, "28 Jours Collection") is False


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


def test_source_trakt_est_ignoree():
    dossier = {
        "title": "007",
        "sources": [{"provider": "trakt", "traktListId": 11754060, "mediaType": "MOVIE"}],
    }
    requetes, ignorees = construire_requetes(GROUPE_FRANCHISES, dossier)
    assert requetes == []
    assert "trakt" in ignorees[0]


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


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
