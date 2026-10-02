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

Da raiz do repositório, use os atalhos curtos:

```bash
./fp menu
./fp tui
./fp test
```

No PowerShell, use `fp.ps1`:

```powershell
.\fp.ps1 menu
.\fp.ps1 tui
.\fp.ps1 test
```

Dentro de `pipeline/`, os comandos diretos continuam disponíveis:

```bash
uv sync
uv run free-plaud --help
uv run free-plaud menu
uv run free-plaud tui
uv run pytest
```

## Fluxos úteis

```bash
uv run free-plaud corpus rebuild "D:\caminho\pasta" --recursive --yes
uv run free-plaud corpus ask --question "Pergunta" --strategy hybrid --top-k 6
uv run free-plaud corpus index-benchmark --files 100 --repeat 2
uv run free-plaud corpus perf-benchmark --files 100 --repeat 1 --ask-repeat 10 --commit-mode auto
uv run free-plaud corpus embedding-info
uv run free-plaud tui
```

Na TUI, o modo `Corpus` pergunta contra SQLite + Chroma sem exigir arquivo novo.
O modo `Arquivo` continua disponível para consulta isolada.

Para pastas grandes, a indexação de corpus usa batches configuráveis:

```bash
FREE_PLAUD_CORPUS_COMMIT_MODE=auto
FREE_PLAUD_CORPUS_MICRO_BATCH_CHUNKS=64
FREE_PLAUD_CORPUS_MICRO_BATCH_FILES=32
FREE_PLAUD_CORPUS_ATOMIC_MAX_FILES=32
FREE_PLAUD_CORPUS_ATOMIC_MAX_CHUNKS=64
FREE_PLAUD_CORPUS_EMBEDDING_BATCH_SIZE=64
FREE_PLAUD_CORPUS_UPSERT_BATCH_SIZE=128
FREE_PLAUD_CORPUS_INDEX_WORKERS=1
FREE_PLAUD_EMBEDDING_DEVICE=cpu
```

`auto` usa modo atômico em corpus pequeno e micro-lotes em corpus grande. Em micro-lotes, SQLite/Chroma recebem dados durante a indexação, então `corpus status` e `corpus ask` passam a enxergar lotes já commitados antes do fim.

## CUDA opcional

CPU continua sendo o padrão. `uv sync --extra cpu` fixa o PyTorch de CPU (é o que o CI e o
release usam). Os extras `cpu` e `gpu-cu128` são excludentes. Para usar PyTorch CUDA 12.8 com
`uv` sem voltar para build CPU no próximo `uv run`:

```bash
uv sync --extra gpu-cu128
FREE_PLAUD_EMBEDDING_MODEL=sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
FREE_PLAUD_EMBEDDING_DEVICE=cuda
uv run free-plaud corpus embedding-info
```

Se CUDA não estiver disponível, `embedding-info` mostra o erro de configuração antes de iniciar indexação pesada.
