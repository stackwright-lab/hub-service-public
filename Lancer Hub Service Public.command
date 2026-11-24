#!/bin/bash
# Double-cliquez sur ce fichier (macOS) pour ouvrir la page du Hub Service Public dans votre navigateur.
cd "$(dirname "$0")" || exit 1
for p in "$HOME/.local/bin" "$HOME/.cargo/bin" /opt/homebrew/bin /usr/local/bin; do [ -x "$p/uv" ] && PATH="$p:$PATH"; done
if ! command -v uv >/dev/null 2>&1; then echo "uv est introuvable : lancez d'abord ./install.sh"; read -r -p "Entrée pour fermer"; exit 1; fi
uv run hub-web
