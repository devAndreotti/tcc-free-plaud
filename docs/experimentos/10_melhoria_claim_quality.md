# Experimento 10 - Melhoria de claim quality no ask

## Objetivo

Validar a hipótese levantada na revisão do handoff de chunking:

> os erros observados em `ata-03`, `paper-03`, `paper-04` e `contrato-03`
> estavam majoritariamente na seleção/composição de claims em `rag.py`,
> não no chunker.

## Escopo

Esta rodada não altera:

- `chunking.py`
- `indexer.py`
- `models.py`
- `schemas.py`
- `normalizer.py`
- `search.py`

Esta rodada altera:

- `pipeline/src/free_plaud/retrieval/rag.py`
- `pipeline/tests/test_rag.py`

## Mudança aplicada

Foram introduzidos três ajustes na seleção de claims:

1. geração de candidatos mais rica
   - candidatos por sentença
   - candidatos por linha
   - fusão de linhas adjacentes

2. ranking de claim mais semântico
   - bônus por frases exatas da pergunta
   - bônus por enumeração em perguntas `quais`
   - bônus por sinais de entidade específica

3. seleção global de claims
   - candidatos agora competem globalmente entre hits
   - um claim por chunk

## Testes executados

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline

$tmp = Join-Path $env:TEMP ("tcc-free-plaud-rag-full-" + [guid]::NewGuid().ToString())
uv run pytest --basetemp $tmp tests\test_rag.py tests\test_benchmark.py tests\test_chunking.py -q

$tmp = Join-Path $env:TEMP ("tcc-free-plaud-all-" + [guid]::NewGuid().ToString())
uv run pytest --basetemp $tmp -q

uv run free-plaud benchmark compare `
  --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

## Resultado dos testes

- bateria focada: `41 passed`
- suíte ampla: `103 passed`

Guardrail de benchmark preservado:

- `lexical MRR = 0.96875`
- `vector MRR = 0.7916666666666666`
- `hybrid MRR = 0.96875`
- `hybrid Recall@3 = 1.0`

## Casos-alvo

### `ata-03`

Antes:

- priorizava a frase genérica de rollout
- não trazia `notificações de email` e `logs de auditoria`

Depois:

- traz os dois tópicos corretos
- ainda arrasta condicionantes extras no segundo claim

### `paper-03`

Antes:

- respondia com frase genérica sobre embeddings + hardware

Depois:

- passou a incluir `nomic-embed-text-v1.5`
- ainda vem verboso demais

### `paper-04`

Antes:

- priorizava a recomendação geral para documentos estruturados

Depois:

- inclui explicitamente `documentos sem estrutura formal`
- inclui `chunking semântico`
- ainda mantém contexto extra além do mínimo

### `contrato-03`

Antes:

- trazia só `React + Node.js`

Depois:

- traz `React + Node.js`
- traz `Python + PostgreSQL`
- ainda carrega heading/anexo junto da resposta

## Veredito

A hipótese estava correta:

- o problema dominante estava em `rag.py`
- não era necessário mudar o chunker para corrigir esses casos primeiro

Ao mesmo tempo, o resultado final ainda não é “polido”.

Estado atual:

- melhorou a completude factual
- preservou benchmark
- não resolveu completamente limpeza e concisão textual

## Próximo passo sugerido

Se houver nova rodada nesta área:

1. manter chunking como está
2. fazer uma segunda slice pequena em `rag.py`
3. focar em:
   - poda de contexto excedente
   - respostas mais curtas
   - preferência por spans mínimos suficientes

Não abrir `title injection` agora.
`heading-aware chunking` continua sendo experimento separado, não correção obrigatória.
