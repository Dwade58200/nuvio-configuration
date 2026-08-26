# Comment appliquer ce correctif (arborescence française + noms de fichiers personnalisés)

## ⚠️ Ce paquet remplace la TOTALITÉ des scripts et tests

Vu l'ampleur des changements (architecture de dossiers), le plus sûr est
de remplacer tous les fichiers ci-dessous plutôt que de faire des diffs
partiels.

## Fichiers à remplacer/ajouter sur GitHub

| Fichier | Emplacement dans ton repo | Action |
|---|---|---|
| scripts/generer_backdrops.py | scripts/generer_backdrops.py | remplacer |
| scripts/mosaique.py | scripts/mosaique.py | remplacer (inchangé, mais fourni pour cohérence) |
| scripts/mettre_a_jour_urls.py | scripts/mettre_a_jour_urls.py | remplacer |
| scripts/purger_cache.py | scripts/purger_cache.py | remplacer |
| scripts/trakt_auth.py | scripts/trakt_auth.py | ajouter (nouveau) |
| tests/*.py | tests/ | remplacer tous |
| tests/fixtures/*.json | tests/fixtures/ | remplacer |
| .github/workflows/generer-backdrops.yml | .github/workflows/generer-backdrops.yml | remplacer |
| BACKDROPS_SETUP.md | BACKDROPS_SETUP.md | remplacer |
| requirements-dev.txt | requirements-dev.txt | remplacer (inchangé) |

⚠️ RAPPEL : sélectionne TOUT le contenu existant (Ctrl+A) et supprime-le
AVANT de coller le nouveau contenu, pour chaque fichier remplacé.

## Ce qui a changé

### 1. Nouvelle arborescence (français, capitalisée)

```
Collections/
├── Decouvertes/Backdrops/*.jpg
├── Franchises/Backdrops/*.jpg          (groupe désactivé, dossier vide)
├── Genres/Backdrops/*.jpg
├── Services de Streaming/Backdrops/*.jpg
├── Sports/Backdrops/*.jpg              (groupe désactivé, dossier vide)
├── Thematiques/Backdrops/*.jpg
├── Vibes/Backdrops/*.jpg
└── Annees/Backdrops/*.jpg              (absent de ta liste, nommé par défaut --
                                          change GROUPE_SLUGS dans le script si besoin)
```

### 2. Fichiers renommés en `Nom_Backdrop.jpg`

Les 15 correspondances demandées sont exactement respectées (vérifiées
par test), ex : `Sci-Fi_Backdrop.jpg`, `Canal+_Backdrop.jpg`,
`TF1_Backdrop.jpg`, `Chasse_au_Tresor_Backdrop.jpg`, etc. Tout titre non
listé obtient un nom générique automatique cohérent.

**Pour changer un nom de dossier ou de fichier plus tard** : tout est
regroupé dans un seul bloc en haut de `scripts/generer_backdrops.py`
("ARCHITECTURE DE SORTIE") -- une ligne à éditer par cas.

### 3. Nettoyage automatique de l'ancienne arborescence

Le workflow supprime automatiquement l'ancien dossier `collections/`
(minuscule) au prochain lancement, pour ne pas avoir les deux en
parallèle. Ça part dans le même commit que la nouvelle génération.

### 4. Encodage d'URL

Le dossier "Services de Streaming" contient un espace -- les URLs
jsDelivr générées (mise à jour des liens + purge du cache) l'encodent
maintenant correctement (%20).

### 5. Recommandations Trakt retirées

`trakt.recommendations.movies/shows` n'est plus reconnu (retombe en
"ignoré", comme avant l'ajout Trakt). L'authentification OAuth Trakt
(access_token/refresh_token) reste utile pour accéder aux LISTES PRIVÉES
de ton second compte -- voir BACKDROPS_SETUP.md.

## Test en local

```bash
pip install -r requirements-dev.txt
pytest tests/ -v   # doit afficher 104 passed

python3 scripts/generer_backdrops.py --dry-run --mosaique --aiometadata Templates/aiometadata-setup.json
# doit donner 53 générés (54 avant le retrait des recommandations, -1 = 53)
```

## Test réel via GitHub Actions

1. Actions → Générer les Backdrops → Run workflow
2. `groupe` = `Genres`, `limite` = `2`, dry_run décoché, desactiver_mosaique décoché
3. Vérifie dans les logs l'étape "Nettoyer l'ancienne arborescence"
4. Vérifie sur GitHub que les fichiers apparaissent bien sous
   `Collections/Genres/Backdrops/..._Backdrop.jpg`
5. Coche `mettre_a_jour_urls` sur un run complet une fois que tu es
   satisfait, pour que le JSON Nuvio pointe vers les nouveaux chemins
6. Si tout va bien, relance en génération complète (sans limite)

## ⚠️ Confirme-moi

Le nom "Annees" pour le groupe Années (absent de ta liste d'origine) --
dis-moi si tu préfères un autre nom, c'est une ligne à changer dans
`GROUPE_SLUGS`.
