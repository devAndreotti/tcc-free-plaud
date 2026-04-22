# 01 - Lexical vs Vector na suite baseline

## Objetivo

Registrar a primeira comparacao reproduzivel entre retrieval `lexical` e `vector` usando a suite real de validacao manual do projeto.

## Pergunta experimental

Com a implementacao atual do backend, o retrieval vetorial baseline com `chroma-default` supera ou nao o baseline lexical na suite real do projeto?

## Suite utilizada

- `data/datasets/manual_validation/suite.json`

Casos incluidos:

- `04_ata_metadados_longos`
- `07_pdf_tecnico_estruturado`
- `08_pdf_problematico_contrato`
- `10_documento_longo_modelagem_dados`

## Comando executado

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json" --export
```

## Configuracao

- `top_k = 3`
- `chunk_size = 800`
- `overlap = 120`
- `embedding_model = chroma-default`
- comparacao entre `lexical` e `vector`

## Resultado agregado

### Lexical

- `MRR = 0.96875`
- `Recall@3 = 1.0`
- `Recall@5 = 1.0`
- `Recall@10 = 1.0`
- `avg_query_latency_ms = 86.375`

### Vector

- `MRR = 0.7916666666666666`
- `Recall@3 = 0.9375`
- `Recall@5 = 0.9375`
- `Recall@10 = 0.9375`
- `avg_query_latency_ms = 1180.0`

## Leitura tecnica

Nesta rodada, o baseline lexical superou o baseline vetorial tanto em qualidade quanto em latencia.

Isso e importante por tres motivos:

1. o retrieval vetorial ja esta operacional, mas ainda nao e o melhor baseline do projeto
2. o embedding `chroma-default` e suficiente para infraestrutura, mas nao pode ser tratado como melhor escolha experimental
3. a suite real do projeto ja consegue mostrar diferenca entre estrategias, entao ela e util para calibracao posterior

## Casos observados

- `04_ata_metadados_longos`: lexical e vector ficaram fortes
- `07_pdf_tecnico_estruturado`: os dois recuperaram bem, mas lexical manteve MRR melhor
- `08_pdf_problematico_contrato`: os dois recuperaram bem, lexical ainda ficou melhor
- `10_documento_longo_modelagem_dados`: vector sofreu mais, especialmente em perguntas com maior especificidade estrutural

## Conclusao atual

O resultado atual nao autoriza afirmar que o retrieval vetorial baseline do projeto ja supera o lexical.

No estado atual, o uso mais correto deste experimento e:

- provar que a comparacao entre estrategias ja e reproduzivel
- usar o lexical como baseline forte
- usar o vector atual como baseline funcional, mas ainda em calibracao

## Proximos passos recomendados

1. variar `chunk_size` e `overlap`
2. testar embeddings alternativos mais adequados a portugues/multilingue
3. observar em quais casos o `vector` perde no rank
4. so depois considerar reranking

## Artefatos gerados

- relatorio JSON exportado pelo comando `benchmark compare`
- relatorio CSV exportado pelo comando `benchmark compare`
- datasets em `data/datasets/manual_validation/`
