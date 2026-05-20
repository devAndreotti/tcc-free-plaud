# 08 - Validacao de retrieval distribuido

## Status

Executado em 2026-05-19

## Objetivo

Validar com evidencia real de runtime se o backend atual ja sustenta:

- persistencia vetorial correta
- retrieval semantico contextual
- recuperacao multi-chunk
- recuperacao multi-file
- grounding
- `no_answer`
- costura de contexto distribuido entre arquivos

Importante:

- esta validacao nao cobre frontend
- esta validacao nao cobre LLM real
- esta validacao separa retrieval de answer layer

## Verificacao de baseline

Comandos:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
$tmp = "D:\Dev\Repos\Own\tcc-free-plaud\.pytest-tmp-$([guid]::NewGuid().ToString())"
uv run pytest --basetemp $tmp -q
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

Resultado:

- `88 passed`
- suite real:
  - `lexical`: `MRR 0.96875`, `Recall@3 1.0`, `avg_query_latency_ms 130.1875`
  - `vector`: `MRR 0.7916666666666666`, `Recall@3 0.9375`, `avg_query_latency_ms 600.0625`
  - `hybrid`: `MRR 0.96875`, `Recall@3 1.0`, `avg_query_latency_ms 761.1875`

Leitura:

- `hybrid` calibrado ja empata com `lexical` na suite real
- esse benchmark ainda nao prova retrieval distribuido multi-file

## Collections usadas

Esta auditoria usou collections isoladas:

- `validation_real_20260519`
- `validation_ctrl_20260519`

Inicializacao:

```powershell
uv run free-plaud storage init
```

## Corpus usado

### Corpus real

Arquivos indexados na mesma collection:

- `samples/manual validetion/04_ata_metadados_longos.txt`
- `samples/manual validetion/07_pdf_tecnico_estruturado.md`
- `samples/manual validetion/10_documento_longo_modelagem_dados.md`

Persistencia final confirmada:

- collection `validation_real_20260519`
- `43` entradas vetoriais

### Corpus controlado

Arquivos temporarios:

- `data/results/validation_distributed_corpus/01_contexto_base.md`
- `data/results/validation_distributed_corpus/02_detalhe_operacional.md`
- `data/results/validation_distributed_corpus/03_restricao_arquitetural.md`

Conteudo distribuido de proposito:

- arquivo `01`: broker adotado
- arquivo `02`: equipe responsavel e prazo do runbook
- arquivo `03`: padrao Bronze/Silver/Gold

Persistencia final confirmada:

- collection `validation_ctrl_20260519`
- `3` entradas vetoriais

## Casos testados

### Caso 1 - Persistencia vetorial real

Comandos:

```powershell
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME='validation_real_20260519'
uv run free-plaud retrieval index "D:\Dev\Repos\Own\tcc-free-plaud\samples\manual validetion\04_ata_metadados_longos.txt"
uv run free-plaud retrieval index "D:\Dev\Repos\Own\tcc-free-plaud\samples\manual validetion\07_pdf_tecnico_estruturado.md"
uv run free-plaud retrieval index "D:\Dev\Repos\Own\tcc-free-plaud\samples\manual validetion\10_documento_longo_modelagem_dados.md"
```

Evidencia:

| note_id | chunks_indexed | vector_entries_count final |
| --- | ---: | ---: |
| `04-ata-metadados-longos` | `7` | `43` |
| `07-pdf-tecnico-estruturado` | `14` | `43` |
| `10-documento-longo-modelagem-dados` | `22` | `43` |

Veredito:

- embeddings persistidos corretamente: **sim**

### Caso 2 - Single-file retrieval vetorial

Pergunta:

> Qual message broker foi adotado como padrao da plataforma?

Comando:

```powershell
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME='validation_real_20260519'
uv run free-plaud retrieval semantic-search --query "Qual message broker foi adotado como padrao da plataforma?" --top-k 5 --note-id "04-ata-metadados-longos"
```

Top hit:

- `note_id`: `04-ata-metadados-longos`
- `chunk_id`: `04-ata-metadados-longos::v1::ofs-003400-004200::8c5b8714a7`
- `score`: `0.7218732923658913`
- `distance`: `0.3852846622467041`
- `matched_terms`: `message`, `broker`, `adotado`, `padrao`, `plataforma`
- `term_coverage`: `0.8333333333333334`
- `strategy`: `vector`

Veredito:

- chunk relevante recuperado: **sim**

### Caso 3 - Multi-chunk no mesmo arquivo

Pergunta:

> Qual message broker foi adotado e qual foi o prazo para o runbook de operacao?

Comando:

```powershell
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME='validation_real_20260519'
uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\samples\manual validetion\04_ata_metadados_longos.txt" --question "Qual message broker foi adotado e qual foi o prazo para o runbook de operacao?" --strategy hybrid
```

Resultado:

- `status`: `answer`
- `reason_for_no_answer`: `null`
- `used_sources.chunk_ids`:
  - `04-ata-metadados-longos::v1::ofs-003400-004200::8c5b8714a7`
  - `04-ata-metadados-longos::v1::ofs-001360-002160::9e38a9265b`
  - `04-ata-metadados-longos::v1::ofs-002040-002840::0f90f0a381`

Claims citados:

1. `Prazo para runbook de operacao: 15 de abril de 2025`
2. `RFC compara Apache Kafka, RabbitMQ e NATS`

Veredito:

- retrieval multi-chunk no mesmo arquivo: **sim**
- grounding/citations: **sim**

### Caso 4 - Multi-file retrieval vetorial no corpus real

Pergunta:

> Qual message broker foi adotado e qual padrao divide o pipeline nas camadas Bronze, Silver e Gold?

Comando:

```powershell
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME='validation_real_20260519'
uv run free-plaud retrieval semantic-search --query "Qual message broker foi adotado e qual padrao divide o pipeline nas camadas Bronze, Silver e Gold?" --top-k 8
```

Hits relevantes:

| rank | note_id | chunk_id | score | distance | matched_terms | term_coverage |
| ---: | --- | --- | ---: | ---: | --- | ---: |
| 1 | `04-ata-metadados-longos` | `04-ata-metadados-longos::v1::ofs-003400-004200::8c5b8714a7` | `0.6693983288917489` | `0.49389851093292236` | `message`, `broker`, `adotado`, `padrao` | `0.36363636363636365` |
| 2 | `10-documento-longo-modelagem-dados` | `10-documento-longo-modelagem-dados::v1::ofs-004080-004880::b2d73964a4` | `0.6566619091875318` | `0.522830069065094` | `pipeline`, `camadas`, `bronze`, `silver`, `gold` | `0.45454545454545453` |

Veredito:

- retrieval multi-file real: **sim**

### Caso 5 - Multi-file retrieval controlado

Pergunta:

> Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?

Comando:

```powershell
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME='validation_ctrl_20260519'
uv run free-plaud retrieval semantic-search --query "Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?" --top-k 6
```

Hits:

| rank | note_id | chunk_id | score | distance | matched_terms | term_coverage |
| ---: | --- | --- | ---: | ---: | --- | ---: |
| 1 | `03-restricao-arquitetural` | `03-restricao-arquitetural::v1::ofs-000000-000249::9664a7574a` | `0.7328838847648957` | `0.3644726276397705` | `padrao`, `divide`, `pipeline`, `bronze`, `silver`, `gold` | `0.4` |
| 2 | `02-detalhe-operacional` | `02-detalhe-operacional::v1::ofs-000000-000316::11ad43ca64` | `0.6792550517855975` | `0.47220104932785034` | `broker`, `equipe`, `ficou`, `runbook` | `0.26666666666666666` |
| 3 | `01-contexto-base` | `01-contexto-base::v1::ofs-000000-000310::2d2b81f98c` | `0.6535852097873602` | `0.530022382736206` | `message`, `broker`, `foi`, `adotado`, `padrao`, `pipeline` | `0.4` |

Veredito:

- retrieval distribuido controlado: **sim**

### Caso 6 - Hybrid multi-file em nivel de funcao

Observacao:

- nao existe CLI atual para `hybrid_search` multi-file
- o teste foi feito direto na funcao `hybrid_search` com chunks agregados dos 3 arquivos controlados

Resultado:

| rank | note_id | score | distance | matched_terms | term_coverage | strategy |
| ---: | --- | ---: | ---: | --- | ---: | --- |
| 1 | `03-restricao-arquitetural` | `0.04058699101004759` | `0.3644726276397705` | `padrao`, `divide`, `pipeline`, `bronze`, `silver`, `gold` | `0.4` | `hybrid` |
| 2 | `01-contexto-base` | `0.0404631798074421` | `0.530022382736206` | `message`, `broker`, `foi`, `adotado`, `padrao`, `pipeline` | `0.4` | `hybrid` |
| 3 | `02-detalhe-operacional` | `0.039938556067588324` | `0.47220104932785034` | `broker`, `equipe`, `ficou`, `runbook` | `0.26666666666666666` | `hybrid` |

Veredito:

- `hybrid` multi-file existe em nivel de funcao: **sim**
- `hybrid` multi-file exposto por CLI pronta: **nao**

### Caso 7 - Answer layer single-file funciona

Pergunta:

> Qual message broker foi adotado como padrao do pipeline?

Comando:

```powershell
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME='validation_ctrl_20260519'
uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\data\results\validation_distributed_corpus\01_contexto_base.md" --question "Qual message broker foi adotado como padrao do pipeline?" --strategy hybrid
```

Resultado:

- `status`: `answer`
- `answer`: `RabbitMQ ... message broker padrao`
- `chunk_id`: `01-contexto-base::v1::ofs-000000-000310::2d2b81f98c`
- `support_level`: `direct`

Veredito:

- answer com grounding e citacao: **sim**

### Caso 8 - Answer layer multi-file nao existe por design atual

Pergunta:

> Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?

Comandos:

```powershell
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME='validation_ctrl_20260519'
uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\data\results\validation_distributed_corpus\01_contexto_base.md" --question "Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?" --strategy vector
uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\data\results\validation_distributed_corpus\01_contexto_base.md" --question "Qual message broker foi adotado, qual equipe ficou responsavel pelo runbook e qual padrao divide o pipeline em Bronze, Silver e Gold?" --strategy hybrid
```

Resultado:

- `status`: `no_answer`
- `reason_for_no_answer`: `missing_named_anchor`
- `used_sources`: apenas `01-contexto-base`

Diagnostico:

- `retrieval ask <arquivo>` carrega uma unica `Note`
- na camada `rag.py`, retrieval vetorial/hibrido e filtrado com `note_id=note.note_id`
- portanto a resposta atual nao consulta corpus multi-documento

Veredito:

- answer multi-file: **nao implementado por design atual**

### Caso 9 - Falso positivo vetorial

Pergunta:

> Quais tecnologias o candidato domina para desenvolver apps mobile?

Comando:

```powershell
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME='validation_real_20260519'
uv run free-plaud retrieval semantic-search --query "Quais tecnologias o candidato domina para desenvolver apps mobile?" --top-k 5
```

Top hits:

| rank | note_id | score | distance | matched_terms | term_coverage |
| ---: | --- | ---: | ---: | --- | ---: |
| 1 | `07-pdf-tecnico-estruturado` | `0.6472515311601286` | `0.5449944138526917` | `domina` | `0.16666666666666666` |
| 2 | `04-ata-metadados-longos` | `0.6416948082635856` | `0.558373212814331` | nenhum | `0.0` |
| 3 | `10-documento-longo-modelagem-dados` | `0.640712315357925` | `0.560762882232666` | nenhum | `0.0` |

Veredito:

- busca vetorial aberta ainda traz falso positivo: **sim**

### Caso 10 - `no_answer` do answer layer

Pergunta:

> Quais tecnologias o candidato domina para desenvolver apps mobile?

Comando:

```powershell
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME='validation_real_20260519'
uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\samples\manual validetion\07_pdf_tecnico_estruturado.md" --question "Quais tecnologias o candidato domina para desenvolver apps mobile?" --strategy hybrid
```

Resultado:

- `status`: `no_answer`
- `reason_for_no_answer`: `insufficient_grounded_claims`

Veredito:

- filtro de grounding/no_answer funciona melhor que a busca vetorial crua: **sim**

## Diagnostico tecnico

### O que funciona hoje

- indexacao de arquivos suportados
- chunking deterministico com offsets
- persistencia vetorial em ChromaDB
- retrieval vetorial single-file
- retrieval vetorial multi-file
- retrieval multi-chunk no mesmo arquivo
- `hybrid` calibrado na suite de benchmark
- citations e grounding em perguntas respondiveis de uma unica nota
- `no_answer` em perguntas irrelevantes ou mal ancoradas

### O que funciona parcialmente

- retrieval distribuido multi-file: existe, mas depende de usar collection compartilhada e consulta aberta
- `hybrid` multi-file: existe em nivel de funcao, mas nao em CLI pronta
- ranking vetorial aberto: ainda aceita ruido semantico em perguntas irrelevantes

### O que nao existe hoje

- answer multi-file
- answer orchestration multi-document
- costura automatica de resposta a partir de multiplos arquivos no contrato atual de `retrieval ask`

## Veredito objetivo

1. embeddings estao persistidos corretamente?
   - **sim**
2. chunks estao recuperaveis?
   - **sim**
3. busca vetorial traz contexto semanticamente relacionado?
   - **sim**, inclusive em multi-file
4. retrieval multi-file existe de fato?
   - **sim**
5. answer multi-file existe de fato?
   - **nao**
6. o sistema atual ja se comporta como um RAG contextual distribuido funcional de producao?
   - **nao ainda**

## Conclusao

Conclusao correta desta auditoria:

> retrieval distribuido existe parcialmente no backend atual, mas answer orchestration multi-document ainda nao e suportada pelo desenho atual.

Em outras palavras:

- o banco vetorial funciona
- semantic retrieval multi-file funciona
- grounding local por nota funciona
- stitching real entre arquivos ainda nao existe no `ask`

## Proximo passo recomendado

Gargalo principal agora:

- **multi-document orchestration no answer layer**

Ordem recomendada:

1. introduzir um fluxo de `ask` baseado em corpus/index multi-documento
2. manter filtros de grounding e `no_answer`
3. so depois recalibrar ranking, se o stitching multi-file continuar fraco
