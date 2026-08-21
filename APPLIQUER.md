# Comment appliquer ce correctif à ton repo (pas de doublons, catalogues globaux uniquement)

## Fichiers à remplacer sur GitHub

| Fichier | Emplacement dans ton repo | Action |
|---|---|---|
| scripts/generer_backdrops.py | scripts/generer_backdrops.py | remplacer l'existant |
| tests/test_generer_backdrops.py | tests/test_generer_backdrops.py | remplacer l'existant |
| tests/test_mosaique_integration.py | tests/test_mosaique_integration.py | remplacer l'existant |
| BACKDROPS_SETUP.md | BACKDROPS_SETUP.md | remplacer l'existant |

Rien à ajouter/supprimer.

## Ce qui a été corrigé

1. **Sources françaises exclues** : certains dossiers (Découvrir/Populaire,
   Découvrir/Top, Années/*) ont deux catalogues TMDB en parallèle -- un
   "🌍 global" et un "🇫🇷 France" (withOriginalLanguage=fr). Seul le
   catalogue global est maintenant utilisé ; le français est explicitement
   exclu et journalisé ("source langue-spécifique exclue").
2. **Vrai bug de doublon corrigé** : un film présent à la fois dans une
   collection (ex: une saga) ET dans les résultats d'un catalogue discover
   n'était pas reconnu comme le même titre (types "collection" vs "movie"
   différents dans la logique de dédoublonnage) -> il pouvait apparaître
   deux fois dans une même mosaïque. C'est corrigé : une collection ne
   contient que des films, donc son media_type est maintenant "movie"
   partout, et la déduplication fonctionne correctement.

## Test en local

```bash
pip install -r requirements-dev.txt
pytest tests/ -v   # doit afficher 47 passed
python3 scripts/generer_backdrops.py --dry-run --mosaique   # doit toujours donner 43/179
```

## Test réel via GitHub Actions

1. Actions → Générer les Backdrops → Run workflow
2. `groupe` = `Années`, `limite` = `1`, dry_run décoché, desactiver_mosaique décoché
3. Ce dossier avait 2 sources françaises en plus des 2 globales -- vérifie
   dans les logs (onglet "Générer les backdrops" en mode verbose si besoin)
   qu'elles sont bien listées comme "source langue-spécifique exclue"
4. Regarde l'image générée : plus de doublon visuel côté films de sagas
5. Si tout va bien, relance en génération complète (tous champs vides)
