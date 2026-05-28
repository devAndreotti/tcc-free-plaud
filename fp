#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE="$ROOT/pipeline"
UI="$ROOT/UI"

show_help() {
  cat <<'EOF'
Uso: ./fp <comando> [args]

Comandos:
  tui     abre a TUI Textual
  menu    abre o menu terminal numerado
  app     builda o React e abre o app integrado PyWebView
  front   roda o Vite com mock de desenvolvimento
  test    roda os testes do backend

Exemplos:
  ./fp tui
  ./fp menu
  ./fp app
EOF
}

cmd="${1:-help}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$cmd" in
  tui)
    (cd "$PIPELINE" && uv run free-plaud tui "$@")
    ;;
  menu)
    (cd "$PIPELINE" && uv run free-plaud menu "$@")
    ;;
  app)
    npm --prefix "$UI" run build
    (cd "$PIPELINE" && uv run --extra desktop python "$UI/main.py" "$@")
    ;;
  front | dev)
    npm --prefix "$UI" run dev "$@"
    ;;
  test)
    (cd "$PIPELINE" && uv run pytest "$@")
    ;;
  help | -h | --help)
    show_help
    ;;
  *)
    echo "Comando desconhecido: $cmd" >&2
    echo >&2
    show_help >&2
    exit 2
    ;;
esac
