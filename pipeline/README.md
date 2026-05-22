# Pipeline backend `free-plaud`

Este diretório contém o backend experimental do projeto, implementado em **Python 3.12** com **uv**, **Typer**, **Pydantic**, **PyPDF** e **Pytest**.

O objetivo desta primeira base é permitir evolução incremental do pipeline local-first do TCC, começando por ingestão textual, estruturação em Markdown, recuperação inicial e benchmark independente da interface.

No estado atual, o backend já cobre:

- ingestão local de `.txt`, `.md` e `.pdf`
- estruturação inicial de notas em Markdown
- CLI modular para inspeção, notas, retrieval, benchmark e storage
- TUI textual para perguntar contra corpus indexado, operar notas/corpus e rodar benchmark
- menu terminal numerado para operar corpus, ask e benchmark sem abrir a TUI
- testes automatizados para config, CLI, ingestão, chunking e nota estruturada

## Estrutura

O código vive em `src/free_plaud/` e os testes em `tests/`, seguindo o padrão `src layout` recomendado para projetos Python modernos.

## Comandos iniciais

```bash
uv sync
uv run free-plaud --help
uv run free-plaud menu
uv run free-plaud-tui
uv run pytest
```

## Fluxos úteis

```bash
uv run free-plaud corpus rebuild "D:\caminho\pasta" --recursive --yes
uv run free-plaud corpus ask --question "Pergunta" --strategy hybrid --top-k 6
uv run free-plaud corpus index-benchmark --files 100 --repeat 2
uv run free-plaud-tui
```

Na TUI, o modo `Corpus` pergunta contra SQLite + Chroma sem exigir arquivo novo.
O modo `Arquivo` continua disponível para consulta isolada.

Para pastas grandes, a indexação de corpus usa batches configuráveis:

```bash
FREE_PLAUD_CORPUS_EMBEDDING_BATCH_SIZE=64
FREE_PLAUD_CORPUS_UPSERT_BATCH_SIZE=128
```
