"""
Tests pour generer_defaults_outil.py -- synchronisation des valeurs par
défaut de outils/reglage-style-mosaique.html avec les vraies constantes
de scripts/mosaique.py (évite que l'outil affiche un point de départ
obsolète après un changement de style ailleurs que via l'outil lui-même).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generer_defaults_outil import (
    extraire_constantes,
    mettre_a_jour_html,
    valeurs_outil_depuis_constantes,
)

MOSAIQUE_FACTICE = """
TUILE_LARGEUR = 372       # commentaire
TUILE_HAUTEUR = 210
ECART = 9
RAYON_COIN = 9
DECALAGE_LIGNE = 0.5
INCLINAISON_DEG = 10
INTENSITE_OMBRE = 1.0
RAYON_FLOU_LUEUR_MIN = 24
"""

OUTIL_FACTICE = """
<input type="range" id="tuileLargeur" min="150" max="500" step="2" value="372">
<input type="number" class="valeur-num" id="tuileLargeurNum" min="150" max="500" step="2" value="372">
<input type="range" id="decalage" min="0" max="100" step="5" value="50">
<input type="number" class="valeur-num" id="decalageNum" min="0" max="100" step="5" value="50">
var defaults = {tuileLargeur:372, tuileHauteur:210, ecart:9, rayon:9, decalage:50, inclinaison:10, ombre:100, flou:24, accentColor:'#7f77dd'};
"""


def test_extraire_constantes_lit_les_valeurs_entieres_et_flottantes():
    constantes = extraire_constantes(MOSAIQUE_FACTICE)
    assert constantes["TUILE_LARGEUR"] == 372
    assert constantes["DECALAGE_LIGNE"] == 0.5
    assert constantes["INTENSITE_OMBRE"] == 1.0


def test_extraire_constantes_lit_une_valeur_negative():
    """INCLINAISON_DEG est négatif en pratique (ex: -10) -- doit être lu
    correctement, et pas seulement les valeurs positives des fixtures
    ci-dessus."""
    mosaique_negatif = MOSAIQUE_FACTICE.replace("INCLINAISON_DEG = 10", "INCLINAISON_DEG = -10")
    constantes = extraire_constantes(mosaique_negatif)
    assert constantes["INCLINAISON_DEG"] == -10.0


def test_mettre_a_jour_html_gere_une_valeur_negative():
    """Le remplacement dans l'attribut HTML value="..." et dans l'objet JS
    `defaults` doit fonctionner aussi pour une valeur négative (ex:
    inclinaison=-10), pas seulement en écriture depuis une valeur
    positive."""
    outil_avec_inclinaison_negative = OUTIL_FACTICE.replace(
        "var defaults = {tuileLargeur:372, tuileHauteur:210, ecart:9, rayon:9, decalage:50, inclinaison:10,",
        "var defaults = {tuileLargeur:372, tuileHauteur:210, ecart:9, rayon:9, decalage:50, inclinaison:-10,",
    )
    outil_avec_inclinaison_negative = (
        outil_avec_inclinaison_negative
        + '\n<input type="range" id="inclinaison" min="-25" max="25" step="1" value="-10">'
        + '\n<input type="number" class="valeur-num" id="inclinaisonNum" min="-25" max="25" step="1" value="-10">'
    )
    nouveau, modifies, introuvables = mettre_a_jour_html(outil_avec_inclinaison_negative, {"inclinaison": -15})
    assert introuvables == []
    assert 'id="inclinaison" min="-25" max="25" step="1" value="-15"' in nouveau
    assert 'id="inclinaisonNum" min="-25" max="25" step="1" value="-15"' in nouveau
    assert "inclinaison:-15" in nouveau


def test_extraire_constantes_absente_est_simplement_omise():
    """Une constante renommée/retirée de mosaique.py ne doit pas planter
    l'extraction -- juste être absente du dict retourné (signalée par
    l'appelant, voir main())."""
    contenu_partiel = "TUILE_LARGEUR = 400\n"
    constantes = extraire_constantes(contenu_partiel)
    assert constantes == {"TUILE_LARGEUR": 400.0}


def test_valeurs_outil_depuis_constantes_convertit_les_fractions_en_pourcentage():
    """DECALAGE_LIGNE et INTENSITE_OMBRE sont des fractions (0.5, 1.0)
    côté script mais des pourcentages entiers côté outil (curseurs
    0-100/0-200) -- la conversion est le point le plus fragile de ce
    script, donc testée isolément."""
    constantes = extraire_constantes(MOSAIQUE_FACTICE)
    valeurs = valeurs_outil_depuis_constantes(constantes)
    assert valeurs["decalage"] == 50
    assert valeurs["ombre"] == 100
    assert valeurs["tuileLargeur"] == 372


def test_mettre_a_jour_html_ne_change_rien_si_deja_synchronise():
    valeurs = {"tuileLargeur": 372, "decalage": 50}
    nouveau, modifies, introuvables = mettre_a_jour_html(OUTIL_FACTICE, valeurs)
    assert nouveau == OUTIL_FACTICE
    assert modifies == []
    assert introuvables == []


def test_mettre_a_jour_html_met_a_jour_curseur_numerique_et_defaults_js():
    """Le coeur du script : une valeur qui a changé doit être répercutée
    aux TROIS endroits -- l'attribut value du curseur, celui du champ
    numérique jumeau (XNum), et l'objet JS `defaults`."""
    valeurs = {"tuileLargeur": 400, "decalage": 35}
    nouveau, modifies, introuvables = mettre_a_jour_html(OUTIL_FACTICE, valeurs)

    assert introuvables == []
    assert set(modifies) == {
        "tuileLargeur",
        "tuileLargeurNum",
        "defaults.tuileLargeur",
        "decalage",
        "decalageNum",
        "defaults.decalage",
    }
    assert 'id="tuileLargeur" min="150" max="500" step="2" value="400"' in nouveau
    assert 'id="tuileLargeurNum" min="150" max="500" step="2" value="400"' in nouveau
    assert 'id="decalage" min="0" max="100" step="5" value="35"' in nouveau
    assert "tuileLargeur:400" in nouveau
    assert "decalage:35" in nouveau
    # Les autres clés de l'objet defaults, non concernées, restent intactes.
    assert "tuileHauteur:210" in nouveau
    assert "accentColor:'#7f77dd'" in nouveau


def test_mettre_a_jour_html_id_ne_matche_pas_par_prefixe():
    """id="tuileLargeur" ne doit JAMAIS toucher id="tuileLargeurNum" par
    accident (sous-chaîne) -- la valeur y est mise à jour séparément, une
    seule fois chacune."""
    valeurs = {"tuileLargeur": 450}
    nouveau, modifies, _ = mettre_a_jour_html(OUTIL_FACTICE, valeurs)
    assert nouveau.count('value="450"') == 2  # une fois pour chaque input, pas plus
    assert modifies.count("tuileLargeur") == 1
    assert modifies.count("tuileLargeurNum") == 1


def test_mettre_a_jour_html_signale_un_id_introuvable():
    nouveau, modifies, introuvables = mettre_a_jour_html(OUTIL_FACTICE, {"idInexistant": 1})
    assert nouveau == OUTIL_FACTICE
    assert modifies == []
    assert "idInexistant" in introuvables
    assert "idInexistantNum" in introuvables
    assert "defaults.idInexistant" in introuvables
