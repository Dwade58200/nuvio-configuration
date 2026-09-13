"""
Tests pour purger_cache.py -- en particulier la purge SÉLECTIVE
(--fichiers-modifies), qui évite de purger inutilement des centaines de
fichiers inchangés à chaque run (voir APPLIQUER.md).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from purger_cache import charger_fichiers_modifies, purger_cdn  # noqa: E402


class FausseReponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code


@pytest.fixture
def arborescence(tmp_path: Path) -> Path:
    """Reproduit Collections/<groupe>/Backdrops/<fichier>.jpg pour 2 groupes."""
    racine = tmp_path / "Collections"
    for groupe, titre in (("Genres", "Action"), ("Thematiques", "Noel")):
        dossier = racine / groupe / "Backdrops"
        dossier.mkdir(parents=True)
        (dossier / f"{titre}_Backdrop.jpg").write_bytes(b"\xff\xd8\xff")
    return racine


def test_charger_fichiers_modifies_absent_retourne_none(tmp_path):
    """Fichier --fichiers-modifies absent (ou argument omis) -> None,
    signal explicite pour purger_cdn de repartir sur l'ancien comportement
    (tout purger) -- usage manuel/standalone sans contexte Git."""
    assert charger_fichiers_modifies(tmp_path / "inexistant.txt") is None


def test_charger_fichiers_modifies_fichier_vide_retourne_liste_vide(tmp_path):
    """Fichier présent mais sans ligne (aucun backdrop modifié, seul un
    JSON a changé p.ex.) -> liste VIDE, pas None -- distinction cruciale :
    None veut dire 'tout purger', [] veut dire 'rien à purger'."""
    chemin = tmp_path / "fichiers_modifies.txt"
    chemin.write_text("", encoding="utf-8")
    resultat = charger_fichiers_modifies(chemin)
    assert resultat == []


def test_charger_fichiers_modifies_ignore_les_lignes_vides(tmp_path):
    chemin = tmp_path / "fichiers_modifies.txt"
    chemin.write_text("Collections/Genres/Backdrops/Action_Backdrop.jpg\n\n  \n", encoding="utf-8")
    resultat = charger_fichiers_modifies(chemin)
    assert resultat == [Path("Collections/Genres/Backdrops/Action_Backdrop.jpg")]


def test_purger_cdn_sans_fichiers_purge_tout_repertoire(arborescence, monkeypatch):
    """Comportement historique préservé : sans --fichiers-modifies (fichiers=None),
    purge TOUS les .jpg trouvés sous --sortie."""
    session_mock = MagicMock(return_value=FausseReponse(200))
    monkeypatch.setattr("purger_cache.requests.get", session_mock)
    monkeypatch.setattr("purger_cache.time.sleep", lambda _: None)

    purger_cdn("owner/repo", "main", arborescence, fichiers=None)

    assert session_mock.call_count == 2  # les 2 fichiers de l'arborescence


def test_purger_cdn_avec_fichiers_ne_purge_que_ceux_la(arborescence, monkeypatch):
    """Le coeur de l'optimisation : avec une liste explicite, seuls CES
    fichiers déclenchent une requête de purge -- pas les autres backdrops
    présents sur disque mais non modifiés."""
    session_mock = MagicMock(return_value=FausseReponse(200))
    monkeypatch.setattr("purger_cache.requests.get", session_mock)
    monkeypatch.setattr("purger_cache.time.sleep", lambda _: None)

    seul_fichier = arborescence / "Genres" / "Backdrops" / "Action_Backdrop.jpg"
    purger_cdn("owner/repo", "main", arborescence, fichiers=[seul_fichier])

    assert session_mock.call_count == 1
    url_appelee = session_mock.call_args.args[0]
    assert "Genres" in url_appelee and "Action_Backdrop.jpg" in url_appelee


def test_purger_cdn_liste_vide_ne_purge_rien(arborescence, monkeypatch):
    """fichiers=[] (résultat de charger_fichiers_modifies sur un fichier
    vide) -> aucune requête réseau, même si l'arborescence contient des
    .jpg -- c'est la distinction [] vs None qui rend la purge sélective
    sûre (pas de fallback accidentel sur "tout purger")."""
    session_mock = MagicMock(return_value=FausseReponse(200))
    monkeypatch.setattr("purger_cache.requests.get", session_mock)

    purger_cdn("owner/repo", "main", arborescence, fichiers=[])

    session_mock.assert_not_called()


def test_purger_cdn_ignore_un_fichier_hors_du_repertoire_de_sortie(arborescence, monkeypatch, capsys):
    """Un chemin qui ne commence pas par --sortie (ex: désynchronisation
    entre le --sortie fourni et les chemins du fichier --fichiers-modifies)
    est ignoré (avec un avertissement) plutôt que de faire planter tout le
    run pour une seule entrée mal formée."""
    session_mock = MagicMock(return_value=FausseReponse(200))
    monkeypatch.setattr("purger_cache.requests.get", session_mock)
    monkeypatch.setattr("purger_cache.time.sleep", lambda _: None)

    hors_sortie = Path("/ailleurs/completement/Backdrop.jpg")
    purger_cdn("owner/repo", "main", arborescence, fichiers=[hors_sortie])

    session_mock.assert_not_called()
    assert "ignoré" in capsys.readouterr().err.lower()
