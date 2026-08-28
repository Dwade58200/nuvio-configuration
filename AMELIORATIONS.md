# Améliorations potentielles — nuvio-configuration

Liste de travail, par ordre de priorité décroissant. Rien ici n'est cassé
dans le pipeline actuel : ce sont des pistes pour se rapprocher d'un dépôt
de qualité professionnelle, pas des correctifs urgents.

---

## ✅ Fait (session du 27 août 2026)

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

