"""
Tests unitaires pour scripts/comparer_collections.py

Ne teste que la fonction pure `comparer()` (aucun accès Git ni disque) --
le chargement Git est une fine couche d'I/O testée manuellement (voir
BACKDROPS_SETUP.md).

Lancer avec : pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from comparer_collections import comparer  # noqa: E402


def _groupe(titre, titres_dossiers):
    return {"title": titre, "folders": [{"title": t} for t in titres_dossiers]}


def test_comparer_sans_aucun_changement():
    collections = [_groupe("Genres", ["Action", "Comédie"])]
    rapport = comparer(collections, collections)
    assert "Aucun changement" in rapport


def test_comparer_detecte_un_groupe_ajoute():
    ancien = [_groupe("Genres", ["Action"])]
    nouveau = [_groupe("Genres", ["Action"]), _groupe("Vibes", ["Chill"])]
    rapport = comparer(ancien, nouveau)
    assert "1 groupe(s) ajouté(s)" in rapport
    assert "'Vibes'" in rapport


def test_comparer_detecte_un_groupe_supprime():
    ancien = [_groupe("Genres", ["Action"]), _groupe("Sports", ["Foot"])]
    nouveau = [_groupe("Genres", ["Action"])]
    rapport = comparer(ancien, nouveau)
    assert "1 groupe(s) supprimé(s)" in rapport
    assert "'Sports'" in rapport


def test_comparer_reconnait_le_meme_groupe_malgre_un_emoji_different():
    ancien = [_groupe("🎭 Genres", ["Action"])]
    nouveau = [_groupe("🎭Genres", ["Action", "Horreur"])]
    rapport = comparer(ancien, nouveau)
    # Pas de groupe ajouté/supprimé -- seulement un dossier ajouté au sein
    # du même groupe reconnu malgré le changement d'emoji.
    assert "groupe(s) ajouté" not in rapport
    assert "groupe(s) supprimé" not in rapport
    assert "'Horreur'" in rapport


def test_comparer_detecte_dossiers_ajoutes_et_supprimes_dans_un_groupe_commun():
    ancien = [_groupe("Genres", ["Action", "Comédie"])]
    nouveau = [_groupe("Genres", ["Action", "Horreur"])]
    rapport = comparer(ancien, nouveau)
    assert "+ 'Horreur'" in rapport
    assert "- 'Comédie'" in rapport
