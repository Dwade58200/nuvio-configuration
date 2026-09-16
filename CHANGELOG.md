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
- **Ergonomie de l'outil de réglage des backdrops** : réinitialisation par champ (double-clic), unités manquantes affichées, info-bulles sur les réglages peu intuitifs, nouveau réglage "Ratio du canvas final" (aligné sur `--ratio-canvas`), confirmation avant écrasement/suppression de preset, export/import des presets en JSON, retour visuel pendant la génération réelle, contour de focus clavier.
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
- **Naruto affichait Naruto Shippuden** : `rechercher_titre` privilégiait le résultat TMDB le plus populaire sans vérifier la correspondance de titre. Un résultat au titre exactement identique à la recherche est désormais toujours préféré.
- **Orientation incohérente des tuiles** : le repli catalogue (`champ_image_repli`, souvent un poster portrait) n'est plus forcé dans une tuile paysage quand la recherche TMDB échoue pour un candidat `champ_titre` -- écarté plutôt que mal recadré.
- **Répétitions évitables dans la mosaïque (#17)** : marge de candidats (~+30%) demandée en amont pour absorber les échecs de résolution/téléchargement, et retry du décodage PIL sur image reçue mais corrompue -- maximise le nombre d'images uniques réellement utilisées avant de recourir à une répétition.
- **Liens 404 vers l'outil de style** (README.md, BACKDROPS_SETUP.md) : le workflow `deployer-outils.yml` publie le contenu de `outils/` comme racine du site Pages, sans segment `/outils/` dans l'URL finale.
- **Bug négatif dans `generer_defaults_outil.py`** : la synchronisation des valeurs par défaut ne gérait pas les constantes négatives (`INCLINAISON_DEG = -10`), silencieusement ignorées.

### Modifié
- **Refonte ergonomique de l'outil de style (#14)** : `outils/reglage-style-mosaique.html` restructuré (aperçu épinglé, sections repliables, génération réelle en 3 étapes), sans changement des `id` ni de la logique JS.
- **Mélange + génération liés** : cliquer sur "Mélanger" régénère désormais immédiatement l'aperçu, au lieu de nécessiter un second clic sur "Générer".

## [1.0.0] - 2024-09-14

### Ajouté
- Génération automatique de backdrops pour collections Nuvio
- Support des sources TMDB, Fanart.tv, et MDBList
- Mode mosaïque pour les backdrops
- Purge CDN sélective après génération
- Tests unitaires et d'intégration (256 tests)
- CI/CD avec GitHub Actions (lint, type-check, tests, validation JSON)
- Documentation complète (README, BACKDROPS_SETUP.md, AMELIORATIONS.md)
