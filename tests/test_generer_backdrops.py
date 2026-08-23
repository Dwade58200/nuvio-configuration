# -*- coding: utf-8 -*-
"""
Tests unitaires pour scripts/generer_backdrops.py

Aucun de ces tests n'appelle le réseau : on teste uniquement la logique de
résolution/mapping, qui est la partie la plus fragile (et celle qui
contenait le bug initial sur les titres de groupes).

Lancer avec : pytest tests/ -v
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generer_backdrops import (  # noqa: E402
    GROUPE_GENRES,
    GROUPE_SPORTS,
    GROUPE_STREAMING,
    GROUPE_DECOUVRIR,
    GROUPE_FRANCHISES,
    GROUPE_VIBES,
    GROUPE_THEMATIQUES,
    _mapper_filtres_discover,
    _extraire_slug_thematique,
    _resoudre_genre_depuis_texte,
    charger_catalogues_aiometadata,
    construire_requetes,
    dossier_actif,
    slugifier,
    normaliser,
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


def test_source_trakt_avec_liste_produit_une_requete_trakt_liste():
    dossier = {
        "title": "007",
        "sources": [{"provider": "trakt", "traktListId": 11754060, "mediaType": "MOVIE"}],
    }
    requetes, ignorees = construire_requetes(GROUPE_FRANCHISES, dossier)
    assert len(requetes) == 1
    assert requetes[0].kind == "trakt_liste"
    assert requetes[0].tmdb_id == 11754060
    assert requetes[0].media_type == "movie"
    assert ignorees == []


def test_source_trakt_sans_liste_est_ignoree():
    dossier = {
        "title": "Recommandation",
        "sources": [{"provider": "trakt", "mediaType": "MOVIE"}],  # pas de traktListId
    }
    requetes, ignorees = construire_requetes(GROUPE_DECOUVRIR, dossier)
    assert requetes == []
    assert "traktListId" in ignorees[0]


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


def test_charger_catalogues_aiometadata():
    catalogues = charger_catalogues_aiometadata(FIXTURE_AIOMETADATA)
    # seuls les catalogues avec une config "discover" exacte sont indexés
    assert "tmdb.discover.movie.global.mt49lr48" in catalogues
    assert catalogues["tmdb.discover.movie.global.mt49lr48"]["media_type"] == "movie"
    assert catalogues["tmdb.discover.movie.global_copy.mt49lz6m"]["media_type"] == "tv"  # "series" normalisé en "tv"
    # les catalogues sans config discover (trakt/mdblist/tmdb.top statique) sont exclus
    assert "trakt.watchlist" not in catalogues
    assert "mdblist.102554" not in catalogues
    assert "tmdb.top" not in catalogues


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


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
