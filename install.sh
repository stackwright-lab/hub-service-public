#!/usr/bin/env bash
# Installation du Hub Service Public (macOS et Linux).
# Usage : ./install.sh            (interactif)
#         ./install.sh --oui      (accepte toutes les étapes, synchronisation complète comprise)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO=0
[[ "${1:-}" == "--oui" || "${1:-}" == "--yes" ]] && AUTO=1

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ask()  { [[ $AUTO == 1 ]] && return 0; read -r -p "$1 [o/N] " r; [[ "$r" =~ ^[oOyY] ]]; }

cd "$ROOT"

say "1/5  Vérification de uv (gestionnaire Python)"
if ! command -v uv >/dev/null 2>&1; then
  for p in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
    [[ -x "$p" ]] && export PATH="$(dirname "$p"):$PATH" && break
  done
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv n'est pas installé (https://docs.astral.sh/uv/)."
  if ask "L'installer maintenant avec le script officiel d'Astral ?"; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  else
    echo "Installez uv puis relancez ./install.sh"; exit 1
  fi
fi
UV="$(command -v uv)"
echo "uv : $UV"

say "2/5  Installation des dépendances et tests"
"$UV" sync --extra dev
"$UV" run pytest -q

say "3/5  Synchronisation du catalogue data.gouv.fr"
if [[ -f data/catalogue.sqlite ]]; then
  echo "Index déjà présent : mise à jour incrémentale."
  "$UV" run hub-harvest --incremental
elif ask "Lancer la synchronisation complète maintenant (30 à 60 minutes, environ 600 Mo) ?"; then
  "$UV" run hub-harvest --max-pages 2
  "$UV" run hub-harvest
  "$UV" run hub-harvest --fill-gaps || true
else
  echo "À faire plus tard : uv run hub-harvest"
fi

say "4/5  Branchement à l'application Claude Desktop"
case "$(uname -s)" in
  Darwin) CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json" ;;
  *)      CFG="${XDG_CONFIG_HOME:-$HOME/.config}/Claude/claude_desktop_config.json" ;;
esac
if [[ -d "$(dirname "$CFG")" ]] && ask "Application Claude détectée : y brancher aussi le hub ($CFG) ? Quittez l'application avant."; then
  "$UV" run python - "$CFG" "$UV" "$ROOT" <<'PY'
import json, pathlib, shutil, sys
cfg, uv, root = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
data = {}
if cfg.exists():
    shutil.copy(cfg, str(cfg) + ".avant-hub")
    data = json.loads(cfg.read_text(encoding="utf-8") or "{}")
data.setdefault("mcpServers", {})["hub-service-public"] = {"command": uv, "args": ["--directory", root, "run", "hub-server"]}
cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Hub ajouté à", cfg)
PY
else
  echo "Claude Desktop non détecté ou étape ignorée (voir README, « Brancher Claude »)."
fi
if command -v claude >/dev/null 2>&1 && ask "Ajouter aussi le hub à Claude Code ?"; then
  claude mcp add hub-service-public -- "$UV" --directory "$ROOT" run hub-server || true
fi

say "5/5  Terminé"
cat <<EOF
- Pour ouvrir la page web : double-cliquez sur « Lancer Hub Service Public.command »
  (ou : uv run hub-web). Elle s'ouvre dans votre navigateur.
- Réponses rédigées par Claude dans la page (facultatif) : copiez .env.example en .env
  et renseignez ANTHROPIC_API_KEY.
- Si vous avez branché l'application Claude : rouvrez-la, « hub-service-public » doit
  apparaître en « En cours » (Paramètres > Application de bureau > Serveurs MCP locaux).
EOF
