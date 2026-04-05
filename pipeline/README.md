# Pipeline backend `free-plaud`

Este diretório contém o backend experimental do projeto, implementado em **Python 3.12** com **uv**, **Typer**, **Pydantic**, **PyPDF** e **Pytest**.

O objetivo desta primeira base é permitir evolução incremental do pipeline local-first do TCC, começando por ingestão textual, estruturação em Markdown, recuperação inicial e benchmark independente da interface.

No estado atual, o backend já cobre:

- ingestão local de `.txt`, `.md` e `.pdf`
- estruturação inicial de notas em Markdown
- CLI modular para inspeção, notas, retrieval, benchmark e storage
- testes automatizados para config, CLI, ingestão, chunking e nota estruturada

## Estrutura

O código vive em `src/free_plaud/` e os testes em `tests/`, seguindo o padrão `src layout` recomendado para projetos Python modernos.

## Comandos iniciais

```bash
uv sync
uv run free-plaud --help
uv run pytest
```
