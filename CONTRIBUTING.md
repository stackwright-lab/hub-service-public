# Contribuer au Hub Service Public

Merci de votre intérêt. Le projet vise un objectif simple : rendre les données publiques françaises interrogeables en français, avec des réponses sourcées et vérifiables. Toute contribution qui va dans ce sens est bienvenue, du signalement d'une erreur à l'ajout d'une source.

## Par où commencer

- **Vous avez trouvé un problème** : ouvrez un ticket « Signaler un problème » en indiquant la question posée, ce que vous attendiez et ce que le hub a répondu.
- **Vous connaissez une source utile** (API publique, jeu de données de référence) : ouvrez un ticket « Proposer une source ».
- **Vous voulez coder** : la [feuille de route](docs/ROADMAP.md) liste des tâches de départ, classées par difficulté.

## Installer l'environnement de développement

```bash
uv sync --extra dev
uv run pytest
```

Tous les tests tournent hors ligne, en quelques secondes. Une contribution qui ajoute un comportement ajoute le test qui le vérifie.

## Règles du projet

1. **Lecture seule.** Le hub ne fait que des requêtes GET vers les sources. Le seul outil qui écrit (`synchroniser_index`) n'écrit que dans l'index local.
2. **Jamais d'URL fournie par l'utilisateur ou par un tiers sans contrôle.** Les adresses passent par la garde anti-SSRF de `net.py`. Une nouvelle source tierce a un hôte fixe, déclaré dans `config.py`.
3. **Pas de donnée inventée.** Une réponse cite toujours le jeu, le producteur et la date. Quand une donnée manque, le hub le dit.
4. **Vie privée.** Aucun nom de personne physique dans l'index ; aucune donnée personnelle dans les exemples, les tests ou les captures.
5. **Polie avec les serveurs publics.** Pas plus de requêtes que nécessaire, nouvelles tentatives espacées, pas de parallélisme agressif.
6. **Français d'abord.** Interface, messages et documentation en français clair.

## Proposer une modification

1. Créez une branche depuis `main`.
2. Faites une modification ciblée, avec ses tests.
3. Vérifiez que `uv run pytest` passe.
4. Ouvrez une pull request qui explique le besoin, la solution et la façon de la vérifier.

En contribuant, vous acceptez que votre contribution soit distribuée sous la licence du projet (EUPL-1.2).

## Code de conduite

Échanges courtois, critiques sur le code et pas sur les personnes. Les comportements irrespectueux entraînent la fermeture des discussions concernées.
