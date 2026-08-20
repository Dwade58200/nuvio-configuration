# Comment appliquer ce correctif à ton repo (mosaïque + accent color)

## Fichiers à ajouter/remplacer sur GitHub

| Fichier | Emplacement dans ton repo | Action |
|---|---|---|
| scripts/mosaique.py | scripts/mosaique.py | ajouter (nouveau) |
| scripts/generer_backdrops.py | scripts/generer_backdrops.py | remplacer l'existant |
| tests/test_mosaique.py | tests/test_mosaique.py | ajouter (nouveau) |
| tests/test_mosaique_integration.py | tests/test_mosaique_integration.py | ajouter (nouveau) |
| .github/workflows/generer-backdrops.yml | .github/workflows/generer-backdrops.yml | remplacer l'existant |
| BACKDROPS_SETUP.md | BACKDROPS_SETUP.md | remplacer l'existant |

Rien à supprimer.

## Test en local (recommandé avant de pousser)

```bash
pip install -r requirements-dev.txt
pytest tests/ -v   # doit afficher 36 passed

# Vérifier que la couverture n'a pas changé (43 générés / 179 ignorés)
python3 scripts/generer_backdrops.py --dry-run --mosaique
```

## Test réel via GitHub Actions

1. Actions → Générer les Backdrops → Run workflow
2. `groupe` = `Genres`, `limite` = `1`, dry_run décoché,
   desactiver_mosaique décoché (donc mosaïque active)
3. Ça va prendre un peu plus longtemps qu'avant (jusqu'à 12 images
   téléchargées pour composer une seule mosaïque)
4. Va voir l'image générée sur GitHub (collections/genres/backdrop/...jpg) :
   tu dois voir une grille de plusieurs affiches avec un dégradé teinté,
   pas un backdrop unique comme avant
5. Si le résultat te plaît, relance en génération complète (tous champs
   vides, desactiver_mosaique décoché)

## Pour revenir en arrière si besoin

Coche **desactiver_mosaique** au déclenchement manuel : ça repasse
temporairement sur l'ancien mode "1 seul backdrop par dossier", sans rien
supprimer côté code.
