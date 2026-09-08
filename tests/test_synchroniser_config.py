"""
Tests unitaires pour scripts/synchroniser_config.py et pour les fonctions
de config externe de scripts/config_collections.py.

Lancer avec : pytest tests/ -v
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from config_collections import (  # noqa: E402
    CRITERES_GROUPES,
    GROUPE_SLUGS,
    appliquer_config_externe,
    charger_config_groupes_externe,
)
from synchroniser_config import synchroniser  # noqa: E402


def _groupe(titre, titres_dossiers):
    return {"title": titre, "folders": [{"title": t} for t in titres_dossiers]}


def test_synchroniser_ajoute_un_groupe_inconnu():
    collections = [_groupe("Un Groupe Totalement Inconnu", ["Dossier A"])]
    nouvelle_config, ajoutes, disparus = synchroniser(collections, {})
    assert ajoutes == ["Un Groupe Totalement Inconnu"]
    assert disparus == []
    assert "un groupe totalement inconnu" in nouvelle_config
    entree = nouvelle_config["un groupe totalement inconnu"]
    assert entree["actif"] is True
    assert entree["slug"]  # non vide


def test_synchroniser_n_ajoute_rien_pour_un_groupe_deja_dans_criteres_groupes():
    # "Genres" est déjà déclaré en dur dans CRITERES_GROUPES.
    collections = [_groupe("🎭 Genres", ["Action"])]
    nouvelle_config, ajoutes, disparus = synchroniser(collections, {})
    assert ajoutes == []
    assert nouvelle_config == {}


def test_synchroniser_signale_un_groupe_disparu_de_la_config_externe():
    config_existante = {
        "un ancien groupe": {"actif": True, "slug": "Ancien_Groupe", "inclure": None, "exclure": None}
    }
    collections = [_groupe("Genres", ["Action"])]  # "un ancien groupe" n'y est plus
    nouvelle_config, ajoutes, disparus = synchroniser(collections, config_existante)
    assert disparus == ["un ancien groupe"]
    # Rapport seul : l'entrée reste dans la config tant qu'elle n'est pas purgée explicitement.
    assert "un ancien groupe" in nouvelle_config


def test_synchroniser_ne_signale_jamais_un_groupe_code_en_dur_comme_disparu():
    # "Sports" est dans CRITERES_GROUPES -- même absent du JSON de
    # collections, ce n'est jamais un "groupe disparu" au sens de ce script.
    config_existante = {"sports": {"actif": False, "slug": "Sports", "inclure": None, "exclure": None}}
    collections = [_groupe("Genres", ["Action"])]
    _, _, disparus = synchroniser(collections, config_existante)
    assert disparus == []


def test_appliquer_config_externe_absente_ne_change_rien():
    avant_criteres = dict(CRITERES_GROUPES)
    avant_slugs = dict(GROUPE_SLUGS)
    appliquer_config_externe(None)
    assert CRITERES_GROUPES == avant_criteres
    assert GROUPE_SLUGS == avant_slugs


def test_appliquer_config_externe_fusionne_un_nouveau_groupe(tmp_path):
    chemin = tmp_path / "groupes-config.json"
    chemin.write_text(
        json.dumps(
            {
                "un groupe de test unique xyz": {
                    "actif": True,
                    "slug": "GroupeTestUniqueXYZ",
                    "inclure": ["Populaire"],
                    "exclure": None,
                }
            }
        ),
        encoding="utf-8",
    )
    try:
        appliquer_config_externe(chemin)
        assert "un groupe de test unique xyz" in CRITERES_GROUPES
        critere = CRITERES_GROUPES["un groupe de test unique xyz"]
        assert critere.actif is True
        assert critere.inclure == ("Populaire",)
        assert GROUPE_SLUGS["un groupe de test unique xyz"] == "GroupeTestUniqueXYZ"
    finally:
        # Nettoyage : éviter de polluer les autres tests du même run.
        CRITERES_GROUPES.pop("un groupe de test unique xyz", None)
        GROUPE_SLUGS.pop("un groupe de test unique xyz", None)


def test_charger_config_groupes_externe_absente_retourne_dict_vide(tmp_path):
    assert charger_config_groupes_externe(None) == {}
    assert charger_config_groupes_externe(tmp_path / "n_existe_pas.json") == {}
