"""Tests pour scripts/valider_collections.py."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from valider_collections import valider  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
SCHEMA = RACINE / "schema" / "nuvio-collections.schema.json"
COLLECTIONS_REELLES = RACINE / "Templates" / "Nuvio-Collections-Dwade58200.json"


def test_le_vrai_fichier_de_collections_est_conforme_au_schema():
    """Régression : le schéma doit rester synchronisé avec ce que le code
    (`construire_requetes`) accepte réellement, sinon la CI casse sur un
    fichier par ailleurs parfaitement valide."""
    erreurs = valider(COLLECTIONS_REELLES, SCHEMA)
    assert erreurs == []


def test_groupe_sans_folders_est_rejete(tmp_path):
    chemin = tmp_path / "collections.json"
    chemin.write_text(json.dumps([{"title": "Genres"}]), encoding="utf-8")

    erreurs = valider(chemin, SCHEMA)

    assert len(erreurs) >= 1


def test_source_tmdb_sans_tmdbsourcetype_est_rejetee(tmp_path):
    chemin = tmp_path / "collections.json"
    donnees = [
        {
            "title": "Genres",
            "folders": [
                {
                    "id": "action",
                    "title": "Action",
                    "sources": [{"provider": "tmdb", "mediaType": "MOVIE"}],  # tmdbSourceType manquant
                }
            ],
        }
    ]
    chemin.write_text(json.dumps(donnees), encoding="utf-8")

    erreurs = valider(chemin, SCHEMA)

    assert len(erreurs) >= 1


def test_source_mdblist_avec_juste_une_url_est_acceptee(tmp_path):
    """Format documenté dans BACKDROPS_SETUP.md pour ajouter une liste
    MDBList à la main -- une seule des 3 façons (mdblistUrl seule ici)
    suffit, `catalogId` n'est PAS requis pour ce provider."""
    chemin = tmp_path / "collections.json"
    donnees = [
        {
            "title": "Thématiques",
            "folders": [
                {
                    "id": "sitcom",
                    "title": "Sitcom",
                    "sources": [
                        {"provider": "mdblist", "mdblistUrl": "https://mdblist.com/lists/quelquun/une-liste"}
                    ],
                }
            ],
        }
    ]
    chemin.write_text(json.dumps(donnees), encoding="utf-8")

    erreurs = valider(chemin, SCHEMA)

    assert erreurs == []


def test_source_mdblist_sans_aucun_identifiant_est_rejetee(tmp_path):
    chemin = tmp_path / "collections.json"
    donnees = [
        {
            "title": "Thématiques",
            "folders": [
                {"id": "sitcom", "title": "Sitcom", "sources": [{"provider": "mdblist"}]},
            ],
        }
    ]
    chemin.write_text(json.dumps(donnees), encoding="utf-8")

    erreurs = valider(chemin, SCHEMA)

    assert len(erreurs) >= 1


def test_provider_inconnu_est_rejete(tmp_path):
    chemin = tmp_path / "collections.json"
    donnees = [
        {
            "title": "Genres",
            "folders": [
                {"id": "action", "title": "Action", "sources": [{"provider": "trakt"}]},
            ],
        }
    ]
    chemin.write_text(json.dumps(donnees), encoding="utf-8")

    erreurs = valider(chemin, SCHEMA)

    assert len(erreurs) >= 1
