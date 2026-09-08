"""
Tests unitaires/intégration pour scripts/definir_image_manuelle.py

N'utilise que le chemin "fichier local" (pas de mock réseau nécessaire) --
le chemin "URL" réutilise `telecharger_et_traiter`, déjà couvert par
test_pipeline_integration.py.

Lancer avec : pytest tests/ -v
"""

import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from definir_image_manuelle import (  # noqa: E402
    sauver_images_manuelles,
    trouver_groupe_du_dossier,
)


def _image_locale(tmp_path: Path) -> Path:
    chemin = tmp_path / "source.jpg"
    Image.new("RGB", (400, 200), (10, 20, 30)).save(chemin)
    return chemin


def test_trouver_groupe_du_dossier_trouve_le_bon_groupe():
    collections = [
        {"title": "🎭 Genres", "folders": [{"title": "Action"}, {"title": "Horreur"}]},
        {"title": "Sports", "folders": [{"title": "Foot"}]},
    ]
    assert trouver_groupe_du_dossier(collections, "Horreur") == "🎭 Genres"
    assert trouver_groupe_du_dossier(collections, "Foot") == "Sports"


def test_trouver_groupe_du_dossier_retourne_none_si_absent():
    collections = [{"title": "Genres", "folders": [{"title": "Action"}]}]
    assert trouver_groupe_du_dossier(collections, "Introuvable") is None


def test_sauver_images_manuelles_cree_le_fichier_et_les_dossiers_parents(tmp_path):
    chemin = tmp_path / "sous_dossier" / "images-manuelles.json"
    sauver_images_manuelles(chemin, {"Netflix": "https://exemple.test/img.jpg"})
    assert chemin.exists()
    assert json.loads(chemin.read_text(encoding="utf-8")) == {"Netflix": "https://exemple.test/img.jpg"}


def test_cli_bout_en_bout_fichier_local_puis_retrait(tmp_path, capsys):
    """Test bout en bout du script (subprocess-free, appel direct de main())
    avec une image locale : enregistrement + génération immédiate, puis
    retrait de la surcharge."""
    import definir_image_manuelle

    collections_path = tmp_path / "collections.json"
    collections_path.write_text(
        json.dumps([{"title": "🎭 Genres", "folders": [{"title": "Action"}]}]),
        encoding="utf-8",
    )
    images_manuelles_path = tmp_path / "images-manuelles.json"
    sortie_path = tmp_path / "sortie"
    source_image = _image_locale(tmp_path)

    ancien_argv = sys.argv
    try:
        sys.argv = [
            "definir_image_manuelle.py",
            "Action",
            str(source_image),
            "--collections", str(collections_path),
            "--images-manuelles", str(images_manuelles_path),
            "--sortie", str(sortie_path),
        ]
        code = definir_image_manuelle.main()
    finally:
        sys.argv = ancien_argv

    assert code == 0
    assert json.loads(images_manuelles_path.read_text(encoding="utf-8")) == {"Action": str(source_image)}
    fichier_genere = sortie_path / "Genres" / "Backdrops" / "Action_Backdrop.jpg"
    assert fichier_genere.exists()

    # Retrait de la surcharge
    try:
        sys.argv = [
            "definir_image_manuelle.py",
            "Action",
            "--retirer",
            "--images-manuelles", str(images_manuelles_path),
        ]
        code = definir_image_manuelle.main()
    finally:
        sys.argv = ancien_argv

    assert code == 0
    assert json.loads(images_manuelles_path.read_text(encoding="utf-8")) == {}
