# Experimento 14 - Consistencia, reset e rebuild do corpus

## Objetivo

Validar se o corpus local consegue:

1. diagnosticar divergencia entre SQLite e Chroma;
2. impedir uso de vetores sem chunk persistido;
3. simular reset sem apagar dados;
4. reconstruir corpus a partir de uma pasta controlada;
5. responder pergunta multi-documento apenas com o corpus reconstruido.

## Escopo

- Backend CLI apenas.
- Sem frontend, Tauri, audio, imagem ou LLM real.
- Banco real default usado somente para `corpus status`.
- Reset/rebuild destrutivo validado apenas em workspace temporario.
- Fonte controlada: `data/results/validation_distributed_corpus`.

## Estado sujo inicial observado

Comando:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud corpus status
```

Resumo observado em 2026-05-22:

```json
{
  "sqlite_path": "D:\\Dev\\Repos\\Own\\tcc-free-plaud\\data\\results\\free_plaud.sqlite3",
  "vector_store_dir": "D:\\Dev\\Repos\\Own\\tcc-free-plaud\\data\\results\\vector_store",
  "vector_collection_name": "free_plaud_chunks",
  "notes_count": 7,
  "sqlite_chunks_count": 53,
  "vector_chunks_count": 122,
  "stale_vector_chunks_count": 122,
  "missing_vector_chunks_count": 53,
  "orphan_vector_note_ids": [
    "07-pdf-tecnico-estruturado",
    "arquitetura-backend",
    "ask-invalid",
    "cyberops-agentes-de-ameaca",
    "cyberops-soc",
    "cyberops-windows",
    "resume"
  ],
  "status": "inconsistent"
}
```

Interpretacao: o banco default estava operacionalmente sujo. Todos os vetores da collection ativa tinham `chunk_id`
ausente no SQLite, e todos os chunks do SQLite estavam ausentes no Chroma. A causa provavel e mistura de execucoes
experimentais, reindexacoes e mudancas de chunking/modelo sem rebuild atomico.

## Validacao em workspace temporario

Comandos equivalentes executados com variaveis `FREE_PLAUD_*` apontando para pasta temporaria dentro de `pipeline`.

```powershell
uv run free-plaud corpus status
uv run free-plaud corpus reset --dry-run
uv run free-plaud corpus rebuild "D:\Dev\Repos\Own\tcc-free-plaud\data\results\validation_distributed_corpus" --recursive --yes
uv run free-plaud corpus status
uv run free-plaud corpus ask --question "Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?" --strategy hybrid --top-k 6
uv run free-plaud corpus ask --question "Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?" --strategy vector --top-k 6
uv run free-plaud corpus ask --question "Quais tecnologias o candidato domina para desenvolver apps mobile?" --strategy hybrid --top-k 6
```

Resumo observado:

```json
{
  "status_before": "empty",
  "reset_preview": "preview",
  "rebuild_status": "success",
  "rebuild_indexed": 3,
  "rebuild_skipped": 0,
  "status_after": "clean",
  "sqlite_chunks_after": 3,
  "vector_chunks_after": 3,
  "stale_after": 0,
  "missing_after": 0
}
```

## Pergunta multi-fonte

Pergunta:

```text
Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?
```

Resultado `hybrid`:

```json
{
  "status": "answer",
  "no_answer": false,
  "sources": [
    "03-restricao-arquitetural",
    "01-contexto-base",
    "02-detalhe-operacional"
  ],
  "citations": [
    "03-restricao-arquitetural",
    "01-contexto-base",
    "02-detalhe-operacional"
  ]
}
```

Resposta sintetizada:

```text
Para analise e consumo posterior, o pipeline deve organizar os dados segundo o padrao Medallion, dividido nas camadas Bronze, Silver e Gold. O pipeline de ingestao orientado a eventos adotou o RabbitMQ como message broker padrao para desacoplar a captura dos estagios de processamento interno. O runbook de operacao do broker ficou sob responsabilidade da equipe de Plataforma.
```

Resultado `vector`:

```json
{
  "status": "answer",
  "no_answer": false,
  "sources": [
    "03-restricao-arquitetural",
    "01-contexto-base"
  ],
  "citations": [
    "03-restricao-arquitetural",
    "01-contexto-base"
  ]
}
```

Interpretacao: `vector` respondeu com evidencia real e sem stale, mas ainda nao recuperou todas as fontes da pergunta.
`hybrid` continua default correto para demo multi-documento.

## Pergunta negativa

Pergunta:

```text
Quais tecnologias o candidato domina para desenvolver apps mobile?
```

Resultado:

```json
{
  "status": "no_answer",
  "no_answer": true,
  "reason_for_no_answer": "insufficient_hybrid_evidence"
}
```

## Testes automatizados

Comando:

```powershell
uv run pytest --basetemp .pytest-tmp-corpus-slice4 tests\test_corpus_rebuild.py tests\test_corpus_reset.py tests\test_corpus_status.py tests\test_corpus_service.py tests\test_corpus_ask.py tests\test_cli.py -q
```

Resultado:

```text
27 passed in 12.92s
```

## Decisao tecnica

- `corpus status` passa a ser o primeiro comando para diagnosticar corpus sujo.
- `corpus ask` filtra qualquer hit cujo `chunk_id` nao exista no SQLite antes de citations, sources e grounding.
- `corpus reset` fica seguro por default: sem `--yes`, apenas preview.
- `corpus rebuild` e o caminho recomendado para demo ou validacao limpa.
- Banco default real nao deve ser limpo automaticamente por agente; o usuario deve executar `corpus reset --yes` ou `corpus rebuild --yes` conscientemente.

## Limitacoes restantes

- Ainda nao existe `corpus_id`/namespace; o corpus ativo continua unico.
- `vector` sozinho ainda pode retornar resposta parcial em perguntas multi-fonte.
- Reindexacao de um arquivo isolado ainda pode deixar vetores antigos se `chunk_id` mudar; `rebuild` resolve isso no acervo inteiro.
- Botao TUI de reset/rebuild ainda nao foi implementado nesta slice.
