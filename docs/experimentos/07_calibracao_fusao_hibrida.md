# 07 - Calibracao de fusao hibrida

## Status

Executado e encerrado em 2026-05-17

## Objetivo da rodada

Calibrar apenas o peso lexical da busca `hybrid`, mantendo:

- `chunk_size = 800`
- `overlap = 120`
- `top_k = 3`
- `rank_constant = 60`
- `vector_weight = 1.0`
- pools automaticos

Pergunta experimental:

> aumentar o peso do ranking lexical reduz o gap de `MRR` entre `hybrid` e `lexical` sem perder `Recall@3 = 1.0`?

## Suite utilizada

- `data/datasets/manual_validation/suite.json`
- `4` documentos
- `16` queries

## Baseline antes da rodada

Resultado anterior da suite real:

| Estrategia | MRR | Recall@3 |
| --- | --- | --- |
| `lexical` | `0.96875` | `1.0` |
| `vector` | `0.7916666666666666` | `0.9375` |
| `hybrid` | `0.9375` | `1.0` |

Leitura:

- `hybrid` ja recuperava cobertura
- gap restante era de ordenacao no topo

## Configuracao fixa

- `chunk_size = 800`
- `overlap = 120`
- `top_k = 3`
- `hybrid_rank_constant = 60`
- `hybrid_vector_weight = 1.0`
- `hybrid_lexical_pool = 9`
- `hybrid_vector_pool = 24`

## Comando base

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json" --chunk-size 800 --overlap 120 --top-k 3 --hybrid-rank-constant 60 --hybrid-lexical-weight 1.5 --hybrid-vector-weight 1.0
```

## Rodada 1 - peso lexical

| rank_constant | lexical_weight | vector_weight | lexical_pool | vector_pool | hybrid MRR | hybrid Recall@3 | avg_query_latency_ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `60` | `1.0` | `1.0` | `9` | `24` | `0.9375` | `1.0` | `816.6875` |
| `60` | `1.1` | `1.0` | `9` | `24` | `0.9375` | `1.0` | `690.3125` |
| `60` | `1.25` | `1.0` | `9` | `24` | `0.9375` | `1.0` | `727.875` |
| `60` | `1.5` | `1.0` | `9` | `24` | `0.96875` | `1.0` | `729.5625` |

## Resultado vencedor

Combinacao vencedora da Rodada 1:

- `rank_constant = 60`
- `lexical_weight = 1.5`
- `vector_weight = 1.0`
- `lexical_pool = 9`
- `vector_pool = 24`

Resultado:

- `hybrid MRR = 0.96875`
- `hybrid Recall@3 = 1.0`

## Interpretacao

Nesta suite, aumentar o peso lexical para `1.5` foi suficiente para:

1. manter a cobertura total da estrategia `hybrid`
2. eliminar o gap de `MRR` contra `lexical`
3. melhorar ordenacao no topo sem precisar ainda de reranking

Tambem ficou claro que:

- `1.0`, `1.1` e `1.25` nao mudaram o ranking agregado
- o salto relevante apareceu apenas em `1.5`
- a latencia media de `hybrid` continua acima de `lexical`, mas a rodada atual buscava prioridade de ordenacao

## Conclusao final do experimento

Rodada 1 encerrou com evidencia suficiente para considerar a fusao calibrada.

Estado atual apos calibracao:

- `lexical`: `MRR 0.96875`, `Recall@3 1.0`
- `hybrid` calibrado: `MRR 0.96875`, `Recall@3 1.0`

Decisao tomada:

1. promover `lexical_weight = 1.5` como padrao do projeto para `hybrid`
2. manter `vector_weight = 1.0`
3. manter `rank_constant = 60`
4. dispensar Rodada 2 nesta fase

## Proximo passo recomendado

Encerrar este experimento e seguir para proximo ciclo de retrieval apenas se surgir nova hipotese forte.

Nesta fase:

- `lexical_weight = 1.5` vira baseline default do `hybrid`
- Rodada 2 fica dispensada
- branch `feat/hybrid-retrieval` fica pronta para merge
