# Améliorations potentielles — nuvio-configuration

Liste de travail, par ordre de priorité décroissant. Rien ici n'est cassé
dans le pipeline actuel : ce sont des pistes pour se rapprocher d'un dépôt
de qualité professionnelle, pas des correctifs urgents.

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

- [ ] Écrire des tests pour la détection automatique de la branche Git
      courante et la création de session HTTP dans les scripts annexes,
      si/quand ces fonctions sont ajoutées (pas encore présentes dans le
      code actuel malgré une mention dans une version antérieure de cette
      liste)

---

## ⚪ Idées plus lointaines (pas de demande explicite pour l'instant)

- Intégrer les Animés dans le Aiometadata puis dans les backdrops.
- Modifié le AIOStream pour intégrer les animés (avec regex et/ou filtres propres) et modifier le le style du texte du lien. 
- Faciliter les modifications du style des Backdrop en créant un modificateur avec un visuel.


## ❌ Explicitement écarté (ne pas reproposer)

- **Trakt** — retiré entièrement du projet (voir `BACKDROPS_SETUP.md`) :
  créer une application Trakt nécessite désormais un abonnement VIP,
  indisponible pour ce compte. MDBList couvre le même besoin sans ce
  problème.
- **Recommandations MDBList personnalisées** (`mdblist.recommended.*`,
  anciennement `trakt.recommendations.*`) — pas de solution possible :
  liste calculée à partir de l'historique de visionnage du compte lié,
  sans URL publique fixe à interroger.

