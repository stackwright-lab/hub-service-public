# Historique des versions

## 1.0.1 (24 novembre 2026)

- Descriptions des outils MCP précisées pour que les assistants choisissent le bon outil : quand utiliser `repondre` plutôt que `rechercher`, et ce qui distingue `etat_du_hub` (état du hub), `disponibilite_sources` (services en ligne) et `sante_des_donnees` (qualité des données publiées).
- Ajout de `glama.json`, de Dependabot et de l'analyse de code CodeQL.

## 1.0.0 (24 novembre 2026)

Première version publique.

- Page web locale, lancée d'un double-clic : questions en langage naturel, réponses sourcées, état des sources par catégorie, onglet Santé des données.
- Réponses rédigées par Claude avec une clé d'API Anthropic (facultatif) ; sinon, présentation des pistes trouvées par le hub.
- Serveur MCP pour l'application Claude et Claude Code (14 outils, lecture seule sauf la mise à jour de l'index local).
- Index local du catalogue data.gouv.fr : jeux de données, API, organisations, réutilisations, discussions ; synchronisation complète, incrémentale et reprise.
- Lecture en direct des fichiers tabulaires et appel des API ouvertes du catalogue, sous contrôle anti-SSRF.
- DPE d'une adresse (ADEME et Base Adresse Nationale).
- Indicateurs de santé : fraîcheur, complétude des métadonnées, documentation et joignabilité des API.
- Script d'installation et lanceurs pour macOS, Windows et Linux.
