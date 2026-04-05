# Pipeline backend `free-plaud`

Este diretório contém o backend experimental do projeto, implementado em **Python 3.12** com **uv**, **Typer**, **Pydantic** e **Pytest**.

O objetivo desta primeira base é permitir evolução incremental do pipeline local-first do TCC, começando por ingestão textual, estruturação em Markdown, recuperação inicial e benchmark independente da interface.

## Estrutura

O código vive em `src/free_plaud/` e os testes em `tests/`, seguindo o padrão `src layout` recomendado para projetos Python modernos.

## Comandos iniciais

```bash
uv sync
uv run free-plaud --help
uv run pytest
```
