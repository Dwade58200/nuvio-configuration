# Améliorations potentielles — nuvio-configuration

Liste de travail, par ordre de priorité décroissant. Rien ici n'est cassé
dans le pipeline actuel : ce sont des pistes pour se rapprocher d'un dépôt
de qualité professionnelle, pas des correctifs urgents.

---

## 🔴 Priorité 1 — sécuriser ce qui existe déjà

### Aucune CI n'exécute les tests automatiquement
104 tests existent et sont de bonne qualité, mais rien ne les fait tourner
avant qu'un changement parte en prod. Un commit qui casse un test peut
directement écraser de vrais backdrops sans que personne ne le sache avant
le prochain lancement réel.

- [ ] Créer `.github/workflows/tests.yml`, déclenché sur `push` et
      `pull_request` (séparé du workflow mensuel de génération)
- [ ] Étapes : `pip install -r requirements-dev.txt` puis `pytest tests/ -v`
- [ ] Ajouter aussi un `python3 scripts/generer_backdrops.py --dry-run`
      dans ce workflow, pour vérifier que le pipeline complet s'importe et
      s'exécute sans erreur (au-delà des tests unitaires)

---

## 🟡 Priorité 2 — hygiène des dépendances

### Les dépendances CI et les dépendances déclarées peuvent diverger
Le workflow de génération installe `pillow requests` écrit en dur,
séparément de `requirements-dev.txt`. Rien ne signale si les deux
divergent un jour.

- [ ] Créer `requirements.txt` (juste `requests` + `Pillow`, ce dont le
      pipeline a besoin en prod)
- [ ] Garder `requirements-dev.txt` pour `pytest` en plus (ex: via
      `-r requirements.txt` en première ligne, pour ne pas dupliquer)
- [ ] Faire pointer le workflow vers `pip install -r requirements.txt`
      au lieu de la liste écrite en dur

### Dépendance inutilisée
- [ ] Retirer `PyYAML>=6.0` de `requirements-dev.txt` — aucun `import yaml`
      nulle part dans `scripts/` ou `tests/`

---

## 🟢 Priorité 3 — qualité de code automatisée

Le code a déjà une bonne discipline de typage (`from __future__ import
annotations`, type hints quasi partout) — ajouter les outils qui
vérifient ça automatiquement serait presque gratuit.

- [ ] Ajouter un `ruff.toml` (ou `pyproject.toml`) minimal, avec une
      config par défaut
- [ ] Optionnel : ajouter `mypy`
- [ ] Faire tourner l'un ou l'autre (voire les deux) dans le même
      `tests.yml` proposé en priorité 1

---

## 🔵 Priorité 4 — petits résidus de code

Rien de cassé, juste des restes accumulés au fil des sessions.

- [ ] Retirer `Iterable` de l'import `typing` en haut de
      `generer_backdrops.py` (jamais utilisé)
- [ ] Déplacer `import os` (actuellement fait localement dans `main()`)
      vers les imports en haut du fichier, par cohérence avec le reste
- [ ] Écrire quelques tests pour `detecter_branche_courante()` et
      `creer_session_http()` (ajoutées récemment, jamais testées)
- [ ] Ajouter un `.gitignore` (aucun trouvé actuellement — évite qu'un
      `__pycache__/` ou un fichier local de test finisse commité par
      accident)

---

## ⚪ Idées plus lointaines (pas de demande explicite pour l'instant)

- Étendre l'automatisation aux **logos** : TMDB `/images` renvoie déjà les
  logos dans la même réponse mise en cache que les backdrops — quasi
  gratuit à ajouter au pipeline existant
- Génération de variantes `.webp` en plus du `.jpg`
- Activer Franchises/Sports si un jour ils deviennent pertinents
  (actuellement désactivés volontairement, pas par contrainte technique)
- Validation du JSON de collections par un schéma en CI, pour attraper une
  erreur de structure avant qu'elle ne casse l'import Nuvio

## ❌ Explicitement écarté (ne pas reproposer)

- **Recommandations Trakt personnalisées** (`trakt.recommendations.*`) —
  retiré volontairement : nécessiterait un compte avec un vrai historique
  de visionnage pour être pertinent, ce qui n'est pas le cas du compte
  secondaire dédié à ce pipeline
