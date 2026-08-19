# Nuvio Backdrops Automation

Génération automatique des images de fond (backdrops) pour les collections
Nuvio de ce dépôt, à partir de `Templates/Nuvio-Collections-Dwade58200.json`.

Inspiré du pipeline de [luckynumb3rs/stremio-perfect-setup](https://github.com/luckynumb3rs/stremio-perfect-setup),
adapté à la structure de collections propre à ce dépôt.

## 🎯 Comment ça marche

Le script `scripts/generer_backdrops.py` lit `Templates/Nuvio-Collections-Dwade58200.json`,
et pour **chaque dossier de chaque groupe actif**, il :

1. Regarde les `sources` du dossier et essaie de construire une requête TMDB fiable
   (collection, discover avec filtres, ou endpoint générique) ;
2. Si aucune source directe n'est exploitable, tente un repli heuristique
   (ex : dossier "Action" dans le groupe Genres → genre TMDB "Action" ;
   thématique "Arts martiaux" → recherche par mot-clé TMDB "martial arts") ;
3. Télécharge le premier backdrop trouvé (TMDB, avec repli Fanart.tv si besoin) ;
4. Redimensionne/compresse l'image et l'enregistre dans
   `collections/<groupe>/backdrop/<dossier>.jpg`.

### ⚠️ Phase 1 : couverture actuelle

Ce n'est **pas encore** un portage 1:1 du système de luckynumb3rs (pas de
mosaïque multi-titres, pas de couleur d'accent). C'est la fondation propre
et testée sur laquelle on va itérer.

Sur les collections actuelles, la couverture est :

| Groupe | Dossiers résolus | Notes |
|---|---|---|
| 🔭 Découvrir | 3 / 6 | "Recommandation" nécessite Trakt (non géré) |
| 🎬 Streaming | 0 / 9 | volontairement désactivé (sources FlixPatrol, non-TMDB) |
| 🎭 Genres | 15 / 15 | ✅ |
| 🎨 Thématiques | 13 / 14 | 1 dossier nécessite Trakt |
| Vibe | 4 / 4 | ✅ |
| 📅 Années | 8 / 8 | ✅ |
| Franchises | 0 / 158 | volontairement désactivé (à la demande de l'utilisateur) |
| Sports | 0 / 8 | volontairement désactivé (pas pertinent pour un backdrop) |

Les dossiers non résolus sont **journalisés avec la raison** (jamais échoués
en silence) — voir le résumé affiché à la fin de chaque exécution.

## ✅ Configuration requise

### 1. Clés API

- **TMDB** : créez un compte sur https://www.themoviedb.org/settings/api et
  récupérez une clé API (v3).
- **Fanart.tv** (optionnel, utilisé en repli quand TMDB n'a pas de backdrop) :
  https://fanart.tv/profile/api-access/

### 2. Secrets GitHub

Dans **Settings → Secrets and variables → Actions** du dépôt, créez :
- `TMDB_API_KEY`
- `FANART_API_KEY` (optionnel)

## 📝 Utilisation

### En local (recommandé avant de pousser)

```bash
pip install -r requirements-dev.txt

# 1. Lancer les tests unitaires (aucune clé API nécessaire)
pytest tests/ -v

# 2. Simulation complète sans appeler TMDB (vérifie la couverture)
python3 scripts/generer_backdrops.py --dry-run

# 3. Test réel limité à quelques dossiers, avec ta vraie clé
export TMDB_API_KEY="ta_cle_ici"
python3 scripts/generer_backdrops.py --groupe Genres --limite 3 -v

# 4. Génération complète
python3 scripts/generer_backdrops.py --profil compresse
```

Options utiles de `generer_backdrops.py` :

| Option | Effet |
|---|---|
| `--dry-run` | Ne fait aucun appel réseau, affiche juste ce qui serait généré |
| `--groupe "Genres"` | Limite le traitement à un seul groupe (pratique pour tester) |
| `--limite 5` | Limite le nombre de dossiers traités |
| `--profil {standard,haute,compresse}` | Taille/qualité de sortie |
| `-v` | Logs détaillés |

### Depuis GitHub Actions

1. Onglet **Actions** → workflow **Générer les Backdrops** → **Run workflow**
2. Le déclenchement manuel permet aussi de cocher **dry_run**, ou de préciser
   un `groupe`/une `limite` pour un test rapide sans tout régénérer.

Le workflow tourne aussi automatiquement le **1er de chaque mois à 4h00 UTC**
(modifiable dans `.github/workflows/generer-backdrops.yml`, section `cron`).

## 📂 Structure de fichiers

```
nuvio-configuration/
├── .github/workflows/
│   └── generer-backdrops.yml        # Workflow d'automatisation
├── Templates/
│   └── Nuvio-Collections-Dwade58200.json  # Source de vérité des collections
├── collections/
│   └── <groupe>/backdrop/*.jpg      # Images générées (ex: genres/backdrop/action.jpg)
├── scripts/
│   ├── generer_backdrops.py         # Script principal
│   └── purger_cache.py              # Purge du cache CDN jsDelivr
├── tests/
│   ├── test_generer_backdrops.py    # Tests de la logique de résolution
│   └── test_pipeline_integration.py # Test bout-en-bout (HTTP simulé)
└── BACKDROPS_SETUP.md               # Ce fichier
```

## 🐛 Dépannage

**"clé TMDB manquante"** → vérifie le secret `TMDB_API_KEY`, ou utilise `--dry-run`.

**Un dossier n'a pas de backdrop après une exécution réelle** → regarde la
section "Dossiers ignorés, par raison" dans le résumé : c'est très souvent
une source Trakt (non gérée pour l'instant) ou un catalogue "addon" propre
à ta configuration Stremio qu'on ne peut pas résoudre sans son fichier de
définition.

**Les images ne se mettent pas à jour sur Nuvio** → jsDelivr cache les
fichiers ~7 jours ; le workflow purge automatiquement le cache après chaque
commit, mais tu peux aussi lancer `python3 scripts/purger_cache.py` toi-même.

## 🗺️ Prochaines étapes (phases suivantes)

- Intégrer l'API Trakt pour résoudre les listes/recommandations (couvre
  "Recommandation", plusieurs Franchises et 1 Thématique)
- Mosaïque multi-titres + couleur d'accent, comme chez luckynumb3rs
- Génération de variantes `.webp` en plus du `.jpg`
- Mise à jour automatique des champs `heroBackdropUrl` dans le JSON de
  collections une fois les images poussées

---

**Besoin d'aide ?** Regarde les logs du workflow dans l'onglet **Actions**.
