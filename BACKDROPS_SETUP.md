# Nuvio Backdrops Automation

Configuration pour générer automatiquement des images de fond (backdrops) pour votre configuration Nuvio.

## 🎯 Qu'est-ce que c'est ?

Ce système automatise la génération et la mise à jour de backdrops (images de fond) à partir de bases de données de films et séries TV (TMDB et FanArt).

## ✅ Configuration requise

### 1. API Keys

Vous avez besoin de deux clés API :

#### TMDB API Key
1. Créez un compte sur [https://www.themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
2. Demandez une clé API
3. Copiez votre clé API

#### FanArt API Key
1. Créez un compte sur [https://fanart.tv/](https://fanart.tv/)
2. Allez dans [Personal API Keys](https://fanart.tv/profile/api-access/)
3. Copiez votre clé API

### 2. Ajouter les secrets GitHub

1. Allez sur votre repository : **Settings → Secrets and variables → Actions**
2. Créez deux nouveaux secrets :
   - `TMDB_API_KEY` : Votre clé TMDB
   - `FANART_API_KEY` : Votre clé FanArt

## 📝 Utilisation

### Format du fichier items.json

Modifiez le fichier `backdrops/items.json` pour ajouter vos films/séries :

```json
[
  {
    "id": 550,
    "name": "Fight Club",
    "type": "movie"
  },
  {
    "id": 1399,
    "name": "Game of Thrones",
    "type": "tv"
  }
]
```

**Trouver les IDs :**
- Pour les films : Recherchez sur [https://www.themoviedb.org](https://www.themoviedb.org)
- Pour les séries : Idem, mais notez que c'est une série (`type: "tv"`)

### Lancer manuellement la génération

1. Allez sur **Actions** dans votre repository
2. Sélectionnez **Generate Backdrops**
3. Cliquez sur **Run workflow**

### Exécution automatique

Le workflow s'exécute automatiquement le **1er de chaque mois à 4h00 UTC**.

Pour modifier cette fréquence, éditez `.github/workflows/generate-backdrops.yml` :

```yaml
on:
  schedule:
    - cron: "0 4 1 * *"  # Modifiez le cron ici
```

[Aide cron](https://crontab.guru)

## 🖼️ Profils disponibles

- **compressed** (défaut) : Images optimisées en 1920x1080 @ 85% qualité
- **standard** : Images en haute qualité 1920x1080 @ 90% qualité
- **hq** : Images haute définition 4096x2160 @ 95% qualité

Pour modifier le profil, éditez `.github/workflows/generate-backdrops.yml` :

```yaml
--profile compressed  # Changez ici
```

## 📂 Structure de fichiers

```
nuvio-configuration/
├── .github/workflows/
│   └── generate-backdrops.yml      # Workflow automation
├── backdrops/
│   ├── items.json                  # Configuration des images
│   └── *.jpg                        # Images générées
├── scripts/
│   ├── generate_backdrops.py        # Script de génération
│   └── purge_cache.py               # Script de cache purging
└── BACKDROPS_SETUP.md               # Ce fichier
```

## 🔄 Flux de travail

1. **Chaque mois** (ou manuellement) : Le workflow se lance
2. **Téléchargement** : Les images sont téléchargées depuis TMDB/FanArt
3. **Traitement** : Les images sont redimensionnées et compressées
4. **Commit** : Les changements sont poussés sur la branche
5. **Cache** : Le CDN jsDelivr est purgé pour mettre à jour les images

## 🐛 Dépannage

### "API Key not found"
- Vérifiez que vos secrets sont bien configurés dans GitHub
- Vérifiez les noms : `TMDB_API_KEY` et `FANART_API_KEY`

### "No backdrop found for..."
- L'API n'a pas trouvé d'image pour cet élément
- Vérifiez que l'ID est correct sur TMDB
- Essayez avec un autre élément

### Les images ne sont pas mises à jour
- Vérifiez les logs du workflow dans l'onglet **Actions**
- Assurez-vous que `backdrops/items.json` n'est pas vide

## 📚 Ressources

- [TMDB API Documentation](https://developer.themoviedb.org/docs)
- [FanArt API Documentation](https://fanart.tv/api-docs/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## ✨ Prochaines étapes

- Remplissez `backdrops/items.json` avec vos films/séries favoris
- Configurez vos API keys
- Testez le workflow manuellement
- Laissez l'automatisation faire le reste !

---

**Besoin d'aide ?** Consultez les logs du workflow dans l'onglet **Actions** de votre repository.
