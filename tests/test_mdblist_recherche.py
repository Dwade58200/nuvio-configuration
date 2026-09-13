"""
Tests pour mdblist_recherche.py -- script local (pas de CI) de recherche
de listes publiques MDBList, sans aucune couverture jusqu'ici.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mdblist_recherche  # noqa: E402
from mdblist_recherche import afficher, main, rechercher  # noqa: E402


class FausseReponse:
    def __init__(self, status_code: int = 200, donnees=None):
        self.status_code = status_code
        self._donnees = donnees

    def json(self):
        return self._donnees

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


def test_rechercher_trie_par_nombre_items_decroissant(monkeypatch):
    donnees = [
        {"name": "Petite liste", "items": 5, "user_name": "bob", "slug": "petite"},
        {"name": "Grosse liste", "items": 500, "user_name": "ana", "slug": "grosse"},
        {"name": "Sans items", "user_name": "zed", "slug": "vide"},  # pas de clé "items"
    ]
    monkeypatch.setattr("mdblist_recherche.requests.get", MagicMock(return_value=FausseReponse(200, donnees)))

    resultats = rechercher("cle123", "james bond")

    assert [r["name"] for r in resultats] == ["Grosse liste", "Petite liste", "Sans items"]


def test_rechercher_transmet_bien_la_cle_et_la_requete(monkeypatch):
    get_mock = MagicMock(return_value=FausseReponse(200, []))
    monkeypatch.setattr("mdblist_recherche.requests.get", get_mock)

    rechercher("ma-cle", "star wars")

    _url, kwargs = get_mock.call_args
    assert kwargs["params"] == {"apikey": "ma-cle", "query": "star wars"}


def test_rechercher_cle_invalide_quitte_avec_code_1(monkeypatch, capsys):
    monkeypatch.setattr("mdblist_recherche.requests.get", MagicMock(return_value=FausseReponse(401)))

    with pytest.raises(SystemExit) as exc_info:
        rechercher("mauvaise-cle", "james bond")

    assert exc_info.value.code == 1
    assert "clé API invalide" in capsys.readouterr().err


def test_rechercher_erreur_serveur_leve_httperror(monkeypatch):
    monkeypatch.setattr("mdblist_recherche.requests.get", MagicMock(return_value=FausseReponse(500)))

    with pytest.raises(requests.exceptions.HTTPError):
        rechercher("cle123", "james bond")


def test_rechercher_reponse_inattendue_retourne_liste_vide(monkeypatch, capsys):
    """L'API répond en principe une liste JSON -- si un jour elle renvoie
    autre chose (ex: un objet d'erreur), on ne plante pas en tentant de
    trier un non-itérable, on prévient et on retourne []."""
    monkeypatch.setattr(
        "mdblist_recherche.requests.get", MagicMock(return_value=FausseReponse(200, {"error": "oops"}))
    )

    resultats = rechercher("cle123", "james bond")

    assert resultats == []
    assert "inattendue" in capsys.readouterr().err.lower()


def test_afficher_liste_vide(capsys):
    afficher([])
    assert "Aucune liste trouvée." in capsys.readouterr().out


def test_afficher_formate_le_snippet_et_les_infos(capsys):
    afficher(
        [
            {
                "name": "James Bond Collection",
                "user_name": "007fan",
                "slug": "james-bond",
                "items": 27,
                "likes": 12,
                "mediatype": "movie",
            }
        ]
    )
    sortie = capsys.readouterr().out
    assert "James Bond Collection" in sortie
    assert "27 items" in sortie
    assert "12 likes" in sortie
    assert "https://mdblist.com/lists/007fan/james-bond" in sortie
    assert '"provider": "mdblist"' in sortie
    assert '"mdblistUrl": "https://mdblist.com/lists/007fan/james-bond"' in sortie
    assert "🔒" not in sortie


def test_afficher_signale_les_listes_privees_et_valeurs_par_defaut(capsys):
    """Une liste privée doit être signalée clairement (inaccessible sans
    être connecté avec le compte propriétaire) ; les champs absents
    (likes, mediatype) doivent avoir un repli propre plutôt que planter."""
    afficher([{"name": "Perso", "user_name": "moi", "slug": "perso", "private": True}])
    sortie = capsys.readouterr().out
    assert "🔒 PRIVÉE" in sortie
    assert "0 likes" in sortie
    assert "mixte" in sortie


def test_main_sans_cle_api_ni_variable_environnement_echoue(monkeypatch, capsys):
    monkeypatch.delenv("MDBLIST_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["mdblist_recherche.py", "james bond"])

    assert main() == 1
    assert "clé API manquante" in capsys.readouterr().err


def test_main_utilise_la_variable_environnement_si_present(monkeypatch):
    monkeypatch.setenv("MDBLIST_API_KEY", "cle-env")
    monkeypatch.setattr("sys.argv", ["mdblist_recherche.py", "james bond"])
    rechercher_mock = MagicMock(return_value=[])
    monkeypatch.setattr(mdblist_recherche, "rechercher", rechercher_mock)
    monkeypatch.setattr(mdblist_recherche, "afficher", MagicMock())

    assert main() == 0
    rechercher_mock.assert_called_once_with("cle-env", "james bond")


def test_main_argument_cle_api_prend_le_pas_sur_la_variable_environnement(monkeypatch):
    monkeypatch.setenv("MDBLIST_API_KEY", "cle-env")
    monkeypatch.setattr("sys.argv", ["mdblist_recherche.py", "--cle-api", "cle-argument", "star wars"])
    rechercher_mock = MagicMock(return_value=[])
    monkeypatch.setattr(mdblist_recherche, "rechercher", rechercher_mock)
    monkeypatch.setattr(mdblist_recherche, "afficher", MagicMock())

    assert main() == 0
    rechercher_mock.assert_called_once_with("cle-argument", "star wars")
