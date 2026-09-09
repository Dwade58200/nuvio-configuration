# Améliorations potentielles — nuvio-configuration

Liste de travail, par ordre de priorité décroissant. Rien ici n'est cassé
dans le pipeline actuel : ce sont des pistes pour se rapprocher d'un dépôt
de qualité professionnelle, pas des correctifs urgents.

---

## ✅ Fait (session du 8 septembre 2026 -- backdrop pour FanKai, comme Bingecat)

- [x] **FanKai résolu comme un catalogue "custom" (comme Bingecat)** :
      son addon réel est **FKStream** (`https://streamio.fankai.fr/...`),
      agrégé via AIOStreams -- son addonId n'est donc pas `aio-metadata`.
      `generer_backdrops.py` élargi pour accepter n'importe quel addon dès
      lors que son `catalogId` est enregistré comme catalogue `custom`
      dans l'export fourni (mêmes garde-fous : les heuristiques de repli
      restent réservées à `aio-metadata`, pas de risque de résolution
      hasardeuse pour un addon inconnu).
- [x] **Nouveau mode "images directes"** pour les catalogues sans id IMDb
      exploitable : FKStream utilise des ids `fk:N` (confirmé par
      `idPrefixes: ["fk"]` dans son manifeste, `imdb_id` toujours `null`
      dans ses items) -- la conversion IMDb->TMDB de Bingecat est donc
      inopérante ici. Ajout d'un champ optionnel `"champImage": "poster"`
      dans l'entrée de catalogue (`ClientCatalogueCustom.recuperer_images_directes`) :
      les URLs de ce champ sont utilisées telles quelles, sans passer par
      TMDB. Dédoublonnage corrigé au passage : sans `tmdb_id`, la clé de
      dédoublonnage utilisait `(media_type, None)` pour TOUS les items
      (bug qui aurait fait disparaître 99% des affiches FanKai) -- bascule
      sur l'URL d'image elle-même comme clé quand `tmdb_id` est absent.
- [x] **`Templates/catalogues-personnalises.json`** (fusionné par-dessus
      `--aiometadata`) : registre séparé pour ces catalogues non couverts
      par l'export AIOMetadata standard. Fichier gabarit
      (`.example.json`) committé, vrai fichier dans `.gitignore` (contient
      une URL avec la config AIOStreams -- et donc une clé de service
      debrid -- encodée en base64). Automatisable en CI via un secret
      GitHub `CATALOGUES_PERSONNALISES`, matérialisé sur le runner par
      une nouvelle étape du workflow (jamais loggé).
- [x] 8 nouveaux tests (dont un test d'intégration bout en bout avec un
      extrait réel du catalogue FanKai transmis par l'utilisateur --
      mosaïque générée avec zéro appel TMDB, confirmé), 191/191 verts au
      total ; `ruff`/`mypy` propres ; run réel sans régression (toujours
      64 générés / 0 erreur sans le fichier personnalisé, FanKai sort
      bien de "provider non géré" une fois le fichier gabarit fourni).
      Documentation à jour (`BACKDROPS_SETUP.md`, nouvelle sous-section
      *Catalogues sans id IMDb*).

---

## ✅ Fait (session du 7 septembre 2026 -- check-up complet du dépôt réel)

Audit demandé sur un export réel du repo GitHub (`Dwade58200/nuvio-configuration`,
branche `main`) plutôt que sur l'état de travail habituel -- a révélé 3
vrais bugs, invisibles jusqu'ici car jamais exercés en CI sur ce contenu
précis :

- [x] **Schéma JSON désynchronisé (régression, cassait la CI)** : le vrai
      `Templates/Nuvio-Collections-Dwade58200.json` contient désormais 22
      sources `provider: "trakt"` (sous-listes James Bond par acteur, dans
      le groupe Franchises -- pour la sélection de contenu Nuvio, sans
      rapport avec la résolution des backdrops) que `schema/nuvio-collections.schema.json`
      ne connaissait pas (`enum` limité à `tmdb`/`addon`/`mdblist`).
      `pytest` échouait sur `test_le_vrai_fichier_de_collections_est_conforme_au_schema`.
      Corrigé : `trakt` ajouté à l'énumération + sous-règle dédiée
      (`traktListId` + `mediaType` requis, `sortBy`/`sortHow` optionnels,
      calquée sur les 22 occurrences réelles). Sans rapport avec le retrait
      de Trakt comme *outil de catalogues* (toujours d'actualité, voir plus
      bas) -- Nuvio lui-même sait très bien consommer des sources Trakt
      pour peupler un dossier, ce n'est pas la même chose.
- [x] **`lint_config.py` jamais exécuté en CI** : construit pour ça (voir
      session précédente) mais l'étape n'avait jamais été ajoutée à
      `.github/workflows/tests.yml`. Ajoutée juste après la validation du
      schéma.
- [x] **Valeur par défaut de `--branche` obsolète** dans
      `mettre_a_jour_urls.py` et `purger_cache.py` (`feature/backdrops-automation`,
      une branche de développement d'une session antérieure) alors que la
      branche réelle du repo est `main` depuis un moment -- sans impact sur
      le workflow automatisé (qui passe toujours `github.ref_name`
      explicitement), mais un run manuel sans `--branche` aurait généré des
      URLs CDN pointant vers la mauvaise branche. Corrigé dans les deux
      scripts (défaut + docstring d'usage).
- [x] Suite complète revérifiée après coup : 182/182 tests verts,
      `ruff`/`mypy`/`lint_config.py`/`valider_collections.py` propres, run
      réel (`--aiometadata` inclus) toujours cohérent (64 générés / 0
      erreur).

### 🔵 Points identifiés, pas encore traités

- [x] ~~`🎌 Animés / FanKai` n'a aucune source résoluble en image~~ --
      résolu, voir la session du 8 septembre 2026 ci-dessus.
- [ ] **`mdblist_recherche.py` et `purger_cache.py` n'ont aucun test**,
      contrairement à tous les autres scripts. Les deux contiennent de la
      logique pure testable sans réseau (construction d'URL de recherche/
      de purge, découpage `chemin_depot`/`chemin_encode`) qui pourrait être
      extraite et couverte avec des appels réseau mockés, sur le modèle des
      tests existants.
- [ ] **Nettoyage mineur** : l'étape "Nettoyer l'ancienne arborescence
      (`collections/` -> `Collections/`)" dans `generer-backdrops.yml` est
      une migration ponctuelle d'une ancienne session, presque certainement
      obsolète aujourd'hui (le dossier en minuscule ne devrait plus jamais
      exister) -- candidate à suppression après confirmation qu'elle ne se
      déclenche plus jamais depuis quelques runs.

---

## ✅ Fait (session du 5 septembre 2026, suite -- outil visuel de style)

- [x] **Outil interactif de réglage du style mosaïque** :
      `outils/reglage-style-mosaique.html`, autonome (aucune dépendance
      externe), aperçu Canvas en direct de la grille de tuiles (largeur,
      hauteur, écart, arrondi des coins, décalage cascade, inclinaison) et
      de la vignette (intensité de l'ombre, flou et couleur de la lueur
      d'accent). Bouton "Copier en JSON" pour exporter les valeurs
      choisies.
- [x] **`INTENSITE_OMBRE` et `RAYON_FLOU_LUEUR_MIN` extraits en
      constantes** dans `scripts/mosaique.py` (auparavant des
      multiplicateurs/valeurs codés en dur dans `appliquer_degrade`) --
      valeurs par défaut strictement inchangées (1.0 et 24, vérifié par la
      suite de tests existante `test_mosaique.py`/`test_mosaique_integration.py`,
      100% verte après coup).
- [x] **`scripts/appliquer_style_mosaique.py`** : applique automatiquement
      dans `mosaique.py` le JSON exporté par l'outil (`--json`/`--json-inline`,
      `--dry-run` disponible). Ne modifie que les clés présentes, signale
      les clés inconnues et les constantes introuvables sans planter. Bug
      corrigé en cours de route : la regex de remplacement collait la
      nouvelle valeur contre un commentaire de fin de ligne existant
      (`340# commentaire`) -- espacement désormais préservé, couvert par
      un test dédié.
- [x] **Déploiement GitHub Pages** de `outils/` :
      `.github/workflows/deployer-outils.yml` (actions officielles
      `configure-pages`/`upload-pages-artifact`/`deploy-pages`), déclenché
      à chaque modification de `outils/`. Une seule étape manuelle requise
      côté utilisateur : Settings → Pages → Source = GitHub Actions, une
      fois pour activer Pages sur le repo. `outils/index.html` ajouté
      comme page d'accueil du dossier (liste les outils disponibles,
      prêt à en accueillir d'autres).
- [x] 7 nouveaux tests, tous verts ; suite complète toujours verte après
      les changements dans `mosaique.py` ; documentation à jour
      (`BACKDROPS_SETUP.md` : nouvelle section *Régler le style
      visuellement* ; ligne correspondante retirée de *Idées pour plus
      tard*).

---

## ✅ Fait (session du 5 septembre 2026, suite -- vérification des "Idées plus lointaines")

- [x] **Intégration des Animés dans l'AIOMetadata puis dans les backdrops**
      -- en réalité déjà en place, contrairement à ce que laissait penser
      la liste "Idées plus lointaines" : le groupe `🎌 Animés` existe dans
      le JSON de collections (9 dossiers, sources MDBList via l'addon
      `aio-metadata`), l'export `Templates/aiometadata-setup.json`
      contient bien tous les catalogues correspondants (Nouveautés,
      Populaires, Top, décennies, Studio Ghibli...), et le workflow
      GitHub Actions (`generer-backdrops.yml`) passe déjà `--aiometadata`
      automatiquement quand ce fichier existe. Vérifié par un run réel
      ciblé (`--groupe Animés --aiometadata ...`) : 9/9 dossiers résolus,
      0 erreur. Item retiré de "Idées plus lointaines" ci-dessous.
- [x] Nettoyage du TODO fantôme "tests pour la détection de branche Git" --
      la note elle-même indiquait que cette fonctionnalité n'existe pas
      dans le code actuel ; supprimé plutôt que traité.
- [x] "Modifier AIOStreams pour les animés" déplacé vers *Explicitement
      écarté* : hors du périmètre technique de ce dépôt (config sur une
      instance AIOStreams hébergée externe, aucun script ici ne la gère).

---

## ✅ Fait (session du 5 septembre 2026, suite -- options "complexes")

- [x] **Config des groupes auto-détectés, persistée** :
      `scripts/synchroniser_config.py` maintient `Templates/groupes-config.json`
      -- ajoute automatiquement une entrée par défaut pour tout groupe vu
      dans le JSON de collections mais absent de `CRITERES_GROUPES`, et
      signale (sans supprimer, sauf `--purger-supprimes`) les groupes
      disparus. `config_collections.appliquer_config_externe()` fusionne ce
      fichier dans `CRITERES_GROUPES`/`GROUPE_SLUGS` au démarrage de
      `generer_backdrops.py` et `mettre_a_jour_urls.py` (option
      `--config-groupes`, sans effet si le fichier n'existe pas -- 100%
      rétro-compatible).
- [x] **Linter de configuration** : `scripts/lint_config.py` détecte les
      incohérences classiques dans `config_collections.py` -- groupe dans
      `CRITERES_GROUPES` sans entrée `GROUPE_SLUGS` (et l'inverse),
      collision de noms de dossiers de sortie, collision de noms de
      fichiers (`NOMS_BACKDROP_PERSONNALISES`), mots présents à la fois
      dans `inclure` et `exclure` d'un même groupe (contradiction),
      entrées `NOMS_BACKDROP_PERSONNALISES` devenues obsolètes (dossier
      renommé/supprimé côté Nuvio). Code de sortie 1 si au moins un
      avertissement (utilisable en CI). Config actuelle du dépôt : aucune
      incohérence détectée.
- [x] **Tableau de bord des backdrops** : `scripts/etat_backdrops.py`,
      vue d'ensemble en lecture seule (généré / manquant / image manuelle
      / ignoré, + fichiers orphelins) pour tous les dossiers ou un groupe
      précis, sans attendre un run complet.
- [x] 20 nouveaux tests (155 -> 175), tous verts ; `ruff`/`mypy` toujours
      au vert (12 fichiers source) ; run réel (`--dry-run` sur le vrai
      JSON) toujours 53 générés / 0 erreur, `valider_collections.py` et
      `lint_config.py` propres -- aucune régression. Documentation à jour
      (`BACKDROPS_SETUP.md` : 3 nouvelles sections ; README resynchronisé).

---

## ✅ Fait (session du 5 septembre 2026, suite -- options "moyennes")

- [x] **Diff entre deux exports Nuvio** : nouveau `scripts/comparer_collections.py`
      -- compare le fichier actuel à la dernière version commitée (Git,
      via `git show <ref>:chemin`) ou à deux fichiers explicites
      (`--ancien`/`--nouveau`), et rapporte précisément les groupes/dossiers
      ajoutés ou supprimés, en réutilisant la même normalisation que le
      pipeline (un simple changement d'emoji n'est pas signalé comme un
      changement). Outil de relecture pur, aucune dépendance du pipeline
      de génération dessus.
- [x] **Config extraite dans un fichier séparé** : tout le contenu de
      l'ancien bandeau `⚙️ ZONE ÉDITABLE` a été déplacé tel quel dans
      **`scripts/config_collections.py`** (module de données pur, aucune
      dépendance vers `generer_backdrops.py` pour éviter tout import
      circulaire). `generer_backdrops.py` l'importe et ré-exporte les noms
      encore utilisés par les tests/`mettre_a_jour_urls.py`
      (`from ... import X as X`, reconnu par `ruff` comme un ré-export
      volontaire). Comportement strictement identique (mêmes 53
      générés/0 erreur sur le vrai JSON).
- [x] **Outil dédié pour les images manuelles** : `scripts/definir_image_manuelle.py`
      ajoute/retire une entrée dans `images-manuelles.json` et, par
      défaut, génère immédiatement le fichier correspondant (URL ou
      fichier local) sans attendre un run complet. La "protection
      anti-écrasement" évoquée dans l'analyse initiale n'a pas nécessité
      de manifeste séparé : elle est déjà native au mécanisme (priorité
      absolue de `images-manuelles.json` à CHAQUE run futur).
- [x] 9 nouveaux tests (146 -> 155), tous verts ; `ruff`/`mypy` toujours au
      vert ; run réel (`--dry-run` sur le vrai JSON) toujours 53 générés /
      0 erreur -- aucune régression. Documentation mise à jour
      (`BACKDROPS_SETUP.md` : nouvelle section *Où éditer la
      configuration*, complément des sections *Images manuelles* et
      *Ajout/suppression* ; README resynchronisé).

---

## ✅ Fait (session du 5 septembre 2026 -- 3 demandes explicites)

- [x] **Ajout/suppression automatique d'une collection Nuvio** :
      `dossier_actif()` traite désormais un groupe absent de
      `CRITERES_GROUPES` comme **actif par défaut** (opt-out) au lieu de
      l'ignorer silencieusement (opt-in) -- un ajout dans Nuvio est pris en
      compte au prochain run sans toucher au script. `mettre_a_jour_urls.py`
      aligné (repli `slugifier` au lieu de `continue` sur un groupe
      inconnu). Message d'avertissement reformulé (`🆕 Nouveau groupe
      détecté...` au lieu de `⚠️ non reconnu`, désormais informatif et non
      bloquant). Nouveau : `detecter_backdrops_orphelins()` +
      `--signaler-orphelins` pour repérer (rapport seul, rien n'est
      supprimé) les images restées sur disque après suppression d'une
      collection/d'un dossier côté Nuvio.
- [x] **Zone éditable clairement indiquée** : bandeau
      `⚙️ ZONE ÉDITABLE -- DÉBUT/FIN` autour de toute la config destinée à
      être modifiée à la main (`CRITERES_GROUPES`, `GROUPE_SLUGS`,
      `NOMS_BACKDROP_PERSONNALISES`, `GENRE_TMDB_IDS`, `NETWORK_TMDB_IDS`...),
      séparée explicitement de la logique du pipeline en dessous.
- [x] **Images manuelles sans génération de backdrop** : nouveau fichier
      optionnel `Templates/images-manuelles.json`
      (`{"Titre du dossier": "url_ou_chemin"}`), chargé via
      `charger_images_manuelles()` et vérifié en priorité ABSOLUE dans
      `traiter_dossier()` -- court-circuite toute résolution
      TMDB/Fanart/MDBList, fonctionne même sur un groupe désactivé
      (Franchises/Sports). Nouveau flag CLI `--images-manuelles`. Code de
      redimensionnement/sauvegarde factorisé (`_redimensionner_et_sauver`)
      entre le téléchargement (`telecharger_et_traiter`) et le nouveau cas
      fichier local (`traiter_image_locale`).
- [x] 7 nouveaux tests (139 -> 146), tous verts ; `ruff`/`mypy` toujours au
      vert ; run réel (`--dry-run` sur le vrai JSON) toujours 53 générés /
      0 erreur -- aucune régression.
- [x] Documentation : nouvelles sections *Images manuelles* et
      *Ajout/suppression d'une collection dans Nuvio* dans
      `BACKDROPS_SETUP.md` (+ sommaire, tableau d'options CLI, section
      Dépannage et Résilience aux renommages mises à jour) ; README
      resynchronisé (nombre de tests, section *Usage courant*).

---

## ✅ Fait (session du 4 septembre 2026, suite -- catalogues France recréés)

- [x] Utilisateur a recréé les catalogues `top_france`/`populaires_france`
      côté AIOMetadata (mêmes `catalogId`, désormais avec de vrais filtres
      `with_original_language=fr` + `watch_region=FR` dans l'export)
- [x] `Templates/aiometadata-setup.json` et
      `Templates/Nuvio-Collections-Dwade58200.json` remplacés par les
      exports fournis (2026-09-04) -- groupe Sports passé de 7 à 9 dossiers
      (Rugby, Autres Sports ; groupe désactivé pour les backdrops, sans
      impact sur la couverture)
- [x] **Repli "france" retiré** de `generer_backdrops.py` (devenu inutile
      -- les 4 sources du dossier "Français" se résolvent maintenant
      directement via l'export AIOMetadata, avec les vrais filtres TMDB) ;
      la correction du bug `media_type` (`"Film"`/`"Série"` non normalisé)
      est conservée, bug indépendant qui touche d'autres dossiers
- [x] Revalidé : 64/64 dossiers ciblés résolus (0 erreur), `ruff`/`mypy`/
      `pytest` (139 tests) toujours au vert

---



- [x] Audit complet du dépôt (structure, CI, schéma, exécution réelle des
      tests/lint/type-check/dry-run) demandé par l'utilisateur
- [x] **3 erreurs mypy corrigées** (`list` invariant déclaré trop strict
      sur `_resoudre_liste_candidats` et `candidats` -- `Sequence` +
      élargissement à `str | None`) ; `mypy` retiré de `continue-on-error`
      dans `tests.yml` (devient bloquant comme `ruff`)
- [x] `LICENSE` ajoutée (MIT) -- couvre le code, pas les fichiers de
      configuration personnelle sous `Templates/`
- [x] README resynchronisé : nombre de tests (120 -> 139), groupe
      "🎌 Animés" (9 dossiers) ajouté au tableau des collections
      (absent), "Découvrir" corrigé (6 -> 7)
- [x] Dossier "Découvrir > Français" ajouté aux dossiers ciblés pour la
      génération de backdrop (`CRITERES_GROUPES[GROUPE_DECOUVRIR].inclure`)
- [x] **Bug corrigé** : `media_type` pour les sources `provider=addon` se
      basait sur `source.get("type") == "movie"` (comparaison stricte,
      anglais minuscule) -- le dossier "Français" utilise `"Film"`/`"Série"`
      (français, capitalisé), donc un film y était traité comme une série
      dans les replis de résolution. Même bug potentiel sur ~40 autres
      sources (`Genres`, `Streaming`, `Animés`, `Franchises`) dès qu'elles
      tombent sur un repli au lieu de l'export AIOMetadata. Corrigé par
      normalisation (`normaliser(...) in ("movie", "film")`)
- [x] Repli dédié ajouté pour les catalogId `tmdb.discover.*france*` non
      présents dans l'export AIOMetadata actuel (`top_france`,
      `populaires_france`) : filtre TMDB `with_original_language=fr`
      plutôt qu'un repli générique "popularité globale" qui aurait produit
      un visuel quasi identique à "Populaire"/"Top"

---



- [x] `.github/workflows/tests.yml` créé, déclenché sur `push` (toutes
      branches) et `pull_request` : `pip install -r requirements-dev.txt`,
      `ruff check`, `mypy` (informatif), `pytest tests/ -v`
- [x] `requirements.txt` créé (`requests` + `Pillow` seulement, ce dont le
      pipeline a besoin en prod) ; `requirements-dev.txt` réduit à
      `-r requirements.txt` + `pytest`/`ruff`/`mypy`
- [x] `PyYAML` retiré de `requirements-dev.txt` (toujours inutilisé)
- [x] `pyproject.toml` ajouté (config `ruff`/`mypy`/`pytest`)
- [x] `Iterable` retiré de l'import `typing` (toujours inutilisé)
- [x] `import os` déplacé en haut de `generer_backdrops.py`
- [x] `.gitignore` ajouté
- [x] Tests ajoutés pour `meilleur_backdrop_tmdb_langue` et
      `charger_collections` (fonctions pures jusque-là non testées
      directement)
- [x] **Bug corrigé** : `charger_catalogues_aiometadata()` lisait
      `catalogs` à la racine du JSON alors que le vrai export (v2.15.0)
      les range sous `config.catalogs` -- l'index était silencieusement
      vide sur un vrai export. Corrigé avec repli sur l'ancien format.
- [x] Les catalogues `source: "mdblist"` de l'export AIOMetadata (ajoutés
      via l'addon, ex: "Sitcom") sont maintenant résolus via leur URL
      publique exportée, au lieu de tomber en "catalogId non résolu"
- [x] Trakt entièrement retiré (`ClientTrakt`, `trakt_auth.py`, CLI, CI,
      secrets, docs) -- voir section "Explicitement écarté" plus bas
- [x] Nettoyage `ruff` complet (35 erreurs -- imports non triés,
      annotations entre guillemets redondantes, variable ambiguë,
      `assert False`, etc.) et `mypy` complet (13 erreurs -- constantes
      `Image.LANCZOS`/`BOX`/`BICUBIC`/`BILINEAR` remplacées par
      `Image.Resampling.*`, types `str | None` corrigés)
- [x] Pool de connexions HTTP agrandi (`HTTPAdapter(pool_maxsize=64)`) --
      le mode mosaïque + `--parallelisme` dépassait le pool par défaut de
      `requests` (10), d'où des warnings `Connection pool is full` en
      boucle dans les logs d'exécution réelle
- [x] "Budget" artificiel d'appels TMDB `/images` (`--limite-appels-tmdb-images`,
      300 par défaut) entièrement retiré -- ce n'était pas une vraie
      limite de l'API TMDB (qui n'a pas de quota fixe par run), juste une
      protection auto-imposée par une session précédente
- [x] Validation du JSON de collections par un schéma JSON (Draft-07),
      en CI (`scripts/valider_collections.py` + `schema/nuvio-collections.schema.json`)
      -- attrape une erreur de structure avant qu'elle ne casse l'import
      Nuvio. La branche `mdblist` du schéma a été corrigée au passage :
      elle exigeait `catalogId` (qui n'existe que pour `provider: "addon"`)
      au lieu de `mdblistUrl`/`mdblistId`/`mdblistUser`+`mdblistSlug`
      (le format réellement lu par le code pour ce provider) -- aurait
      fait échouer la CI sur tout ajout manuel suivant la doc
      `BACKDROPS_SETUP.md`

---

## 🔵 Reste à faire

- [ ] Couvrir `mdblist_recherche.py` et `purger_cache.py` par des tests
      (seuls scripts du dossier sans aucun test actuellement).
- [ ] Vérifier si l'étape de migration `collections/` -> `Collections/`
      dans `generer-backdrops.yml` est encore nécessaire, et la retirer
      si elle ne s'est plus déclenchée depuis plusieurs runs.
- [ ] Une fois le secret `CATALOGUES_PERSONNALISES` configuré côté
      GitHub : vérifier sur un vrai run (pas juste `--dry-run`) que
      FanKai génère effectivement sa mosaïque en conditions réelles.

---

## ⚪ Idées plus lointaines (pas de demande explicite pour l'instant)

- Génération de variantes `.webp` en plus du `.jpg`.


## ❌ Explicitement écarté (ne pas reproposer)

- **Trakt** — retiré entièrement du projet (voir `BACKDROPS_SETUP.md`) :
  créer une application Trakt nécessite désormais un abonnement VIP,
  indisponible pour ce compte. MDBList couvre le même besoin sans ce
  problème.
- **Recommandations MDBList personnalisées** (`mdblist.recommended.*`,
  anciennement `trakt.recommendations.*`) — pas de solution possible :
  liste calculée à partir de l'historique de visionnage du compte lié,
  sans URL publique fixe à interroger.
- **Modifier AIOStreams pour intégrer les animés** (regex/filtres, style
  du texte du lien) — hors du périmètre technique de ce dépôt : AIOStreams
  est configuré sur une instance hébergée externe, aucun script ici ne la
  gère. À traiter depuis la config AIOStreams elle-même, pas depuis ce
  dépôt.


