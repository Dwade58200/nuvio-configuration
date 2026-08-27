# nuvio-configuration

Configuration personnelle de mes **Collections Nuvio**, avec un pipeline
Python qui génère automatiquement les images de fond (*backdrops*) de
chaque dossier de collection à partir de TMDB et Fanart.tv.

Inspiré du pipeline de [luckynumb3rs/stremio-perfect-setup](https://github.com/luckynumb3rs/stremio-perfect-setup),
mais adapté à la structure et aux besoins de ma propre configuration Nuvio.

---

## 🧭 Résumé rapide

Ce dépôt sert à deux choses :

1. **Stocker la configuration de mes Collections Nuvio** : le fichier
   `Templates/Nuvio-Collections-Dwade58200.json` définit tous mes groupes
   (Genres, Thématiques, Années, Franchises…) et, pour chaque dossier à
   l'intérieur, quel catalogue afficher et quel visuel utiliser (logo,
   cover, backdrop).
2. **Générer automatiquement les backdrops** de chaque dossier : un
   script Python (`scripts/generer_backdrops.py`) va chercher les
   affiches des films/séries de chaque catalogue sur TMDB/Fanart.tv, les
   compose en mosaïque, et met à jour le JSON pour que Nuvio pointe vers
   ces images. Le tout tourne automatiquement une fois par mois via
   GitHub Actions — donc mes backdrops se renouvellent seuls, sans
   intervention manuelle.

En résumé : **je n'ai rien à faire au quotidien**. Le dépôt tourne tout
seul chaque mois et actualise mes visuels. Je n'ai besoin d'y revenir que
si je veux ajouter/modifier une collection, ou déboguer un problème.

---

## 📂 Structure du dépôt

```
nuvio-configuration/
├── Templates/
│   └── Nuvio-Collections-Dwade58200.json   # Source de vérité : mes collections Nuvio
├── collections/
│   └── <groupe>/backdrop/*.jpg             # Images générées automatiquement
├── scripts/
│   ├── generer_backdrops.py                # Script principal de génération
│   ├── mosaique.py                         # Composition visuelle des mosaïques
│   ├── mettre_a_jour_urls.py               # Met à jour les URLs dans le JSON
│   └── purger_cache.py                     # Vide le cache CDN après une mise à jour
├── tests/                                  # Tests automatisés des scripts ci-dessus
├── .github/workflows/
│   └── generer-backdrops.yml               # Automatisation mensuelle (GitHub Actions)
├── requirements-dev.txt                    # Dépendances Python nécessaires
└── BACKDROPS_SETUP.md                      # Documentation technique détaillée du pipeline
```

*(Les dossiers `Collections/Covers/` et `Collections/Logos/` — avec
majuscule, à ne pas confondre avec `collections/` ci-dessus — contiennent
mes visuels de couverture et logos gérés manuellement. Depuis la fusion
des branches, ils vivent dans ce même dépôt/branche, à la racine, et ne
sont pas détaillés ici.)*

---

## 🗂️ `Templates/Nuvio-Collections-Dwade58200.json` — le cœur de la config

C'est le fichier que Nuvio importe pour afficher mes collections. Il est
organisé en **groupes**, et chaque groupe contient des **dossiers**
(les tuiles qu'on voit sur l'écran d'accueil de Nuvio). Mes groupes
actuels :

| Groupe | Dossiers | Exemple de contenu |
|---|---|---|
| 🔭 Découvrir | 6 | Recommandation, Tendance, Populaire… |
| 🎬 Services de Streaming | 9 | Netflix, Disney+, Prime Video… |
| 🎭 Genres | 15 | Action, Comédie, Horreur… |
| 🎨 Thématiques | 14 | Arts martiaux, Braquage… |
| 🎭 Vibe | 4 | Ambiances/humeurs de visionnage |
| 📅 Années | 8 | Par décennie |
| 🎞️ Franchises | 158 | Sagas et univers (Marvel, Star Wars…) |
| 🏃‍♂️ Sports | 7 | Documentaires/films sportifs par discipline |

Pour chaque dossier, le JSON précise :
- **`sources` / `catalogSources`** : quel(s) catalogue(s) AIOMetadata
  alimentent ce dossier (ex : un genre TMDB, une liste MDBList, un
  catalogue "discover"…).
- **`titleLogoUrl`** / **`coverImageUrl`** : le logo et la couverture
  affichés dans Nuvio.
- **`heroBackdropUrl`** : l'image de fond en grand format, mise à jour
  automatiquement par le pipeline décrit ci-dessous.

C'est donc ce fichier qu'il faut éditer si je veux ajouter, renommer ou
réorganiser une collection — puis le réimporter dans Nuvio.

---

## 🎨 Le pipeline de génération des backdrops

### Pourquoi ce pipeline existe

Nuvio n'a pas de backdrop "par défaut" satisfaisant pour un dossier de
collection personnalisé (contrairement à un film/série individuel, qui a
son propre backdrop TMDB). Ce pipeline résout ce problème : il fabrique
une image de fond représentative pour **chaque dossier**, à partir des
titres qu'il contient réellement.

### Comment ça marche, étape par étape

1. **`generer_backdrops.py`** lit le JSON de collections et, pour chaque
   dossier actif, identifie ses sources (genre TMDB, discover, mot-clé…).
2. Il récupère jusqu'à 12 titres correspondants via l'API TMDB, en
   excluant les catalogues filtrés sur une langue spécifique (ex :
   variantes "France" en double d'un catalogue global) pour éviter les
   doublons.
3. **`mosaique.py`** compose ces titres en une grille inclinée de
   vignettes 16:9, avec un dégradé sombre et une couleur d'accent extraite
   automatiquement du visuel principal — le même principe visuel que
   `luckynumb3rs/stremio-perfect-setup`.
4. Si une clé **Fanart.tv** est configurée, les vignettes affichent le
   titre du film/série incrusté (artworks "thumb" communautaires) ; sinon
   elles utilisent le backdrop TMDB brut, sans texte.
5. L'image finale est enregistrée dans `collections/<groupe>/backdrop/`.
6. **`mettre_a_jour_urls.py`** (optionnel, activé seulement à la demande)
   met à jour le champ `heroBackdropUrl` du JSON pour qu'il pointe vers
   l'image nouvellement générée sur le CDN du dépôt (jsDelivr).
7. **`purger_cache.py`** vide le cache CDN après chaque mise à jour, pour
   que les nouvelles images apparaissent rapidement dans Nuvio (jsDelivr
   les met sinon en cache ~7 jours).

### Automatisation (`.github/workflows/generer-backdrops.yml`)

Le pipeline tourne **automatiquement le 1er de chaque mois à 4h UTC** :
il régénère toutes les mosaïques et les recommet dans le dépôt, sans
intervention de ma part. Il peut aussi être lancé manuellement depuis
l'onglet **Actions** de GitHub, avec des options utiles pour tester :
mode simulation (`dry_run`), limiter à un seul groupe, limiter le nombre
de dossiers traités, ou désactiver le mode mosaïque pour comparer avec
l'ancien rendu "1 seul backdrop".

### Clés API nécessaires

Le pipeline a besoin de deux secrets GitHub (`Settings → Secrets and
variables → Actions`) :
- **`TMDB_API_KEY`** : obligatoire, sert à récupérer les titres et leurs
  visuels.
- **`FANART_API_KEY`** : fortement recommandé, sinon les mosaïques
  n'affichent aucun titre incrusté sur les vignettes.

### Couverture actuelle

Certains groupes ne génèrent pas encore de backdrop, volontairement ou
par manque d'intégration :

| Groupe | Résolu | Raison si non résolu |
|---|---|---|
| Genres, Vibe, Années, Thématiques | 100% | — |
| Découvrir | Presque | "Recommandation" est une liste MDBList personnalisée au compte, sans URL publique |
| Services de Streaming | 0% | Sources FlixPatrol, non compatibles TMDB |
| Franchises, Sports | 0% | Désactivés volontairement (peu pertinent / trop de dossiers) |

---

## 🧪 `tests/`

Suite de tests automatisés (`pytest`) qui vérifient la logique de
résolution des sources, la composition des mosaïques, et la mise à jour
des URLs — sans avoir besoin de clés API. Ils tournent en local avant de
pousser une modification, pour éviter de casser le pipeline.

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

---

## 📄 Autres fichiers

- **`BACKDROPS_SETUP.md`** — documentation technique complète du
  pipeline (options en ligne de commande, dépannage, logique de
  résilience aux renommages de groupes). À consulter si je dois modifier
  ou déboguer le script.

---

## 🛠️ Ce que je fais concrètement avec ce dépôt

- **Rien, la plupart du temps** — le cron mensuel s'occupe de tout.
- **Ajouter une collection** → j'édite `Templates/Nuvio-Collections-Dwade58200.json`,
  puis je réimporte dans Nuvio.
- **Forcer une régénération** → onglet *Actions* → *Générer les
  Backdrops* → *Run workflow*.
- **Débugger un backdrop manquant** → je regarde les logs du workflow, ou
  je consulte `BACKDROPS_SETUP.md` (section Dépannage).
