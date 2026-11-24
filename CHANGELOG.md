# Historique des versions

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
