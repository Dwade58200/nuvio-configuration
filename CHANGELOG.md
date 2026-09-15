# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Versionnage Sémantique](https://semver.org/lang/fr/).

## [Non publié] - 2024-XX-XX

### Ajouté
- **Généralisation du logo/titre TMDB (#13)** : Le mécanisme d'incrustation de logo/titre TMDB sur les backdrops nus, auparavant réservé à FanKai, est maintenant appliqué à TOUTES les collections utilisant `champ_titre` quand aucune affiche avec titre FR/EN/original n'est trouvée. Recherche prioritaire fr-FR puis en-US.
- **Bouton aléatoire (#16)** : Nouvel outil dans l'interface de génération depuis un dossier d'images pour mélanger aléatoirement l'ordre des images avant composition.
- **Positionnement en spirale (#17)** : Algorithme de placement des tuiles révisé pour une disposition en spirale (du centre vers l'extérieur) au lieu d'une grille inclinée linéaire. Conserve le style visuel des tuiles.
- Support complet du logging structuré (module `logging`) pour un débogage facilité
- Mécanisme de retry/backoff pour les appels API (TMDB, Fanart, MDBList)
- Validation des variables d'environnement au démarrage du script
- Fichier `.env.example` pour la configuration locale
- Configuration `pytest-cov` pour la mesure de couverture de code (~77%)
- Hooks pre-commit (`ruff`, `mypy`, validation de schéma JSON)
- Formatage automatique du code avec `ruff format`
- Support élargi de Python (3.10, 3.11, 3.12)
- Mocking des appels API dans les tests avec `responses`
- Dockerfile pour une exécution reproductible
- Badge de couverture de code dans le README

### Modifié
- **Template initial aligné (#15)** : Les valeurs par défaut de l'outil `reglage-style-mosaique.html` sont synchronisées avec les constantes de `mosaique.py` (inclinaison corrigée à -10°).
- **Test mis à jour** : `test_construire_grille_inclinee_place_le_premier_resultat_au_centre` adapté pour valider le placement central avec suffisamment d'images distinctes.
- Versions des dépendances pinnées dans `requirements.txt` et `requirements-dev.txt`
- Remplacement des `print()` par des appels `logger` dans `generer_backdrops.py`
- Correction de la gestion des groupes inconnus (underscores au lieu d'espaces)
- Niveau de log corrigé (WARNING au lieu de INFO pour les sources non résolues)

### Corrigé
- **Erreurs de linting** : Variables ambiguës renommées (`l` → `logo`), espaces blancs superflus supprimés dans `generer_backdrops.py`.
- Erreurs de typage MyPy pour la bibliothèque `requests` (ajout de `types-requests`)
- Conflits de fusion dans les fichiers binaires (backdrops)

## [1.0.0] - 2024-09-14

### Ajouté
- Génération automatique de backdrops pour collections Nuvio
- Support des sources TMDB, Fanart.tv, et MDBList
- Mode mosaïque pour les backdrops
- Purge CDN sélective après génération
- Tests unitaires et d'intégration (256 tests)
- CI/CD avec GitHub Actions (lint, type-check, tests, validation JSON)
- Documentation complète (README, BACKDROPS_SETUP.md, AMELIORATIONS.md)
