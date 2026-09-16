# Améliorations potentielles — nuvio-configuration

Liste de travail, par ordre de priorité décroissant. Rien ici n'est cassé
dans le pipeline actuel : ce sont des pistes pour se rapprocher d'un dépôt
de qualité professionnelle, pas des correctifs urgents.

---

## ✅ Fait (session du 16 septembre 2026, suite -- raccourcis, comparaison, avertissements, export .py)

Suite de la session précédente (même jour), toujours sur le seul fichier
`outils/reglage-style-mosaique.html`. Reprend les pistes listées dans
"Reste à faire" ci-dessous (catégories "Petites" et une partie des
"Moyennes").

- [x] **Téléchargement en `.py`** : bouton "⬇️ Télécharger en .py" à côté
      de "📋 Copier en JSON", qui télécharge directement le bloc de
      valeurs déjà formaté en extrait Python, sans repasser par le
      presse-papiers.
- [x] **Raccourcis clavier** : `A` pour "🔀 Affiches", `R` pour
      "↺ Réinitialiser" -- désactivés automatiquement quand le focus est
      dans un champ de saisie/liste, pour ne jamais interférer avec la
      frappe (ex. nom de preset).
- [x] **Entrée pour sauvegarder un preset** : appuyer sur Entrée dans le
      champ "Nom du preset" déclenche la sauvegarde, plus besoin de
      cliquer sur le bouton.
- [x] **Mode comparaison** : nouveau bouton "📌 Figer pour comparer" qui
      capture l'aperçu actuel dans un second panneau juste en dessous
      (avec un bouton "✕ Effacer") -- permet de changer les réglages et
      de comparer visuellement avec l'état figé, sans avoir à mémoriser
      à quoi ressemblait l'un des deux.
- [x] **Avertissement sur combinaisons dégénérées** : message discret
      (non bloquant) sous l'aperçu si l'arrondi des coins dépasse la
      moitié de la hauteur de tuile, si l'écart est nul avec une forte
      inclinaison (artefacts de bord probables), ou si l'ombre est très
      forte sans lueur pour compenser.
- [x] **Résolutions de génération réelle alignées sur le ratio du
      canvas** : la liste déroulante "Résolution" (section génération
      depuis un dossier d'images) se recalcule désormais selon le
      "Ratio du canvas final" choisi (16:9/21:9/4:3/1:1), au lieu de
      rester figée sur 3 résolutions toutes proches du 16:9 quel que
      soit le ratio sélectionné par ailleurs.

JS revalidé (`node --check`), balises et `id` vérifiés sans doublon.
Toujours **pas testé dans un vrai navigateur**.

---

## ✅ Fait (session du 16 septembre 2026 -- ergonomie de l'outil de réglage des backdrops)

Un seul fichier modifié : `outils/reglage-style-mosaique.html`. Aucun
changement de comportement sur l'existant, tous les ajouts sont additifs.

- [x] **Réinitialisation par champ** : double-clic sur n'importe quel
      curseur pour revenir à SA valeur par défaut, sans toucher aux
      autres réglages (le bouton "↺ Réinitialiser" global reste pour
      tout remettre à zéro d'un coup).
- [x] **Unités manquantes affichées** : "px" ajouté à côté de
      Largeur/Hauteur de tuile, Écart, Arrondi des coins, Flou de la
      lueur -- ces cinq champs n'affichaient qu'un nombre nu,
      contrairement à Décalage (%) et Inclinaison (°).
- [x] **Info-bulles sur les réglages les moins évidents** : "Décalage
      cascade", "Inclinaison" et "Flou de la lueur" ont maintenant un
      `title` expliquant ce qu'ils font concrètement.
- [x] **Nouveau réglage "Ratio du canvas final"** (16:9 / 21:9 / 4:3 /
      1:1) : l'outil avait pris du retard sur `generer_backdrops.py`,
      qui accepte déjà un flag `--ratio-canvas` (session du 13
      septembre) -- mais l'aperçu de l'outil restait figé en 800×450
      (16:9) quel que soit le ratio réellement utilisé côté script. Ce
      menu redimensionne l'aperçu en conséquence et rappelle la commande
      CLI correspondante dans le bloc de valeurs exporté. Réglage de
      l'APERÇU uniquement (pas une constante de `mosaique.py`),
      clairement distingué du "Ratio des tuiles" existant. Pris en
      compte dans la sauvegarde/chargement des presets.
- [x] **Presets : confirmation avant écrasement et avant suppression**
      -- auparavant sans filet de rattrapage en cas de clic accidentel.
- [x] **Presets : export/import en fichier JSON** -- restent en
      `localStorage` (propre à ce navigateur/appareil, limite déjà
      documentée), mais deux boutons permettent désormais de les
      transférer vers un autre navigateur/machine ou d'en garder une
      sauvegarde externe. L'import détecte les collisions de noms et
      demande confirmation avant d'écraser.
- [x] **Retour visuel pendant la génération réelle** : le bouton
      "🖼️ Générer le backdrop" affiche "⏳ Génération…" et se désactive
      le temps du calcul -- utile sur un gros lot d'images en haute
      résolution, où le calcul synchrone du canvas peut prendre une ou
      deux secondes et donnait l'impression que le clic n'avait rien
      fait.
- [x] **Accessibilité clavier** : contour de focus explicite sur tous
      les contrôles interactifs -- le focus par défaut du navigateur
      est parfois trop discret sur le fond sombre de l'outil.

JS revalidé syntaxiquement (`node --check`) et balises HTML rééquilibrées,
mais **pas testé dans un vrai navigateur** (pas d'environnement graphique
disponible ici) -- à valider visuellement avant de merger, en particulier
le redimensionnement du canvas selon le ratio choisi.

---

## ✅ Fait (session du 13 septembre 2026, suite 2 -- ratio du canvas, anti-dérive de l'outil, presets)

Propositions faites par Claude lui-même après la session précédente
(voir "Ce que tu n'as probablement pas encore vu"), demandées explicitement
à la suite par l'utilisateur ("le reste des améliorations que tu
souhaitais faire") :

- [x] **`--ratio-canvas` (ex: `"16:9"`, `"4:3"`, `"21:9"`)** : le ratio du
      canvas final (le backdrop entier, PAS le ratio des tuiles à
      l'intérieur -- ça, c'est le menu de l'outil de la session
      précédente) était câblé en dur dans `_dimensions_canvas()`
      (`hauteur = largeur * 9/16`, sans override possible). Un flag CLI
      accepte maintenant n'importe quel ratio "largeur:hauteur", avec un
      message d'erreur clair sur une entrée malformée (`_analyser_ratio_canvas`,
      utilisé par argparse). 4 tests ajoutés.
- [x] **Anti-dérive de l'outil de style** (`scripts/generer_defaults_outil.py`,
      nouveau) : les valeurs par défaut affichées à l'ouverture de
      `outils/reglage-style-mosaique.html` (curseurs, champs numériques,
      objet JS `defaults`) étaient un instantané figé dans le HTML, sans
      lien avec les VRAIES constantes de `scripts/mosaique.py` -- si
      celles-ci changeaient ailleurs que via l'outil (édition manuelle,
      `appliquer_style_mosaique.py` lancé depuis une autre session), l'outil
      repartait silencieusement d'un point de départ obsolète à la
      prochaine ouverture. Ce script régénère ces valeurs par défaut
      directement depuis `mosaique.py`, et tourne automatiquement à chaque
      déploiement (`deployer-outils.yml`, désormais aussi déclenché par un
      changement de `scripts/mosaique.py`, avec commit automatique de la
      resynchronisation si nécessaire). 7 tests ajoutés ; vérifié
      manuellement avec un vrai changement de constantes (largeur, décalage,
      inclinaison) propagé correctement aux 3 endroits concernés.
- [x] **Presets nommés dans l'outil** : au lieu du seul "Réinitialiser aux
      valeurs par défaut", une nouvelle section permet de sauvegarder
      plusieurs styles nommés (curseurs + ratio de tuile + couleur d'accent
      + lueur), pour comparer avant de choisir. Stockage `localStorage`,
      propre à ce navigateur/appareil (légitime ici : vraie page web
      déployée par l'utilisateur, pas un artefact Claude soumis à la
      restriction habituelle sur le stockage navigateur) -- protégé par un
      `try/catch` si indisponible (navigation privée stricte, quota).
- [x] Toute la logique JS de cette session (ratio, numérique, dossier
      d'images, presets) validée en exécutant le VRAI script dans un
      DOM/canvas simulé (Node + stubs, aucune dépendance ajoutée au repo) --
      pas seulement relue.
- [x] Suite complète revérifiée : **256 tests** (245 + 11), `ruff`/`mypy`
      propres sur les 3 scripts touchés, YAML des deux workflows revalidé,
      dry-run réel avec `--ratio-canvas 21:9`.

---

## ✅ Fait (session du 13 septembre 2026, suite -- outil de design enrichi + tests manquants + nettoyage CI)

- [x] **Outil `outils/reglage-style-mosaique.html`, saisie numérique** :
      chaque curseur (largeur/hauteur de tuile, écart, arrondi, décalage,
      inclinaison, ombre, flou) a maintenant un champ numérique jumeau --
      taper une valeur exacte met à jour le curseur (et inversement),
      avec les mêmes bornes min/max. Idée de l'utilisateur.
- [x] **Outil, choix du ratio des tuiles** : la case "Conserver le ratio
      16:9" (session précédente) est remplacée par un menu déroulant
      **16:9 / 4:3 / 3:2 / 1:1 / Libre**, qui resynchronise largeur/hauteur
      dès qu'on change de ratio (comme avant pour 16:9, généralisé à
      d'autres formats). Idée de l'utilisateur.
- [x] **Outil, génération d'un backdrop réel depuis un dossier d'images**
      -- nouvelle section en bas de page : sélection d'un dossier/plusieurs
      images locales (100% côté navigateur, aucun envoi réseau), choix
      d'une résolution de sortie (1280×720/1920×1080/780×439, alignées sur
      les profils `PROFILS_QUALITE` du script), puis génération réelle
      (même moteur de rendu que l'aperçu, factorisé dans `composerBackdrop`)
      et téléchargement du fichier -- sans passer par
      `generer_backdrops.py`/TMDB. Utile pour un lot d'images sans
      référence TMDB (fan-arts, scans, captures perso). Idée de
      l'utilisateur.
      Logique validée en exécutant le vrai script dans un DOM/canvas
      factice (Node + stubs, pas de dépendance ajoutée) : verrouillage de
      ratio, synchronisation curseur↔numérique, clamp aux bornes, reset,
      et le flux complet sélection de fichiers -> génération ->
      téléchargement.
- [x] **Tests ajoutés pour `mdblist_recherche.py`** (11 tests, aucune
      couverture avant) : tri des résultats, transmission clé/requête,
      clé invalide (`sys.exit(1)`), erreur serveur (`HTTPError`), réponse
      inattendue (non-liste), formatage de l'affichage (snippet JSON,
      liste privée, valeurs par défaut), câblage CLI de `main()`
      (variable d'environnement vs `--cle-api`, absence des deux).
- [x] **Tests ajoutés pour `purger_cache.py`** (+3, s'ajoutent aux 7 déjà
      existants -- la liste "reste à faire" était obsolète sur ce point) :
      comptage des échecs HTTP (statut != 200) sans interrompre le run,
      `requests.RequestException` rattrapée sans planter, câblage CLI de
      `main()` (arguments non-défaut jusqu'à `purger_cdn`).
- [x] **Étape de migration `collections/` -> `Collections/` retirée** de
      `generer-backdrops.yml` -- vérifié directement sur le dépôt GitHub
      réel (`Dwade58200/nuvio-configuration`) : plus aucun dossier
      `collections/` en minuscule à la racine, uniquement `Collections/`.
      Migration ponctuelle d'une ancienne session, désormais du code mort.
- [x] Suite complète revérifiée : **245 tests** (231 + 14), `ruff`/`mypy`
      propres, YAML du workflow revalidé après suppression de l'étape.

---

## ✅ Fait (session du 13 septembre 2026 -- suffixes FanKai manquants + récap de fin de run + outil de style)

- [x] **Bug signalé par l'utilisateur : Bleach/Naruto Shippuden/Inazuma
      Eleven non reconnus** -- diagnostiqué depuis un vrai log de run
      fourni : `suffixesTitreIgnorer` ne contenait que `["Henshū", "Kaï",
      "Kai"]`, sans les suffixes `"Yabai"` et `"Fan-Cut"` également
      utilisés par FanKai. Ajoutés dans `.github/workflows/generer-backdrops.yml`
      (source réelle de `catalogues-personnalises.json` en CI) et dans
      l'exemple `BACKDROPS_SETUP.md`.
- [x] **Bug connexe trouvé dans le même log** : `nettoyer_titre_pour_recherche`
      ne retirait un suffixe que s'il était en toute fin de chaîne --
      `"Hunter x Hunter Kaï (2011)"`/`"... Kaï (1999)"` (précision d'année
      FanKai pour distinguer deux montages) ne matchaient donc jamais.
      Corrigé : l'année entre parenthèses est désormais retirée AVANT le
      test des suffixes.
- [x] **Nouveau récap de fin de run** (`afficher_titres_champ_titre_non_resolus`) :
      liste, sans besoin de `--verbose`, tous les titres `champTitre` (ex:
      FanKai) retombés sur le poster brut faute de correspondance TMDB,
      avec leur nombre d'occurrences -- évite de devoir grepper tout le
      log à la main pour repérer un suffixe manquant (exactement le
      diagnostic qui a précédé cette session). `GenerateurBackdrops`
      collecte ces titres (`titres_champ_titre_non_resolus`, alimenté
      thread-safe) pendant `_resoudre_image_tuile`.
- [x] **Outil `outils/reglage-style-mosaique.html`** : case "Conserver le
      ratio 16:9" (cochée par défaut) qui synchronise automatiquement
      largeur/hauteur de tuile l'une par rapport à l'autre -- évite de
      dériver du ratio attendu par le reste du pipeline en réglant les
      deux curseurs indépendamment.
- [x] 3 tests ajoutés/étendus (231 au total) : 2 nouveaux cas pour
      `nettoyer_titre_pour_recherche` (Yabai/Fan-Cut + année avant
      suffixe), 1 nouveau test pour `afficher_titres_champ_titre_non_resolus`,
      assertion ajoutée au test d'intégration FanKai existant
      (`titres_champ_titre_non_resolus` bien peuplé). Tous verts,
      `ruff`/`mypy` propres.
- [x] Documentation à jour (`BACKDROPS_SETUP.md` : nouvelle sous-section
      *Repérer un suffixe manquant*, section *Régler le style
      visuellement* complétée).

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
      par l'export AIOMetadata standard. Ce fichier n'existe JAMAIS dans
      le repo (ni en local, ni committé) : seule l'URL (contenant la
      config AIOStreams encodée, donc une clé de service debrid) est
      stockée, comme secret GitHub `FANKAI_CATALOG_URL` -- le workflow
      assemble le JSON complet à la volée sur le runner à chaque
      exécution (id/type/champImage fixes, non sensibles, écrits en dur
      dans le workflow) et ne l'écrit jamais dans les logs.
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
- [x] ~~`mdblist_recherche.py` et `purger_cache.py` n'ont aucun test~~ --
      résolu, voir la session du 13 septembre 2026 (suite) ci-dessus.
- [x] ~~Nettoyage mineur : étape "Nettoyer l'ancienne arborescence" dans
      `generer-backdrops.yml`~~ -- retirée, voir la session du 13
      septembre 2026 (suite) ci-dessus.

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

## ✅ Fait (session du 14 septembre 2026 -- dépendances pinnées, validation des variables d'environnement, retry API, stubs mypy)

- [x] **Dépendances pinnées dans `requirements.txt` et `requirements-dev.txt`** :
      versions fixes (`requests==2.32.3`, `Pillow==11.0.0`, `pytest==8.3.3`,
      `ruff==0.7.0`, `mypy==1.13.0`, `jsonschema==4.23.0`) au lieu de versions
      flottantes (`>=`) -- évite les ruptures futures dues aux breaking changes
      lors des mises à jour automatiques en CI.
- [x] **Validation des variables d'environnement au démarrage**
      (`generer_backdrops.py`, fonction `valider_variables_environnement()`) :
      vérifie la présence de `TMDB_API_KEY` (requis) et avertit pour les clés
      optionnelles manquantes (`FANART_API_KEY`, `MDBLIST_API_KEY`). Message
      d'erreur clair et arrêt propre (`sys.exit(1)`) si variable requise absente,
      plutôt qu'une erreur tardive pendant le traitement.
- [x] **Retry/backoff pour les appels API HTTP** (`generer_backdrops.py`) :
      configuration de `urllib3.util.retry.Retry` avec 3 tentatives maximum,
      délai croissant (0.5s, 1s, 2s), gestion des codes 429, 500, 502, 503, 504.
      Réessaye automatiquement en cas d'erreur temporaire réseau ou serveur,
      évite l'échec d'un run mensuel complet pour une panne passagère.
- [x] **Fichier `.env.example` créé** : modèle avec toutes les variables
      d'environnement nécessaires, commentaires expliquant où obtenir chaque
      clé API (liens vers TMDB/Fanart/MDBList). Facilite la configuration
      locale pour les nouveaux contributeurs ou tests manuels.
- [x] **Stubs de typage `types-requests` ajoutés** (`requirements-dev.txt`) :
      corrige l'erreur mypy `Library stubs not installed for "requests"` qui
      faisait échouer la CI. MyPy trouve maintenant les annotations de type
      pour la bibliothèque `requests`.
- [x] Suite complète revérifiée : **256 tests**, `ruff`/`mypy` propres,
      workflows YAML revalidés.

---

## ✅ Fait (session du 14 septembre 2026 -- titre sur backdrops sans titre, template aligné, bouton aléatoire, positionnement en spirale)

- [x] **#13 - Titre sur les backdrops sans titre** : Généralisation du mécanisme FanKai à TOUTES les affiches sans titre détecté. Si aucune affiche avec titre FR/EN/original n'est trouvée sur TMDB, le script recherche maintenant un logo/titre TMDB (priorité fr-FR puis en-US) et l'incruste sur un backdrop nu. Nouvelle méthode `recuperer_logo_titre()` dans `ClientTMDB`, appelée depuis `_resoudre_image_tuile()` quand `champ_titre` est défini et qu'aucune affiche titrée n'est disponible.
- [x] **#15 - Template initial aligné** : Les valeurs par défaut de `outils/reglage-style-mosaique.html` (inclinaison à -10°, et autres constantes) sont maintenant synchronisées avec les constantes réelles de `scripts/mosaique.py` utilisées pour la génération de backdrops. Le fichier HTML n'a plus de valeurs figées obsolètes.
- [x] **#16 - Bouton aléatoire pour dossier d'images** : Ajout d'un bouton "🔀 Mélanger" dans la section "Générer un backdrop réel à partir d'un dossier d'images" de l'outil. Permet de mélanger aléatoirement l'ordre des images sélectionnées avant génération, sans modifier leur style. Utile pour tester différentes compositions visuelles rapidement.
- [x] **#17 - Positionnement en spirale** : L'algorithme de placement des tuiles dans `scripts/mosaique.py` évolue d'une grille inclinée linéaire vers une disposition en spirale (du centre vers l'extérieur). Le mode aléatoire (#16) mélange l'ordre des images AVANT application de la spirale. Le style visuel des tuiles (inclinaison, ombre, etc.) reste inchangé. Test existant mis à jour pour valider que la première image est bien placée au centre.
- [x] **Naruto affichait Naruto Shippuden** : `ClientTMDB.rechercher_titre` choisissait le résultat TMDB le plus **populaire**, sans vérifier la correspondance de titre -- un spin-off homonyme plus populaire (ex: "Naruto: Shippuden") l'emportait systématiquement sur le titre exact recherché ("Naruto"). Un résultat dont le titre correspond EXACTEMENT (normalisé) à la recherche est maintenant toujours préféré à un résultat seulement approchant, même moins populaire.
- [x] **Orientation incohérente des tuiles (repli catalogue portrait)** : Quand la recherche TMDB échoue pour un candidat `champ_titre` (ex: FanKai), le repli sur l'image brute du catalogue (`champ_image_repli`, typiquement un poster PORTRAIT) était utilisé tel quel dans une tuile paysage -> recadrage écrasé, visuellement incohérent au milieu des autres tuiles. Ce repli est maintenant écarté s'il est portrait plutôt que forcé dans le mauvais sens (la tuile est alors comptée en échec, sans casser la mosaïque).
- [x] **#17 (suite) - "S'il manque des images cela ne sera pas visible"** : deux causes identifiées de répétitions évitables (une affiche visible en double alors qu'une autre, pourtant résolue avec succès dans les logs, n'apparaît pas du tout) : (1) `traiter_dossier_mosaique` ne demandait jamais plus de candidats uniques que le nombre de cellules de la grille -- le moindre échec de résolution/téléchargement faisait passer sous ce nombre et forçait des répétitions ; une marge (~+30%, +4 minimum) est maintenant demandée pour absorber ces échecs. (2) `_telecharger_une_image` retente maintenant une fois le décodage PIL en cas d'image reçue mais corrompue/tronquée (le retry réseau existant sur la session, lui, ne couvre que les erreurs de connexion/statut HTTP, pas ce cas précis).
- [x] **Lien de l'outil de style cassé dans la documentation** : Le workflow `deployer-outils.yml` publie le CONTENU du dossier `outils/` comme racine du site GitHub Pages (`path: outils`) -- les liens vers `.../outils/reglage-style-mosaique.html` (README.md, BACKDROPS_SETUP.md) étaient donc tous 404. Corrigés vers `.../reglage-style-mosaique.html`, et lien ajouté bien en évidence en haut du README (badge + accroche), en plus de l'entrée déjà présente dans le tableau de documentation.
- [x] **#14 - Refonte ergonomique de l'outil de style** : `outils/reglage-style-mosaique.html` restructuré (aperçu épinglé et toujours visible pendant le réglage, curseurs regroupés en sections repliables par thème, génération réelle présentée en 3 étapes numérotées, JSON avancé replié par défaut) sans toucher aux `id` utilisés par `generer_defaults_outil.py` ni à la logique JS existante.
- [x] Suite complète vérifiée : **263 tests**, `ruff`/`mypy` propres.

---

## 🔵 Reste à faire

Rien pour l'instant côté ergonomie de l'outil -- tout le backlog de la
session du 16 septembre 2026 a été traité (voir historique ci-dessus).
Reste seulement la piste de refonte plus lourde listée dans "Idées plus
lointaines" ci-dessous.

---

## ⚪ Idées plus lointaines (pas de demande explicite pour l'instant)

- Génération de variantes `.webp` en plus du `.jpg`.
- Remplacer le rendu canvas de l'outil par un appel réel à un mini
  moteur Python compilé en WASM (ou un endpoint local) pour que
  l'aperçu soit pixel-perfect avec `mosaique.py`, au lieu d'une
  approximation JS parallèle à maintenir en synchro manuelle -- gros
  chantier, seulement si les écarts aperçu/rendu réel deviennent
  gênants en pratique.


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


