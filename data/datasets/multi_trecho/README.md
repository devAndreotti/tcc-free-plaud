# Dataset multi_trecho

Dataset novo para ampliar a avaliação de recuperação com perguntas que exigem juntar informação de
dois trechos. Não altera os datasets de `manual_validation`, cujos números dos experimentos 15 e 17
dependem deles.

## O que tem aqui

| Arquivo | Conteúdo |
|---|---|
| `notas/*.md` | 7 notas sintéticas em PT-BR, entre 1.950 e 2.614 caracteres cada |
| `perguntas.json` | Arquivo mestre: 60 perguntas (30 positivas + 30 negativas) no schema do `manual_validation` |
| `por_nota/<nota>.json` | Perguntas positivas de cada nota (gerado a partir de `perguntas.json`) |
| `negativas.json` | As 30 negativas (gerado a partir de `perguntas.json`), apontado por `negative_dataset_path` |
| `suite.json` | Suite com 7 casos (nota + dataset por nota) e o dataset de negativas |
| `gerar_splits.py` | Gera `por_nota/` e `negativas.json` a partir de `perguntas.json` |
| `checar_termos.py` | Confere que cada termo esperado e cada referência aparecem na nota esperada |

Teste: `pipeline/tests/test_multi_trecho_dataset.py`.

## Como as notas foram construídas

Notas fictícias: atas de reunião (Kafka, incidente de pagamentos), aulas (particionamento Parquet,
TCP), uma entrevista técnica e duas decisões técnicas (cache do catálogo, autenticação OIDC). Todas
têm datas explícitas em `dd/mm/aaaa`, fala coloquial, termos técnicos misturados com inglês e nomes
de pessoas fictícios. Nenhuma nota vem de dado real.

Cada pergunta positiva pertence a um destes tipos (o prefixo do `sample_id` indica o tipo):

- `unica-*` (10, `category: direta`): a resposta está em um trecho da nota.
- `mt-nota-*` (10, `category: inferida`): a resposta junta dois trechos distantes da mesma nota
  (separados por mais de 800 caracteres, sem caber num chunk 800/120).
- `mt-notas-*` (10, `category: inferida`): a pergunta junta informação de duas notas. O campo
  `expected_note_id` aponta para a nota primária, e `expected_terms` só tem termos dessa nota (ver
  limitações).

As 30 negativas (`mtneg-*`) não têm resposta em nenhuma nota. Várias citam pessoas reais do corpus
(Ana Lima Furtado, Júlia Neves, Larissa Quintela, Diego Sampaio, Heitor Rocha) ou entidades das notas
(cluster Kafka, gateway de pagamentos, Keycloak, prova de Redes). As demais são plausíveis mas não
estão nas notas, como o "incidente de 14/09/2025", quando o incidente foi em 09/09/2025.

### Checagem dos termos

`checar_termos.py` normaliza cada nota com o mesmo pipeline do benchmark (`load_document` +
`structure_document`) e confere, com a mesma comparação case-insensitive de `_contains_expected_terms`,
que cada `expected_terms` e cada `expected_ref` aparecem na nota de `expected_note_id`. Também registra,
só como informação, se todos os termos cabem num mesmo chunk 800/120.

Resultado da última execução: 30/30 perguntas positivas com termos e referências na nota esperada.

### Ajustes antes da primeira medição

Antes de rodar o benchmark, cinco perguntas `mt-nota-*` foram reescritas porque os dois termos ainda
cabiam num único chunk, o que não representa uma junção de trechos distantes. Os termos e a nota
continuaram os mesmos tipos, e a checagem foi rodada de novo depois. Nenhuma pergunta foi alterada
depois de ver números de recuperação.

## Composição

- 60 perguntas: 30 positivas (10 `unica`, 10 `mt-nota`, 10 `mt-notas`) e 30 negativas.
- Positivas por nota: ata-incidente-pagamentos 6, ata-migracao-kafka 6, decisao-cache-catalogo 5,
  decisao-autenticacao-oidc 4, aula-particionamento-parquet 3, aula-tcp-congestionamento 3,
  entrevista-backend-julia 3.

## Como rodar

Os caminhos do suite são relativos ao workspace, com a mesma convenção do `manual_validation`.
A partir de `pipeline/`:

```bash
uv sync --locked --dev --extra cpu
uv run python -m escolio benchmark compare --suite ../data/datasets/multi_trecho/suite.json --export
```

`compare` roda `lexical`, `vector` e `hybrid`, então exige um modelo de embeddings disponível
(`--embedding-model`). Ele também mede as negativas no cenário do chat (abstenção).

Para o modo lexical puro, sem embeddings, uma execução por nota:

```bash
uv run python -m escolio benchmark run ../data/datasets/multi_trecho/notas/ata-migracao-kafka.md \
  --dataset ../data/datasets/multi_trecho/por_nota/ata-migracao-kafka.json --strategy lexical
```

Repita para as outras seis notas (os nomes estão em `suite.json`). O resultado agregado da última
execução está em `data/results/multi_trecho_lexical.json`, que é ignorado pelo git.

Para regenerar os splits e conferir os termos:

```bash
python3 data/datasets/multi_trecho/gerar_splits.py
cd pipeline && uv run python ../data/datasets/multi_trecho/checar_termos.py
```

Depois de editar `perguntas.json`, rode `gerar_splits.py` de novo. O teste falha se os arquivos
derivados saírem de sincronia.

## Resultado lexical (top_k 3, chunk 800/120)

Medido com `benchmark run --strategy lexical` nas 7 notas, agregado por tipo de pergunta:

| Grupo | Perguntas | hit@3 | MRR |
|---|---|---|---|
| `unica` | 10 | 1.00 | 1.00 |
| `mt-nota` | 10 | 0.00 | 0.00 |
| `mt-notas` | 10 | 1.00 | 0.80 |

Leitura: o grupo `mt-nota` é 0 por construção, e não por falha de recuperação. A métrica exige que
um único chunk contenha todos os `expected_terms`, e esses dois trechos estão em chunks diferentes.
O grupo `mt-notas` parece perfeito, mas só testa a nota primária, porque o scorer não pode exigir
termos de outra nota. Os números **não** medem a capacidade de juntar trechos. Veja as limitações.

## Limitações (importantes)

1. O scorer atual (`_is_relevant` em `pipeline/src/escolio/benchmark/runners.py`) só aceita um chunk
   que contenha todos os termos. Por isso os 10 `mt-nota-*` não podem ser pontuados como acerto, e
   um sistema que recupere os dois trechos no top-k ainda aparece como erro. Medir junção exige
   mudar a métrica para aceitar cobertura de termos somada entre chunks do top-k. Isso mexe em
   `src/escolio` e ficou fora desta tarefa.
2. Para `mt-notas-*`, `expected_terms` precisa estar na nota esperada (regra da checagem), então o
   segundo trecho, que está em outra nota, não é pontuado. O grupo mede só a recuperação da nota
   primária.
3. O `run` por nota não mede abstenção. A abstenção sobre as 30 negativas só sai no `compare`, que
   exige o modelo de embeddings.
4. Este dataset é outro corpus e outra suite. Os números daqui não substituem os dos experimentos
   15 e 17, que dependem de `manual_validation`.
