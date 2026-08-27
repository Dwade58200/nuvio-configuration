# Nuvio Backdrops Automation

Génération automatique des images de fond (backdrops) pour les collections
Nuvio de ce dépôt, à partir de `Templates/Nuvio-Collections-Dwade58200.json`.

Inspiré du pipeline de [luckynumb3rs/stremio-perfect-setup](https://github.com/luckynumb3rs/stremio-perfect-setup),
adapté à la structure de collections propre à ce dépôt.

## 📁 Architecture de sortie (noms de dossiers/fichiers)

Tous les fichiers atterrissent sous :
```
Collections/<NomDuGroupe>/Backdrops/<NomDuFichier>_Backdrop.jpg
```

Exemples réels : `Collections/Genres/Backdrops/Sci-Fi_Backdrop.jpg`,
`Collections/Services de Streaming/Backdrops/Netflix_Backdrop.jpg`.

**Tout est regroupé dans un seul bloc, en haut de `scripts/generer_backdrops.py`**
(section "ARCHITECTURE DE SORTIE"), pour rester simple à modifier :

- `NOM_DOSSIER_RACINE` -- nom du dossier racine (`Collections`)
- `NOM_DOSSIER_BACKDROPS` -- nom du sous-dossier dans chaque groupe (`Backdrops`)
- `GROUPE_SLUGS` -- nom de dossier (français) pour chaque groupe --
  une ligne par groupe, facile à changer
- `NOMS_BACKDROP_PERSONNALISES` -- table de correspondance EXPLICITE pour
  les noms de fichiers avec un sigle (TF1, HBO), un "+" (Canal+, Disney+),
  ou un raccourci (ex: "Grands réalisateurs du cinéma" → `Grands_Realisateurs`).
  **Pour ajouter/changer un nom de fichier : une seule ligne à ajouter/éditer ici.**
- Tout titre de dossier absent de cette table obtient un nom générique
  calculé automatiquement (mots capitalisés séparés par underscore, sigles
  connus -- `ACRONYMES_BACKDROP` -- mis en majuscules).

⚠️ **Changement d'architecture depuis une version antérieure** : les
dossiers de sortie sont passés de l'anglais minuscule (`collections/genres/backdrop/action.jpg`)
au français capitalisé (`Collections/Genres/Backdrops/Action_Backdrop.jpg`).
Le workflow supprime automatiquement l'ancien dossier `collections/`
(minuscule) au premier lancement après cette mise à jour, pour éviter
d'avoir les deux arborescences en parallèle. Pense à cocher
**mettre_a_jour_urls** une fois après la mise à jour pour que
`heroBackdropUrl` pointe vers les nouveaux chemins.

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
4. Enregistre l'image dans `Collections/<Groupe>/Backdrops/<Nom>_Backdrop.jpg`.

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
nos tuiles paysage). La correspondance de langue est **stricte** : un
artwork tagué `fr-CA` (français canadien) ou toute autre variante
régionale n'est JAMAIS considéré comme "français" -- seul le tag exact
`fr` compte.

### Volume de requêtes : cache + budget de repli

Avec ~70 titres par dossier sur 43 dossiers, le nombre d'appels TMDB peut
vite grimper. Une protection est en place :

- **Cache** : un même titre (souvent présent dans plusieurs dossiers --
  ex: un blockbuster apparaît dans "Populaire", "Action" ET "Tendance") ne
  déclenche qu'un seul appel TMDB `/images` et un seul appel Fanart pour
  toute l'exécution, même s'il est rencontré plusieurs fois.

TMDB n'impose pas de quota fixe d'appels par run (juste une limitation de
débit, gérée par des tentatives avec délai croissant en cas de réponse
`429`) -- il n'y a donc pas de "budget" artificiel de repli sur Fanart à
configurer.

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
| 🔭 Découvrir | 3 / 6 | "Recommandation" est une liste MDBList personnalisée au compte, sans URL publique -- non résolvable |
| 🎬 Streaming | 0 / 9 | volontairement désactivé (sources FlixPatrol, non-TMDB) |
| 🎭 Genres | 15 / 15 | ✅ |
| 🎨 Thématiques | 14 / 14 | ✅ (résolu via l'export AIOMetadata + MDBList) |
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
dossiers deviennent résolvables (ex : après l'ajout d'un nouveau catalogue).

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
- `MDBLIST_API_KEY` (optionnel -- voir section MDBList ci-dessous ; sans lui, seules les listes MDBList *publiques* fonctionnent, ce qui couvre la quasi-totalité des cas)

Trakt n'est **pas pris en charge** (créer une application Trakt nécessite
désormais un abonnement VIP) -- toute source `provider: "trakt"` est
explicitement ignorée et journalisée, jamais une erreur. MDBList (voir
plus bas) couvre le même besoin sans ce problème.

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
| `--aiometadata chemin.json` | Export AIOMetadata pour résoudre les catalogues (dont les listes MDBList ajoutées via l'addon) avec leurs vrais filtres/URLs |
| `--cle-mdblist clé` | Clé API MDBList.com (ou variable `MDBLIST_API_KEY`) -- voir section MDBList ci-dessous |
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
├── Collections/
│   └── <Groupe>/Backdrops/*.jpg      # Images générées (ex: Genres/Backdrops/Action_Backdrop.jpg)
├── scripts/
│   ├── generer_backdrops.py         # Script principal
│   ├── mosaique.py                  # Composition de la grille + couleur d'accent
│   ├── mettre_a_jour_urls.py        # Met à jour heroBackdropUrl vers le CDN du repo
│   ├── mdblist_recherche.py         # Recherche de listes MDBList publiques (usage local)
│   └── purger_cache.py              # Purge du cache CDN jsDelivr
├── tests/
│   ├── test_generer_backdrops.py    # Tests de la logique de résolution
│   ├── test_mosaique.py             # Tests du module de mosaïque (hors-ligne)
│   ├── test_mosaique_integration.py # Test bout-en-bout du mode mosaïque
│   ├── test_mettre_a_jour_urls.py   # Tests de la mise à jour des URLs
│   ├── fixtures/aiometadata-exemple.json          # Fixture AIOMetadata (format réel, config.catalogs)
│   ├── fixtures/aiometadata-exemple-legacy-plat.json  # Fixture ancien format (catalogs à la racine)
│   └── test_pipeline_integration.py # Test bout-en-bout (HTTP simulé)
└── BACKDROPS_SETUP.md               # Ce fichier
```

## 🐛 Dépannage

**"clé TMDB manquante"** → vérifie le secret `TMDB_API_KEY`, ou utilise `--dry-run`.

**Un dossier n'a pas de backdrop après une exécution réelle** → regarde la
section "Dossiers ignorés, par raison" dans le résumé : c'est très souvent
une source `provider: "trakt"` (non prise en charge, voir plus bas), une
liste MDBList personnalisée sans URL publique (ex: "Recommandation"), ou
un catalogue "addon" propre à ta configuration Stremio qu'on ne peut pas
résoudre sans son fichier de définition (`--aiometadata`).

**Les images ne se mettent pas à jour sur Nuvio** → jsDelivr cache les
fichiers ~7 jours ; le workflow purge automatiquement le cache après chaque
commit, mais tu peux aussi lancer `python3 scripts/purger_cache.py` toi-même.

**"⚠️ Groupe non reconnu dans le JSON"** → un groupe entier a été renommé
dans Nuvio au-delà d'un simple emoji/espace/accent (ce que le script gère
déjà tout seul). Il faut ajouter ce nouveau nom au script : dans
`scripts/generer_backdrops.py`, section `CRITERES_GROUPES`/`GROUPE_SLUGS`
en haut du fichier. Le message indique le titre normalisé pour t'aider à
identifier de quel groupe canonique il s'agit.

**"⚠️ Groupe(s) attendu(s) mais absent(s) du JSON"** → l'inverse : un
groupe que le script s'attend à trouver (ex: "vibe") n'apparaît nulle part
dans le JSON actuel. Vérifie qu'il n'a pas été renommé de façon
méconnaissable, ou supprimé.

**Un nom de groupe a juste changé d'emoji/espace/accent** → rien à faire,
c'est géré automatiquement (voir "Résilience aux renommages" ci-dessous).

## 📺 Export AIOMetadata (résolution exacte des catalogues)

Les catalogId "addon/aio-metadata" opaques (ex : `tmdb.discover.movie.global.mt49lr48`
pour Netflix) ne portent, par eux-mêmes, aucune information exploitable
sur le vrai filtre TMDB derrière -- juste un label libre et un hash.

**Solution** : exporte la configuration de ton addon AIOMetadata (dans
l'addon : Réglages → Export) et place le fichier JSON obtenu à
`Templates/aiometadata-setup.json` dans ce dépôt. Le script le charge
automatiquement s'il est présent (aucune configuration supplémentaire) et
construit une table exacte `catalogId -> vrais filtres TMDB`
(`with_watch_providers`, `with_genres`, dates, etc., directement extraits
de l'export). Cette correspondance est utilisée en **priorité absolue**
avant toute heuristique.

Concrètement, pour Netflix/Prime/HBO/Disney+/Paramount+/Apple TV+/Canal+,
ça permet d'obtenir le VRAI filtre `with_watch_providers` de la
plateforme (ex: `8` pour Netflix, `337` pour Disney+) au lieu d'un simple
contenu populaire générique. Pour TF1/M6, ça récupère aussi leur filtre
genre spécifique ("Reality"), pas juste le fournisseur.

**Si l'export n'est pas fourni**, ou si un catalogue en est absent
(nouveau catalogue ajouté depuis dans Nuvio), le script utilise
automatiquement les replis habituels dans cet ordre :
1. Réseau TV connu (TF1/M6, via `with_networks`) ;
2. Popularité globale générique, sans filtre plateforme.

⚠️ **Pense à ré-exporter et remplacer `Templates/aiometadata-setup.json`
si tu ajoutes/modifies des catalogues dans AIOMetadata** -- sinon le
script utilisera les replis génériques pour les nouveaux catalogues, ou
une config obsolète pour les anciens.

Les catalogues FlixPatrol/`streaming.*`/`custom.*` (non-TMDB, ex: Top 10
France) restent non résolus -- ils n'ont pas d'équivalent TMDB direct.

## 🎬 Trakt (non pris en charge)

Créer une application Trakt nécessite désormais un abonnement Trakt VIP
(voir la discussion du 2 août 2026 sur forums.trakt.tv), ce qui n'est
pas disponible pour ce projet. Toute source `provider: "trakt"` dans le
JSON de collections est donc explicitement **ignorée et journalisée**
avec la raison -- jamais une erreur. **MDBList (ci-dessous) couvre le
même besoin** (listes de films/séries) sans ce problème : la connexion à
MDBList se fait via un compte Trakt **gratuit** ("Login with Trakt" --
c'est l'application *de MDBList*, pas la tienne, qui est déjà
enregistrée), et MDBList délivre ensuite sa propre clé API, gratuite,
sans OAuth ni renouvellement de jeton.

## 📋 MDBList

Les sources `provider: "mdblist"` dans le JSON de collections, ainsi que
les catalogues **ajoutés via l'addon AIOMetadata** (`provider: "addon"`
avec un `catalogId` du type `mdblist.<id>`, ex : "Sitcom") sont
résolus via l'API MDBList.com -- ces derniers nécessitent de fournir
`--aiometadata Templates/aiometadata-setup.json` (déjà fait
automatiquement par le workflow GitHub Actions s'il trouve ce fichier).

⚠️ **Cas non résolvable : les listes "Recommandation" personnalisées**
(`mdblist.recommended.*`). Ce sont des recommandations calculées à partir
de l'historique de visionnage du compte MDBList/Trakt lié, sans URL
publique fixe -- MDBList ne fait que lire des listes existantes (les
tiennes ou des listes publiques), pas générer des recommandations à
partir d'un historique. Ce catalogue reste explicitement ignoré, message
à l'appui, plutôt que traité en silence.

### Configuration (optionnelle mais recommandée)

1. Va sur https://mdblist.com, clique sur **Login**, puis **with Trakt.tv**
   -- connecte-toi avec ton compte Trakt habituel (gratuit, aucun VIP requis).
2. Une fois connecté, va dans **Preferences** (https://mdblist.com/preferences/)
   et clique sur **New API Key** pour générer ta clé.
3. Secret GitHub `MDBLIST_API_KEY` (Settings → Secrets and variables → Actions).

Palier gratuit : 1000 requêtes/jour (largement suffisant pour une
exécution périodique du pipeline). **Sans cette clé**, les listes
MDBList **publiques** référencées par une URL (ce qui couvre la quasi-
totalité des cas, y compris tous les catalogues ajoutés via l'addon
AIOMetadata) continuent de fonctionner via le repli JSON public de
MDBList (voir plus bas) -- la clé n'est vraiment utile que pour les
listes référencées uniquement par un identifiant numérique opaque, ou
pour éviter les limites de débit du repli public.

### Comment référencer une liste MDBList manuellement dans le JSON

Trois formats acceptés pour une source `provider: "mdblist"` ajoutée à la
main (indépendamment de l'addon AIOMetadata), du plus simple au plus
explicite (un seul suffit) :

```json
{ "provider": "mdblist", "mdblistUrl": "https://mdblist.com/lists/ton-pseudo/nom-de-la-liste" }
```
```json
{ "provider": "mdblist", "mdblistId": 12345 }
```
```json
{ "provider": "mdblist", "mdblistUser": "ton-pseudo", "mdblistSlug": "nom-de-la-liste" }
```

Le plus simple en pratique : ouvre ta liste sur mdblist.com, copie l'URL
telle quelle depuis la barre d'adresse dans `mdblistUrl`.

### Chercher une liste par titre (`mdblist_recherche.py`)

Pour trouver la bonne liste à mettre en `mdblistUrl` sans avoir à
fouiller le site à la main, un petit script local est fourni :

```bash
export MDBLIST_API_KEY="ta_cle_ici"
python3 scripts/mdblist_recherche.py "james bond"
```

Il interroge l'endpoint officiel de recherche de listes publiques
(`GET /lists/search`) et affiche, pour chaque résultat trouvé (triés par
nombre d'items décroissant), le nombre d'items/likes et surtout le
snippet JSON prêt à coller directement dans une source `mdblist` :

```
1. James Bond Collection
   👤 someuser  ·  📦 27 items  ·  ❤️  142 likes  ·  🎬 movie
   🔗 https://mdblist.com/lists/someuser/james-bond-collection
   Snippet JSON à coller dans une source :
   { "provider": "mdblist", "mdblistUrl": "https://mdblist.com/lists/someuser/james-bond-collection" }
```

Ce script est à lancer en local uniquement (pas besoin dans le workflow
GitHub Actions).

### Repli sans clé API

Si `MDBLIST_API_KEY` est absent ou que l'API officielle échoue pour une
raison quelconque, le pipeline retente automatiquement l'export JSON
public de la liste (`mdblist.com/lists/<user>/<slug>/json/`), qui ne
nécessite aucune clé -- mais qui ne fonctionne que pour des listes
**publiques** et seulement quand la liste est identifiée par
`mdblistUrl`/`mdblistUser`+`mdblistSlug` (pas par `mdblistId` seul, qui
lui nécessite une clé API).

## 🛡️ Résilience aux renommages de groupes

Nuvio a déjà renommé les groupes de collections à plusieurs reprises
(ajout/changement d'emoji, espace en plus ou en moins...). Pour ne plus
jamais casser silencieusement à cause de ça, le script compare les titres
de groupes de façon **normalisée** (minuscule, sans accents, sans emoji,
espaces réduits) plutôt qu'en texte exact. Concrètement :

- `"🎭Genres"`, `"🎭 Genres"`, `"🆕 Genres"` sont tous reconnus comme le
  même groupe "Genres".
- Un renommage plus profond (ex: "Vibe" → "Ambiances") n'est PAS deviné
  automatiquement -- mais il déclenche un avertissement explicite au lieu
  d'échouer en silence (voir Dépannage ci-dessus), avec le nom exact à
  ajouter au script.

## 🗺️ Idées pour plus tard (non planifiées)

Le projet s'arrête ici pour l'instant (mosaïque + accent color = dernière
phase prévue). Pistes possibles si tu veux reprendre un jour :

- ~~Intégrer l'API Trakt pour résoudre les ~28 dossiers restants~~ --
  Trakt nécessite désormais un compte VIP pour créer une application ;
  **retiré du projet**. La quasi-totalité de ces dossiers est maintenant
  résolue automatiquement via MDBList (catalogues ajoutés dans l'addon
  AIOMetadata + `--aiometadata`, voir section dédiée ci-dessus) ; seule
  "Recommandation" (liste personnalisée sans URL publique) reste hors
  d'atteinte.
- Génération de variantes `.webp` en plus du `.jpg`

---

**Besoin d'aide ?** Regarde les logs du workflow dans l'onglet **Actions**.
