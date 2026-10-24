# Dataset multi_trecho_cobertura

Lote novo para medir cobertura de termos entre trechos (`benchmark coverage`, experimento 20). Usa as
**mesmas 7 notas** de `../multi_trecho/notas/`, referenciadas por caminho no `suite.json` (não copiadas).
Não altera `multi_trecho` nem `manual_validation`.

## O que tem aqui

| Arquivo | Conteúdo |
|---|---|
| `perguntas.json` | Arquivo mestre: 40 perguntas positivas no schema do `BenchmarkSample`. |
| `por_nota/<nota>.json` | Perguntas de cada nota primária (gerado por `gerar_splits.py`). |
| `suite.json` | Suite com 7 casos (nota de `multi_trecho` + split de `por_nota/`). Sem negativas. |
| `gerar_splits.py` | Regenera `por_nota/` a partir de `perguntas.json`. |
| `checar_termos.py` | Confere termos por nota, referência e a propriedade de junção. |

Testes: `pipeline/tests/test_multi_trecho_cobertura_dataset.py` e `pipeline/tests/test_coverage.py`.

## Tipos de pergunta

- `mt-nota-01` a `mt-nota-20` (`category: inferida`): dois termos da mesma nota, em chunks distintos.
  Conferido por script: nenhum chunk 800/120 contém os dois termos.
- `mt-notas-01` a `mt-notas-20` (`category: inferida`): termos de duas notas. `expected_note_id` é a primária;
  o campo `expected_terms_por_nota` diz qual termo vem de qual nota.

Campos extras de `perguntas.json`: `expected_terms_por_nota` (mapa nota -> termos). `expected_terms` é a união,
para o loader do benchmark. O checador exige que as duas coisas batam.

## Como foi construído

Mesmo procedimento do lote `multi_trecho`: termos copiados das notas, checados por script antes de qualquer
medição. Na primeira checagem, 4 `mt-nota` (`03`, `04`, `08`, `14`) cabiam num único chunk 800/120 e foram
trocadas por outro termo da mesma nota. Três perguntas vizinhas (`01`, `02`, `09`) foram reescritas para não
repetir termos entre perguntas próximas. Tudo antes de qualquer métrica; nada foi ajustado depois de ver número.

## Como rodar

Regenerar e conferir (a partir da raiz do repositório):

```bash
python3 data/datasets/multi_trecho_cobertura/gerar_splits.py
cd pipeline && uv run python ../data/datasets/multi_trecho_cobertura/checar_termos.py
```

Benchmark e cobertura (a partir de `pipeline/`, com modelo de embedding disponível): ver
`docs/experimentos/20_cobertura_entre_chunks.md`.
