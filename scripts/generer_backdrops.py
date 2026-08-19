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
import re
import sys
import time
import unicodedata
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


# ---------------------------------------------------------------------------
# Configuration générale
# ---------------------------------------------------------------------------

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
FANART_API_BASE = "https://webservice.fanart.tv/v3"

# Titres EXACTS des groupes tels qu'ils existent réellement dans le JSON.
# (le bug initial venait d'un mauvais mapping ici -> corrigé)
GROUPE_DECOUVRIR = "🔭 Découvrir"
GROUPE_STREAMING = "🎬Services de Streaming"
GROUPE_GENRES = "🎭Genres"
GROUPE_THEMATIQUES = "🎨 Thématiques"
GROUPE_VIBES = "Vibe"
GROUPE_ANNEES = "📅 Années"
GROUPE_FRANCHISES = "Franchises"
GROUPE_SPORTS = "Sports"

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
    GROUPE_STREAMING: CritereGroupe(actif=False),  # sources non-TMDB (FlixPatrol)
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


def construire_requetes(
    groupe_titre: str, dossier: dict[str, Any]
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
                params = _mapper_filtres_discover(source.get("filters") or {}, media_type)
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

            ignorees.append(f"addon/aio-metadata catalogId non résolu ({catalog_id})")

        elif provider == "trakt":
            ignorees.append("trakt (nécessite une clé API Trakt — phase ultérieure)")
        else:
            ignorees.append(f"provider non géré ({provider})")

    # Repli final si AUCUNE source n'a donné de requête exploitable :
    # pour les groupes Genres / Thématiques, on tente de deviner à partir
    # du TITRE du dossier lui-même (ex: dossier "Action" -> genre Action).
    if not requetes and groupe_titre in (GROUPE_GENRES,):
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
    critere = CRITERES_GROUPES.get(groupe_titre)
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
    def __init__(self, cle_api: str, session: requests.Session | None = None, langue: str = "fr-FR"):
        self.cle_api = cle_api
        self.session = session or requests.Session()
        self.langue = langue
        self._cache_keyword: dict[str, int | None] = {}

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
        if mot in self._cache_keyword:
            return self._cache_keyword[mot]
        try:
            data = self._get("/search/keyword", {"query": mot})
            resultats = data.get("results") or []
            keyword_id = resultats[0]["id"] if resultats else None
        except requests.RequestException:
            keyword_id = None
        self._cache_keyword[mot] = keyword_id
        return keyword_id

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


class ClientFanart:
    def __init__(self, cle_api: str | None, session: requests.Session | None = None):
        self.cle_api = cle_api
        self.session = session or requests.Session()

    def recuperer_backdrop(self, tmdb_id: int, media_type: str) -> str | None:
        if not self.cle_api or not tmdb_id:
            return None
        chemin = "movies" if media_type == "movie" else "tv"
        try:
            r = self.session.get(
                f"{FANART_API_BASE}/{chemin}/{tmdb_id}",
                params={"api_key": self.cle_api},
                timeout=15,
            )
            if r.status_code != 200:
                return None
            data = r.json()
            for cle in ("moviebackground", "showbackground", "tvthumb"):
                items = data.get(cle) or []
                images_fr = [i for i in items if i.get("lang") in ("fr", "00")]
                choix = images_fr or items
                if choix:
                    return choix[0]["url"]
        except requests.RequestException:
            return None
        return None


# ---------------------------------------------------------------------------
# Téléchargement + traitement d'image
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
    ):
        self.session = requests.Session()
        self.tmdb = ClientTMDB(cle_tmdb, session=self.session)
        self.fanart = ClientFanart(cle_fanart, session=self.session)
        self.repertoire_sortie = repertoire_sortie
        self.profil = profil
        self.dry_run = dry_run

    def traiter_dossier(self, groupe_titre: str, dossier: dict[str, Any]) -> ResultatDossier:
        dossier_titre = dossier.get("title", "sans-titre")

        if not dossier_actif(groupe_titre, dossier_titre):
            return ResultatDossier(groupe_titre, dossier_titre, "ignore", "groupe/dossier non ciblé en phase 1")

        requetes, raisons = construire_requetes(groupe_titre, dossier)
        if not requetes:
            raison = "; ".join(raisons) or "aucune source exploitable"
            return ResultatDossier(groupe_titre, dossier_titre, "ignore", raison)

        chemin_relatif = Path(GROUPE_SLUGS.get(groupe_titre, slugifier(groupe_titre))) / "backdrop" / f"{slugifier(dossier_titre)}.jpg"
        chemin_sortie = self.repertoire_sortie / chemin_relatif

        if self.dry_run:
            return ResultatDossier(groupe_titre, dossier_titre, "genere", f"(dry-run) {len(requetes)} requête(s) prête(s)", str(chemin_relatif))

        for requete in requetes:
            backdrop_path, tmdb_id, media_type = self.tmdb.resoudre_backdrop(requete)
            url_image = None

            if backdrop_path:
                url_image = f"{TMDB_IMAGE_BASE}/original{backdrop_path}"
            elif tmdb_id and media_type:
                url_fanart = self.fanart.recuperer_backdrop(tmdb_id, media_type)
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
        for groupe in collections:
            titre_groupe = groupe.get("title", "")
            if filtre_groupe and normaliser(filtre_groupe) not in normaliser(titre_groupe):
                continue
            for dossier in groupe.get("folders", []):
                taches.append((titre_groupe, dossier))

        if limite:
            taches = taches[:limite]

        resultats: list[ResultatDossier] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallelisme) as executor:
            futurs = {
                executor.submit(self.traiter_dossier, titre_groupe, dossier): (titre_groupe, dossier)
                for titre_groupe, dossier in taches
            }
            for futur in concurrent.futures.as_completed(futurs):
                resultats.append(futur.result())

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
    parser.add_argument("--collections", default="Templates/Nuvio-Collections-Dwade58200.json")
    parser.add_argument("--sortie", default="collections")
    parser.add_argument("--profil", choices=list(PROFILS_QUALITE), default="standard")
    parser.add_argument("--parallelisme", type=int, default=4)
    parser.add_argument("--groupe", default=None, help="Ne traiter qu'un seul groupe (ex: Genres)")
    parser.add_argument("--limite", type=int, default=None, help="Limiter le nombre de dossiers (tests)")
    parser.add_argument("--dry-run", action="store_true", help="Simule sans appeler TMDB ni écrire d'image")
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
        cle_fanart=args.cle_fanart or __import__("os").environ.get("FANART_API_KEY"),
        repertoire_sortie=Path(args.sortie),
        profil=args.profil,
        dry_run=args.dry_run,
    )
    resultats = generateur.generer_tout(
        collections, parallelisme=args.parallelisme, filtre_groupe=args.groupe, limite=args.limite
    )
    afficher_resume(resultats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
