# 03 - Embeddings alternativos na suite baseline

## Status

Executado em 2026-04-22

## Objetivo

Comparar embeddings alternativos contra o baseline `800/120 + chroma-default` usando a mesma suite real do projeto.

## Pergunta experimental

Trocar apenas o embedding model, mantendo `chunk_size = 800` e `overlap = 120`, melhora o retrieval vetorial na suite real?

## Referencia de comparacao

Experimentos anteriores:

- `docs/experimentos/01_lexical_vs_vector_suite_baseline.md`
- `docs/experimentos/02_calibracao_retrieval_vetorial.md`

Baseline vetorial de referencia:

- `embedding_model = chroma-default`
- `chunk_size = 800`
- `overlap = 120`
- `vector MRR = 0.7916666666666666`
- `vector Recall@3 = 0.9375`

## Suite utilizada

- `data/datasets/manual_validation/suite.json`

## Modelos testados

1. `chroma-default`
2. `sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
3. `sentence-transformer:sentence-transformers/paraphrase-multilingual-mpnet-base-v2`

## Configuracao fixa

- `top_k = 3`
- `chunk_size = 800`
- `overlap = 120`

## Comando base

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json" --embedding-model "sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" --export
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json" --embedding-model "sentence-transformer:sentence-transformers/paraphrase-multilingual-mpnet-base-v2" --export
```

## Resultado agregado

| Embedding | Vector MRR | Vector Recall@3 | Observacao |
| --- | --- | --- | --- |
| `chroma-default` | `0.7916666666666666` | `0.9375` | melhor baseline vetorial desta rodada |
| `paraphrase-multilingual-MiniLM-L12-v2` | `0.6145833333333334` | `0.75` | pior que o baseline |
| `paraphrase-multilingual-mpnet-base-v2` | `0.53125` | `0.8125` | tambem pior que o baseline |

## Leitura por caso

### `case-04-ata`

- `chroma-default`: `MRR 1.0`
- `MiniLM multilingual`: `MRR 0.75`
- `MPNet multilingual`: `MRR 0.8333333333333334`

### `case-07-paper`

- `chroma-default`: `MRR 0.7083333333333334`
- `MiniLM multilingual`: `MRR 0.625`
- `MPNet multilingual`: `MRR 0.4583333333333333`

### `case-08-contrato`

- `chroma-default`: `MRR 0.8333333333333334`
- `MiniLM multilingual`: `MRR 0.4583333333333333`
- `MPNet multilingual`: `MRR 0.4583333333333333`

### `case-10-modelagem`

- `chroma-default`: `MRR 0.625`
- `MiniLM multilingual`: `MRR 0.625`
- `MPNet multilingual`: `MRR 0.375`

## Comandos e artefatos

Os relatórios desta rodada foram gerados em:

- `data/results/experiments/03_embeddings/baseline_chroma_default.json`
- `data/results/experiments/03_embeddings/baseline_chroma_default.csv`
- `data/results/experiments/03_embeddings/multilingual_minilm_l12_v2.json`
- `data/results/experiments/03_embeddings/multilingual_minilm_l12_v2.csv`
- `data/results/experiments/03_embeddings/multilingual_mpnet_base_v2.json`
- `data/results/experiments/03_embeddings/multilingual_mpnet_base_v2.csv`

## Interpretacao tecnica

Nesta suite e nesta configuracao de chunking, trocar o embedding model nao melhorou o retrieval vetorial.

Os dois modelos multilíngues testados ficaram abaixo do baseline `chroma-default`.

Isso muda a leitura anterior:

1. nao ha evidencia atual de que apenas trocar o embedding resolva o gap para `lexical`
2. o baseline `chroma-default` segue sendo a melhor opcao vetorial testada ate aqui
3. o proximo ganho provavelmente nao vira de um swap simples de embedding

## Conclusao atual

O resultado nao sustenta a hipotese de que o problema principal era apenas o embedding model.

Com a evidencia atual, o caminho mais forte deixa de ser “testar embeddings parecidos indefinidamente” e passa a ser:

- avaliar retrieval hibrido
- avaliar reranking
- ou testar um embedding mais forte e estruturalmente diferente, nao apenas outro sentence-transformer multilingual

## Proximos passos recomendados

1. manter `chroma-default` como baseline vetorial atual
2. preservar `chunk_size = 800` e `overlap = 120`
3. abrir o proximo ciclo experimental para `hybrid retrieval` ou `reranking`
