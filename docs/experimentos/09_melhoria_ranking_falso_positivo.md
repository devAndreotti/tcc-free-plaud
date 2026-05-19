# 09 - Melhoria de ranking e filtro de falso positivo

## Status

Executado em 2026-05-19

## Objetivo

Reduzir falso positivo na busca aberta de `semantic-search` sem:

- quebrar recuperacao valida
- degradar benchmark atual
- alterar answer layer

Escopo aplicado:

- fluxo aberto de `retrieval semantic-search`
- sem promocao imediata para todos os caminhos vetoriais

## Mudanca implementada

Arquivos alterados:

- `pipeline/src/free_plaud/retrieval/search.py`
- `pipeline/src/free_plaud/retrieval/cli.py`
- `pipeline/tests/test_vector_store.py`

Mudanca:

1. criacao de `open_semantic_search(...)`
2. reranking lexical-aware para busca aberta
3. poda leve de hits com evidencia insuficiente em queries longas
4. comando `retrieval semantic-search` passa a usar esse fluxo quando `--note-id` nao e informado

Regras novas da busca aberta:

- bonus para `term_coverage`
- bonus para mais `matched_terms`
- bonus para matches em termos de alto sinal
- penalidade para `matched_terms = []`
- penalidade para `term_coverage = 0`
- penalidade para hit que so casa termo generico em query longa
- fallback desligado para query longa quando todos os hits sao fracos

## Testes

Comandos:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
$tmp = "D:\Dev\Repos\Own\tcc-free-plaud\.pytest-tmp-$([guid]::NewGuid().ToString())"
uv run pytest --basetemp $tmp tests\test_vector_store.py -q
uv run pytest --basetemp $tmp -q
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

Resultados:

- `tests/test_vector_store.py`: `11 passed`
- suite completa: `92 passed`
- benchmark guardrail:
  - `lexical`: `MRR 0.96875`, `Recall@3 1.0`
  - `vector`: `MRR 0.7916666666666666`, `Recall@3 0.9375`
  - `hybrid`: `MRR 0.96875`, `Recall@3 1.0`

Leitura:

- mudanca nao degradou benchmark atual
- `ask` e `hybrid` ficaram estaveis

## Collections usadas

- `validation_real_false_positive_20260519`
- `validation_ctrl_false_positive_20260519`

## Baseline ruim antes da mudanca

### Caso negativo 1

Pergunta:

> Quais tecnologias o candidato domina para desenvolver apps mobile?

Antes:

| rank | note_id | score | matched_terms | term_coverage |
| ---: | --- | ---: | --- | ---: |
| 1 | `07-pdf-tecnico-estruturado` | `0.6472515311601286` | `domina` | `0.16666666666666666` |
| 2 | `04-ata-metadados-longos` | `0.6416948082635856` | nenhum | `0.0` |
| 3 | `10-documento-longo-modelagem-dados` | `0.640712315357925` | nenhum | `0.0` |
| 4 | `07-pdf-tecnico-estruturado` | `0.639156289511023` | nenhum | `0.0` |
| 5 | `10-documento-longo-modelagem-dados` | `0.6385061318177548` | nenhum | `0.0` |

Problema:

- `open_noise_at_5 = 5`
- `matched_terms = []` em `4/5`
- retrieval aberto devolvia lixo

### Caso negativo 2

Pergunta:

> Qual banco relacional foi escolhido para autenticar o painel web?

Antes:

| rank | note_id | score | matched_terms | term_coverage |
| ---: | --- | ---: | --- | ---: |
| 1 | `10-documento-longo-modelagem-dados` | `0.649545099731784` | `foi`, `escolhido` | `0.2857142857142857` |
| 2 | `04-ata-metadados-longos` | `0.6179874275784012` | `foi`, `escolhido` | `0.2857142857142857` |

Problema:

- retrieval casava verbo generico
- nao havia match de alto sinal como `banco`, `relacional`, `autenticar`, `painel`

## Resultados depois da mudanca

### Caso positivo real

Pergunta:

> Qual message broker foi adotado como padrao da plataforma?

Depois:

| rank | note_id | score | matched_terms | term_coverage |
| ---: | --- | ---: | --- | ---: |
| 1 | `04-ata-metadados-longos` | `0.7218732923658913` | `message`, `broker`, `adotado`, `padrao`, `plataforma` | `0.8333333333333334` |
| 2 | `04-ata-metadados-longos` | `0.6380591507483854` | `foi`, `adotado`, `padrao`, `plataforma` | `0.6666666666666666` |
| 3 | `04-ata-metadados-longos` | `0.6724577640075193` | `message`, `broker`, `plataforma` | `0.5` |

Leitura:

- `open_relevant_top1`: preservado
- recuperacao valida nao caiu

### Caso negativo real 1

Pergunta:

> Quais tecnologias o candidato domina para desenvolver apps mobile?

Depois:

- resultado: `[]`

Leitura:

- `open_noise_at_5`: `0`
- lixo removido

### Caso negativo real 2

Pergunta:

> Qual banco relacional foi escolhido para autenticar o painel web?

Depois:

- resultado: `[]`

Leitura:

- hits que so casavam `foi` e `escolhido` foram descartados
- filtro de alto sinal funcionou

### Caso positivo multi-file controlado

Pergunta:

> Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?

Depois:

| rank | note_id | score | matched_terms | term_coverage |
| ---: | --- | ---: | --- | ---: |
| 1 | `03-restricao-arquitetural` | `0.7328838847648957` | `padrao`, `divide`, `pipeline`, `bronze`, `silver`, `gold` | `0.4` |
| 2 | `01-contexto-base` | `0.6535852097873602` | `message`, `broker`, `foi`, `adotado`, `padrao`, `pipeline` | `0.4` |

Leitura:

- recuperacao multi-file continuou existindo
- top 2 ainda traz duas partes corretas do contexto distribuido

### Caso misto real

Pergunta:

> Qual message broker foi adotado e qual custo mensal foi aprovado?

Depois:

| rank | note_id | score | matched_terms | term_coverage |
| ---: | --- | ---: | --- | ---: |
| 1 | `04-ata-metadados-longos` | `0.7029235705208619` | `message`, `broker`, `adotado`, `aprovado` | `0.5714285714285714` |
| 2 | `04-ata-metadados-longos` | `0.6569056270914934` | `message`, `broker`, `custo` | `0.42857142857142855` |
| 3 | `04-ata-metadados-longos` | `0.6534852630979515` | `message`, `broker` | `0.2857142857142857` |

Leitura:

- busca aberta nao colapsou quando parte da pergunta nao tinha resposta explicita
- contexto util continuou vindo

### Caso misto controlado

Pergunta:

> Qual equipe ficou responsavel pelo runbook e qual linguagem foi escolhida para o app mobile?

Depois:

| rank | note_id | score | matched_terms | term_coverage |
| ---: | --- | ---: | --- | ---: |
| 1 | `02-detalhe-operacional` | `0.7176154378450034` | `equipe`, `ficou`, `runbook` | `0.3` |

Leitura:

- parte valida da pergunta continuou recuperavel
- filtro nao matou caso parcialmente util

## Impacto em `ask`

Comando:

```powershell
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME='validation_real_false_positive_20260519'
uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\samples\manual validetion\07_pdf_tecnico_estruturado.md" --question "Quais tecnologias o candidato domina para desenvolver apps mobile?" --strategy hybrid
```

Resultado:

- `status`: `no_answer`
- `reason_for_no_answer`: `insufficient_grounded_claims`

Leitura:

- `ask` continuou estavel
- slice ficou confinada ao fluxo aberto

## Veredito

1. retrieval aberto melhorou?
   - **sim**
2. falso positivo caiu?
   - **sim**
3. recuperacao valida foi preservada?
   - **sim**
4. benchmark guardrail ficou estavel?
   - **sim**
5. mudanca ficou confinada ao fluxo aberto ou impactou shared path?
   - **confinada ao fluxo aberto do CLI**

## Conclusao

Esta rodada ficou aceitavel.

Decisao:

- manter mudanca como melhoria do fluxo aberto
- nao promover ainda para todos os caminhos vetoriais
- so abrir nova rodada se surgirem queries reais onde filtro ficou agressivo demais
