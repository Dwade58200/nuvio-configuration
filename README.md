# nuvio-configuration

[![Tests](https://github.com/Dwade58200/nuvio-configuration/actions/workflows/tests.yml/badge.svg)](https://github.com/Dwade58200/nuvio-configuration/actions/workflows/tests.yml)
[![Backdrops](https://github.com/Dwade58200/nuvio-configuration/actions/workflows/generer-backdrops.yml/badge.svg)](https://github.com/Dwade58200/nuvio-configuration/actions/workflows/generer-backdrops.yml)

Configuration personnelle de mes **Collections Nuvio**, avec un pipeline
Python qui génère automatiquement les images de fond (*backdrops*) de
chaque dossier de collection à partir de TMDB, Fanart.tv et MDBList.

Inspiré du pipeline de [luckynumb3rs/stremio-perfect-setup](https://github.com/luckynumb3rs/stremio-perfect-setup),
mais adapté à la structure et aux besoins de ma propre configuration Nuvio.

## En bref

Ce dépôt sert à deux choses :

1. **Stocker la configuration de mes Collections Nuvio** --
   `Templates/Nuvio-Collections-Dwade58200.json` définit tous mes groupes
   (Genres, Thématiques, Années, Franchises…) et, pour chaque dossier à
   l'intérieur, quel catalogue afficher et quel visuel utiliser.
2. **Générer automatiquement les backdrops** de chaque dossier -- un
   script Python va chercher les titres de chaque catalogue sur
   TMDB/Fanart.tv/MDBList, les compose en mosaïque, et le tout est commité
   dans ce dépôt puis servi via CDN (jsDelivr) pour que Nuvio les affiche.

Le pipeline tourne **automatiquement chaque mois** via GitHub Actions :
je n'ai rien à faire au quotidien, je ne reviens sur ce dépôt que pour
ajouter/modifier une collection ou déboguer un problème.

## Structure du dépôt

```
nuvio-configuration/
├── Templates/
│   ├── Nuvio-Collections-Dwade58200.json  # Source de vérité : mes collections Nuvio
│   └── aiometadata-setup.json             # Export de mon addon AIOMetadata (résolution précise des catalogues)
├── schema/
│   └── nuvio-collections.schema.json      # Schéma JSON du fichier de collections, validé en CI
├── Collections/
│   └── <Groupe>/Backdrops/*.jpg           # Images générées automatiquement (ex: Genres/Backdrops/Action_Backdrop.jpg)
├── Badges/
│   └── Badges_Nuvio_Gold.json             # Config des badges qualité Nuvio (langue, résolution, source…), gérée à part
├── scripts/                                # Pipeline de génération -- voir BACKDROPS_SETUP.md
├── tests/                                  # Tests automatisés (pytest)
├── .github/workflows/
│   ├── generer-backdrops.yml              # Automatisation mensuelle des backdrops
│   └── tests.yml                          # CI : tests + lint (ruff/mypy) + validation du schéma
├── requirements.txt / requirements-dev.txt # Dépendances runtime / développement
└── BACKDROPS_SETUP.md                      # Documentation technique complète du pipeline
```

## Mes collections

| Groupe | Dossiers | Exemple de contenu |
|---|---|---|
| 🔭 Découvrir | 7 | Recommandation, Tendance, Populaire… |
| 🎬 Services de Streaming | 9 | Netflix, Disney+, Prime Video… |
| 🎭 Genres | 15 | Action, Comédie, Horreur… |
| 🎨 Thématiques | 14 | Arts martiaux, Braquage… |
| 🎭 Vibe | 4 | Ambiances/humeurs de visionnage |
| 🎌 Animés | 9 | Catalogues animés dédiés |
| 📅 Années | 8 | Par décennie |
| 🎞️ Franchises | 158 | Sagas et univers (Marvel, Star Wars…) |
| 🏃 Sports | 9 | Documentaires/films sportifs par discipline |

Pour chaque dossier, `Templates/Nuvio-Collections-Dwade58200.json` précise
ses `sources` (catalogue TMDB/AIOMetadata/MDBList qui l'alimente), son
logo/sa couverture, et son `heroBackdropUrl` -- mis à jour automatiquement
par le pipeline. C'est ce fichier qu'il faut éditer pour ajouter, renommer
ou réorganiser une collection, puis le réimporter dans Nuvio.

## Génération des backdrops

Chaque dossier obtient une mosaïque d'environ 70 vignettes composées à
partir des vrais titres du catalogue, avec une couleur d'accent extraite
automatiquement -- pas un simple backdrop générique. Le détail complet du
fonctionnement (résolution des sources, cascade d'images, export
AIOMetadata, intégration MDBList, options CLI, dépannage) est documenté
dans **[`BACKDROPS_SETUP.md`](BACKDROPS_SETUP.md)**.

**Couverture actuelle** : 53 dossiers sur 54 ciblés génèrent leur backdrop
avec succès (Genres, Thématiques, Vibe, Années et Services de Streaming à
100% ; Franchises et Sports sont volontairement exclus). Détail complet
et raisons dans `BACKDROPS_SETUP.md`, section *Couverture actuelle*.

## Démarrage rapide

```bash
git clone https://github.com/Dwade58200/nuvio-configuration.git
cd nuvio-configuration
pip install -r requirements-dev.txt

# Tests + validation du schéma (aucune clé API nécessaire)
pytest tests/ -v
python3 scripts/valider_collections.py

# Simulation complète de la génération, sans appel réseau
python3 scripts/generer_backdrops.py --dry-run
```

Pour une exécution réelle, deux secrets GitHub sont nécessaires
(`Settings → Secrets and variables → Actions`) : `TMDB_API_KEY` et
`FANART_API_KEY` (`MDBLIST_API_KEY` est optionnel). Détails dans
`BACKDROPS_SETUP.md`, section *Configuration requise*.

## Qualité & CI

À chaque push/PR, `.github/workflows/tests.yml` fait tourner :
- **pytest** (146 tests) -- résolution des sources, composition des
  mosaïques, mise à jour des URLs, validation du schéma ;
- **ruff** -- lint (bloquant) ;
- **mypy** -- vérification de types (bloquant) ;
- **`valider_collections.py`** -- conformité de
  `Templates/Nuvio-Collections-Dwade58200.json` à
  `schema/nuvio-collections.schema.json`.

## Documentation

| Fichier | Contenu |
|---|---|
| [`BACKDROPS_SETUP.md`](BACKDROPS_SETUP.md) | Référence technique complète du pipeline : fonctionnement détaillé, options CLI, configuration MDBList/AIOMetadata, dépannage |
| [`AMELIORATIONS.md`](AMELIORATIONS.md) | Liste de travail : ce qui a été fait, ce qui reste, pistes non planifiées |
| [`APPLIQUER.md`](APPLIQUER.md) | Journal des corrections de la dernière session en date, pour suivre ce qui a changé |

## Licence

Le code (`scripts/`, `tests/`, `schema/`) est sous licence [MIT](LICENSE).
Le contenu de `Templates/Nuvio-Collections-Dwade58200.json` et
`Templates/aiometadata-setup.json` reste une configuration personnelle
(pas de garantie de compatibilité si réutilisé tel quel avec un autre
compte AIOMetadata/Nuvio).

## Usage courant

- **Rien, la plupart du temps** -- le cron mensuel s'occupe de tout.
- **Ajouter/renommer une collection dans Nuvio** → rien à faire côté script,
  c'est pris en compte automatiquement au prochain run (voir
  `BACKDROPS_SETUP.md`, section *Ajout/suppression d'une collection*).
- **Imposer une image sans passer par la génération** → fichier
  `Templates/images-manuelles.json` (voir `BACKDROPS_SETUP.md`, section
  *Images manuelles*).
- **Ajouter une collection** → éditer `Templates/Nuvio-Collections-Dwade58200.json`
  (idéalement en suivant `schema/nuvio-collections.schema.json`), puis
  réimporter dans Nuvio.
- **Forcer une régénération** → onglet *Actions* → *Générer les
  Backdrops* → *Run workflow*.
- **Déboguer un backdrop manquant** → logs du workflow, ou
  `BACKDROPS_SETUP.md` section *Dépannage*.
