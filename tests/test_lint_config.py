"""
Tests unitaires pour scripts/lint_config.py

Chaque test mute temporairement une structure de config_collections pour
déclencher un cas précis, puis la restaure -- ces structures sont des
dicts partagés au niveau module, donc toujours nettoyer dans un `finally`.

Lancer avec : pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import config_collections as cc  # noqa: E402
from lint_config import (  # noqa: E402
    verifier_coherence_groupes,
    verifier_collisions_noms_fichiers,
    verifier_collisions_slugs,
    verifier_filtres_contradictoires,
    verifier_noms_personnalises_obsoletes,
)


def test_config_reelle_ne_declenche_aucun_avertissement_structurel():
    """Garde-fou : la config du dépôt doit rester cohérente (hors
    croisement avec le JSON de collections, qui est un test séparé)."""
    assert verifier_coherence_groupes() == []
    assert verifier_collisions_slugs() == []
    assert verifier_collisions_noms_fichiers() == []
    assert verifier_filtres_contradictoires() == []


def test_detecte_un_groupe_sans_slug_correspondant():
    cc.CRITERES_GROUPES["groupe_test_sans_slug_xyz"] = cc.CritereGroupe(actif=True)
    try:
        avertissements = verifier_coherence_groupes()
    finally:
        del cc.CRITERES_GROUPES["groupe_test_sans_slug_xyz"]
    assert any("groupe_test_sans_slug_xyz" in a for a in avertissements)


def test_detecte_une_collision_de_slugs():
    cc.GROUPE_SLUGS["groupe_test_collision_xyz"] = "Genres"  # collision volontaire
    try:
        avertissements = verifier_collisions_slugs()
    finally:
        del cc.GROUPE_SLUGS["groupe_test_collision_xyz"]
    assert any("'Genres'" in a for a in avertissements)


def test_detecte_une_collision_de_noms_de_fichiers():
    cc.NOMS_BACKDROP_PERSONNALISES["TestCollisionA"] = "MemeNomXYZ"
    cc.NOMS_BACKDROP_PERSONNALISES["TestCollisionB"] = "MemeNomXYZ"
    try:
        avertissements = verifier_collisions_noms_fichiers()
    finally:
        del cc.NOMS_BACKDROP_PERSONNALISES["TestCollisionA"]
        del cc.NOMS_BACKDROP_PERSONNALISES["TestCollisionB"]
    assert any("MemeNomXYZ" in a for a in avertissements)


def test_detecte_des_filtres_inclure_exclure_contradictoires():
    cc.CRITERES_GROUPES["groupe_contradictoire_xyz"] = cc.CritereGroupe(
        actif=True, inclure=("Top",), exclure=("top",)
    )
    try:
        avertissements = verifier_filtres_contradictoires()
    finally:
        del cc.CRITERES_GROUPES["groupe_contradictoire_xyz"]
    assert any("groupe_contradictoire_xyz" in a for a in avertissements)


def test_detecte_un_nom_personnalise_obsolete():
    cc.NOMS_BACKDROP_PERSONNALISES["Dossier Fantome XYZ"] = "Fantome"
    try:
        collections = [{"title": "Genres", "folders": [{"title": "Action"}]}]
        avertissements = verifier_noms_personnalises_obsoletes(collections)
    finally:
        del cc.NOMS_BACKDROP_PERSONNALISES["Dossier Fantome XYZ"]
    assert any("Dossier Fantome XYZ" in a for a in avertissements)


def test_noms_personnalises_absents_du_json_pas_de_croisement_donne_aucun_avertissement():
    assert verifier_noms_personnalises_obsoletes(None) == []
