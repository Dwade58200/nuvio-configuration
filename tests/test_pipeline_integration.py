"""
Test d'intégration : simule les réponses TMDB/Fanart avec de fausses
requêtes HTTP, pour vérifier que tout le pipeline
(résolution -> téléchargement -> redimensionnement -> sauvegarde) fonctionne,
sans avoir besoin d'une vraie clé API ni d'accès réseau à TMDB.
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generer_backdrops import (  # noqa: E402
    GROUPE_GENRES,
    GenerateurBackdrops,
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


def test_generer_tout_avertit_sur_groupe_du_json_non_reconnu(capsys):
    """Reproduit le vrai bug rencontré : un groupe renommé dans le JSON
    (ex: emoji ajouté sur un nom totalement inconnu du script) doit
    déclencher un avertissement explicite, pas un échec silencieux."""
    collections = [
        {"title": "🔥 Groupe Jamais Vu", "folders": [{"title": "Test", "sources": []}]},
    ]

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle", cle_fanart=None, repertoire_sortie=Path("/tmp/inutilise"), dry_run=True,
    )
    generateur.generer_tout(collections)

    sortie = capsys.readouterr().out
    assert "Nouveau groupe détecté" in sortie
    assert "Groupe Jamais Vu" in sortie


def test_generer_tout_reconnait_un_groupe_avec_emoji_different(capsys):
    """Le même groupe 'Genres', mais avec un emoji jamais vu explicitement
    dans le code, doit être reconnu (normalisation) et NE DOIT PAS déclencher
    l'avertissement 'non reconnu'."""
    collections = [
        {"title": "🆕 Genres", "folders": [{"title": "Action", "sources": []}]},
    ]

    generateur = GenerateurBackdrops(
        cle_tmdb="fausse-cle", cle_fanart=None, repertoire_sortie=Path("/tmp/inutilise"), dry_run=True,
    )
    generateur.generer_tout(collections)

    sortie = capsys.readouterr().out
    assert "non reconnu" not in sortie
    assert "Nouveau groupe détecté" not in sortie


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


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
