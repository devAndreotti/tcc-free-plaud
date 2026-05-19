# Experimento 11 - Poda de span minimo suficiente no ask

## Objetivo

Reduzir verbosidade do `ask` sem tocar:

- retrieval
- chunking
- benchmark

Escopo aplicado:

- `pipeline/src/free_plaud/retrieval/rag.py`
- `pipeline/tests/test_rag.py`

## Hipotese

Depois da slice `10_melhoria_claim_quality.md`, o backend estava mais correto
factualmente, mas ainda devolvia spans grandes demais.

Hipotese desta rodada:

- o problema remanescente estava em poda de span e composicao final do claim
- nao em retrieval
- nao em chunking

## Mudanca aplicada

Foram introduzidos cinco ajustes locais em `rag.py`:

1. trimming local de claim para span menor
2. remocao de prefixos administrativos quando existe variante mais informativa
3. preferencia por sentenca unica em perguntas singulares
4. deteccao de perguntas realmente multipartes para permitir mais de um claim
5. poda de cauda truncada em spans incompletos

Tambem entrou um refinamento no ranking de candidates:

- termos de baixo sinal deixam de dominar a escolha de claim
- perguntas sobre embedding/modelo ganham bonus para spans com identificador tecnico real

## Testes adicionados

Foram adicionados guardrails em `test_rag.py` para:

- `ata-03`
- `paper-03`
- `paper-04`
- `contrato-03`
- `ata-01`
- `contrato-02`
- `contrato-04`
- `dw-02`
- trimming de cauda truncada

## Baseline before

Artefato local gerado:

- `data/results/ask_suite_span_prune_before.json`

Cobertura:

- `16` queries da suite real

Problemas mais claros no baseline:

- `ata-01`: trazia decisao correta + ruido adicional
- `ata-03`: trazia resposta correta + duas condicionantes extras
- `paper-03`: trazia CPU, corpus e metodologia junto da resposta
- `paper-04`: trazia discussao inteira em vez da sentenca central
- `contrato-03`: trazia heading/anexo junto da resposta
- `contrato-04`: trazia matriz inteira em vez do SLA minimo suficiente

## Validacao executada

### Bateria focada

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
$tmp = Join-Path $env:TEMP ("tcc-free-plaud-span-prune-focused-final-" + [guid]::NewGuid().ToString())
uv run pytest --basetemp $tmp tests\test_rag.py tests\test_benchmark.py tests\test_chunking.py -q
```

Resultado:

- `46 passed`

### Suite ampla

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
$tmp = Join-Path $env:TEMP ("tcc-free-plaud-span-prune-all-rerun-" + [guid]::NewGuid().ToString())
uv run pytest --basetemp $tmp -q
```

Resultado:

- `108 passed`

Conclusao pratica:

- a suite ampla passou inteira
- esta rodada nao trouxe evidencia de regressao em retrieval, ask ou ingest

### Benchmark guardrail

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud benchmark compare `
  --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

Resultado:

- `lexical MRR = 0.96875`
- `vector MRR = 0.7916666666666666`
- `hybrid MRR = 0.96875`
- `hybrid Recall@3 = 1.0`

Guardrail preservado.

### Artefato after

Gerado:

- `data/results/ask_suite_span_prune_after.json`

## Before vs after

### Casos de melhoria obrigatoria

#### `ata-03`

Antes:

- `649` caracteres
- resposta correta vinha com duas condicionantes extras

Depois:

- `172` caracteres
- manteve:
  - `notificações de email`
  - `logs de auditoria`
- removeu sobra de contexto

#### `paper-03`

Antes:

- `603` caracteres
- misturava corpus, revisores, CPU e resposta

Depois:

- `97` caracteres
- resposta final:
  - `O índice vetorial foiimplementado com ChromaDB e os embeddings gerados com nomic-embed-text-v1.5.`

#### `paper-04`

Antes:

- `948` caracteres
- devolvia bloco inteiro de discussao

Depois:

- `198` caracteres
- ficou centrado na sentenca correta para documentos sem estrutura formal

#### `contrato-03`

Antes:

- `220` caracteres
- vinha com `ANEXO` e heading administrativo

Depois:

- `79` caracteres
- ficou:
  - `Portal do colaborador (React + Node.js) Módulo financeiro (Python + PostgreSQL)`

### Guardrails de estabilidade

#### `ata-01`

Antes:

- `337` caracteres

Depois:

- `61` caracteres
- ficou:
  - `Adotar Apache Kafka como message broker padrão da plataforma.`

#### `paper-02`

Antes:

- `759` caracteres

Depois:

- `234` caracteres
- manteve:
  - `Semântico`
  - `0,81`

#### `contrato-04`

Antes:

- `368` caracteres

Depois:

- `78` caracteres
- manteve:
  - `Prioridade Crítica`
  - `SLA: 2h`

#### `dw-02`

Antes:

- `526` caracteres

Depois:

- `303` caracteres
- manteve:
  - `SCD Tipo 2`
  - `Preserva o histórico completo`

### Caso de nuance ainda imperfeito

#### `contrato-02`

Antes:

- `456` caracteres
- vinha com trecho irrelevante da cláusula `3.1`

Depois:

- `48` caracteres
- ficou:
  - `de 3 (três) anos após o encerramento da vigência`

Leitura:

- resposta ficou muito mais limpa
- ainda perdeu parte do contexto jurídico desejável
- este caso nao virou blocker, mas continua como limite conhecido

## Veredito

Esta slice foi bem-sucedida.

O que melhorou:

- respostas mais curtas
- menos heading/anexo
- menos claims sobrando
- menos spans administrativos

O que nao piorou:

- retrieval
- benchmark
- `hybrid`
- `no_answer` do fluxo vetorial/hibrido nos testes de guardrail

## Limites remanescentes

1. `contrato-02` ainda pode ficar seco demais
2. existe uma falha flaky fora do escopo em `ingest`
3. answer layer continua heuristico, sem LLM

## Conclusao

Conclusao correta desta rodada:

> a poda de span resolveu boa parte da verbosidade sem precisar reabrir chunking ou retrieval.

Proximo passo tecnico, se houver nova rodada nesta area:

1. tratar casos de **contexto juridico minimo** como experimento separado
2. nao mexer em retrieval ainda
3. nao reabrir chunking ainda
