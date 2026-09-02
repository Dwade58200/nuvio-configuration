#!/usr/bin/env python3
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

Tout ce qui n'est pas résoluble (Trakt -- non pris en charge, voir plus
bas --, FlixPatrol, Sports, etc.) est explicitement IGNORÉ et journalisé
avec la raison -- jamais échoué en silence. Ces cas seront traités dans
une phase ultérieure.

Les sources `provider: "mdblist"`, ainsi que les catalogues
`provider: "addon"/aio-metadata` de type `source: "mdblist"` référencés
dans un export AIOMetadata (voir `--aiometadata`), sont résolues via
l'API MDBList.com (clé API simple, pas d'OAuth) -- voir la classe
ClientMDBList plus bas.

Trakt n'est PAS pris en charge : créer une application Trakt nécessite
désormais un abonnement VIP (voir la discussion du 2 août 2026 sur
forums.trakt.tv), ce qui n'est pas disponible pour ce projet. Toute
source `provider: "trakt"` est explicitement ignorée et journalisée.

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
import os
import re
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path
from typing import Any

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

# =============================================================================
# ARCHITECTURE DE SORTIE -- tout ce qui touche aux noms de dossiers/fichiers
# est regroupé ici pour rester simple à modifier en un seul endroit.
# =============================================================================

# Dossier racine de sortie (remplace l'ancien "collections" en minuscule).
NOM_DOSSIER_RACINE = "Collections"

# Sous-dossier contenant les images, dans CHAQUE groupe.
NOM_DOSSIER_BACKDROPS = "Backdrops"

# Nom de dossier (en français) pour chaque groupe -> chemin
# Collections/<NOM>/Backdrops/... "Années" ne figurait pas dans la liste
# fournie ; "Annees" a été choisi par cohérence avec le reste (pas
# d'accent) -- à changer ici si besoin, une seule ligne à éditer.
GROUPE_SLUGS: dict[str, str] = {
    GROUPE_DECOUVRIR: "Decouvertes",
    GROUPE_STREAMING: "Services de Streaming",
    GROUPE_GENRES: "Genres",
    GROUPE_THEMATIQUES: "Thematiques",
    GROUPE_VIBES: "Vibes",
    GROUPE_ANNEES: "Annees",
    GROUPE_FRANCHISES: "Franchises",
    GROUPE_SPORTS: "Sports",
}

# Table de correspondance EXPLICITE pour les noms de fichiers qui ne
# suivent pas la règle générique automatique (sigles à mettre en
# majuscules, "+" à conserver, raccourcis). Clé = titre EXACT du dossier
# tel qu'il apparaît dans le JSON Nuvio ; valeur = nom de fichier voulu,
# SANS le suffixe "_Backdrop.jpg" (ajouté automatiquement).
# Pour ajouter/changer un nom de fichier : une seule ligne à éditer ici.
NOMS_BACKDROP_PERSONNALISES: dict[str, str] = {
    "Sci-Fi": "Sci-Fi",
    "Apple TV+": "Apple_TV",
    "Canal+": "Canal+",
    "TF1": "TF1",
    "HBO Max": "HBO_Max",
    "Prime Video": "Prime_Video",
    "Disney+": "Disney+",
    "Arts martiaux": "Arts_Martiaux",
    "Chasse au trésor": "Chasse_au_Tresor",
    "Comédie Romantique": "Comedie_Romantique",
    "Grands réalisateurs du cinéma": "Grands_Realisateurs",
    "Inspiré de faits réels": "Faits_Reels",
    "Super-Héros": "Super-Heros",
    "Voyage Temporel": "Voyage_Temporel",
    "Retournent le cerveau": "Retournent_Cerveau",
}

# Sigles/acronymes à mettre entièrement en majuscules quand ils
# apparaissent dans un titre non couvert par NOMS_BACKDROP_PERSONNALISES
# (repli générique automatique, voir `nom_fichier_backdrop`).
ACRONYMES_BACKDROP = {"tv", "hbo", "tf1", "m6", "vf", "vo"}


def _mettre_en_forme_mot(mot: str) -> str:
    if mot.lower() in ACRONYMES_BACKDROP:
        return mot.upper()
    return mot[:1].upper() + mot[1:].lower() if mot else mot


def nom_fichier_backdrop(titre_dossier: str) -> str:
    """Nom de fichier (SANS l'extension .jpg) pour le backdrop d'un
    dossier, au format `Nom_Du_Dossier_Backdrop`. Utilise
    NOMS_BACKDROP_PERSONNALISES pour les cas particuliers (sigles, "+",
    raccourcis) ; sinon dérive un nom générique automatiquement à partir
    du titre (mots séparés par underscore, chaque mot capitalisé, sigles
    connus en majuscules)."""
    base = NOMS_BACKDROP_PERSONNALISES.get(titre_dossier)
    if base is None:
        texte_normalise = normaliser(titre_dossier)  # minuscule, sans accents/emoji
        mots = [m for m in texte_normalise.split() if m]
        base = "_".join(_mettre_en_forme_mot(m) for m in mots) or "Sans_Titre"
    return f"{base}_Backdrop"


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
    kind: str  # "collection" | "discover" | "endpoint" | "person" | "mdblist_liste" | "custom_catalogue"
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


def charger_catalogues_aiometadata(chemin: Path | None) -> dict[str, dict[str, Any]]:
    """Charge un export AIOMetadata (Réglages -> Export dans l'addon) et
    construit un index {catalogId: {...}} pour résoudre un catalogue (ex:
    Streaming, Genres, MDBList...) avec ses VRAIS filtres/identifiants
    plutôt qu'une heuristique de repli à partir du nom.

    Trois formes de catalogues sont indexées, distinguées par la clé "kind" :
      - {"kind": "discover", "media_type", "params"} : catalogue TMDB avec
        une config "discover" exacte exportée (Streaming, Genres...).
      - {"kind": "mdblist", "media_type", "mdblist_url"} : catalogue
        `source: "mdblist"` avec une URL de liste publique exportée dans
        `metadata.url` (ex: "Sitcom" -> mdblist.37087).
      - {"kind": "custom_catalogue", "media_type", "url"} : catalogue
        `source: "custom"` (ex: Bingecat) avec une `sourceUrl` -- un
        catalogue Stremio classique dont les `metas` utilisent des
        identifiants IMDb (convertis en TMDB à la résolution).

    IMPORTANT : selon la version de l'export, la clé "catalogs" se trouve
    soit à la racine du JSON, soit sous "config" (export réel observé --
    `{"version", "exportedAt", "config": {"catalogs": [...]}, "metadata": {...}}`).
    On accepte les deux, en préférant "config.catalogs" quand il existe,
    pour ne PLUS silencieusement charger un index vide sur un vrai export.

    Retourne un dict vide si le fichier est absent/invalide (aucune erreur)."""
    if not chemin:
        return {}
    try:
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    catalogues_bruts = (data.get("config") or {}).get("catalogs")
    if catalogues_bruts is None:
        catalogues_bruts = data.get("catalogs")

    index: dict[str, dict[str, Any]] = {}
    for entree in catalogues_bruts or []:
        catalog_id = entree.get("id")
        if not catalog_id:
            continue

        discover = ((entree.get("metadata") or {}).get("discover")) or {}
        params = discover.get("params")
        media_type_brut = discover.get("mediaType")
        if catalog_id and params and media_type_brut:
            media_type = "tv" if media_type_brut in ("tv", "series") else "movie"
            index[catalog_id] = {"kind": "discover", "media_type": media_type, "params": dict(params)}
            continue

        if entree.get("source") == "mdblist":
            url_liste = (entree.get("metadata") or {}).get("url")
            if url_liste and analyser_url_mdblist(url_liste):
                media_type_brut = (entree.get("type") or (entree.get("metadata") or {}).get("mediatype") or "movie")
                media_type = "tv" if media_type_brut in ("tv", "series", "show", "shows") else "movie"
                index[catalog_id] = {"kind": "mdblist", "media_type": media_type, "mdblist_url": url_liste}
            continue

        if entree.get("source") == "custom" and entree.get("sourceUrl"):
            media_type_brut = entree.get("type") or "movie"
            media_type = "tv" if media_type_brut in ("tv", "series", "show", "shows") else "movie"
            index[catalog_id] = {"kind": "custom_catalogue", "media_type": media_type, "url": entree["sourceUrl"]}

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
            # connaît ce catalogue exact, on utilise ses VRAIS filtres/
            # identifiants plutôt qu'une heuristique de repli à partir du
            # nom/hash.
            info_aiometadata = (catalogues_aiometadata or {}).get(catalog_id)
            if info_aiometadata and info_aiometadata.get("kind") == "mdblist":
                user_slug = analyser_url_mdblist(info_aiometadata["mdblist_url"])
                if user_slug:
                    requetes.append(
                        RequeteTMDB(
                            kind="mdblist_liste",
                            media_type=info_aiometadata["media_type"],
                            params={"mdblist_user": user_slug[0], "mdblist_slug": user_slug[1]},
                        )
                    )
                    continue
            if info_aiometadata and info_aiometadata.get("kind") == "custom_catalogue":
                requetes.append(
                    RequeteTMDB(
                        kind="custom_catalogue",
                        media_type=info_aiometadata["media_type"],
                        params={"url": info_aiometadata["url"]},
                    )
                )
                continue
            if info_aiometadata and info_aiometadata.get("kind", "discover") == "discover":
                params_reels = {
                    cle: _resoudre_placeholder_date(valeur) for cle, valeur in info_aiometadata["params"].items()
                }
                params_reels.setdefault("sort_by", "popularity.desc")
                requetes.append(
                    RequeteTMDB(kind="discover", media_type=info_aiometadata["media_type"], params=params_reels)
                )
                continue

            # Repli MDBList : certains catalogId "mdblist.<id>" n'ont pas
            # d'URL exportée exploitable (ex: "mdblist.recommended.*",
            # personnalisé par compte -- non résolvable via l'API publique)
            # -- explicitement journalisé plutôt que noyé dans le message
            # générique "catalogId non résolu".
            if catalog_id.startswith("mdblist.recommended."):
                ignorees.append(
                    f"mdblist recommandation personnalisée non résolvable sans compte lié ({catalog_id})"
                )
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
            # Trakt n'est plus pris en charge (créer une application Trakt
            # nécessite désormais un abonnement VIP, voir MDBList plus haut) :
            # on journalise proprement plutôt que de tenter une résolution.
            ignorees.append("trakt non pris en charge (application Trakt indisponible sans abonnement VIP)")

        elif provider == "mdblist":
            # Trois façons équivalentes d'identifier une liste MDBList dans
            # le JSON, de la plus pratique (coller l'URL telle quelle depuis
            # le navigateur) à la plus explicite :
            #   - "mdblistUrl": "https://mdblist.com/lists/<user>/<slug>"
            #   - "mdblistUser" + "mdblistSlug"
            #   - "mdblistId": <id numérique de la liste>
            mdblist_id = source.get("mdblistId")
            user_slug = None
            if source.get("mdblistUrl"):
                user_slug = analyser_url_mdblist(source["mdblistUrl"])
            elif source.get("mdblistUser") and source.get("mdblistSlug"):
                user_slug = (source["mdblistUser"], source["mdblistSlug"])

            if mdblist_id:
                requetes.append(RequeteTMDB(kind="mdblist_liste", params={"mdblist_id": mdblist_id}))
            elif user_slug:
                requetes.append(
                    RequeteTMDB(
                        kind="mdblist_liste",
                        params={"mdblist_user": user_slug[0], "mdblist_slug": user_slug[1]},
                    )
                )
            else:
                ignorees.append(
                    "mdblist sans identifiant de liste exploitable "
                    "(mdblistUrl / mdblistId / mdblistUser+mdblistSlug)"
                )
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
    ):
        self.cle_api = cle_api
        self.session = session or requests.Session()
        self.langue = langue
        self._cache_keyword: dict[str, int | None] = {}
        self._cache_images: dict[tuple[int, str], dict[str, Any]] = {}
        self._cache_tvdb_id: dict[int, int | None] = {}
        self._cache_imdb: dict[str, tuple[int, str, str | None, str | None] | None] = {}
        # Ce client est partagé entre plusieurs threads (traitement de dossiers
        # en parallèle, chacun téléchargeant lui-même ses tuiles en parallèle) :
        # sans verrou, deux threads peuvent rater le cache au même instant et
        # refaire le même appel en double.
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

    def resoudre_imdb_vers_tmdb(self, imdb_id: str) -> tuple[int, str, str | None, str | None] | None:
        """Convertit un identifiant IMDb ('tt...') en identifiant TMDB, via
        l'endpoint `/find` (`external_source=imdb_id`). Nécessaire pour les
        catalogues Stremio/Nuvio "custom" (ex: Bingecat), qui exposent des
        `id` IMDb et non TMDB dans leurs `metas`.

        Retourne (tmdb_id, media_type, backdrop_path, langue_originale), ou
        None si l'identifiant n'a pas été trouvé côté TMDB. Mis en cache par
        imdb_id (le même titre populaire revient souvent dans plusieurs
        catalogues/dossiers durant une même exécution)."""
        with self._verrou:
            if imdb_id in self._cache_imdb:
                return self._cache_imdb[imdb_id]
        resultat = None
        try:
            data = self._get(f"/find/{imdb_id}", {"external_source": "imdb_id"})
            for media_type, cle in (("movie", "movie_results"), ("tv", "tv_results")):
                items = data.get(cle) or []
                if items:
                    item = items[0]
                    resultat = (item.get("id"), media_type, item.get("backdrop_path"), item.get("original_language"))
                    break
        except requests.RequestException:
            resultat = None
        with self._verrou:
            self._cache_imdb[imdb_id] = resultat
        return resultat

    def recuperer_images(self, tmdb_id: int, media_type: str, langue_originale: str | None = None) -> dict[str, Any]:
        """Backdrops TMDB avec leur langue taguée (`iso_639_1`) -- certains
        titres ont des backdrops spécifiquement envoyés pour un marché
        (ex: France), qui incluent parfois un titre local incrusté. On ne
        demande que les langues qui nous intéressent pour rester léger :
        fr, en, et la langue originale du titre (`langue_originale`, ex:
        "ko" pour un drama coréen) si elle diffère des deux premières --
        utilisée en dernier repli texté avant le "sans texte".

        Mis en cache par (tmdb_id, media_type) -- le même titre populaire
        revient souvent dans plusieurs dossiers/groupes durant une même
        exécution, inutile de le redemander à chaque fois. La langue
        originale d'un titre TMDB donné ne change jamais, donc ignorer ce
        paramètre lors d'un cache hit est sans risque.
        """
        cle_cache = (tmdb_id, media_type)
        with self._verrou:
            if cle_cache in self._cache_images:
                return self._cache_images[cle_cache]

        chemin = "movie" if media_type != "tv" else "tv"
        langues = ["fr", "en"]
        if langue_originale and langue_originale.lower() not in ("fr", "en"):
            langues.append(langue_originale)
        langues.append("null")
        try:
            resultat = self._get(f"/{chemin}/{tmdb_id}/images", {"include_image_language": ",".join(langues)})
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
                assert requete.endpoint is not None  # garanti par construire_requetes() pour ce kind
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
        multi-titres. La langue originale sert de dernier repli texté côté
        TMDB (backdrop tagué dans la langue originale du titre, ex: coréen
        pour un drama coréen) si ni le français ni l'anglais n'ont abouti --
        voir GenerateurBackdrops._resoudre_image_tuile. Elle n'intervient
        PAS dans la résolution Fanart.tv, qui ne cherche que l'anglais.
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
                assert requete.endpoint is not None  # garanti par construire_requetes() pour ce kind
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
        self.session = session or requests.Session()
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
            logging.debug("[FANART] GET %s/%s -> HTTP %s", chemin, tmdb_ou_tvdb_id, r.status_code)
            if r.status_code == 200:
                resultat = r.json()
                # Quirk connu de l'API Fanart : une clé invalide/quota dépassé
                # renvoie parfois un statut HTTP 200 avec un corps d'erreur
                # JSON, pas un code 4xx/5xx. Sans ce log, ce cas est
                # indiscernable d'un 200 "aucun artwork" : le diagnostic ici
                # ne change PAS le comportement (le dict d'erreur ne contient
                # de toute façon aucune des clés attendues par
                # _candidats_par_type, donc le résultat final est déjà
                # "aucun candidat" -- on documente juste la vraie cause).
                if isinstance(resultat, dict) and resultat.get("status") == "error":
                    logging.warning(
                        "[FANART] Réponse 200 mais corps d'erreur pour %s/%s : %s",
                        chemin, tmdb_ou_tvdb_id, resultat.get("error message") or resultat,
                    )
            else:
                resultat = None
                if r.status_code != 404:
                    # 404 = pas de fiche Fanart pour ce titre, c'est un cas normal et fréquent.
                    logging.warning(
                        "[FANART] Statut HTTP inattendu %s pour %s/%s", r.status_code, chemin, tmdb_ou_tvdb_id,
                    )
        except requests.RequestException as exc:
            resultat = None
            logging.warning("[FANART] Erreur réseau/timeout pour %s/%s : %s", chemin, tmdb_ou_tvdb_id, exc)

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


def analyser_url_mdblist(url: str) -> tuple[str, str] | None:
    """Extrait (username, slug) d'une URL de liste MDBList telle que collée
    depuis le navigateur, ex:
        https://mdblist.com/lists/linaspurinis/top-watched-movies
        https://www.mdblist.com/lists/linaspurinis/top-watched-movies/
        mdblist.com/lists/linaspurinis/top-watched-movies/json/
    Retourne None si l'URL ne correspond pas au format attendu."""
    if not url:
        return None
    nettoyee = url.strip()
    nettoyee = re.sub(r"^https?://", "", nettoyee)
    nettoyee = re.sub(r"^www\.", "", nettoyee)
    segments = [s for s in nettoyee.split("/") if s]
    # segments attendus : ["mdblist.com", "lists", "<user>", "<slug>", ...]
    try:
        i = segments.index("lists")
    except ValueError:
        return None
    if len(segments) < i + 3:
        return None
    user, slug = segments[i + 1], segments[i + 2]
    if not user or not slug or slug == "json":
        return None
    return user, slug


class ClientMDBList:
    """Accès en lecture aux listes MDBList.com via une simple clé API
    (pas d'OAuth, pas de renouvellement de jeton).

    Pourquoi MDBList : créer une application Trakt nécessite désormais un
    abonnement VIP (voir discussion du 2 août 2026 sur forums.trakt.tv),
    ce qui est indisponible pour ce projet -- Trakt n'est donc pas pris en
    charge (voir plus haut). MDBList permet de se connecter avec un
    compte Trakt gratuit ("Login with Trakt" sur mdblist.com, via LEUR
    application déjà enregistrée) puis délivre sa PROPRE clé API MDBList,
    gratuite (1000 requêtes/jour), sans jamais toucher à l'API Trakt
    directement.

    Deux stratégies de récupération, dans cet ordre :
      1. API officielle authentifiée par clé (`api.mdblist.com/lists/...`).
      2. Repli sur l'export JSON public de la liste
         (`mdblist.com/lists/<user>/<slug>/json/`), qui ne nécessite AUCUNE
         clé et fonctionne pour toute liste PUBLIQUE -- confirmé par le
         développeur de MDBList lui-même comme méthode d'accès légitime
         sans API (voir github.com/jurialmunkey/plugin.video.themoviedb.helper/issues/741).
         Utile si la clé API est absente/épuisée, ou si l'endpoint exact de
         l'API officielle change.

    Ne lève jamais d'exception : liste vide en cas d'échec.
    """

    API_BASE = "https://api.mdblist.com"
    SITE_BASE = "https://mdblist.com"

    def __init__(self, api_key: str | None, session: requests.Session | None = None):
        self.api_key = api_key
        self.session = session or requests.Session()
        self._cache_liste: dict[str, list[tuple[int, str]]] = {}
        self._verrou = threading.Lock()  # client partagé entre threads, comme ClientTMDB/ClientFanart

    @staticmethod
    def _items_depuis_reponse(data: Any) -> list[tuple[int, str]]:
        """Normalise la réponse MDBList (dict avec 'movies'/'shows', OU liste
        brute) en tuples (tmdb_id, media_type). Le champ 'id' d'un item
        MDBList est déjà l'identifiant TMDB (confirmé par les exemples
        officiels de list-items / media-info)."""
        resultat: list[tuple[int, str]] = []
        if isinstance(data, dict):
            for item in data.get("movies") or []:
                tmdb_id = item.get("id")
                if tmdb_id:
                    resultat.append((tmdb_id, "movie"))
            for item in data.get("shows") or []:
                tmdb_id = item.get("id")
                if tmdb_id:
                    resultat.append((tmdb_id, "tv"))
        elif isinstance(data, list):
            for item in data:
                tmdb_id = item.get("id")
                if not tmdb_id:
                    continue
                media_type_brut = (item.get("mediatype") or item.get("type") or "movie").lower()
                resultat.append((tmdb_id, "tv" if media_type_brut in ("tv", "show", "shows") else "movie"))
        return resultat

    def _recuperer(self, cle_cache: str, urls_et_params: list[tuple[str, dict[str, Any]]]) -> list[tuple[int, str]]:
        with self._verrou:
            if cle_cache in self._cache_liste:
                return self._cache_liste[cle_cache]

        resultat: list[tuple[int, str]] = []
        for url, params in urls_et_params:
            try:
                r = self.session.get(url, params=params, timeout=15)
                if r.status_code == 200:
                    resultat = self._items_depuis_reponse(r.json())
                    if resultat:
                        break
            except (requests.RequestException, ValueError):
                continue

        with self._verrou:
            self._cache_liste[cle_cache] = resultat
        return resultat

    def recuperer_items_liste_par_id(self, mdblist_id: int, limite: int = 50) -> list[tuple[int, str]]:
        """Récupère les items d'une liste MDBList identifiée par son id
        numérique. Nécessite une clé API (pas de repli JSON public sans
        connaître le user/slug)."""
        if not self.api_key:
            return []
        cle_cache = f"id:{mdblist_id}"
        url = f"{self.API_BASE}/lists/{mdblist_id}/items"
        params = {"apikey": self.api_key, "limit": limite}
        return self._recuperer(cle_cache, [(url, params)])

    def recuperer_items_liste(self, username: str, slug: str, limite: int = 50) -> list[tuple[int, str]]:
        """Récupère les items d'une liste MDBList identifiée par
        (username, slug) -- ce que donne `analyser_url_mdblist()` à partir
        d'une URL collée depuis le navigateur. Essaie l'API officielle avec
        clé, puis l'export JSON public (sans clé) en repli."""
        cle_cache = f"{username}/{slug}"
        tentatives: list[tuple[str, dict[str, Any]]] = []
        if self.api_key:
            tentatives.append(
                (f"{self.API_BASE}/lists/{username}/{slug}/items", {"apikey": self.api_key, "limit": limite})
            )
        tentatives.append((f"{self.SITE_BASE}/lists/{username}/{slug}/json/", {}))
        return self._recuperer(cle_cache, tentatives)

    def rechercher_listes(self, requete: str, limite: int = 20) -> list[dict[str, Any]]:
        """Recherche des listes PUBLIQUES par titre (endpoint confirmé par
        lecture du code source officiel du client Go `mdblist-cli` :
        GET /lists/search?apikey=...&query=... -- voir
        github.com/luckylittle/mdblist-cli/blob/main/internal/client/mdblist.go).

        Retourne les résultats bruts (dicts avec au moins : id, name, slug,
        user_name, mediatype, items, likes, private) triés par nombre
        d'items décroissant, sans exception en cas d'échec (liste vide).
        Nécessite une clé API (contrairement à la lecture d'une liste
        déjà connue, qui a un repli public sans clé)."""
        if not self.api_key or not requete.strip():
            return []
        try:
            r = self.session.get(
                f"{self.API_BASE}/lists/search",
                params={"apikey": self.api_key, "query": requete.strip()},
                timeout=15,
            )
            if r.status_code != 200:
                return []
            resultats = r.json()
            if not isinstance(resultats, list):
                return []
            return sorted(resultats, key=lambda liste: -(liste.get("items") or 0))[:limite]
        except (requests.RequestException, ValueError):
            return []


# ---------------------------------------------------------------------------
# Résolution TMDB /images (backdrops tagués par langue)
# ---------------------------------------------------------------------------

def meilleur_backdrop_tmdb_langue(
    images_data: dict[str, Any] | None,
    langue: str | None,
    pays_autorises: set[str] | None = None,
) -> str | None:
    """`images_data` = réponse de /movie|tv/{id}/images. Retourne le
    meilleur backdrop_path tagué EXACTEMENT `langue` (None = untagged).

    `pays_autorises` : si fourni, exclut les candidats dont le pays
    (`iso_3166_1`) est renseigné et absent de cet ensemble -- les images
    sans pays renseigné restent acceptées. Sert à distinguer un vrai
    backdrop français de France d'un backdrop tagué langue "fr" mais pays
    "CA" (contenu québécois) : ce sont deux champs DISTINCTS renvoyés par
    l'API TMDB (confirmé sur des réponses réelles, ex: séries "From" et
    "Supernatural"), et seule la langue était vérifiée jusqu'ici."""
    if not images_data:
        return None
    langue_norm = langue.lower() if langue else None
    candidats = [b for b in (images_data.get("backdrops") or []) if (b.get("iso_639_1") or None) == langue_norm]
    if pays_autorises:
        candidats = [
            b for b in candidats
            if (b.get("iso_3166_1") or None) is None or b.get("iso_3166_1") in pays_autorises
        ]
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
        image = image.resize((largeur_cible, int(image.height * ratio)), Image.Resampling.LANCZOS)

    chemin_sortie.parent.mkdir(parents=True, exist_ok=True)
    image.save(chemin_sortie, "JPEG", quality=reglages["qualite"], optimize=True)


# ---------------------------------------------------------------------------
# Catalogues Stremio "custom" (ex: Bingecat) -- exposés via un export
# AIOMetadata avec "source": "custom" et une "sourceUrl"
# ---------------------------------------------------------------------------

def corriger_url_catalogue_mal_formee(url: str) -> str:
    """Certains exports AIOMetadata contiennent une `sourceUrl` où la
    query string de l'addon (ex: "?bcv=6") est positionnée AVANT le
    chemin de la ressource plutôt qu'après (cas réel observé avec
    Bingecat) : "https://host/base?bcv=6/catalog/movie/x.json" au lieu de
    "https://host/base/catalog/movie/x.json?bcv=6". Tout client HTTP
    standard (dont le nôtre) interprète tout ce qui suit le premier "?"
    comme une query string, donc l'URL telle quelle renvoie une 404.

    Cette fonction déplace la partie qui suit le premier "/" après le "?"
    (le vrai chemin de ressource) devant la query, sans y toucher si l'URL
    est déjà bien formée (pas de "/" après le premier "?")."""
    if "?" not in url:
        return url
    base, _, reste = url.partition("?")
    if "/" not in reste:
        return url
    query_reelle, _, chemin_reel = reste.partition("/")
    return f"{base}/{chemin_reel}?{query_reelle}"


class ClientCatalogueCustom:
    """Accès en lecture à un catalogue Stremio/Nuvio "custom" générique
    (ex: Bingecat), dont les `metas` utilisent des identifiants IMDb (pas
    TMDB) -- conversion faite séparément via ClientTMDB.resoudre_imdb_vers_tmdb.

    Ne lève jamais d'exception : liste vide en cas d'échec."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self._cache: dict[str, list[str]] = {}
        self._verrou = threading.Lock()  # client partagé entre threads, comme ClientTMDB/ClientFanart/ClientMDBList

    def recuperer_ids_imdb(self, url: str, limite: int) -> list[str]:
        with self._verrou:
            if url in self._cache:
                return self._cache[url][:limite]
        ids: list[str] = []
        try:
            r = self.session.get(corriger_url_catalogue_mal_formee(url), timeout=15)
            r.raise_for_status()
            data = r.json()
            for meta in data.get("metas") or []:
                identifiant = meta.get("id") or ""
                if identifiant.startswith("tt"):
                    ids.append(identifiant)
        except (requests.RequestException, ValueError):
            ids = []
        with self._verrou:
            self._cache[url] = ids
        return ids[:limite]


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
        cle_mdblist: str | None = None,
        catalogues_aiometadata: dict[str, dict[str, Any]] | None = None,
    ):
        self.session = requests.Session()
        # Le profil `mosaique` télécharge jusqu'à 12 tuiles en parallèle par
        # dossier, potentiellement pour plusieurs dossiers en même temps
        # (`--parallelisme`) : la taille de pool par défaut de `requests`
        # (10) est vite dépassée sur les mêmes hôtes (TMDB/Fanart), ce qui
        # fait fermer/rouvrir des connexions en boucle ("Connection pool is
        # full, discarding connection") sans que ce soit une erreur, juste
        # un gâchis de connexions TCP. On agrandit le pool en conséquence.
        adaptateur = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=64)
        self.session.mount("https://", adaptateur)
        self.session.mount("http://", adaptateur)
        self.tmdb = ClientTMDB(cle_tmdb, session=self.session)
        self.fanart = ClientFanart(cle_fanart, session=self.session)
        self.mdblist = ClientMDBList(cle_mdblist, session=self.session)
        self.catalogue_custom = ClientCatalogueCustom(session=self.session)
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

    def _telecharger_une_image(self, url: str) -> Image.Image | None:
        try:
            r = self.session.get(url, timeout=20)
            r.raise_for_status()
            return mosaique_module.image_depuis_bytes(r.content)
        except Exception:  # noqa: BLE001
            return None

    def _resoudre_image_tuile(self, candidat: tuple[str | None, int, str, str | None]) -> Image.Image | None:
        """Cascade de résolution pour une tuile, dans l'ordre demandé (revu
        pour limiter le nombre de requêtes et privilégier les sources ayant
        le plus de chances de porter un vrai titre incrusté) :

          1. backdrop TMDB tagué français (pays FR ou non renseigné --
             jamais un backdrop marqué langue "fr" mais pays "CA", cas réel
             rencontré sur "From"/"Supernatural") ;
          2. Fanart "thumb" anglais (movie thumb / tv thumb uniquement --
             plus de background ni clearart, ça évite le détour par un fond
             de compositing et une bonne partie des téléchargements
             inutiles) ;
          3. backdrop TMDB tagué anglais ;
          4. backdrop TMDB tagué avec la langue ORIGINALE du titre (ex:
             coréen pour un drama coréen), si elle diffère de fr/en ;
          5. backdrop TMDB générique (non tagué, sans texte) ;
          6. en tout dernier recours SILENCIEUX (aucune requête
             supplémentaire) : le backdrop brut déjà connu du candidat, pour
             ne jamais laisser une tuile complètement vide.
        """
        backdrop_path, tmdb_id, media_type, langue_originale = candidat
        logging.debug("[TUILE] Résolution pour tmdb_id=%s (%s), langue préférée=%s", tmdb_id, media_type, self.langue_preferee)

        if not tmdb_id:
            logging.debug("[TUILE] Pas de tmdb_id -> backdrop brut du candidat directement")
            return self._telecharger_une_image(f"{TMDB_IMAGE_BASE}/w1280{backdrop_path}") if backdrop_path else None

        images_tmdb = self.tmdb.recuperer_images(tmdb_id, media_type, langue_originale)

        # 1) TMDB dans la langue préférée -- le filtre pays FR n'a de sens
        # que pour le français (voir le cas fr/CA plus haut) ; pour toute
        # autre langue préférée, pas de restriction pays.
        if self.langue_preferee:
            pays_autorises = {"FR"} if self.langue_preferee.lower() == "fr" else None
            chemin = meilleur_backdrop_tmdb_langue(images_tmdb, self.langue_preferee, pays_autorises=pays_autorises)
            if chemin:
                brut: dict[str, Any] = next((b for b in (images_tmdb.get("backdrops") or []) if b.get("file_path") == chemin), {})
                image = self._telecharger_une_image(f"{TMDB_IMAGE_BASE}/w1280{chemin}")
                if image:
                    logging.info(
                        "[TUILE] tmdb_id=%s -> retenu (1) : TMDB backdrop %s (langue='%s' pays='%s')",
                        tmdb_id, chemin, brut.get("iso_639_1"), brut.get("iso_3166_1"),
                    )
                    return image
                logging.debug("[TUILE] tmdb_id=%s : TMDB backdrop fr trouvé mais téléchargement échoué", tmdb_id)

        # 2) Fanart "thumb" anglais uniquement -- pas de clé configurée ou
        # pas de données : palier simplement sauté (pas d'erreur, cas
        # normal et fréquent).
        if self.fanart.cle_api:
            identifiant_fanart = self.tmdb.recuperer_tvdb_id(tmdb_id) if media_type == "tv" else tmdb_id
            if not identifiant_fanart:
                logging.warning("[TUILE] tmdb_id=%s (tv) : échec de conversion tmdb_id->tvdb_id, Fanart sauté", tmdb_id)
            else:
                fanart_data = self.fanart.donnees(identifiant_fanart, media_type)
                if fanart_data:
                    url_thumb_en = self.fanart.url_par_type_et_langue(fanart_data, media_type, "thumb", "en")
                    if url_thumb_en:
                        image = self._telecharger_une_image(url_thumb_en)
                        if image:
                            logging.info("[TUILE] tmdb_id=%s -> retenu (2) : Fanart thumb anglais", tmdb_id)
                            return image
                elif fanart_data is None:
                    logging.debug("[TUILE] tmdb_id=%s : Fanart n'a renvoyé aucune donnée exploitable (voir logs [FANART] ci-dessus)", tmdb_id)

        # 3) TMDB anglais.
        chemin_en = meilleur_backdrop_tmdb_langue(images_tmdb, "en")
        if chemin_en:
            image = self._telecharger_une_image(f"{TMDB_IMAGE_BASE}/w1280{chemin_en}")
            if image:
                logging.info("[TUILE] tmdb_id=%s -> retenu (3) : TMDB backdrop anglais %s", tmdb_id, chemin_en)
                return image
            logging.debug("[TUILE] tmdb_id=%s : TMDB backdrop en trouvé mais téléchargement échoué", tmdb_id)

        # 4) TMDB langue native du titre (si différente de fr/en).
        if langue_originale and langue_originale.lower() not in {(self.langue_preferee or "").lower(), "en"}:
            chemin_natif = meilleur_backdrop_tmdb_langue(images_tmdb, langue_originale)
            if chemin_natif:
                image = self._telecharger_une_image(f"{TMDB_IMAGE_BASE}/w1280{chemin_natif}")
                if image:
                    logging.info(
                        "[TUILE] tmdb_id=%s -> retenu (4) : TMDB backdrop langue native '%s'", tmdb_id, langue_originale,
                    )
                    return image

        # 5) TMDB générique (non tagué, sans texte).
        chemin_generique = meilleur_backdrop_tmdb_langue(images_tmdb, None)
        if chemin_generique:
            image = self._telecharger_une_image(f"{TMDB_IMAGE_BASE}/w1280{chemin_generique}")
            if image:
                logging.info("[TUILE] tmdb_id=%s -> retenu (5) : TMDB backdrop générique non taggué", tmdb_id)
                return image

        # 6) Dernier recours silencieux : backdrop brut déjà connu, aucune requête de plus.
        if backdrop_path:
            logging.info("[TUILE] tmdb_id=%s -> retenu (6, dernier recours) : backdrop brut du candidat", tmdb_id)
            return self._telecharger_une_image(f"{TMDB_IMAGE_BASE}/w1280{backdrop_path}")
        logging.warning("[TUILE] tmdb_id=%s -> ÉCHEC TOTAL : aucune image trouvée", tmdb_id)
        return None

    def _telecharger_images_pour_mosaique(
        self, candidats: list[tuple[str | None, int, str, str | None]]
    ) -> list[Image.Image]:
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

    def _resoudre_liste_candidats(self, requete: RequeteTMDB, cible: int, pages: int) -> list[tuple[str | None, int, str, str | None]]:
        """Résout une requête en liste de candidats (backdrop_path, tmdb_id,
        media_type, langue_originale) -- gère aussi bien les requêtes TMDB
        classiques que les listes MDBList (`kind == "mdblist_liste"`) et les
        catalogues Stremio "custom" type Bingecat (`kind == "custom_catalogue"`)."""
        if requete.kind == "mdblist_liste":
            if "mdblist_id" in requete.params:
                items = self.mdblist.recuperer_items_liste_par_id(requete.params["mdblist_id"], limite=cible)
            else:
                items = self.mdblist.recuperer_items_liste(
                    requete.params["mdblist_user"], requete.params["mdblist_slug"], limite=cible
                )
            return [(None, tmdb_id, media_type, None) for tmdb_id, media_type in items]
        if requete.kind == "custom_catalogue":
            # On demande un peu plus d'ids IMDb que la cible : certains ne se
            # résolvent pas côté TMDB (retiré/introuvable), autant limiter le
            # risque de retomber sous la cible après conversion.
            ids_imdb = self.catalogue_custom.recuperer_ids_imdb(requete.params["url"], limite=cible * 2)
            candidats: list[tuple[str | None, int, str, str | None]] = []
            for imdb_id in ids_imdb:
                resolu = self.tmdb.resoudre_imdb_vers_tmdb(imdb_id)
                if resolu:
                    tmdb_id, media_type, backdrop_path, langue_originale = resolu
                    candidats.append((backdrop_path, tmdb_id, media_type, langue_originale))
                if len(candidats) >= cible:
                    break
            return candidats
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

        chemin_relatif = Path(GROUPE_SLUGS.get(normaliser(groupe_titre), slugifier(groupe_titre))) / NOM_DOSSIER_BACKDROPS / f"{nom_fichier_backdrop(dossier_titre)}.jpg"
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
    parser.add_argument("--cle-mdblist", default=None, help="Clé API MDBList.com, pour résoudre les sources provider=mdblist (optionnel, ou variable MDBLIST_API_KEY)")
    parser.add_argument("--aiometadata", default=None, help="Chemin vers un export AIOMetadata (JSON) pour résoudre les catalogues avec leurs vrais filtres TMDB (optionnel)")
    parser.add_argument("--collections", default="Templates/Nuvio-Collections-Dwade58200.json")
    parser.add_argument("--sortie", default=NOM_DOSSIER_RACINE)
    parser.add_argument("--profil", choices=list(PROFILS_QUALITE), default="standard")
    parser.add_argument("--parallelisme", type=int, default=4)
    parser.add_argument("--groupe", default=None, help="Ne traiter qu'un seul groupe (ex: Genres)")
    parser.add_argument("--limite", type=int, default=None, help="Limiter le nombre de dossiers (tests)")
    parser.add_argument("--dry-run", action="store_true", help="Simule sans appeler TMDB ni écrire d'image")
    parser.add_argument("--mosaique", action="store_true", help="Génère une mosaïque multi-titres + couleur d'accent au lieu d'un seul backdrop (repli automatique si pas assez d'images)")
    parser.add_argument("--langue-preferee", default="fr", help="Code langue préféré pour le backdrop TMDB avec titre incrusté (palier 1 de la cascade -- n'affecte PAS Fanart.tv, qui ne cherche que l'anglais) (défaut: fr)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

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
        cle_mdblist=args.cle_mdblist or os.environ.get("MDBLIST_API_KEY"),
        catalogues_aiometadata=charger_catalogues_aiometadata(Path(args.aiometadata) if args.aiometadata else None),
    )

    resultats = generateur.generer_tout(
        collections, parallelisme=args.parallelisme, filtre_groupe=args.groupe, limite=args.limite
    )
    afficher_resume(resultats)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
