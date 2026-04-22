# 02 - Calibracao de retrieval vetorial

## Status

Executado em 2026-04-22

## Objetivo

Calibrar o baseline vetorial do projeto contra a suite real, testando variacoes de `chunk_size`, `overlap` e `embedding_model`.

## Pergunta experimental

Quais configuracoes de chunking e embedding melhoram o retrieval vetorial o suficiente para aproximar ou superar o baseline lexical na suite real do projeto?

## Referencia de comparacao

Experimento anterior:

- `docs/experimentos/01_lexical_vs_vector_suite_baseline.md`

Baseline atual observado:

- `lexical`: `MRR 0.96875`, `Recall@3 1.0`
- `vector`: `MRR 0.7916666666666666`, `Recall@3 0.9375`

## Suite utilizada

- `data/datasets/manual_validation/suite.json`

## Hipoteses a testar

1. o `chunk_size` atual pode estar grande demais para algumas perguntas especificas
2. o `overlap` atual pode estar insuficiente para preservar contexto em chunks limítrofes
3. o `embedding_model = chroma-default` pode ser fraco para portugues brasileiro ou comparacoes mais semanticas

## Matriz inicial sugerida

### Variacoes de chunking

- `chunk_size = 400`, `overlap = 60`
- `chunk_size = 600`, `overlap = 90`
- `chunk_size = 800`, `overlap = 120`
- `chunk_size = 1000`, `overlap = 150`

### Variacoes de embedding

- `chroma-default`
- `__preencher_quando_houver_novo_embedding_1__`
- `__preencher_quando_houver_novo_embedding_2__`

## Comandos base

### Comparacao baseline

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json" --export
```

### Rodadas com variacao de chunking

```powershell
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json" --chunk-size 400 --overlap 60 --export
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json" --chunk-size 600 --overlap 90 --export
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json" --chunk-size 1000 --overlap 150 --export
```

## Tabela de preenchimento

| Rodada | Embedding | Chunk Size | Overlap | Lexical MRR | Vector MRR | Lexical Recall@3 | Vector Recall@3 | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | chroma-default | 800 | 120 | 0.96875 | 0.7916666666666666 | 1.0 | 0.9375 | baseline atual |
| 2 | chroma-default | 400 | 60 | 0.84375 | 0.6041666666666666 | 0.875 | 0.6875 | qualidade caiu forte; latencia vetorial melhorou |
| 3 | chroma-default | 600 | 90 | 0.96875 | 0.6666666666666666 | 1.0 | 0.8125 | melhor que 400/60, mas ainda pior que baseline |
| 4 | chroma-default | 1000 | 150 | 0.875 | 0.6875 | 1.0 | 0.875 | recuperou parte da qualidade, mas nao passou 800/120 |

## Leitura por caso

Registrar especialmente:

- quais casos continuam favorecendo `lexical`
- quais casos aproximam `vector` do lexical
- se existe algum documento em que `vector` passa o lexical
- se a perda do `vector` esta concentrada em perguntas muito especificas

### Observacoes desta rodada

- `case-04-ata`: o `vector` ficou forte em quase todas as configuracoes e igualou o lexical no baseline `800/120`
- `case-07-paper`: continuou favorecendo `lexical` em todas as variacoes; piorou bastante com `400/60`
- `case-08-contrato`: `vector` se manteve utilizavel, mas lexical continuou melhor ou igual
- `case-10-modelagem`: segue sendo o caso mais dificil para `vector`, especialmente em perguntas estruturais e especificas

Nao houve caso em que o `vector` tenha se tornado globalmente melhor que o `lexical` na suite.

## Criterio de decisao

O experimento deve responder:

1. vale mudar `chunk_size` ou `overlap` como novo baseline?
2. o problema principal esta no chunking ou no embedding?
3. o proximo passo deve ser trocar embedding ou introduzir reranking?

## Resultado final

Entre as configuracoes testadas, `chunk_size = 800` e `overlap = 120` continuam sendo o melhor baseline vetorial do projeto.

Leitura principal:

1. reduzir demais o chunk (`400/60`) derruba a qualidade de `lexical` e `vector`
2. `600/90` melhora em relacao a `400/60`, mas ainda perde para `800/120`
3. `1000/150` recupera parte da qualidade, mas tambem nao supera o baseline
4. o problema principal do retrieval vetorial atual parece estar mais ligado ao `embedding_model` do que ao chunking

Conclusao desta rodada:

- manter `800/120` como baseline atual
- nao trocar chunking agora
- priorizar teste com embeddings alternativos antes de qualquer reranking

## Artefatos gerados

- `data/results/experiments/02_calibracao/baseline_800_120.json`
- `data/results/experiments/02_calibracao/baseline_800_120.csv`
- `data/results/experiments/02_calibracao/small_400_60.json`
- `data/results/experiments/02_calibracao/small_400_60.csv`
- `data/results/experiments/02_calibracao/medium_600_90.json`
- `data/results/experiments/02_calibracao/medium_600_90.csv`
- `data/results/experiments/02_calibracao/large_1000_150.json`
- `data/results/experiments/02_calibracao/large_1000_150.csv`

## Proximos passos

1. testar um embedding alternativo mais adequado a portugues/multilingue
2. rerodar a mesma suite com o novo embedding
3. comparar contra o baseline `800/120 + chroma-default`
4. so considerar reranking depois dessa troca de embedding
