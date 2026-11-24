# Feuille de route

Tâches ouvertes aux contributions. Le niveau indique l'effort attendu pour une première contribution.

## Nouvelles sources

| Tâche | Niveau | Intérêt |
|---|---|---|
| Valeurs foncières d'une adresse ou d'une rue (DVF géolocalisées) | Moyen | « Combien s'est vendu un appartement rue X ? » |
| Risques d'une commune (API Géorisques : inondation, argile, radon) | Moyen | Question fréquente avant un achat immobilier |
| Recherche d'entreprise par SIREN ou nom (API Recherche d'entreprises) | Facile | API ouverte, très demandée |
| Informations légales d'une commune (API Découpage administratif) | Facile | Code Insee, population, EPCI |
| DPE des bâtiments tertiaires et des logements neufs (ADEME) | Facile | Étend l'outil DPE existant |

## Qualité des réponses

| Tâche | Niveau | Intérêt |
|---|---|---|
| Mieux reconnaître le lieu dans une question (codes postaux, arrondissements) | Facile | Filtrage plus précis des fichiers |
| Classer les pistes en tenant compte de la fraîcheur des jeux | Moyen | Éviter de proposer un jeu périmé en premier |
| Reconnaître plus de colonnes de commune dans les fichiers | Facile | Plus de réponses filtrées sur le bon lieu |
| Tester les opérateurs `less` et `greater` de l'API tabulaire | Facile | Requêtes par seuil fiables |

## Santé des données

| Tâche | Niveau | Intérêt |
|---|---|---|
| Mesurer la disponibilité réelle des fichiers (liens cassés) | Moyen | Indicateur manquant aujourd'hui |
| Historique des indicateurs de santé (évolution semaine après semaine) | Moyen | Voir si le catalogue s'améliore |
| Export du tableau de bord en PDF ou CSV | Facile | Partage avec des producteurs de données |

## Installation et diffusion

| Tâche | Niveau | Intérêt |
|---|---|---|
| Script d'installation Windows (`install.ps1`) | Moyen | Installation en un clic sous Windows |
| Paquet `uvx` installable sans cloner le dépôt | Moyen | Installation plus simple pour les utilisateurs de Claude |
| Traduction anglaise de l'interface | Facile | Public international du MCP |
