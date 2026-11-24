#!/usr/bin/env bash
# Linux : ouvre la page du Hub Service Public dans le navigateur.
cd "$(dirname "$0")" && exec uv run hub-web "$@"
