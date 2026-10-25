# 20 - Cobertura de termos entre chunks (perguntas que juntam trechos)

## Status

Implementado e testado com dados fixos, sem modelo. **Nenhum número de qualidade existe ainda.** Todos os
resultados abaixo estão `NÃO MEDIDO` até alguém rodar `benchmark compare` na máquina com os modelos de
embedding. Esta entrega fecha a pendência 1 do experimento 19 no lado da métrica; a medição fica em aberto.

## Objetivo

Medir se o sistema recupera os trechos necessários para uma pergunta que junta informação de dois lugares.
Isso não é o que o scorer atual mede.

## Por que `_is_relevant` não serve para junção

`_is_relevant` (`pipeline/src/escolio/benchmark/runners.py`) exige que **um único chunk** 800/120 contenha
todos os `expected_terms`. Consequências no dataset `multi_trecho`:

- `mt-nota-*` (junta dois trechos distantes da mesma nota): pontua 0 por construção. Nenhum chunk tem os dois
  termos, mesmo que o top-k contenha os dois trechos certos.
- `mt-notas-*` (junta duas notas): `expected_terms` só tem termos da nota primária, porque o scorer não pode
  exigir termos de outra nota. O segundo trecho nunca entra na conta.

Por isso o `hit@3` de `mt-nota` é 0 mesmo quando o retrieval acerta tudo. Os números do README de
`multi_trecho` medem isso, não a capacidade de juntar trechos.

## Método

Arquivo: `pipeline/src/escolio/benchmark/coverage.py` (funções puras), com o subcomando em
`pipeline/src/escolio/benchmark/coverage_cli.py`. O scorer, `metrics.py` e os datasets `manual_validation` e
`multi_trecho` não foram alterados.

Para cada pergunta positiva e cada estratégia, dado o ranking `r_1..r_D` do corpus:

- **Cobertura@k**: fração dos `expected_terms` que aparecem na **união** dos textos de `r_1..r_k`. Comparação
  sem acento, sem caixa e com espaços colapsados (`_strip_accents` de `retrieval/search.py`).
- **Junção completa@k**: 1 se a cobertura@k é 1.0 (todos os termos na união), senão 0.
- **Grupo**: pelo prefixo do `sample_id` (`unica`, `mt-nota`, `mt-notas`); `todos` agrega os três.
- **IC 95%**: `bootstrap_ci` de `metrics.py` (percentil, 1000 reamostras, seed 0) sobre os valores por pergunta.

Fonte dos trechos:

- A **passada no corpus** do `compare` (`corpus.queries`), com profundidade 10 sobre todas as notas da suite, como
  o chat busca. É a única com profundidade suficiente para k=5 e k=10 e com notas misturadas.
- A passada por nota (`cases[].<estrategia>`) usa só o `top_k` do compare (3 por padrão), então não serve para
  k > 3 e não é usada aqui.
- O JSON do compare grava `char_start`/`char_end` de cada hit, não o texto. O texto é reconstruído da nota da
  suite com o mesmo `normalized_text.strip()` que o chunking usa. Nota do ranking fora da suite é erro, não zero.

Limites conhecidos:

- A união não é restrita à nota da pergunta. Um termo que aparece por acaso num trecho de outra nota conta como
  coberto. Os termos do lote são específicos (datas, siglas, valores), mas o viés existe e é de sentido positivo.
- A métrica mede cobertura de termos, não resposta correta. Um termo presente num trecho irrelevante conta.
- Sem negativas neste lote: a abstenção não é medida aqui (ela sai do `compare` normal).

## Lote novo: `data/datasets/multi_trecho_cobertura/`

Pelo `AGENTS.md`, mudar o scorer pede lote novo. O lote usa as **mesmas 7 notas** de `multi_trecho`, referenciadas
por caminho relativo no `suite.json` (não copiadas).

- 40 perguntas positivas: 20 `mt-nota-*` (dois termos da mesma nota) e 20 `mt-notas-*` (termos de duas notas;
  `expected_note_id` é a primária).
- `checar_termos.py` confere, por script, que cada termo está na nota indicada, que a referência existe na nota
  primária, que cada `mt-nota` **não** cabe num único chunk 800/120 e que cada `mt-notas` tem termos de duas notas.
  Resultado: 40/40.
- Ajuste de construção, feito **antes de qualquer métrica** e antes de qualquer `compare`: na primeira checagem,
  4 perguntas `mt-nota` (`03`, `04`, `08`, `14`) tinham os dois termos num único chunk e foram trocadas por outro
  termo da mesma nota. Três perguntas vizinhas (`01`, `02`, `09`) foram reescritas para não repetir termos entre
  perguntas próximas. Nenhuma pergunta foi alterada depois de ver número de recuperação.
- Sem negativas: o lote mede só junção. A suite não tem `negative_dataset_path`.

## Como rodar

A partir de `pipeline/`, com os modelos de embedding disponíveis:

```bash
uv sync --locked --dev --extra cpu
uv run python -m escolio benchmark compare --suite ../data/datasets/multi_trecho_cobertura/suite.json --export
```

O `compare` imprime o `comparison_id` e grava `data/results/<comparison_id>.json`. Depois:

```bash
uv run python -m escolio benchmark coverage \
  --results ../data/results/<comparison_id>.json \
  --suite ../data/datasets/multi_trecho_cobertura/suite.json \
  --k 3,5,10 \
  --saida ../data/results/cobertura_multi_trecho.json
```

`--workspace` padrão é a raiz do repositório (settings). O `--k` máximo não pode passar da profundidade gravada
(10). Para conferir o lote sem modelo:

```bash
cd pipeline && uv run python ../data/datasets/multi_trecho_cobertura/checar_termos.py
```

Testes sem rede e sem modelos: `pipeline/tests/test_coverage.py` (inclui um CLI com JSON fixture montado a partir
das notas reais) e `pipeline/tests/test_multi_trecho_cobertura_dataset.py`.

### Bloco `coverage` no JSON do compare (para o painel)

`benchmark compare --cobertura 3,5,10 --export` grava o bloco `coverage` no mesmo JSON, para a seção "Cobertura por
tipo de pergunta" do painel. Escolhas de leitura, para o número bater com a UI:

- **Uma profundidade:** o painel mostra um k só, então o bloco usa o maior da lista (10). A tabela completa, com
  todos os k, continua no subcomando `benchmark coverage`.
- **Contagens, não frações:** `single_chunk` e `across_chunks` são perguntas (a UI divide por `n`). `single_chunk`
  conta as perguntas com todos os termos num trecho só, da nota certa, no top-k (a régua antiga, `relevant_rank <= k`).
  `across_chunks` conta as perguntas em que a união do top-k cobre todos os termos (junção completa).
- **Uma estratégia:** a do chat (`default_ask_strategy` gravada no compare; `hybrid` sem ela).
- O bloco e o subcomando saem da mesma passada no corpus. Um teste confere que o `across_chunks` do bloco é igual
  ao `juncao_completa` do subcomando sobre o mesmo JSON (`pipeline/tests/test_compare_flags_cli.py`).

`NÃO MEDIDO`: o bloco existe e foi conferido com provedores falsos. Nenhum número de qualidade foi gerado.

## Resultados

| Medida | Estratégia | Grupo | k | Resultado |
|---|---|---|---|---|
| Cobertura média [IC 95%] | lexical / vector / hybrid | mt-nota | 3, 5, 10 | NÃO MEDIDO |
| Cobertura média [IC 95%] | lexical / vector / hybrid | mt-notas | 3, 5, 10 | NÃO MEDIDO |
| Junção completa [IC 95%] | lexical / vector / hybrid | mt-nota | 3, 5, 10 | NÃO MEDIDO |
| Junção completa [IC 95%] | lexical / vector / hybrid | mt-notas | 3, 5, 10 | NÃO MEDIDO |

## Interpretação

Ainda não há interpretação: nenhum número foi medido. O que já está estabelecido é a propriedade do lote (cada
`mt-nota` exige dois chunks distintos, conferido por script) e a propriedade da métrica (cobertura@k é monotônica
em k, e a junção completa só acontece quando a união do top-k contém todos os termos).

## Próximos passos

1. Rodar o `compare` com `--export` na máquina com GPU e registrar o `comparison_id` aqui.
2. Rodar o `coverage` com k=3,5,10 e preencher a tabela acima com média e IC.
3. Comparar com o `hit@3` do `_is_relevant` nos mesmos grupos, para mostrar a diferença que a métrica nova faz.
4. Se a cobertura de `mt-notas` ficar alta demais, checar se os termos do segundo trecho estão casando em trechos
   de outras notas (o viés da união, descrito acima).
