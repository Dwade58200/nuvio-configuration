#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generer_backdrops.py
=====================

Génère les images de fond (backdrops) des collections Nuvio à partir du
fichier `Templates/Nuvio-Collections-Dwade58200.json`, en s'inspirant du
pipeline de luckynumb3rs (stremio-perfect-setup).

PHASE 1 (fondations) :
-----------------------
Pour chaque dossier (folder) de collection, le script essaie, DANS CET ORDRE,
de résoudre une source TMDB fiable :

  1. Sources directement typées `provider: "tmdb"` déjà présentes dans le
     JSON (COLLECTION, DISCOVER, DIRECTOR) -> aucune ambiguïté, ce sont des
     appels TMDB "prêts à l'emploi".
  2. Sources `provider: "addon", addonId: "aio-metadata"` dont le
     `catalogId` correspond à un endpoint TMDB générique connu
     (tendances / populaire / les mieux notés).
  3. Repli (fallback) heuristique pour les groupes "Genres" et
     "Thématiques" : le nom du dossier / le suffixe du catalogId est
     rapproché d'un genre TMDB connu, ou utilisé comme recherche de
     mot-clé TMDB (endpoint /search/keyword) pour les thématiques.

Tout ce qui n'est pas résoluble (Trakt sans clé API, FlixPatrol, Sports,
etc.) est explicitement IGNORÉ et journalisé avec la raison -- jamais
échoué en silence. Ces cas seront traités dans une phase ultérieure.

Ce choix "honnête" fait qu'au lancement, certains dossiers n'auront pas
de backdrop généré : c'est normal et voulu pour cette phase. Le résumé
final indique précisément combien de dossiers sont dans ce cas et pourquoi.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import io
import json
import logging
import math
import re
import sys
import threading
import time
import unicodedata
from datetime import date as _date
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import requests
except ImportError:  # pragma: no cover
    print("Le paquet 'requests' est requis : pip install requests", file=sys.stderr)
    raise

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("Le paquet 'Pillow' est requis : pip install Pillow", file=sys.stderr)
    raise

import mosaique as mosaique_module  # module compagnon, scripts/mosaique.py


# ---------------------------------------------------------------------------
# Configuration générale
# ---------------------------------------------------------------------------

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
FANART_API_BASE = "https://webservice.fanart.tv/v3"
TRAKT_API_BASE = "https://api.trakt.tv"

# Le pipeline traite plusieurs dossiers en parallèle (--parallelisme), et
# chacun télécharge en plus ses tuiles en parallèle (jusqu'à 12 threads) --
# soit potentiellement plusieurs dizaines de requêtes HTTP simultanées vers
# les mêmes hôtes (TMDB, Fanart, Trakt). Le pool de connexions par défaut de
# `requests`/urllib3 (10 par hôte) est trop petit pour ça et produit un flot
# d'avertissements "Connection pool is full, discarding connection" -- sans
# gravité (les connexions sont juste recréées au lieu d'être réutilisées),
# mais évitable en élargissant le pool une bonne fois pour toutes ici.


def creer_session_http() -> requests.Session:
    """Session HTTP partagée entre threads, avec un pool de connexions assez
    large pour la concurrence réelle du pipeline (voir commentaire ci-dessus)."""
    session = requests.Session()
    adaptateur = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=50)
    session.mount("https://", adaptateur)
    session.mount("http://", adaptateur)
    return session

# Titres EXACTS des groupes tels qu'ils existent réellement dans le JSON.
# (le bug initial venait d'un mauvais mapping ici -> corrigé, puis reproduit
# une seconde fois quand Nuvio a ajouté/changé des emojis sur les groupes)
#
# Pour ne PLUS jamais casser sur un simple changement d'emoji, d'espace ou
# d'accent, ces constantes sont des clés CANONIQUES et NORMALISÉES (voir
# `normaliser()` plus bas) : le titre réel du groupe, tel qu'il apparaît
# dans le JSON, est toujours normalisé avant comparaison. Exemple :
# "🎭Genres", "🎭 Genres" et "🎭  Genres " normalisent tous en "genres".
GROUPE_DECOUVRIR = "decouvrir"
GROUPE_STREAMING = "services de streaming"
GROUPE_GENRES = "genres"
GROUPE_THEMATIQUES = "thematiques"
GROUPE_VIBES = "vibe"
GROUPE_ANNEES = "annees"
GROUPE_FRANCHISES = "franchises"
GROUPE_SPORTS = "sports"

# Certains dossiers ont, en plus d'une source TMDB "globale" (withOriginalLanguage
# absent), une source dupliquée filtrée sur une langue précise (ex: catalogues
# "🇫🇷 France" avec withOriginalLanguage="fr"). Sur demande explicite, on ne
# conserve que les catalogues mondiaux/globaux -> ces sources langue-spécifique
# sont exclues pour éviter les quasi-doublons et le biais vers un seul pays.
LANGUES_SOURCES_EXCLUES = {"fr"}

# Slug de sortie (chemin sur disque / URL jsDelivr), aligné sur la
# convention déjà utilisée par luckynumb3rs pour rester cohérent.
GROUPE_SLUGS: dict[str, str] = {
    GROUPE_DECOUVRIR: "discover",
    GROUPE_STREAMING: "streaming",
    GROUPE_GENRES: "genres",
    GROUPE_THEMATIQUES: "themes",
    GROUPE_VIBES: "vibes",
    GROUPE_ANNEES: "decades",
    GROUPE_FRANCHISES: "franchises",
    GROUPE_SPORTS: "sports",
}

# Groupes activés pour la génération en Phase 1, et filtres optionnels de
# titres de dossiers (inclusion/exclusion). None = tous les dossiers.
@dataclass(frozen=True)
class CritereGroupe:
    actif: bool
    inclure: tuple[str, ...] | None = None
    exclure: tuple[str, ...] | None = None


CRITERES_GROUPES: dict[str, CritereGroupe] = {
    GROUPE_DECOUVRIR: CritereGroupe(
        actif=True,
        inclure=("Recommandation", "Tendance", "Populaire", "Top"),
        exclure=("TV", "Magnet"),
    ),
    GROUPE_STREAMING: CritereGroupe(actif=True),  # certains catalogues sont désormais résolubles via TMDB
    GROUPE_GENRES: CritereGroupe(actif=True),
    GROUPE_THEMATIQUES: CritereGroupe(actif=True),
    GROUPE_VIBES: CritereGroupe(actif=True),
    GROUPE_ANNEES: CritereGroupe(actif=True),
    GROUPE_FRANCHISES: CritereGroupe(actif=False),  # désactivé à la demande de l'utilisateur
    GROUPE_SPORTS: CritereGroupe(actif=False),  # pas de backdrop pour le sport
}

# Endpoints TMDB génériques (pas besoin de filtres) pour les catalogId
# "addon/aio-metadata" les plus courants.
CATALOGID_VERS_ENDPOINT: dict[str, tuple[str, str]] = {
    # catalogId -> (media_type, endpoint)
    "tmdb.trending_movie": ("movie", "/trending/movie/week"),
    "tmdb.trending_series": ("tv", "/trending/tv/week"),
    "tmdb.top_movie": ("movie", "/movie/popular"),
    "tmdb.top_series": ("tv", "/tv/popular"),
    "tmdb.top_rated_movie": ("movie", "/movie/top_rated"),
    "tmdb.top_rated_series": ("tv", "/tv/top_rated"),
}

# Genres TMDB connus : clé normalisée -> (id_film, id_serie_ou_None)
GENRE_TMDB_IDS: dict[str, tuple[int, int | None]] = {
    "action": (28, 10759),
    "animation": (16, 16),
    "aventure": (12, 10759),
    "adventure": (12, 10759),
    "comedie": (35, 35),
    "comedy": (35, 35),
    "policier": (80, 80),
    "crime": (80, 80),
    "documentaire": (99, 99),
    "documentaires": (99, 99),
    "documentary": (99, 99),
    "drame": (18, 18),
    "drama": (18, 18),
    "familial": (10751, 10751),
    "family": (10751, 10751),
    "fantastique": (14, 10765),
    "fantasy": (14, 10765),
    "histoire": (36, None),
    "history": (36, None),
    "horreur": (27, None),
    "horror": (27, None),
    "musique": (10402, None),
    "music": (10402, None),
    "mystere": (9648, 9648),
    "mystery": (9648, 9648),
    "romance": (10749, None),
    "science-fiction": (878, 10765),
    "scifi": (878, 10765),
    "sci-fi": (878, 10765),
    "sciencefiction": (878, 10765),
    "thriller": (53, None),
    "guerre": (10752, 10768),
    "war": (10752, 10768),
    "western": (37, 37),
}

# Chaînes TV françaises connues (pour les catalogues "Streaming" liés à un
# diffuseur plutôt qu'à une plateforme SVOD) -> id de réseau TMDB.
# Vérifiés manuellement sur themoviedb.org/network/{id}.
NETWORK_TMDB_IDS: dict[str, int] = {
    "tf1": 290,
    "m6": 712,
}


def _resoudre_reseaux_depuis_texte(texte: str) -> list[int]:
    """Détecte les chaînes connues mentionnées dans un texte (ex: un
    catalogId comme 'tmdb.discover.series.m6_et_tf1...') et retourne la
    liste (dédupliquée, dans l'ordre de détection) des id de réseau TMDB
    correspondants."""
    trouves: list[int] = []
    for token in normaliser(texte).split():
        id_reseau = NETWORK_TMDB_IDS.get(token)
        if id_reseau and id_reseau not in trouves:
            trouves.append(id_reseau)
    return trouves

# Correspondance des filtres "camelCase" du JSON Nuvio vers les paramètres
# TMDB /discover (certains dépendent du media_type movie/tv).
def _mapper_filtres_discover(filtres: dict[str, Any], media_type: str) -> dict[str, Any]:
    """Convertit le dict `filters` du JSON Nuvio en paramètres /discover TMDB."""
    if not filtres:
        return {}

    params: dict[str, Any] = {}
    prefixe_date = "primary_release_date" if media_type == "movie" else "first_air_date"

    mapping_simple = {
        "withGenres": "with_genres",
        "voteCountGte": "vote_count.gte",
        "voteAverageGte": "vote_average.gte",
        "voteAverageLte": "vote_average.lte",
        "withKeywords": "with_keywords",
        "withCompanies": "with_companies",
        "withNetworks": "with_networks",
        "withOriginCountry": "with_origin_country",
        "withOriginalLanguage": "with_original_language",
        "withWatchProviders": "with_watch_providers",
        "watchRegion": "watch_region",
    }
    for cle_source, cle_tmdb in mapping_simple.items():
        valeur = filtres.get(cle_source)
        if valeur not in (None, "", []):
            params[cle_tmdb] = valeur

    if filtres.get("releaseDateGte"):
        params[f"{prefixe_date}.gte"] = filtres["releaseDateGte"]
    if filtres.get("releaseDateLte"):
        params[f"{prefixe_date}.lte"] = filtres["releaseDateLte"]
    if filtres.get("year"):
        params["year" if media_type == "movie" else "first_air_date_year"] = filtres["year"]

    return params


# ---------------------------------------------------------------------------
# Utilitaires texte / slugs
# ---------------------------------------------------------------------------

def normaliser(texte: str) -> str:
    """minuscule, sans accents, sans emoji/ponctuation -> pour comparaisons."""
    if not texte:
        return ""
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = texte.lower()
    texte = re.sub(r"[^a-z0-9]+", " ", texte).strip()
    return texte


def slugifier(texte: str) -> str:
    """Convertit un titre en slug utilisable dans un chemin de fichier / URL."""
    base = normaliser(texte)
    slug = re.sub(r"\s+", "-", base).strip("-")
    return slug or "sans-titre"


# ---------------------------------------------------------------------------
# Résolution des requêtes TMDB à partir des `sources` d'un dossier
# ---------------------------------------------------------------------------

@dataclass
class RequeteTMDB:
    kind: str  # "collection" | "discover" | "endpoint" | "person"
    media_type: str = "movie"
    endpoint: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    tmdb_id: int | None = None


def _resoudre_genre_depuis_texte(texte: str) -> tuple[int, int | None] | None:
    cle = normaliser(texte).replace(" ", "")
    if cle in GENRE_TMDB_IDS:
        return GENRE_TMDB_IDS[cle]
    # recherche par sous-mot (ex: "genre_action_and_aventure" contient "action")
    mots = normaliser(texte).split()
    for mot in mots:
        if mot in GENRE_TMDB_IDS:
            return GENRE_TMDB_IDS[mot]
    return None


def _extraire_slug_thematique(catalog_id: str) -> str | None:
    """`tmdb.discover.movie.theme.coming-of-age` -> "coming of age" """
    m = re.search(r"\.theme\.([a-z0-9-]+)$", catalog_id or "")
    if not m:
        return None
    return m.group(1).replace("-", " ").replace("_", " ").strip()


# ---------------------------------------------------------------------------
# Export AIOMetadata (optionnel) : mapping catalogId -> VRAIS filtres TMDB
# ---------------------------------------------------------------------------

def _resoudre_placeholder_date(valeur: Any) -> Any:
    """AIOMetadata encode certaines dates comme '__tmdb_date__:today:to'
    (résolu côté addon au moment de l'appel) -- on le remplace par la date
    du jour, calculée à l'exécution du script (pas celle figée dans
    l'export, qui serait obsolète)."""
    if isinstance(valeur, str) and valeur.startswith("__tmdb_date__:today"):
        return _date.today().isoformat()
    return valeur


def charger_catalogues_aiometadata(chemin: "Path | None") -> dict[str, dict[str, Any]]:
    """Charge un export AIOMetadata (Réglages -> Export dans l'addon) et
    construit un index {catalogId: {"media_type", "params"}} pour les
    catalogues de type "discover" qui ont une config TMDB exacte exportée
    -- permet de résoudre un catalogue (ex: Streaming, Genres...) avec les
    VRAIS filtres plutôt qu'une heuristique de repli à partir du nom.
    Retourne un dict vide si le fichier est absent/invalide (aucune erreur)."""
    if not chemin:
        return {}
    try:
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    index: dict[str, dict[str, Any]] = {}
    for entree in data.get("catalogs", []) or []:
        discover = ((entree.get("metadata") or {}).get("discover")) or {}
        params = discover.get("params")
        media_type_brut = discover.get("mediaType")
        catalog_id = entree.get("id")
        if not (catalog_id and params and media_type_brut):
            continue
        media_type = "tv" if media_type_brut in ("tv", "series") else "movie"
        index[catalog_id] = {"media_type": media_type, "params": dict(params)}
    return index


def construire_requetes(
    groupe_titre: str, dossier: dict[str, Any], catalogues_aiometadata: dict[str, dict[str, Any]] | None = None
) -> tuple[list[RequeteTMDB], list[str]]:
    """
    Retourne (requetes_resolues, raisons_ignorees).
    `raisons_ignorees` liste les sources qu'on n'a pas su traiter (pour le log).
    """
    requetes: list[RequeteTMDB] = []
    ignorees: list[str] = []

    for source in dossier.get("sources", []) or []:
        provider = source.get("provider")

        if provider == "tmdb":
            media_type = "movie" if source.get("mediaType") == "MOVIE" else "tv"
            type_source = source.get("tmdbSourceType")

            if type_source == "COLLECTION" and source.get("tmdbId"):
                requetes.append(RequeteTMDB(kind="collection", tmdb_id=source["tmdbId"]))
            elif type_source == "DISCOVER":
                filtres = source.get("filters") or {}
                langue_source = (filtres.get("withOriginalLanguage") or "").lower()
                if langue_source in LANGUES_SOURCES_EXCLUES:
                    ignorees.append(f"source langue-spécifique exclue ({langue_source}) -- catalogue global conservé")
                    continue
                params = _mapper_filtres_discover(filtres, media_type)
                requetes.append(
                    RequeteTMDB(
                        kind="discover",
                        media_type=media_type,
                        params={**params, "sort_by": source.get("sortBy") or "popularity.desc"},
                    )
                )
            elif type_source == "DIRECTOR" and source.get("tmdbId"):
                requetes.append(
                    RequeteTMDB(
                        kind="discover",
                        media_type="movie",
                        params={"with_crew": source["tmdbId"], "sort_by": "popularity.desc"},
                    )
                )
            else:
                ignorees.append(f"tmdb/{type_source or '?'} sans identifiant exploitable")

        elif provider == "addon" and source.get("addonId") == "aio-metadata":
            catalog_id = source.get("catalogId") or ""
            media_type = "movie" if source.get("type") == "movie" else "tv"

            # Priorité absolue : si un export AIOMetadata a été fourni et
            # connaît ce catalogue exact, on utilise ses VRAIS filtres TMDB
            # plutôt qu'une heuristique de repli à partir du nom/hash.
            info_aiometadata = (catalogues_aiometadata or {}).get(catalog_id)
            if info_aiometadata:
                params_reels = {
                    cle: _resoudre_placeholder_date(valeur) for cle, valeur in info_aiometadata["params"].items()
                }
                params_reels.setdefault("sort_by", "popularity.desc")
                requetes.append(
                    RequeteTMDB(kind="discover", media_type=info_aiometadata["media_type"], params=params_reels)
                )
                continue

            if catalog_id in ("trakt.recommendations.movies", "trakt.recommendations.shows"):
                media_type_reco = "movie" if catalog_id.endswith("movies") else "tv"
                requetes.append(RequeteTMDB(kind="trakt_recommandations", media_type=media_type_reco))
                continue

            if catalog_id in CATALOGID_VERS_ENDPOINT:
                mt, endpoint = CATALOGID_VERS_ENDPOINT[catalog_id]
                requetes.append(RequeteTMDB(kind="endpoint", media_type=mt, endpoint=endpoint))
                continue

            # Repli thématiques : mot-clé TMDB à partir du suffixe du catalogId
            slug_theme = _extraire_slug_thematique(catalog_id)
            if slug_theme:
                requetes.append(
                    RequeteTMDB(
                        kind="discover",
                        media_type=media_type,
                        params={"__keyword_search__": slug_theme, "sort_by": "popularity.desc"},
                    )
                )
                continue

            # Repli genres : on tente d'extraire un nom de genre du catalogId
            genre = _resoudre_genre_depuis_texte(catalog_id)
            if genre:
                genre_id = genre[0] if media_type == "movie" else genre[1]
                if genre_id:
                    requetes.append(
                        RequeteTMDB(
                            kind="discover",
                            media_type=media_type,
                            params={"with_genres": genre_id, "sort_by": "popularity.desc"},
                        )
                    )
                    continue

            # Repli chaînes TV françaises (ex: catalogues "Streaming" liés à
            # TF1/M6 plutôt qu'à une vraie plateforme SVOD)
            reseaux = _resoudre_reseaux_depuis_texte(catalog_id)
            if reseaux and media_type == "tv":
                requetes.append(
                    RequeteTMDB(
                        kind="discover",
                        media_type="tv",
                        params={"with_networks": ",".join(str(r) for r in reseaux), "sort_by": "popularity.desc"},
                    )
                )
                continue

            # Dernier repli : un catalogue clairement rattaché à TMDB (préfixe
            # "tmdb.discover.") mais dont on n'arrive à déduire ni genre, ni
            # thématique, ni chaîne -> popularité globale, sans filtre. C'est
            # le cas de plusieurs catalogues "Streaming" (Netflix, Prime,
            # HBO...) dont le nom ("global", "populaire_copy...") ne porte
            # plus l'info de plateforme d'origine -- mieux vaut un contenu
            # populaire générique que rien du tout.
            if catalog_id.startswith("tmdb.discover."):
                requetes.append(
                    RequeteTMDB(kind="discover", media_type=media_type, params={"sort_by": "popularity.desc"})
                )
                continue

            ignorees.append(f"addon/aio-metadata catalogId non résolu ({catalog_id})")

        elif provider == "trakt":
            trakt_list_id = source.get("traktListId")
            if trakt_list_id:
                media_type_trakt = "movie" if source.get("mediaType") == "MOVIE" else "tv"
                requetes.append(RequeteTMDB(kind="trakt_liste", media_type=media_type_trakt, tmdb_id=trakt_list_id))
            else:
                ignorees.append("trakt sans traktListId exploitable")
        else:
            ignorees.append(f"provider non géré ({provider})")

    # Repli final si AUCUNE source n'a donné de requête exploitable :
    # pour les groupes Genres / Thématiques, on tente de deviner à partir
    # du TITRE du dossier lui-même (ex: dossier "Action" -> genre Action).
    if not requetes and normaliser(groupe_titre) in (GROUPE_GENRES,):
        genre = _resoudre_genre_depuis_texte(dossier.get("title", ""))
        if genre:
            for media_type, genre_id in (("movie", genre[0]), ("tv", genre[1])):
                if genre_id:
                    requetes.append(
                        RequeteTMDB(
                            kind="discover",
                            media_type=media_type,
                            params={"with_genres": genre_id, "sort_by": "popularity.desc"},
                        )
                    )
        if requetes:
            ignorees.append("résolu via repli sur le titre du dossier (genre)")

    return requetes, ignorees


def dossier_actif(groupe_titre: str, dossier_titre: str) -> bool:
    critere = CRITERES_GROUPES.get(normaliser(groupe_titre))
    if critere is None or not critere.actif:
        return False
    if critere.inclure and not any(mot.lower() in dossier_titre.lower() for mot in critere.inclure):
        return False
    if critere.exclure and any(mot.lower() in dossier_titre.lower() for mot in critere.exclure):
        return False
    return True


# ---------------------------------------------------------------------------
# Client TMDB / Fanart
# ---------------------------------------------------------------------------

class ClientTMDB:
    def __init__(
        self,
        cle_api: str,
        session: requests.Session | None = None,
        langue: str = "fr-FR",
        limite_appels_images: int = 300,
    ):
        self.cle_api = cle_api
        self.session = session or creer_session_http()
        self.langue = langue
        self._cache_keyword: dict[str, int | None] = {}
        self._cache_images: dict[tuple[int, str], dict[str, Any]] = {}
        self._cache_tvdb_id: dict[int, int | None] = {}
        self.limite_appels_images = limite_appels_images
        self.compteur_appels_images = 0
        self.budget_images_epuise = False  # exposé pour le résumé final (log utilisateur)
        # Ce client est partagé entre plusieurs threads (traitement de dossiers
        # en parallèle, chacun téléchargeant lui-même ses tuiles en parallèle) :
        # sans verrou, le compteur de budget peut être légèrement dépassé avant
        # que la limite soit détectée, et deux threads peuvent rater le cache
        # au même instant et refaire le même appel en double.
        self._verrou = threading.Lock()

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = dict(params or {})
        params["api_key"] = self.cle_api
        params.setdefault("language", self.langue)
        for tentative in range(3):
            try:
                r = self.session.get(f"{TMDB_API_BASE}{endpoint}", params=params, timeout=15)
                if r.status_code == 429:
                    time.sleep(1.5 * (tentative + 1))
                    continue
                r.raise_for_status()
                return r.json()
            except requests.RequestException:
                if tentative == 2:
                    raise
                time.sleep(1.0 * (tentative + 1))
        return {}

    def rechercher_mot_cle(self, mot: str) -> int | None:
        with self._verrou:
            if mot in self._cache_keyword:
                return self._cache_keyword[mot]
        try:
            data = self._get("/search/keyword", {"query": mot})
            resultats = data.get("results") or []
            keyword_id = resultats[0]["id"] if resultats else None
        except requests.RequestException:
            keyword_id = None
        with self._verrou:
            self._cache_keyword[mot] = keyword_id
        return keyword_id

    def recuperer_tvdb_id(self, tmdb_id: int) -> int | None:
        """Fanart.tv indexe les séries par TheTVDB, pas par TMDB -- il faut
        d'abord résoudre l'identifiant externe. Mis en cache (le même titre
        revient souvent dans plusieurs dossiers/groupes)."""
        with self._verrou:
            if tmdb_id in self._cache_tvdb_id:
                return self._cache_tvdb_id[tmdb_id]
        try:
            data = self._get(f"/tv/{tmdb_id}/external_ids")
            resultat = data.get("tvdb_id")
        except requests.RequestException:
            resultat = None
        with self._verrou:
            self._cache_tvdb_id[tmdb_id] = resultat
        return resultat

    def recuperer_images(self, tmdb_id: int, media_type: str) -> dict[str, Any]:
        """Backdrops TMDB avec leur langue taguée (`iso_639_1`) -- certains
        titres ont des backdrops spécifiquement envoyés pour un marché
        (ex: France), qui incluent parfois un titre local incrusté. On ne
        demande que les langues qui nous intéressent pour rester léger.

        Mis en cache par (tmdb_id, media_type) -- le même titre populaire
        revient souvent dans plusieurs dossiers/groupes durant une même
        exécution, inutile de le redemander à chaque fois.

        Au-delà de `limite_appels_images` appels réussis sur CETTE
        exécution, on arrête d'interroger TMDB pour cet enrichissement et
        on bascule directement sur Fanart pour tous les candidats restants
        -- protection contre la limitation de débit TMDB sur de gros runs.
        """
        cle_cache = (tmdb_id, media_type)
        with self._verrou:
            if cle_cache in self._cache_images:
                return self._cache_images[cle_cache]
            if self.compteur_appels_images >= self.limite_appels_images:
                self.budget_images_epuise = True
                return {}
            # Réservé tout de suite, sous verrou : avec des dizaines de
            # threads concurrents, incrémenter APRÈS l'appel laisserait
            # passer plusieurs threads au-delà de la limite avant que
            # celle-ci ne soit détectée.
            self.compteur_appels_images += 1

        chemin = "movie" if media_type != "tv" else "tv"
        try:
            resultat = self._get(f"/{chemin}/{tmdb_id}/images", {"include_image_language": "fr,en,null"})
        except requests.RequestException:
            resultat = {}

        with self._verrou:
            self._cache_images[cle_cache] = resultat
        return resultat

    def resoudre_backdrop(self, requete: RequeteTMDB) -> tuple[str | None, int | None, str | None]:
        """Retourne (backdrop_path, tmdb_id_du_resultat, media_type) ou (None, None, None)."""
        try:
            if requete.kind == "collection":
                data = self._get(f"/collection/{requete.tmdb_id}")
                backdrop = data.get("backdrop_path")
                if not backdrop and self.langue != "en-US":
                    data = self._get(f"/collection/{requete.tmdb_id}", {"language": "en-US"})
                    backdrop = data.get("backdrop_path")
                return backdrop, requete.tmdb_id, "collection"

            if requete.kind == "endpoint":
                data = self._get(requete.endpoint)
                for item in data.get("results", []):
                    if item.get("backdrop_path"):
                        return item["backdrop_path"], item.get("id"), requete.media_type
                return None, None, None

            if requete.kind == "discover":
                params = dict(requete.params)
                mot_cle = params.pop("__keyword_search__", None)
                if mot_cle:
                    keyword_id = self.rechercher_mot_cle(mot_cle)
                    if not keyword_id:
                        return None, None, None
                    params["with_keywords"] = keyword_id
                data = self._get(f"/discover/{requete.media_type}", params)
                for item in data.get("results", []):
                    if item.get("backdrop_path"):
                        return item["backdrop_path"], item.get("id"), requete.media_type
                return None, None, None

        except requests.RequestException as exc:
            logging.debug("Erreur TMDB (%s): %s", requete.kind, exc)
            return None, None, None

        return None, None, None

    def resoudre_backdrops_multiples(
        self, requete: RequeteTMDB, limite: int = 12, pages: int = 2
    ) -> list[tuple[str, int, str, str | None]]:
        """Retourne jusqu'à `limite` tuples (backdrop_path, tmdb_id, media_type,
        langue_originale) pour une requête donnée -- utilisé pour la mosaïque
        multi-titres. La langue originale sert à prioriser les artworks
        Fanart.tv dans la bonne langue (voir ClientFanart.choisir_url).
        """
        resultats: list[tuple[str, int, str, str | None]] = []
        try:
            if requete.kind == "collection":
                data = self._get(f"/collection/{requete.tmdb_id}")
                parts = data.get("parts") or []
                parts = sorted(parts, key=lambda p: p.get("popularity", 0), reverse=True)
                for item in parts:
                    if item.get("backdrop_path"):
                        # une collection ne contient que des films -> media_type "movie",
                        # pas "collection" (sinon le même film n'est pas reconnu comme
                        # doublon s'il apparaît aussi via une requête discover/endpoint)
                        resultats.append((item["backdrop_path"], item.get("id"), "movie", item.get("original_language")))
                    if len(resultats) >= limite:
                        break
                return resultats

            if requete.kind == "endpoint":
                for page in range(1, pages + 1):
                    data = self._get(requete.endpoint, {"page": page})
                    items = data.get("results", [])
                    if not items:
                        break
                    for item in items:
                        if item.get("backdrop_path"):
                            resultats.append((item["backdrop_path"], item.get("id"), requete.media_type, item.get("original_language")))
                        if len(resultats) >= limite:
                            return resultats
                return resultats

            if requete.kind == "discover":
                params = dict(requete.params)
                mot_cle = params.pop("__keyword_search__", None)
                if mot_cle:
                    keyword_id = self.rechercher_mot_cle(mot_cle)
                    if not keyword_id:
                        return []
                    params["with_keywords"] = keyword_id
                for page in range(1, pages + 1):
                    data = self._get(f"/discover/{requete.media_type}", {**params, "page": page})
                    items = data.get("results", [])
                    if not items:
                        break
                    for item in items:
                        if item.get("backdrop_path"):
                            resultats.append((item["backdrop_path"], item.get("id"), requete.media_type, item.get("original_language")))
                        if len(resultats) >= limite:
                            return resultats
                return resultats

        except requests.RequestException as exc:
            logging.debug("Erreur TMDB multiples (%s): %s", requete.kind, exc)
            return resultats

        return resultats


class ClientFanart:
    def __init__(self, cle_api: str | None, session: requests.Session | None = None):
        self.cle_api = cle_api
        self.session = session or creer_session_http()
        self._cache_donnees: dict[tuple[int, str], dict[str, Any] | None] = {}
        self._verrou = threading.Lock()  # ce client est partagé entre threads (voir ClientTMDB)

    def _normaliser_langue(self, valeur: Any) -> str | None:
        """Normalise en minuscule/strip. IMPORTANT : ceci ne fusionne PAS
        les variantes régionales entre elles -- "fr-ca" reste "fr-ca" et
        ne correspondra JAMAIS à "fr" (comparaison stricte ailleurs). On ne
        veut que le français de France, pas le français canadien/belge/etc."""
        if valeur is None:
            return None
        valeur = str(valeur).strip().lower()
        return None if valeur in ("", "00", "none", "null") else valeur

    def donnees(self, tmdb_ou_tvdb_id: int, media_type: str) -> dict[str, Any] | None:
        """Mis en cache par (id, media_type) -- le même titre populaire
        revient souvent dans plusieurs dossiers/groupes durant une même
        exécution, inutile de le redemander à chaque fois à Fanart."""
        cle_cache = (tmdb_ou_tvdb_id, media_type)
        with self._verrou:
            if cle_cache in self._cache_donnees:
                return self._cache_donnees[cle_cache]

        chemin = "movies" if media_type == "movie" else "tv"
        try:
            r = self.session.get(
                f"{FANART_API_BASE}/{chemin}/{tmdb_ou_tvdb_id}",
                params={"api_key": self.cle_api},
                timeout=15,
            )
            resultat = r.json() if r.status_code == 200 else None
        except requests.RequestException:
            resultat = None

        with self._verrou:
            self._cache_donnees[cle_cache] = resultat
        return resultat

    def _candidats_par_type(self, data: dict[str, Any], media_type: str, type_nom: str) -> list[dict[str, Any]]:
        """Pas de 'banner' volontairement (hors format pour nos tuiles paysage)."""
        if media_type == "tv":
            mapping = {
                "background": data.get("showbackground") or [],
                "thumb": data.get("tvthumb") or [],
                "clearart": (data.get("hdclearart") or []) + (data.get("clearart") or []),
            }
        else:
            mapping = {
                "background": data.get("moviebackground") or [],
                "thumb": data.get("moviethumb") or [],
                "clearart": (data.get("hdmovieclearart") or []) + (data.get("movieart") or []),
            }
        return mapping.get(type_nom, [])

    def url_par_type_et_langue(
        self, data: dict[str, Any] | None, media_type: str, type_nom: str, langue: str | None
    ) -> str | None:
        """Meilleure URL pour un type d'artwork donné, dans EXACTEMENT la
        langue demandée (`None` = version sans texte uniquement)."""
        if not data:
            return None
        langue_norm = self._normaliser_langue(langue)
        candidats = [c for c in self._candidats_par_type(data, media_type, type_nom) if self._normaliser_langue(c.get("lang")) == langue_norm]
        if not candidats:
            return None
        meilleur = sorted(candidats, key=lambda c: -int(c.get("likes", 0)))[0]
        return meilleur.get("url")

    def meilleure_url_fond(self, data: dict[str, Any] | None, media_type: str) -> str | None:
        """Une image 'background' Fanart, n'importe quelle langue (utilisée
        comme fond pour composer un artwork 'clearart' transparent)."""
        if not data:
            return None
        candidats = self._candidats_par_type(data, media_type, "background")
        if not candidats:
            return None
        meilleur = sorted(candidats, key=lambda c: -int(c.get("likes", 0)))[0]
        return meilleur.get("url")


class ClientTrakt:
    """Accès aux listes Trakt (publiques via Client ID seul, privées et
    recommandations personnalisées via authentification OAuth complète).

    - Sans access_token : seules les listes PUBLIQUES (traktListId) fonctionnent.
    - Avec access_token (+ refresh_token + client_secret) : accès aux listes
      privées du compte authentifié, et à `/recommendations/movies|shows`
      (catalogues "trakt.recommendations.*").

    Voir scripts/trakt_auth.py pour obtenir un access_token/refresh_token
    (flux "device code" OAuth, à faire une fois en local).
    """

    def __init__(
        self,
        client_id: str | None,
        session: requests.Session | None = None,
        client_secret: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.session = session or creer_session_http()
        self._cache_liste: dict[int, list[tuple[int, str]]] = {}
        self._cache_recommandations: dict[str, list[tuple[int, str]]] = {}
        self._verrou = threading.Lock()  # ce client est partagé entre threads (voir ClientTMDB)
        self.tokens_ont_change = False  # True si rafraichir_token() a produit de nouveaux tokens

    def _headers(self) -> dict[str, str]:
        entetes = {
            "Content-Type": "application/json",
            "trakt-api-key": self.client_id or "",
            "trakt-api-version": "2",
        }
        if self.access_token:
            entetes["Authorization"] = f"Bearer {self.access_token}"
        return entetes

    def rafraichir_token(self) -> bool:
        """Échange le refresh_token contre un nouvel access_token (+ un
        NOUVEAU refresh_token -- celui-ci est à usage unique côté Trakt).
        À appeler une fois en début d'exécution : les access_token Trakt
        ne durent que 7 jours, donc un cron mensuel/hebdomadaire doit
        quasi systématiquement rafraîchir. Met à jour self.access_token/
        self.refresh_token et positionne self.tokens_ont_change=True en
        cas de succès (pour que l'appelant sache qu'il faut les
        re-sauvegarder, ex: en secret GitHub)."""
        if not (self.refresh_token and self.client_id and self.client_secret):
            return False
        try:
            r = self.session.post(
                f"{TRAKT_API_BASE}/oauth/token",
                json={
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                },
                timeout=15,
            )
            if r.status_code != 200:
                return False
            data = r.json()
            nouvel_access = data.get("access_token")
            nouveau_refresh = data.get("refresh_token")
            if not (nouvel_access and nouveau_refresh):
                return False
            self.access_token = nouvel_access
            self.refresh_token = nouveau_refresh
            self.tokens_ont_change = True
            return True
        except requests.RequestException:
            return False

    def recuperer_items_liste(self, trakt_list_id: int, limite: int = 50) -> list[tuple[int, str]]:
        """Retourne une liste de (tmdb_id, media_type) pour les items d'une
        liste Trakt. Fonctionne pour une liste PUBLIQUE avec juste un
        Client ID ; pour une liste PRIVÉE, il faut un access_token valide
        pour le compte propriétaire (ou collaborateur) de la liste.
        Liste vide si pas de clé, liste inaccessible, ou erreur réseau --
        jamais d'exception."""
        with self._verrou:
            if trakt_list_id in self._cache_liste:
                return self._cache_liste[trakt_list_id]

        resultat: list[tuple[int, str]] = []
        if self.client_id:
            try:
                r = self.session.get(
                    f"{TRAKT_API_BASE}/lists/{trakt_list_id}/items",
                    headers=self._headers(),
                    params={"limit": limite},
                    timeout=15,
                )
                if r.status_code == 200:
                    for item in r.json() or []:
                        type_item = item.get("type")  # "movie" ou "show"
                        bloc = item.get(type_item) or {}
                        tmdb_id = (bloc.get("ids") or {}).get("tmdb")
                        if tmdb_id:
                            resultat.append((tmdb_id, "movie" if type_item == "movie" else "tv"))
            except requests.RequestException:
                pass

        with self._verrou:
            self._cache_liste[trakt_list_id] = resultat
        return resultat

    def recuperer_recommandations(self, media_type: str, limite: int = 50) -> list[tuple[int, str]]:
        """Recommandations personnalisées pour le compte authentifié.
        Nécessite un access_token valide -- retourne une liste vide sinon
        (pas d'exception), ex: si l'authentification n'a pas été configurée
        ou a expiré sans pouvoir être rafraîchie."""
        cle_cache = media_type
        with self._verrou:
            if cle_cache in self._cache_recommandations:
                return self._cache_recommandations[cle_cache]

        resultat: list[tuple[int, str]] = []
        if self.access_token:
            chemin = "movies" if media_type == "movie" else "shows"
            try:
                r = self.session.get(
                    f"{TRAKT_API_BASE}/recommendations/{chemin}",
                    headers=self._headers(),
                    params={"limit": limite},
                    timeout=15,
                )
                if r.status_code == 200:
                    for item in r.json() or []:
                        # Deux formats possibles selon l'endpoint Trakt :
                        # objet média direct ({"ids": {...}}) ou enveloppé
                        # ({"movie"/"show": {"ids": {...}}}) -- on gère les deux.
                        ids = item.get("ids")
                        if ids is None:
                            bloc = item.get("movie") or item.get("show") or {}
                            ids = bloc.get("ids") or {}
                        tmdb_id = ids.get("tmdb")
                        if tmdb_id:
                            resultat.append((tmdb_id, media_type))
            except requests.RequestException:
                pass

        with self._verrou:
            self._cache_recommandations[cle_cache] = resultat
        return resultat


# ---------------------------------------------------------------------------
# Résolution TMDB /images (backdrops tagués par langue)
# ---------------------------------------------------------------------------

def meilleur_backdrop_tmdb_langue(images_data: dict[str, Any] | None, langue: str | None) -> str | None:
    """`images_data` = réponse de /movie|tv/{id}/images. Retourne le
    meilleur backdrop_path tagué EXACTEMENT `langue` (None = untagged)."""
    if not images_data:
        return None
    langue_norm = langue.lower() if langue else None
    candidats = [b for b in (images_data.get("backdrops") or []) if (b.get("iso_639_1") or None) == langue_norm]
    if not candidats:
        return None
    meilleur = sorted(candidats, key=lambda b: -(b.get("vote_average") or 0))[0]
    return meilleur.get("file_path")



# ---------------------------------------------------------------------------

PROFILS_QUALITE = {
    "standard": {"largeur": 1280, "qualite": 82},
    "haute": {"largeur": 1920, "qualite": 88},
    "compresse": {"largeur": 780, "qualite": 75},
}


def telecharger_et_traiter(
    url: str, chemin_sortie: Path, session: requests.Session, profil: str = "standard"
) -> None:
    reglages = PROFILS_QUALITE.get(profil, PROFILS_QUALITE["standard"])
    r = session.get(url, timeout=30)
    r.raise_for_status()

    image = Image.open(io.BytesIO(r.content)).convert("RGB")
    largeur_cible = reglages["largeur"]
    if image.width > largeur_cible:
        ratio = largeur_cible / image.width
        image = image.resize((largeur_cible, int(image.height * ratio)), Image.LANCZOS)

    chemin_sortie.parent.mkdir(parents=True, exist_ok=True)
    image.save(chemin_sortie, "JPEG", quality=reglages["qualite"], optimize=True)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

@dataclass
class ResultatDossier:
    groupe: str
    dossier: str
    statut: str  # "genere" | "ignore" | "erreur"
    detail: str = ""
    chemin: str | None = None


class GenerateurBackdrops:
    def __init__(
        self,
        cle_tmdb: str,
        cle_fanart: str | None,
        repertoire_sortie: Path,
        profil: str = "standard",
        dry_run: bool = False,
        mosaique: bool = False,
        langue_preferee: str = "fr",
        limite_appels_tmdb_images: int = 300,
        cle_trakt: str | None = None,
        catalogues_aiometadata: dict[str, dict[str, Any]] | None = None,
        trakt_client_secret: str | None = None,
        trakt_access_token: str | None = None,
        trakt_refresh_token: str | None = None,
    ):
        self.session = creer_session_http()
        self.tmdb = ClientTMDB(cle_tmdb, session=self.session, limite_appels_images=limite_appels_tmdb_images)
        self.fanart = ClientFanart(cle_fanart, session=self.session)
        self.trakt = ClientTrakt(
            cle_trakt,
            session=self.session,
            client_secret=trakt_client_secret,
            access_token=trakt_access_token,
            refresh_token=trakt_refresh_token,
        )
        self.repertoire_sortie = repertoire_sortie
        self.profil = profil
        self.dry_run = dry_run
        self.mosaique = mosaique
        self.langue_preferee = langue_preferee
        self.catalogues_aiometadata = catalogues_aiometadata or {}

    def _dimensions_canvas(self) -> tuple[int, int]:
        largeur = PROFILS_QUALITE.get(self.profil, PROFILS_QUALITE["standard"])["largeur"]
        # on vise un canvas plus grand pour la mosaïque (plus de détail par tuile)
        largeur = max(largeur, 1280)
        hauteur = round(largeur * 9 / 16)
        return largeur, hauteur

    def _telecharger_une_image(self, url: str) -> "Image.Image | None":
        try:
            r = self.session.get(url, timeout=20)
            r.raise_for_status()
            return mosaique_module.image_depuis_bytes(r.content)
        except Exception:  # noqa: BLE001
            return None

    def _obtenir_fond_pour_clearart(
        self, fanart_data: dict[str, Any] | None, media_type: str, backdrop_path_repli: str | None
    ) -> "Image.Image | None":
        """Un clearart est détouré (transparent) : on lui trouve un vrai
        fond derrière plutôt qu'une couleur plate -- d'abord un
        'background' Fanart (n'importe quelle langue, il n'a pas de texte
        de toute façon), sinon le backdrop TMDB brut du candidat."""
        if fanart_data:
            url_fond = self.fanart.meilleure_url_fond(fanart_data, media_type)
            if url_fond:
                image = self._telecharger_une_image(url_fond)
                if image:
                    return image
        if backdrop_path_repli:
            return self._telecharger_une_image(f"{TMDB_IMAGE_BASE}/w1280{backdrop_path_repli}")
        return None

    def _resoudre_image_tuile(self, candidat: tuple[str, int, str, str | None]) -> "Image.Image | None":
        """Cascade de résolution pour une tuile, dans l'ordre demandé :

        Pour chaque langue en (français, anglais) :
          1. backdrop TMDB tagué exactement cette langue (/images) ;
          2. Fanart "background" dans cette langue ;
          3. Fanart "thumb" dans cette langue ;
          4. Fanart "clearart"/"hdclearart" dans cette langue, composé sur
             un vrai fond (jamais une couleur plate).
        Si rien trouvé dans aucune des deux langues : même cascade
        Fanart (background/thumb/clearart) en version SANS TEXTE, puis un
        backdrop TMDB générique (non tagué), puis le backdrop brut connu
        du candidat en tout dernier recours.
        """
        backdrop_path, tmdb_id, media_type, _langue_originale_ignoree = candidat

        if not tmdb_id:
            return self._telecharger_une_image(f"{TMDB_IMAGE_BASE}/w1280{backdrop_path}") if backdrop_path else None

        # Chargement paresseux des données Fanart : on ne les récupère que
        # si TMDB seul n'a pas suffi (économise un appel API dans le cas,
        # fréquent, où le backdrop TMDB taggué FR existe déjà).
        cache_fanart: dict[str, Any] = {}

        def obtenir_fanart_data() -> dict[str, Any] | None:
            if "valeur" not in cache_fanart:
                valeur = None
                if self.fanart.cle_api:
                    identifiant = self.tmdb.recuperer_tvdb_id(tmdb_id) if media_type == "tv" else tmdb_id
                    if identifiant:
                        valeur = self.fanart.donnees(identifiant, media_type)
                cache_fanart["valeur"] = valeur
            return cache_fanart["valeur"]

        images_tmdb = self.tmdb.recuperer_images(tmdb_id, media_type)

        for langue in (self.langue_preferee, "en"):
            if not langue:
                continue

            chemin = meilleur_backdrop_tmdb_langue(images_tmdb, langue)
            if chemin:
                image = self._telecharger_une_image(f"{TMDB_IMAGE_BASE}/w1280{chemin}")
                if image:
                    return image

            fanart_data = obtenir_fanart_data()
            if fanart_data:
                for type_nom in ("background", "thumb"):
                    url = self.fanart.url_par_type_et_langue(fanart_data, media_type, type_nom, langue)
                    if url:
                        image = self._telecharger_une_image(url)
                        if image:
                            return image

                url_clearart = self.fanart.url_par_type_et_langue(fanart_data, media_type, "clearart", langue)
                if url_clearart:
                    clearart = self._telecharger_une_image(url_clearart)
                    if clearart:
                        fond = self._obtenir_fond_pour_clearart(fanart_data, media_type, backdrop_path)
                        return mosaique_module.composer_sur_fond(clearart, fond) if fond else clearart

        # Dernier recours : sans texte
        fanart_data = obtenir_fanart_data()
        if fanart_data:
            for type_nom in ("background", "thumb"):
                url = self.fanart.url_par_type_et_langue(fanart_data, media_type, type_nom, None)
                if url:
                    image = self._telecharger_une_image(url)
                    if image:
                        return image

            url_clearart = self.fanart.url_par_type_et_langue(fanart_data, media_type, "clearart", None)
            if url_clearart:
                clearart = self._telecharger_une_image(url_clearart)
                if clearart:
                    fond = self._obtenir_fond_pour_clearart(fanart_data, media_type, backdrop_path)
                    return mosaique_module.composer_sur_fond(clearart, fond) if fond else clearart

        chemin_generique = meilleur_backdrop_tmdb_langue(images_tmdb, None)
        if chemin_generique:
            image = self._telecharger_une_image(f"{TMDB_IMAGE_BASE}/w1280{chemin_generique}")
            if image:
                return image

        if backdrop_path:
            return self._telecharger_une_image(f"{TMDB_IMAGE_BASE}/w1280{backdrop_path}")
        return None

    def _telecharger_images_pour_mosaique(
        self, candidats: list[tuple[str, int, str, str | None]]
    ) -> list["Image.Image"]:
        """Résout (cascade TMDB langue -> Fanart -> sans texte) et
        télécharge en parallèle les images des candidats ; retourne les
        images PIL valides (dans l'ordre, en ignorant les échecs)."""
        images: dict[int, Any] = {}

        def _traiter(index_et_candidat):
            index, candidat = index_et_candidat
            return index, self._resoudre_image_tuile(candidat)

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            for index, image in executor.map(_traiter, enumerate(candidats)):
                if image is not None:
                    images[index] = image

        return [images[i] for i in sorted(images)]

    def _resoudre_liste_candidats(self, requete: RequeteTMDB, cible: int, pages: int) -> list[tuple[str, int, str, str | None]]:
        """Résout une requête en liste de candidats (backdrop_path, tmdb_id,
        media_type, langue_originale) -- gère les requêtes TMDB classiques,
        les listes Trakt (`kind == "trakt_liste"`), et les recommandations
        Trakt personnalisées (`kind == "trakt_recommandations"`)."""
        if requete.kind == "trakt_liste":
            items = self.trakt.recuperer_items_liste(requete.tmdb_id, limite=cible)
            # backdrop_path/langue inconnus à ce stade -- la cascade de
            # résolution de tuile (TMDB /images -> Fanart) n'en a pas besoin,
            # ils ne servent que de tout dernier repli.
            return [(None, tmdb_id, media_type, None) for tmdb_id, media_type in items]
        if requete.kind == "trakt_recommandations":
            items = self.trakt.recuperer_recommandations(requete.media_type, limite=cible)
            return [(None, tmdb_id, media_type, None) for tmdb_id, media_type in items]
        return self.tmdb.resoudre_backdrops_multiples(requete, limite=cible, pages=pages)

    def traiter_dossier_mosaique(
        self, groupe_titre: str, dossier_titre: str, requetes: list[RequeteTMDB], chemin_sortie: Path
    ) -> ResultatDossier | None:
        """Tente une génération en mosaïque. Retourne None si pas assez
        d'images trouvées (l'appelant doit alors retomber sur le mode
        single-backdrop)."""
        largeur, hauteur = self._dimensions_canvas()
        # nombre de cases de la grille -> on vise ce nombre d'images DISTINCTES
        # pour éviter les répétitions rapprochées d'une même affiche
        cible = mosaique_module.nombre_cellules_grille(largeur, hauteur, echelle=largeur / 1920)
        pages_necessaires = min(6, math.ceil(cible / 18) + 1)

        candidats: list[tuple[str, int, str, str | None]] = []
        vus: set[tuple[str, int]] = set()

        # on interleave les requêtes pour ne pas être dominé par la première
        listes_par_requete = [
            self._resoudre_liste_candidats(req, cible, pages_necessaires) for req in requetes
        ]
        max_len = max((len(liste) for liste in listes_par_requete), default=0)
        for i in range(max_len):
            for liste in listes_par_requete:
                if i < len(liste):
                    backdrop_path, tmdb_id, media_type, langue_originale = liste[i]
                    cle = (media_type, tmdb_id)
                    if cle not in vus:
                        vus.add(cle)
                        candidats.append((backdrop_path, tmdb_id, media_type, langue_originale))
            if len(candidats) >= cible:
                break

        if not mosaique_module.assez_d_images(len(candidats)):
            return None  # pas assez d'images -> repli sur le mode single-image

        images = self._telecharger_images_pour_mosaique(candidats[:cible])
        if not mosaique_module.assez_d_images(len(images)):
            return None  # trop d'échecs de téléchargement -> repli aussi

        resultat = mosaique_module.generer_mosaique(images, largeur, hauteur, titre_repli=dossier_titre)
        if resultat is None:
            return None

        chemin_sortie.parent.mkdir(parents=True, exist_ok=True)
        resultat.image.save(chemin_sortie, "JPEG", quality=PROFILS_QUALITE.get(self.profil, PROFILS_QUALITE["standard"])["qualite"], optimize=True)

        detail = f"mosaïque {resultat.nb_tuiles} tuiles distinctes, accent RGB{resultat.accent}"
        return ResultatDossier(groupe_titre, dossier_titre, "genere", detail, None)

    def traiter_dossier(self, groupe_titre: str, dossier: dict[str, Any]) -> ResultatDossier:
        dossier_titre = dossier.get("title", "sans-titre")

        if not dossier_actif(groupe_titre, dossier_titre):
            return ResultatDossier(groupe_titre, dossier_titre, "ignore", "groupe/dossier non ciblé en phase 1")

        requetes, raisons = construire_requetes(groupe_titre, dossier, self.catalogues_aiometadata)
        if not requetes:
            raison = "; ".join(raisons) or "aucune source exploitable"
            return ResultatDossier(groupe_titre, dossier_titre, "ignore", raison)

        chemin_relatif = Path(GROUPE_SLUGS.get(normaliser(groupe_titre), slugifier(groupe_titre))) / "backdrop" / f"{slugifier(dossier_titre)}.jpg"
        chemin_sortie = self.repertoire_sortie / chemin_relatif

        if self.dry_run:
            mode = "mosaïque" if self.mosaique else "single"
            return ResultatDossier(groupe_titre, dossier_titre, "genere", f"(dry-run, mode {mode}) {len(requetes)} requête(s) prête(s)", str(chemin_relatif))

        if self.mosaique:
            resultat_mosaique = self.traiter_dossier_mosaique(groupe_titre, dossier_titre, requetes, chemin_sortie)
            if resultat_mosaique is not None:
                resultat_mosaique.chemin = str(chemin_relatif)
                return resultat_mosaique
            # sinon : pas assez d'images -> on continue avec le mode single-backdrop ci-dessous

        for requete in requetes:
            backdrop_path, tmdb_id, media_type = self.tmdb.resoudre_backdrop(requete)
            url_image = None

            if backdrop_path:
                url_image = f"{TMDB_IMAGE_BASE}/original{backdrop_path}"
            elif tmdb_id and media_type:
                identifiant_fanart = self.tmdb.recuperer_tvdb_id(tmdb_id) if media_type == "tv" else tmdb_id
                fanart_data = self.fanart.donnees(identifiant_fanart, media_type) if identifiant_fanart else None
                url_fanart = None
                for langue in (self.langue_preferee, "en", None):
                    for type_nom in ("background", "thumb"):
                        url_fanart = self.fanart.url_par_type_et_langue(fanart_data, media_type, type_nom, langue)
                        if url_fanart:
                            break
                    if url_fanart:
                        break
                if url_fanart:
                    url_image = url_fanart

            if url_image:
                try:
                    telecharger_et_traiter(url_image, chemin_sortie, self.session, self.profil)
                    return ResultatDossier(groupe_titre, dossier_titre, "genere", url_image, str(chemin_relatif))
                except Exception as exc:  # noqa: BLE001
                    return ResultatDossier(groupe_titre, dossier_titre, "erreur", str(exc))

        return ResultatDossier(groupe_titre, dossier_titre, "ignore", "aucun backdrop trouvé (TMDB + Fanart)")

    def generer_tout(
        self, collections: list[dict[str, Any]], parallelisme: int = 4,
        filtre_groupe: str | None = None, limite: int | None = None,
    ) -> list[ResultatDossier]:
        taches: list[tuple[str, dict[str, Any]]] = []
        groupes_connus = set(CRITERES_GROUPES.keys())
        groupes_vus: set[str] = set()

        for groupe in collections:
            titre_groupe = groupe.get("title", "")
            cle_normalisee = normaliser(titre_groupe)
            groupes_vus.add(cle_normalisee)

            if cle_normalisee not in groupes_connus:
                print(
                    f"⚠️  Groupe non reconnu dans le JSON : {titre_groupe!r} (normalisé: {cle_normalisee!r}) "
                    "-- aucun mapping connu, ce groupe entier sera ignoré. "
                    "Si ce groupe existe bien dans Nuvio, il faut l'ajouter au script (CRITERES_GROUPES / GROUPE_SLUGS)."
                )

            if filtre_groupe and normaliser(filtre_groupe) not in cle_normalisee:
                continue
            for dossier in groupe.get("folders", []):
                taches.append((titre_groupe, dossier))

        groupes_manquants = groupes_connus - groupes_vus
        if groupes_manquants and not filtre_groupe:
            print(
                f"⚠️  Groupe(s) attendu(s) mais absent(s) du JSON : {sorted(groupes_manquants)} "
                "-- a peut-être été renommé au-delà d'un simple emoji/espace."
            )

        if limite:
            taches = taches[:limite]

        resultats: list[ResultatDossier] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallelisme) as executor:
            futurs = {
                executor.submit(self.traiter_dossier, titre_groupe, dossier): (titre_groupe, dossier)
                for titre_groupe, dossier in taches
            }
            for futur in concurrent.futures.as_completed(futurs):
                titre_groupe, dossier = futurs[futur]
                dossier_titre = dossier.get("title", "sans-titre")
                try:
                    resultats.append(futur.result())
                except Exception as exc:  # noqa: BLE001 -- une erreur inattendue sur UN dossier
                    # ne doit jamais faire perdre les résultats déjà obtenus pour les autres.
                    logging.debug("Erreur inattendue sur [%s] %s : %s", titre_groupe, dossier_titre, exc)
                    resultats.append(
                        ResultatDossier(titre_groupe, dossier_titre, "erreur", f"exception inattendue : {exc}")
                    )

        return resultats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def charger_collections(chemin: Path) -> list[dict[str, Any]]:
    with chemin.open(encoding="utf-8") as f:
        return json.load(f)


def afficher_resume(resultats: list[ResultatDossier]) -> None:
    generes = [r for r in resultats if r.statut == "genere"]
    ignores = [r for r in resultats if r.statut == "ignore"]
    erreurs = [r for r in resultats if r.statut == "erreur"]

    print("\n" + "=" * 60)
    print(f"✅ Générés : {len(generes)}")
    print(f"⏭️  Ignorés : {len(ignores)}")
    print(f"❌ Erreurs : {len(erreurs)}")
    print("=" * 60)

    if erreurs:
        print("\nDétail des erreurs :")
        for r in erreurs:
            print(f"  - [{r.groupe}] {r.dossier} : {r.detail}")

    par_raison: dict[str, int] = {}
    for r in ignores:
        par_raison[r.detail] = par_raison.get(r.detail, 0) + 1
    if par_raison:
        print("\nDossiers ignorés, par raison :")
        for raison, n in sorted(par_raison.items(), key=lambda x: -x[1]):
            print(f"  - {n:>3}x  {raison}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Génère les backdrops des collections Nuvio.")
    parser.add_argument("--cle-tmdb", default=None, help="Clé API TMDB (ou variable TMDB_API_KEY)")
    parser.add_argument("--cle-fanart", default=None, help="Clé API Fanart.tv (optionnel)")
    parser.add_argument("--cle-trakt", default=None, help="Client ID Trakt.tv, pour résoudre les traktListId publiques (optionnel)")
    parser.add_argument("--trakt-client-secret", default=None, help="Client Secret Trakt.tv (nécessaire pour l'auth OAuth complète, optionnel)")
    parser.add_argument("--trakt-access-token", default=None, help="Access token OAuth Trakt.tv (optionnel, voir scripts/trakt_auth.py)")
    parser.add_argument("--trakt-refresh-token", default=None, help="Refresh token OAuth Trakt.tv (optionnel, voir scripts/trakt_auth.py)")
    parser.add_argument("--aiometadata", default=None, help="Chemin vers un export AIOMetadata (JSON) pour résoudre les catalogues avec leurs vrais filtres TMDB (optionnel)")
    parser.add_argument("--collections", default="Templates/Nuvio-Collections-Dwade58200.json")
    parser.add_argument("--sortie", default="collections")
    parser.add_argument("--profil", choices=list(PROFILS_QUALITE), default="standard")
    parser.add_argument("--parallelisme", type=int, default=4)
    parser.add_argument("--groupe", default=None, help="Ne traiter qu'un seul groupe (ex: Genres)")
    parser.add_argument("--limite", type=int, default=None, help="Limiter le nombre de dossiers (tests)")
    parser.add_argument("--dry-run", action="store_true", help="Simule sans appeler TMDB ni écrire d'image")
    parser.add_argument("--mosaique", action="store_true", help="Génère une mosaïque multi-titres + couleur d'accent au lieu d'un seul backdrop (repli automatique si pas assez d'images)")
    parser.add_argument("--langue-preferee", default="fr", help="Code langue Fanart.tv préféré pour les artworks avec titre incrusté (défaut: fr)")
    parser.add_argument("--limite-appels-tmdb-images", type=int, default=300, help="Au-delà de ce nombre d'appels TMDB /images sur l'exécution, bascule sur Fanart uniquement (défaut: 300)")
    parser.add_argument("--fichier-tokens-trakt", default=None, help="Si fourni, écrit ici les tokens Trakt actualisés après rafraîchissement (JSON), pour qu'un step CI puisse les re-sauvegarder en secrets")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    import os

    cle_tmdb = args.cle_tmdb or os.environ.get("TMDB_API_KEY")
    if not cle_tmdb and not args.dry_run:
        print("Erreur : clé TMDB manquante (--cle-tmdb ou TMDB_API_KEY). Utilise --dry-run pour tester sans clé.", file=sys.stderr)
        return 1

    collections = charger_collections(Path(args.collections))
    generateur = GenerateurBackdrops(
        cle_tmdb=cle_tmdb or "dry-run",
        cle_fanart=args.cle_fanart or os.environ.get("FANART_API_KEY"),
        repertoire_sortie=Path(args.sortie),
        profil=args.profil,
        dry_run=args.dry_run,
        mosaique=args.mosaique,
        langue_preferee=args.langue_preferee,
        limite_appels_tmdb_images=args.limite_appels_tmdb_images,
        cle_trakt=args.cle_trakt or os.environ.get("TRAKT_CLIENT_ID"),
        catalogues_aiometadata=charger_catalogues_aiometadata(Path(args.aiometadata) if args.aiometadata else None),
        trakt_client_secret=args.trakt_client_secret or os.environ.get("TRAKT_CLIENT_SECRET"),
        trakt_access_token=args.trakt_access_token or os.environ.get("TRAKT_ACCESS_TOKEN"),
        trakt_refresh_token=args.trakt_refresh_token or os.environ.get("TRAKT_REFRESH_TOKEN"),
    )

    # Les access_token Trakt ne durent que 7 jours : sur un cron peu
    # fréquent, on a quasi toujours besoin de rafraîchir. On le fait une
    # fois ici (pas par thread/dossier) pour éviter des rafraîchissements
    # concurrents (le refresh_token est à usage unique côté Trakt).
    if not args.dry_run and generateur.trakt.refresh_token:
        rafraichi = generateur.trakt.rafraichir_token()
        if rafraichi:
            print("🔑 Token Trakt rafraîchi.")
        else:
            print(
                "⚠️  Échec du rafraîchissement du token Trakt -- les recommandations/listes "
                "privées ne seront pas disponibles cette fois. Refaire l'authentification "
                "avec scripts/trakt_auth.py si besoin."
            )

    resultats = generateur.generer_tout(
        collections, parallelisme=args.parallelisme, filtre_groupe=args.groupe, limite=args.limite
    )
    afficher_resume(resultats)
    if generateur.tmdb.budget_images_epuise:
        print(
            f"\n⚠️  Budget d'appels TMDB /images atteint ({generateur.tmdb.limite_appels_images}) : "
            "les derniers titres traités sont passés directement en résolution Fanart uniquement "
            "(--limite-appels-tmdb-images pour ajuster)."
        )

    if generateur.trakt.tokens_ont_change:
        print("\n🔑 Nouveaux tokens Trakt générés (le refresh_token précédent est maintenant invalide).")
        if args.fichier_tokens_trakt:
            with open(args.fichier_tokens_trakt, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "access_token": generateur.trakt.access_token,
                        "refresh_token": generateur.trakt.refresh_token,
                    },
                    f,
                )
            print(f"   -> écrits dans {args.fichier_tokens_trakt} pour sauvegarde en secrets GitHub.")
        else:
            print("   Pense à les re-sauvegarder (TRAKT_ACCESS_TOKEN / TRAKT_REFRESH_TOKEN) si tu veux que ça continue de fonctionner au prochain run.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
