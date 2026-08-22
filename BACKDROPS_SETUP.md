# Nuvio Backdrops Automation

Génération automatique des images de fond (backdrops) pour les collections
Nuvio de ce dépôt, à partir de `Templates/Nuvio-Collections-Dwade58200.json`.

Inspiré du pipeline de [luckynumb3rs/stremio-perfect-setup](https://github.com/luckynumb3rs/stremio-perfect-setup),
adapté à la structure de collections propre à ce dépôt.

## 🎯 Comment ça marche

Le script `scripts/generer_backdrops.py` lit `Templates/Nuvio-Collections-Dwade58200.json`,
et pour **chaque dossier de chaque groupe actif**, il :

1. Regarde les `sources` du dossier et essaie de construire une ou plusieurs
   requêtes TMDB fiables (collection, discover avec filtres, ou endpoint
   générique). Les sources dupliquées filtrées sur une langue précise
   (ex : catalogues "🇫🇷 France" avec `withOriginalLanguage=fr`) sont
   exclues -- seuls les catalogues **globaux/mondiaux** sont conservés ;
2. Si aucune source directe n'est exploitable, tente un repli heuristique
   (ex : dossier "Action" dans le groupe Genres → genre TMDB "Action" ;
   thématique "Arts martiaux" → recherche par mot-clé TMDB "martial arts") ;
3. Récupère jusqu'à 12 titres (films/séries) correspondants -- dédupliqués
   même si un même film provient à la fois d'une collection et d'un
   catalogue discover -- et compose une **mosaïque** avec dégradé +
   couleur d'accent extraite automatiquement (voir section dédiée
   ci-dessous) ; en dessous de 3 titres distincts, bascule automatiquement
   sur l'ancien mode "1 seul backdrop" ;
4. Enregistre l'image dans `collections/<groupe>/backdrop/<dossier>.jpg`.

## 🎨 Mode mosaïque (par défaut)

Chaque dossier affiche une grille de tuiles **paysage** (16:9), disposées en
cascade inclinée -- même principe visuel que luckynumb3rs. Par-dessus :
- un dégradé sombre (bas, gauche, coin bas-gauche) pour un effet vignette ;
- une lueur diffuse d'une **couleur d'accent** extraite automatiquement à
  partir du premier titre trouvé, placée en haut à droite.

### ⚠️ Important : le titre affiché sur chaque tuile dépend de Fanart.tv

Le script n'écrit **aucun texte** lui-même. Les titres/logos visibles sur
les tuiles viennent des artworks **"thumb"** de [Fanart.tv](https://fanart.tv)
(`moviethumb`/`tvthumb`) -- des visuels communautaires qui incluent déjà le
titre stylisé. **Sans clé `FANART_API_KEY` configurée, les tuiles utilisent
le backdrop TMDB brut (sans aucun texte)** : la mosaïque reste jolie mais
sans titre visible.

Pour avoir les titres :
1. Crée un compte sur https://fanart.tv/profile/api-access/ et récupère une clé
2. Ajoute-la comme secret GitHub `FANART_API_KEY` (voir section suivante)

Pour chaque titre, le script cherche une image dans CET ordre précis :

1. **Backdrop TMDB tagué français** (via l'endpoint `/images` de TMDB) --
   certains titres ont des visuels envoyés spécifiquement pour le marché
   français, qui incluent parfois un titre local incrusté.
2. **Fanart.tv, en français** : d'abord **background** (image de fond),
   puis **thumb** (image avec titre incrusté), puis **clearart/hdclearart**
   (artwork détouré) -- dans ce cas, il est recomposé sur un VRAI fond
   (un autre visuel Fanart ou le backdrop TMDB), jamais sur une couleur plate.
3. **Même schéma, en anglais** (backdrop TMDB tagué EN, puis Fanart EN).
4. **Sans texte, en tout dernier recours** : Fanart sans langue précise,
   puis backdrop TMDB générique, puis le backdrop déjà connu du candidat.

Le type **"banner"** de Fanart n'est jamais utilisé (mauvais format pour
nos tuiles paysage).

C'est le comportement **par défaut** (`--mosaique`, activé aussi dans le
workflow GitHub Actions, y compris le cron mensuel). Si un dossier a moins
de 3 titres distincts résolus, le script repasse automatiquement sur
l'ancien mode "1 seul backdrop TMDB/Fanart", sans erreur.

**Pas de doublon visible** : la grille inclinée contient environ 70 cases
(quelle que soit la résolution de sortie). Le script récupère donc jusqu'à
~70 titres distincts par dossier (pagination TMDB automatique) pour remplir
toute la grille sans répéter la même affiche. Si un dossier a réellement
moins de titres disponibles que de cases (catalogue restreint), les
images sont répétées (cycle) en dernier recours pour compléter, comme le
fait luckynumb3rs -- mais uniquement dans ce cas.

Pour forcer l'ancien comportement (debug, comparaison) :
```bash
python3 scripts/generer_backdrops.py --collections ... # sans --mosaique
```
Ou, depuis GitHub Actions, coche **desactiver_mosaique** au déclenchement manuel.

### Couverture actuelle

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

## 🔗 Mise à jour des URLs (`heroBackdropUrl`)

Un second script, `scripts/mettre_a_jour_urls.py`, met à jour le champ
`heroBackdropUrl` du JSON de collections pour qu'il pointe vers ton propre
CDN. **Il n'a pas besoin de tourner à chaque exécution** : l'URL d'un
backdrop dépend uniquement du chemin du fichier (groupe + titre du
dossier), qui ne change pas d'un mois à l'autre — seule l'image derrière
cette URL est remplacée. Il suffit donc de le lancer une fois pour les
dossiers déjà résolus, puis de le relancer uniquement quand de *nouveaux*
dossiers deviennent résolvables (ex : après l'intégration de Trakt).

## ✅ Configuration requise

### 1. Clés API

- **TMDB** : créez un compte sur https://www.themoviedb.org/settings/api et
  récupérez une clé API (v3).
- **Fanart.tv** (fortement recommandé -- c'est la source des titres/logos
  incrustés sur les tuiles de la mosaïque, voir section précédente) :
  https://fanart.tv/profile/api-access/

### 2. Secrets GitHub

Dans **Settings → Secrets and variables → Actions** du dépôt, créez :
- `TMDB_API_KEY`
- `FANART_API_KEY` (recommandé -- sans lui, les mosaïques n'ont pas de titre visible)

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
| `--mosaique` | Grille multi-titres + couleur d'accent (repli auto si < 6 titres) |
| `--groupe "Genres"` | Limite le traitement à un seul groupe (pratique pour tester) |
| `--limite 5` | Limite le nombre de dossiers traités |
| `--profil {standard,haute,compresse}` | Taille/qualité de sortie |
| `-v` | Logs détaillés |

### Depuis GitHub Actions

1. Onglet **Actions** → workflow **Générer les Backdrops** → **Run workflow**
2. Le déclenchement manuel permet aussi de cocher **dry_run**, ou de préciser
   un `groupe`/une `limite` pour un test rapide sans tout régénérer.
3. La mosaïque est **active par défaut** (aussi sur le cron mensuel) ; coche
   **desactiver_mosaique** uniquement pour du débug/comparaison.
4. La case **mettre_a_jour_urls** est décochée par défaut (voir plus haut
   pourquoi) : coche-la uniquement la première fois, ou après une phase qui
   débloque de nouveaux dossiers.

Le workflow tourne aussi automatiquement le **1er de chaque mois à 4h00 UTC**
(modifiable dans `.github/workflows/generer-backdrops.yml`, section `cron`) —
cette exécution planifiée régénère les mosaïques mais ne touche jamais au
JSON (`mettre_a_jour_urls` reste désactivé par défaut).

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
│   ├── mosaique.py                  # Composition de la grille + couleur d'accent
│   ├── mettre_a_jour_urls.py        # Met à jour heroBackdropUrl vers le CDN du repo
│   └── purger_cache.py              # Purge du cache CDN jsDelivr
├── tests/
│   ├── test_generer_backdrops.py    # Tests de la logique de résolution
│   ├── test_mosaique.py             # Tests du module de mosaïque (hors-ligne)
│   ├── test_mosaique_integration.py # Test bout-en-bout du mode mosaïque
│   ├── test_mettre_a_jour_urls.py   # Tests de la mise à jour des URLs
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

## 🗺️ Idées pour plus tard (non planifiées)

Le projet s'arrête ici pour l'instant (mosaïque + accent color = dernière
phase prévue). Pistes possibles si tu veux reprendre un jour :

- Intégrer l'API Trakt pour résoudre les ~28 dossiers restants
  ("Recommandation", quelques Franchises/Thématiques)
- Génération de variantes `.webp` en plus du `.jpg`

---

**Besoin d'aide ?** Regarde les logs du workflow dans l'onglet **Actions**.# Nuvio Backdrops Automation

Génération automatique des images de fond (backdrops) pour les collections
Nuvio de ce dépôt, à partir de `Templates/Nuvio-Collections-Dwade58200.json`.

Inspiré du pipeline de [luckynumb3rs/stremio-perfect-setup](https://github.com/luckynumb3rs/stremio-perfect-setup),
adapté à la structure de collections propre à ce dépôt.

## 🎯 Comment ça marche

Le script `scripts/generer_backdrops.py` lit `Templates/Nuvio-Collections-Dwade58200.json`,
et pour **chaque dossier de chaque groupe actif**, il :

1. Regarde les `sources` du dossier et essaie de construire une ou plusieurs
   requêtes TMDB fiables (collection, discover avec filtres, ou endpoint
   générique). Les sources dupliquées filtrées sur une langue précise
   (ex : catalogues "🇫🇷 France" avec `withOriginalLanguage=fr`) sont
   exclues -- seuls les catalogues **globaux/mondiaux** sont conservés ;
2. Si aucune source directe n'est exploitable, tente un repli heuristique
   (ex : dossier "Action" dans le groupe Genres → genre TMDB "Action" ;
   thématique "Arts martiaux" → recherche par mot-clé TMDB "martial arts") ;
3. Récupère jusqu'à 12 titres (films/séries) correspondants -- dédupliqués
   même si un même film provient à la fois d'une collection et d'un
   catalogue discover -- et compose une **mosaïque** avec dégradé +
   couleur d'accent extraite automatiquement (voir section dédiée
   ci-dessous) ; en dessous de 3 titres distincts, bascule automatiquement
   sur l'ancien mode "1 seul backdrop" ;
4. Enregistre l'image dans `collections/<groupe>/backdrop/<dossier>.jpg`.

## 🎨 Mode mosaïque (par défaut)

Chaque dossier affiche une grille de tuiles **paysage** (16:9), disposées en
cascade inclinée -- même principe visuel que luckynumb3rs. Par-dessus :
- un dégradé sombre (bas, gauche, coin bas-gauche) pour un effet vignette ;
- une lueur diffuse d'une **couleur d'accent** extraite automatiquement à
  partir du premier titre trouvé, placée en haut à droite.

### ⚠️ Important : le titre affiché sur chaque tuile dépend de Fanart.tv

Le script n'écrit **aucun texte** lui-même. Les titres/logos visibles sur
les tuiles viennent des artworks **"thumb"** de [Fanart.tv](https://fanart.tv)
(`moviethumb`/`tvthumb`) -- des visuels communautaires qui incluent déjà le
titre stylisé. **Sans clé `FANART_API_KEY` configurée, les tuiles utilisent
le backdrop TMDB brut (sans aucun texte)** : la mosaïque reste jolie mais
sans titre visible.

Pour avoir les titres :
1. Crée un compte sur https://fanart.tv/profile/api-access/ et récupère une clé
2. Ajoute-la comme secret GitHub `FANART_API_KEY` (voir section suivante)

Le script cherche parmi plusieurs types d'artworks Fanart (par ordre de
préférence de type) : **thumb** (image complète avec titre incrusté),
**banner** (bannière large, contient souvent aussi un logo), **background**
(image de fond pure), **clearart/hdclearart** (artwork détouré, souvent sur
fond transparent -- recomposé proprement sur un fond sombre au moment du
recadrage, pour éviter tout artefact noir/blanc).

Priorité de LANGUE pour le choix de l'artwork (dans cet ordre) :
1. langue préférée (`--langue-preferee`, `fr` par défaut)
2. langue originale du titre
3. **n'importe quelle autre langue disponible, du moment qu'il y a un titre incrusté**
4. version sans texte -- seulement en tout dernier recours, si aucune
   langue n'a de version avec titre

Ce dernier point est volontaire : un titre dans une langue "inattendue"
reste préférable à une tuile sans aucun titre. Toutes les fiches Fanart
n'ont pas de version dans chaque langue ; le script prend le meilleur
disponible selon cet ordre.

C'est le comportement **par défaut** (`--mosaique`, activé aussi dans le
workflow GitHub Actions, y compris le cron mensuel). Si un dossier a moins
de 3 titres distincts résolus, le script repasse automatiquement sur
l'ancien mode "1 seul backdrop TMDB/Fanart", sans erreur.

**Pas de doublon visible** : la grille inclinée contient environ 70 cases
(quelle que soit la résolution de sortie). Le script récupère donc jusqu'à
~70 titres distincts par dossier (pagination TMDB automatique) pour remplir
toute la grille sans répéter la même affiche. Si un dossier a réellement
moins de titres disponibles que de cases (catalogue restreint), les
images sont répétées (cycle) en dernier recours pour compléter, comme le
fait luckynumb3rs -- mais uniquement dans ce cas.

Pour forcer l'ancien comportement (debug, comparaison) :
```bash
python3 scripts/generer_backdrops.py --collections ... # sans --mosaique
```
Ou, depuis GitHub Actions, coche **desactiver_mosaique** au déclenchement manuel.

### Couverture actuelle

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

## 🔗 Mise à jour des URLs (`heroBackdropUrl`)

Un second script, `scripts/mettre_a_jour_urls.py`, met à jour le champ
`heroBackdropUrl` du JSON de collections pour qu'il pointe vers ton propre
CDN. **Il n'a pas besoin de tourner à chaque exécution** : l'URL d'un
backdrop dépend uniquement du chemin du fichier (groupe + titre du
dossier), qui ne change pas d'un mois à l'autre — seule l'image derrière
cette URL est remplacée. Il suffit donc de le lancer une fois pour les
dossiers déjà résolus, puis de le relancer uniquement quand de *nouveaux*
dossiers deviennent résolvables (ex : après l'intégration de Trakt).

## ✅ Configuration requise

### 1. Clés API

- **TMDB** : créez un compte sur https://www.themoviedb.org/settings/api et
  récupérez une clé API (v3).
- **Fanart.tv** (fortement recommandé -- c'est la source des titres/logos
  incrustés sur les tuiles de la mosaïque, voir section précédente) :
  https://fanart.tv/profile/api-access/

### 2. Secrets GitHub

Dans **Settings → Secrets and variables → Actions** du dépôt, créez :
- `TMDB_API_KEY`
- `FANART_API_KEY` (recommandé -- sans lui, les mosaïques n'ont pas de titre visible)

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
| `--mosaique` | Grille multi-titres + couleur d'accent (repli auto si < 6 titres) |
| `--groupe "Genres"` | Limite le traitement à un seul groupe (pratique pour tester) |
| `--limite 5` | Limite le nombre de dossiers traités |
| `--profil {standard,haute,compresse}` | Taille/qualité de sortie |
| `-v` | Logs détaillés |

### Depuis GitHub Actions

1. Onglet **Actions** → workflow **Générer les Backdrops** → **Run workflow**
2. Le déclenchement manuel permet aussi de cocher **dry_run**, ou de préciser
   un `groupe`/une `limite` pour un test rapide sans tout régénérer.
3. La mosaïque est **active par défaut** (aussi sur le cron mensuel) ; coche
   **desactiver_mosaique** uniquement pour du débug/comparaison.
4. La case **mettre_a_jour_urls** est décochée par défaut (voir plus haut
   pourquoi) : coche-la uniquement la première fois, ou après une phase qui
   débloque de nouveaux dossiers.

Le workflow tourne aussi automatiquement le **1er de chaque mois à 4h00 UTC**
(modifiable dans `.github/workflows/generer-backdrops.yml`, section `cron`) —
cette exécution planifiée régénère les mosaïques mais ne touche jamais au
JSON (`mettre_a_jour_urls` reste désactivé par défaut).

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
│   ├── mosaique.py                  # Composition de la grille + couleur d'accent
│   ├── mettre_a_jour_urls.py        # Met à jour heroBackdropUrl vers le CDN du repo
│   └── purger_cache.py              # Purge du cache CDN jsDelivr
├── tests/
│   ├── test_generer_backdrops.py    # Tests de la logique de résolution
│   ├── test_mosaique.py             # Tests du module de mosaïque (hors-ligne)
│   ├── test_mosaique_integration.py # Test bout-en-bout du mode mosaïque
│   ├── test_mettre_a_jour_urls.py   # Tests de la mise à jour des URLs
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

## 🗺️ Idées pour plus tard (non planifiées)

Le projet s'arrête ici pour l'instant (mosaïque + accent color = dernière
phase prévue). Pistes possibles si tu veux reprendre un jour :

- Intégrer l'API Trakt pour résoudre les ~28 dossiers restants
  ("Recommandation", quelques Franchises/Thématiques)
- Génération de variantes `.webp` en plus du `.jpg`

---

**Besoin d'aide ?** Regarde les logs du workflow dans l'onglet **Actions**.
