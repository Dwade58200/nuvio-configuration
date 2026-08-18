#!/usr/bin/env python3
"""
Génère les fonds d'écran (backdrops) pour les collections Nuvio.

Objectif:
    Ce script lit le fichier Nuvio-Collections-Dwade58200.json pour :
    1. Charger les définitions des dossiers de collections
    2. Extraire les sources de catalogue TMDB
    3. Filtrer selon les critères spécifiés (pas TV, pas Magnet, pas Sports, etc.)
    4. Générer les images de fond via les APIs TMDB/FanArt
    5. Sauvegarder les backdrops dans collections/[groupe]/fond/

Groupes et critères de génération:
    Découvrir: Recommandation, Tendance, Populaire, Top (SAUF TV, Magnet)
    Genres: Tous
    Thématiques: Tous
    Vibes: Tous
    Années: Tous
    Sports: Aucun
    Services de Streaming: SAUF Netflix, Prime Video, HBO Max, etc. (non-TMDB)
    Franchises: Aucun

Paramètres:
    --cle-api: Clé API TMDB (obligatoire)
    --cle-fanart: Clé API FanArt.tv (optionnel)
    --collections: Chemin vers Nuvio-Collections-Dwade58200.json
    --sortie: Répertoire de sortie pour les backdrops
    --profil: Profil de qualité (compresse, standard, qualite-haute)
    --parallelisme: Nombre de téléchargements parallèles
    --log-groupe: Afficher les logs groupés par dossier

Exemples:
    python3 -B generer_backdrops.py \\
      --cle-api VOTRE_CLE_TMDB \\
      --cle-fanart VOTRE_CLE_FANART

    python3 -B generer_backdrops.py \\
      --cle-api VOTRE_CLE_TMDB \\
      --profil qualite-haute
"""

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import requests
from PIL import Image
from io import BytesIO

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
REPERTOIRE_COLLECTIONS_PAR_DEFAUT = REPO_ROOT / "collections"
FICHIER_COLLECTIONS_PAR_DEFAUT = REPO_ROOT / "Templates" / "Nuvio-Collections-Dwade58200.json"

# Critères de filtrage pour chaque groupe de collections
CRITERES_FILTRAGE = {
    "🔭 Découvrir": {
        "inclure": ["Recommandation", "Tendance", "Populaire", "Top"],
        "exclure": ["TV", "Magnet"]
    },
    "🎭 Genres": {
        "inclure": None,  # Tous
        "exclure": []
    },
    "🎨 Thématiques": {
        "inclure": None,
        "exclure": []
    },
    "✨ Vibes": {
        "inclure": None,
        "exclure": []
    },
    "📅 Années": {
        "inclure": None,
        "exclure": []
    },
    "🏆 Sports": {
        "inclure": [],  # Aucun
        "exclure": None
    },
    "🎬 Services de Streaming": {
        "inclure": [],  # Aucun (sources non-TMDB)
        "exclure": None
    },
    "🎬Services de Streaming": {  # Variante sans espace
        "inclure": [],
        "exclure": None
    },
    "🎥 Franchises": {
        "inclure": [],
        "exclure": None
    }
}


def charger_json(chemin: Path) -> dict:
    """Charge un fichier JSON."""
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erreur lors du chargement de {chemin}: {e}", file=sys.stderr)
        sys.exit(1)


def doit_generer_backdrop(groupe_titre: str, dossier_titre: str) -> bool:
    """Détermine si un dossier doit avoir un backdrop généré."""
    criteres = CRITERES_FILTRAGE.get(groupe_titre)
    
    if criteres is None:
        return False
    
    inclure = criteres.get("inclure")
    exclure = criteres.get("exclure", [])
    
    # Si la liste d'inclusion est vide et exclure n'est pas None, exclure tout
    if inclure is not None and len(inclure) == 0:
        return False
    
    # Vérifier les exclusions
    if exclure:
        for motif_exclu in exclure:
            if motif_exclu.lower() in dossier_titre.lower():
                return False
    
    # Vérifier les inclusions si spécifiées
    if inclure is not None:
        for motif_inclus in inclure:
            if motif_inclus.lower() in dossier_titre.lower():
                return True
        return False
    
    # Si inclure est None (tous les dossiers), retourner True
    return True


def extraire_sources_tmdb(dossier: Dict) -> List[Dict]:
    """Extrait les sources TMDB valides d'un dossier."""
    sources_tmdb = []
    sources = dossier.get("sources", [])
    
    for source in sources:
        # Vérifier que c'est une source TMDB valide
        provider = source.get("provider", "").lower()
        addon_id = source.get("addonId", "").lower()
        
        # Accepter les sources aio-metadata (qui contiennent des catalogues TMDB)
        if provider == "addon" and "aio-metadata" in addon_id:
            type_media = source.get("type")
            catalog_id = source.get("catalogId")
            
            if type_media and catalog_id:
                sources_tmdb.append({
                    "type": type_media,
                    "catalogueId": catalog_id
                })
        
        # Accepter aussi les sources TMDB directes
        elif provider == "tmdb":
            sources_tmdb.append({
                "type": source.get("mediaType", "").lower(),
                "filtres": source.get("filters", {}),
                "triPar": source.get("sortBy"),
                "catalogueId": None
            })
    
    return sources_tmdb


class GenerateurBackdrops:
    """Génère et traite les backdrops pour les collections Nuvio."""

    def __init__(self, cle_api_tmdb: str, cle_fanart: Optional[str] = None, 
                 profil: str = "compresse", parallelisme: int = 3):
        self.cle_api_tmdb = cle_api_tmdb
        self.cle_fanart = cle_fanart
        self.profil = profil
        self.parallelisme = parallelisme
        self.compteur_generes = 0
        self.compteur_ignores = 0
        self.compteur_erreurs = 0

    def telecharger_et_traiter_image(self, url: str, chemin_sortie: Path) -> bool:
        """Télécharge et traite une image."""
        try:
            reponse = requests.get(url, timeout=15)
            reponse.raise_for_status()
            
            img = Image.open(BytesIO(reponse.content))
            
            # Convertir en RGB si nécessaire
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            
            # Appliquer le profil
            if self.profil == "compresse":
                img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
                img.save(chemin_sortie, "JPEG", quality=85, optimize=True)
            elif self.profil == "qualite-haute":
                img.thumbnail((4096, 2160), Image.Resampling.LANCZOS)
                img.save(chemin_sortie, "JPEG", quality=95)
            else:
                img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
                img.save(chemin_sortie, "JPEG", quality=90)
            
            return True
        except Exception as e:
            print(f"Erreur lors du traitement de l'image {url}: {e}", file=sys.stderr)
            return False

    def recuperer_backdrop_tmdb(self, item_id: int, type_media: str) -> Optional[str]:
        """Récupère l'URL du backdrop depuis TMDB."""
        try:
            endpoint = f"https://api.themoviedb.org/3/{type_media}/{item_id}"
            params = {"api_key": self.cle_api_tmdb, "language": "fr-FR"}
            reponse = requests.get(endpoint, params=params, timeout=10)
            reponse.raise_for_status()
            donnees = reponse.json()
            
            if "backdrop_path" in donnees and donnees["backdrop_path"]:
                return f"https://image.tmdb.org/t/p/original{donnees['backdrop_path']}"
        except Exception as e:
            print(f"Erreur TMDB pour {type_media} {item_id}: {e}", file=sys.stderr)
        
        return None

    def recuperer_backdrop_fanart(self, item_id: int, type_media: str) -> Optional[str]:
        """Récupère l'URL du backdrop depuis FanArt."""
        if not self.cle_fanart:
            return None
        
        try:
            endpoint = f"https://webservice.fanart.tv/v3/{type_media}/{item_id}"
            params = {"api_key": self.cle_fanart}
            reponse = requests.get(endpoint, params=params, timeout=10)
            reponse.raise_for_status()
            donnees = reponse.json()
            
            if "backdrops" in donnees and donnees["backdrops"]:
                return donnees["backdrops"][0]["url"]
        except Exception as e:
            print(f"Erreur FanArt pour {type_media} {item_id}: {e}", file=sys.stderr)
        
        return None

    def generer_backdrop_pour_catalogue(self, groupe: str, dossier_titre: str, 
                                       sources_tmdb: List[Dict], 
                                       repertoire_sortie: Path) -> bool:
        """Génère un backdrop en combinant les images des sources TMDB."""
        if not sources_tmdb:
            return False
        
        chemin_sortie = repertoire_sortie / groupe.split()[0].replace("🔭", "").replace("🎭", "").replace("🎨", "").replace("✨", "").replace("📅", "").strip().lower() / "fond" / f"{dossier_titre.lower().replace(' ', '-')}.jpg"
        chemin_sortie.parent.mkdir(parents=True, exist_ok=True)
        
        # Récupérer des images depuis TMDB
        url_backdrop = None
        for source in sources_tmdb[:1]:  # Utiliser la première source
            try:
                # Récupérer un titre populaire du catalogue
                type_media = "movie" if source.get("type") == "movie" else "tv"
                
                # Utiliser une liste TMDB standard
                endpoint_decouverte = f"https://api.themoviedb.org/3/discover/{type_media}"
                params = {
                    "api_key": self.cle_api_tmdb,
                    "language": "fr-FR",
                    "sort_by": "popularity.desc",
                    "page": 1
                }
                
                reponse = requests.get(endpoint_decouverte, params=params, timeout=10)
                reponse.raise_for_status()
                donnees = reponse.json()
                
                if donnees.get("results"):
                    premier_titre = donnees["results"][0]
                    item_id = premier_titre.get("id")
                    
                    if item_id:
                        url_backdrop = self.recuperer_backdrop_tmdb(item_id, type_media)
                        if not url_backdrop:
                            url_backdrop = self.recuperer_backdrop_fanart(item_id, "movies" if type_media == "movie" else "shows")
            except Exception as e:
                print(f"Erreur lors de la récupération du backdrop: {e}", file=sys.stderr)
        
        if url_backdrop:
            return self.telecharger_et_traiter_image(url_backdrop, chemin_sortie)
        
        return False

    def generer_tous_backdrops(self, donnees_collections: List[Dict], 
                              repertoire_sortie: Path):
        """Génère tous les backdrops selon les critères."""
        taches = []
        
        for groupe in donnees_collections:
            groupe_titre = groupe.get("title", "")
            
            for dossier in groupe.get("folders", []):
                dossier_titre = dossier.get("title", "")
                
                # Vérifier les critères de filtrage
                if not doit_generer_backdrop(groupe_titre, dossier_titre):
                    print(f"⏭️  Ignoré: {groupe_titre} → {dossier_titre}")
                    self.compteur_ignores += 1
                    continue
                
                # Extraire les sources TMDB
                sources_tmdb = extraire_sources_tmdb(dossier)
                
                if sources_tmdb:
                    taches.append((groupe_titre, dossier_titre, sources_tmdb))
                    print(f"✅ En attente: {groupe_titre} → {dossier_titre}")
        
        print(f"\nGénération de {len(taches)} backdrop(s)...\n")
        
        # Traiter en parallèle
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.parallelisme) as executor:
            futures = [
                executor.submit(self.generer_backdrop_pour_catalogue, groupe, dossier, sources, repertoire_sortie)
                for groupe, dossier, sources in taches
            ]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    if future.result():
                        self.compteur_generes += 1
                    else:
                        self.compteur_erreurs += 1
                except Exception as e:
                    print(f"Erreur lors de la génération: {e}", file=sys.stderr)
                    self.compteur_erreurs += 1


def principal():
    """Point d'entrée principal."""
    parseur = argparse.ArgumentParser(
        description="Génère les backdrops pour les collections Nuvio"
    )
    parseur.add_argument("--cle-api", required=True, help="Clé API TMDB")
    parseur.add_argument("--cle-fanart", default=None, help="Clé API FanArt.tv")
    parseur.add_argument("--collections", default=str(FICHIER_COLLECTIONS_PAR_DEFAUT), 
                        help="Chemin vers Nuvio-Collections-Dwade58200.json")
    parseur.add_argument("--sortie", default=str(REPERTOIRE_COLLECTIONS_PAR_DEFAUT), 
                        help="Répertoire de sortie")
    parseur.add_argument("--profil", choices=["compresse", "standard", "qualite-haute"], 
                        default="compresse", help="Profil de qualité")
    parseur.add_argument("--parallelisme", type=int, default=3, 
                        help="Nombre de téléchargements parallèles")
    parseur.add_argument("--log-groupe", action="store_true", 
                        help="Afficher les logs groupés")
    
    args = parseur.parse_args()
    
    # Charger les collections
    donnees_collections = charger_json(Path(args.collections))
    
    # Créer le générateur
    generateur = GenerateurBackdrops(
        args.cle_api,
        args.cle_fanart,
        args.profil,
        args.parallelisme
    )
    
    # Générer les backdrops
    generateur.generer_tous_backdrops(donnees_collections, Path(args.sortie))
    
    # Afficher le résumé
    print(f"\n📊 Résumé:")
    print(f"✅ Générés: {generateur.compteur_generes}")
    print(f"⏭️  Ignorés: {generateur.compteur_ignores}")
    print(f"❌ Erreurs: {generateur.compteur_erreurs}")


if __name__ == "__main__":
    principal()
