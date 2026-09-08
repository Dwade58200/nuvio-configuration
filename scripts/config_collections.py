#!/usr/bin/env python3
"""
config_collections.py
=======================

Toute la configuration éditable du pipeline de backdrops Nuvio, séparée de
la logique (`generer_backdrops.py`) : c'est le SEUL fichier à ouvrir pour
ajouter/exclure un groupe, renommer un fichier de backdrop, ajuster un
filtre de dossiers, ou ajouter un genre/réseau TV connu.

Ce module est un fichier de DONNÉES pures : aucune dépendance vers
`generer_backdrops.py` (pour éviter tout import circulaire), aucun appel
réseau, aucune résolution de source -- seulement des constantes et le
petit type `CritereGroupe` qui les structure.

Depuis la mise à jour "ajout automatique" (voir BACKDROPS_SETUP.md,
section « Ajout/suppression d'une collection dans Nuvio ») : un groupe
absent de CRITERES_GROUPES n'est PLUS ignoré par le pipeline -- il est
traité par défaut avec les réglages génériques (voir `dossier_actif` dans
generer_backdrops.py). Une entrée ici n'est donc nécessaire QUE pour :
  - exclure un groupe (comme Sports/Franchises) ;
  - filtrer certains dossiers d'un groupe (comme Découvrir) ;
  - lui donner un nom de dossier de sortie personnalisé (GROUPE_SLUGS).
Un ajout de collection dans Nuvio n'exige donc pas de retouche ici.

Complément optionnel : `Templates/groupes-config.json`, maintenu par
`scripts/synchroniser_config.py`, PERSISTE les réglages des groupes
auto-détectés au lieu de les laisser implicites -- voir
`appliquer_config_externe()` en bas de ce fichier et BACKDROPS_SETUP.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# =============================================================================
# Titres de groupes
# =============================================================================
# Titres EXACTS des groupes tels qu'ils existent réellement dans le JSON.
# (le bug initial venait d'un mauvais mapping ici -> corrigé, puis reproduit
# une seconde fois quand Nuvio a ajouté/changé des emojis sur les groupes)
#
# Pour ne PLUS jamais casser sur un simple changement d'emoji, d'espace ou
# d'accent, ces constantes sont des clés CANONIQUES et NORMALISÉES (voir
# `normaliser()` dans generer_backdrops.py) : le titre réel du groupe, tel
# qu'il apparaît dans le JSON, est toujours normalisé avant comparaison.
# Exemple : "🎭Genres", "🎭 Genres" et "🎭  Genres " normalisent tous en
# "genres".
GROUPE_DECOUVRIR = "decouvrir"
GROUPE_STREAMING = "services de streaming"
GROUPE_GENRES = "genres"
GROUPE_THEMATIQUES = "thematiques"
GROUPE_VIBES = "vibe"
GROUPE_ANIMES = "animes"
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
    GROUPE_ANIMES: "Animes",
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
# (repli générique automatique, voir `nom_fichier_backdrop` dans
# generer_backdrops.py).
ACRONYMES_BACKDROP = {"tv", "hbo", "tf1", "m6", "vf", "vo"}

# =============================================================================
# Groupes actifs et filtres de dossiers
# =============================================================================


@dataclass(frozen=True)
class CritereGroupe:
    """Groupes activés pour la génération, et filtres optionnels de titres
    de dossiers (inclusion/exclusion). None = tous les dossiers."""

    actif: bool
    inclure: tuple[str, ...] | None = None
    exclure: tuple[str, ...] | None = None


CRITERES_GROUPES: dict[str, CritereGroupe] = {
    GROUPE_DECOUVRIR: CritereGroupe(
        actif=True,
        inclure=("Recommandation", "Tendance", "Populaire", "Top", "Français"),
        exclure=("TV", "Magnet"),
    ),
    GROUPE_STREAMING: CritereGroupe(actif=True),  # certains catalogues sont désormais résolubles via TMDB
    GROUPE_GENRES: CritereGroupe(actif=True),
    GROUPE_THEMATIQUES: CritereGroupe(actif=True),
    GROUPE_VIBES: CritereGroupe(actif=True),
    GROUPE_ANIMES: CritereGroupe(actif=True),  # tout résolu via MDBList/AIOMetadata, aucun filtre nécessaire
    GROUPE_ANNEES: CritereGroupe(actif=True),
    GROUPE_FRANCHISES: CritereGroupe(actif=False),  # désactivé à la demande de l'utilisateur
    GROUPE_SPORTS: CritereGroupe(actif=False),  # pas de backdrop pour le sport
}

# =============================================================================
# Résolution TMDB -- endpoints, genres, réseaux connus
# =============================================================================

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

# =============================================================================
# Config externe optionnelle (Templates/groupes-config.json)
# =============================================================================
# Ce fichier JSON, maintenu par `scripts/synchroniser_config.py`, PERSISTE
# les réglages des groupes découverts automatiquement dans le JSON de
# collections (au lieu de les laisser implicites dans le comportement par
# défaut de `dossier_actif`). Format :
#   {"<titre_groupe_normalise>": {"actif": bool, "slug": str|null,
#                                  "inclure": list[str]|null, "exclure": list[str]|null}}
# Totalement optionnel : absent, rien ne change (comportement par défaut
# de `dossier_actif` inchangé).


def charger_config_groupes_externe(chemin: Path | None) -> dict[str, dict[str, Any]]:
    """Charge `groupes-config.json`. Absent = dict vide."""
    if chemin is None or not chemin.exists():
        return {}
    with chemin.open(encoding="utf-8") as f:
        donnees = json.load(f)
    if not isinstance(donnees, dict):
        raise ValueError(f"{chemin} doit contenir un objet JSON {{titre_groupe: {{...}}}}")
    return donnees


def appliquer_config_externe(chemin: Path | None) -> None:
    """Fusionne `groupes-config.json` DANS CRITERES_GROUPES et GROUPE_SLUGS
    (mutation en place) : une entrée du fichier externe complète ou
    surcharge une entrée codée en dur ici. Sert principalement aux groupes
    ajoutés par `synchroniser_config.py` sans toucher au code Python."""
    overlay = charger_config_groupes_externe(chemin)
    for cle_normalisee, reglages in overlay.items():
        slug = reglages.get("slug")
        if slug:
            GROUPE_SLUGS[cle_normalisee] = slug
        inclure = tuple(reglages["inclure"]) if reglages.get("inclure") else None
        exclure = tuple(reglages["exclure"]) if reglages.get("exclure") else None
        CRITERES_GROUPES[cle_normalisee] = CritereGroupe(
            actif=reglages.get("actif", True), inclure=inclure, exclure=exclure
        )
