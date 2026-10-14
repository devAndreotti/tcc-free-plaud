#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE="$ROOT/pipeline"
UI="$ROOT/UI"

show_help() {
  cat <<'EOF'
Uso: ./es <comando> [args]

Comandos:
  tui     abre a TUI Textual
  menu    abre o menu terminal numerado
  app     builda o React e abre o app integrado PyWebView
  front   roda o Vite com mock de desenvolvimento
  doctor  executa diagnostico estruturado do ambiente
  bench   executa o benchmark experimental
  test    roda os testes do backend
  release gera o executavel standalone desktop (.exe e .zip)

Exemplos:
  ./es tui
  ./es menu
  ./es app
EOF
}

cmd="${1:-help}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$cmd" in
  tui)
    (cd "$PIPELINE" && uv run escolio tui "$@")
    ;;
  menu)
    (cd "$PIPELINE" && uv run escolio menu "$@")
    ;;
  app)
    npm --prefix "$UI" run build
    (cd "$PIPELINE" && uv run --extra desktop python "$UI/main.py" "$@")
    ;;
  front | dev)
    npm --prefix "$UI" run dev "$@"
    ;;
  doctor)
    (cd "$PIPELINE" && uv run escolio doctor "$@")
    ;;
  bench)
    (cd "$PIPELINE" && uv run escolio benchmark "$@")
    ;;
  test)
    (cd "$PIPELINE" && uv run pytest "$@")
    ;;
  release)
    (cd "$PIPELINE" && uv run --extra desktop --extra audio python "$ROOT/scripts/build_desktop.py" "$@")
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
