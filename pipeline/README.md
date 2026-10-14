# Pipeline backend do Escólio

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

O código vive em `src/escolio/` e os testes em `tests/`, seguindo o padrão `src layout` recomendado para projetos Python modernos.

## Comandos iniciais

Da raiz do repositório, use os atalhos curtos:

```bash
./es menu
./es tui
./es test
```

No PowerShell, use `es.ps1`:

```powershell
.\es.ps1 menu
.\es.ps1 tui
.\es.ps1 test
```

Dentro de `pipeline/`, os comandos diretos continuam disponíveis:

```bash
uv sync
uv run escolio --help
uv run escolio menu
uv run escolio tui
uv run pytest
```

## Fluxos úteis

```bash
uv run escolio corpus rebuild "D:\caminho\pasta" --recursive --yes
uv run escolio corpus ask --question "Pergunta" --strategy hybrid --top-k 6
uv run escolio corpus index-benchmark --files 100 --repeat 2
uv run escolio corpus perf-benchmark --files 100 --repeat 1 --ask-repeat 10 --commit-mode auto
uv run escolio corpus embedding-info
uv run escolio tui
```

Na TUI, o modo `Corpus` pergunta contra SQLite + Chroma sem exigir arquivo novo.
O modo `Arquivo` continua disponível para consulta isolada.

Variáveis antigas `FREE_PLAUD_*` (ambiente ou `.env`) continuam aceitas como fallback; quando a variável `ESCOLIO_*` correspondente existe, ela vence.

Para pastas grandes, a indexação de corpus usa batches configuráveis:

```bash
ESCOLIO_CORPUS_COMMIT_MODE=auto
ESCOLIO_CORPUS_MICRO_BATCH_CHUNKS=64
ESCOLIO_CORPUS_MICRO_BATCH_FILES=32
ESCOLIO_CORPUS_ATOMIC_MAX_FILES=32
ESCOLIO_CORPUS_ATOMIC_MAX_CHUNKS=64
ESCOLIO_CORPUS_EMBEDDING_BATCH_SIZE=64
ESCOLIO_CORPUS_UPSERT_BATCH_SIZE=128
ESCOLIO_CORPUS_INDEX_WORKERS=1
ESCOLIO_EMBEDDING_DEVICE=cpu
```

`auto` usa modo atômico em corpus pequeno e micro-lotes em corpus grande. Em micro-lotes, SQLite/Chroma recebem dados durante a indexação, então `corpus status` e `corpus ask` passam a enxergar lotes já commitados antes do fim.

## CUDA opcional

CPU continua sendo o padrão. `uv sync --extra cpu` fixa o PyTorch de CPU (é o que o CI e o
release usam). Os extras `cpu` e `gpu-cu128` são excludentes. Para usar PyTorch CUDA 12.8 com
`uv` sem voltar para build CPU no próximo `uv run`:

```bash
uv sync --extra gpu-cu128
ESCOLIO_EMBEDDING_MODEL=sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ESCOLIO_EMBEDDING_DEVICE=cuda
uv run escolio corpus embedding-info
```

Se CUDA não estiver disponível, `embedding-info` mostra o erro de configuração antes de iniciar indexação pesada.
