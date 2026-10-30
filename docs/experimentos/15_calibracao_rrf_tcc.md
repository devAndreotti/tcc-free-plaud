# Experimento 15: Calibração de RRF e Avaliação Multi-Estratégia no AutoRAG

> **AVISO DE PROVENIÊNCIA NÃO VERIFICADA (verificado em 2026-10-25, código do commit `4e18932`).**
>
> - **Proveniência não verificada.** Nenhum script, config `autorag`, saída em `data/results`, teste ou notebook do repositório gera os números desta página. O único artefato é este arquivo, introduzido no commit `88e4fc8` (2026-09-08). Detalhes na seção "Verificação de proveniência" abaixo.
> - **Números não reproduzidos.** Não reproduzi nenhum dos valores desta tabela: nem na suíte atual (`manual_validation`, 10 notas, 39 perguntas positivas), nem na suíte de 4 casos que existia no commit `88e4fc8`, nem com o código desse commit, nem nas variações de `k` e `top_k` testadas.
> - **Diverge do Experimento 17.** Na suíte atual, a mesma estratégia híbrida (RRF, k=60) tem **MRR 0,942** na passada no corpus (`run_corpus_benchmark`, profundidade 10). Esse número foi medido no exp. 17 (2026-10-19) e reproduzido aqui em 2026-10-25.
> - **Sem suíte, profundidade ou IC declarados.** A tabela abaixo não diz qual suíte, qual `top_k` nem qual número de consultas foi usado, e não traz intervalo de confiança.
> - **Recall incompatível com a suíte.** Os valores de Recall@3 e @5 só podem ser frações k/N com N=200 (entre N≤300). Não são frações de 39 nem de 16 consultas (cálculo abaixo).
>
> Até que alguém reproduza ou retire estes números, este experimento vale só como registro histórico. Não cite a tabela abaixo como resultado validado. A pendência está em `docs/experimentos/README.md`.

## Verificação de proveniência (2026-10-25)

### O que se sabe

| Afirmação | Fonte verificada | Situação |
|---|---|---|
| MRR, Recall@3, Recall@5 e latência da tabela | Somente este arquivo (`git log --follow`: único commit `88e4fc8`) | Não reproduzido |
| Suíte, número de consultas, profundidade do ranking, IC | Não declarados em nenhum lugar | Ausente |
| Script, config ou saída que gera a tabela | Não existe no repositório, em nenhum commit de `git log --all` | Ausente |
| `data/results/...` citado em docs 02 e 03 | Pasta ignorada pelo `.gitignore` e nunca commitada (`git log --all -- data/results` vazio) | Ausente |
| Os mesmos números aparecem no TCC | `9c0a7a0` (2026-09-08) e `13756e7` (2026-09-09) em `docs/tcc/texto/TCC.md` | Cópia, não nova medição |
| Vetorial é "ChromaDB + SentenceTransformers" (linha 4) | `pipeline/src/escolio/providers/embed.py:22`: a configuração usada é `chroma-default` (ONNX `all-MiniLM-L6-v2` do próprio Chroma) | Diverge do código |
| "+7,2% MRR" sobre léxico e "+8,9%" sobre vetorial | 0,884 - 0,812 = 0,072 e 0,884 - 0,795 = 0,089: são diferenças absolutas em pontos. As relativas são +8,9% e +11,2% | Unidade trocada |
| "< 1 ms" de sobrecarga do RRF | Sem método de medição declarado. Na própria tabela, híbrido - vetorial = 41,8 - 34,2 = 7,6 ms | Não verificável |
| `k_rrf` e `fp benchmark run --k-rrf` (specs `001-featurename-autorag-rerank`, tasks T006 a T007) | Não existem no código de `88e4fc8` (`git grep k_rrf 88e4fc8` só encontra as specs). O parâmetro real é `rank_constant` / `hybrid_rank_constant` | Spec diverge do código |

### Recall e o tamanho da suíte

Cada Recall@k agregado é uma fração k/N, onde N é o número de consultas. Testei todos os 10 valores de Recall@3 e @5 da tabela (lexical, vetorial e híbrido com k=10, 60 e 100) contra N de 1 a 300:

- N=16 (suíte de 4 casos de `88e4fc8`): 0 de 10 valores possíveis.
- N=39 (suíte atual, 39 perguntas positivas): 0 de 10 valores possíveis.
- N=73 (39 positivas mais 34 negativas): 1 de 10.
- N=200: 10 de 10. É o único N até 300 em que todos aparecem.

Inferência, não verificada: o exp. 15 pode ter usado ~200 consultas, ou uma média por caso, ou outra agregação. Não há nada no repositório que indique qual.

### Reprodução medida neste ambiente

Ambiente: Linux, Python 3.12 via `uv`, commit de código `4e18932` (branch `worktree-agent-a3b38638ddb6ae48e`), executado em 2026-10-25 (UTC). Embedding `chroma-default`, chunk 800, overlap 120. Modelo ONNX já estava em cache (`/root/.cache/chroma/onnx_models/all-MiniLM-L6-v2`, criado em 2026-10-24); nada foi baixado nesta sessão. Saídas JSON em `data/results/repro_exp15/` (ignorado pelo git).

Comando base: `cd pipeline && uv run python -m escolio benchmark compare --suite ../data/datasets/manual_validation/suite.json`

**A. Suíte atual (10 notas, 39 positivas, 34 negativas), padrões do código: `top_k=3`, k=60, pesos 1.5/1.0, pools 9/24**

| Passada | Estratégia | MRR | Recall@3 | Recall@5 | Recall@10 | nDCG@10 |
|---|---|---|---|---|---|---|
| Por nota (`run_benchmark`, `top_k=3`) | lexical | 0.9103 | 1.0 | 1.0 | 1.0 | 0.9338 |
| Por nota | vetorial | 0.8162 | 0.9231 | 0.9231 | 0.9231 | 0.8434 |
| Por nota | híbrido | 0.9145 | 1.0 | 1.0 | 1.0 | 0.9365 |
| Corpus (`run_corpus_benchmark`, depth 10) | lexical | 0.9139 | 0.9744 | 0.9744 | 1.0 | 0.9356 |
| Corpus | vetorial | 0.9359 | 1.0 | 1.0 | 1.0 | 0.9527 |
| Corpus | **híbrido** | **0.9423** | 0.9744 | 1.0 | 1.0 | 0.9570 |

A passada no corpus reproduz o MRR 0,942 do exp. 17 (lexical 0,914, vetorial 0,936, híbrido 0,942). As latências médias variaram entre execuções (híbrido por nota: 16,8 ms no run padrão e 31,7 ms no run k=60 com pesos 1/1), por isso não as comparo com as da tabela original.

**B. Varredura de `k` e `top_k` (pesos 1.0/1.0 quando indicado)**

| Configuração | Híbrido por nota: MRR | Híbrido por nota: Recall@3 | Híbrido corpus: MRR |
|---|---|---|---|
| k=10, pesos 1.0/1.0 | 0.8932 | 0.9744 | 0.9423 |
| k=60, pesos 1.0/1.0 | 0.8932 | 0.9744 | 0.9423 |
| k=100, pesos 1.0/1.0 | 0.8932 | 0.9744 | 0.9423 |
| k=60, pesos 1.0/1.0, `top_k=10` | 0.8996 | 0.9744 | 0.9423 |

Com pesos 1.0/1.0, o MRR por nota não muda com k entre 10, 60 e 100. A curva 0,865 / 0,884 / 0,871 do exp. 15 não aparece em nenhuma configuração testada. Nenhuma das configurações chega a 0,884.

**C. Suíte de 4 casos de `88e4fc8` (16 consultas), datasets e documentos byte-idênticos aos de `88e4fc8`**

| Código | Léxica MRR / R@3 | Vetorial MRR / R@3 | Híbrida MRR / R@3 |
|---|---|---|---|
| `4e18932` (HEAD) | 0.96875 / 1.0 | 0.71875 / 0.875 | 0.9375 / 0.9375 |
| `88e4fc8` (código do exp. 15, executado com o Python do venv de HEAD) | 0.96875 / 1.0 | 0.78125 / 0.9375 | 0.96875 / 1.0 |
| Exp. 15 (não reproduzido) | 0.812 / 0.840 | 0.795 / 0.820 | 0.884 / 0.915 |

A léxica da suíte de 4 casos (0,96875) bate com o exp. 01 e o exp. 07. O vetorial (0,79167 no exp. 01) e o híbrido mudam entre o código de `88e4fc8` e o de HEAD. Nenhum dos dois códigos produz os valores do exp. 15.

Ambiente da execução de `88e4fc8`: `uv sync --locked --dev --extra audio --extra cpu` falhou porque esses extras não existem no `pyproject` daquele commit. `uv sync --locked --dev` também falhou (`No space left on device`: o lock puxa torch com CUDA e restavam 1,7 GB). A execução usou `PYTHONPATH=<snapshot>/pipeline/src` com o Python do venv de HEAD, via `from free_plaud.cli import app`, porque `python -m free_plaud` não existe. As dependências são as de HEAD, não as de `88e4fc8`.

### Causa da divergência (evidência do código)

1. **Suíte.** Em `88e4fc8`, `data/datasets/manual_validation/suite.json` tinha 4 casos (`04_ata`, `07_paper`, `08_contrato`, `10_modelagem`, 16 consultas). Em `87d98f5` (2026-10-08) passou a ter 10 casos, com negativas e IC bootstrap. O exp. 15 não declara qual suíte usou, e nenhuma das duas reproduz seus números (tabelas A e C).
2. **Profundidade e passada.** `run_benchmark` (`pipeline/src/escolio/benchmark/runners.py`, linha 289) busca `top_k` trechos por nota, com `top_k=3` por padrão (`cli.py`, linha 175). `run_corpus_benchmark` (linha 423) busca no corpus inteiro com `CORPUS_RETRIEVAL_DEPTH = 10` (linha 54), que é a mesma busca do chat. O exp. 17 usa a passada no corpus. Os arquivos `run_single.py` e `run_corpus.py` citados na tarefa não existem: as funções são as acima. A passada por nota dá híbrido 0,9145 e a passada no corpus dá 0,9423. Nenhuma das duas dá 0,884.
3. **Pesos.** `DEFAULT_HYBRID_LEXICAL_WEIGHT = 1.5` (`pipeline/src/escolio/retrieval/search.py`, linha 11), já presente em `88e4fc8` (calibrado no exp. 07, 2026-05-17). Com pesos 1.0/1.0, o híbrido por nota cai para 0,8932. O exp. 15 não declara o peso usado.
4. **Sensibilidade a k.** Com pesos iguais, k=10, 60 e 100 dão o mesmo MRR nas quatro casas decimais (tabela B). A variação entre k que o exp. 15 reporta não aparece.
5. **Código.** O vetorial e o híbrido da suíte de 4 casos mudam entre `88e4fc8` e HEAD (tabela C). Os números do exp. 15 podem vir de um estado do código que não está mais no histórico, mas não há nenhum artefato que mostre isso.

### Pendência

Para fechar este experimento é preciso um dos dois: (a) achar o script, a saída ou o registro que gerou a tabela e declarar suíte, N de consultas, `top_k`, pesos e IC; ou (b) refazer a medição com a suíte atual e substituir a tabela, mantendo esta seção como histórico. Até lá, os números desta página ficam marcados como não reproduzidos.

---

## Conteúdo original (sem alterações)

## Objetivo
Avaliar empiricamente o impacto da constante de suavização $k$ no Reciprocal Rank Fusion (RRF) em comparação com as estratégias isoladas léxica (SQLite FTS5 BM25) e vetorial (ChromaDB + SentenceTransformers).

## Metodologia & Dataset
- **Coleção de Teste**: Suite de benchmark com notas pessoais estruturadas em português brasileiro (PT-BR).
- **Métricas Analisadas**: Mean Reciprocal Rank (MRR), Recall@3, Recall@5 e Latência Média (ms).
- **Configurações Avaliadas**:
  1. `Lexical-Only` (BM25 FTS5 puro)
  2. `Vector-Only` (ChromaDB cosine similarity)
  3. `Hybrid RRF (k=10)`
  4. `Hybrid RRF (k=60)` (Baseline padrão)
  5. `Hybrid RRF (k=100)`

## Resultados Obtidos

> Números não reproduzidos e sem proveniência verificada. Ver o aviso no topo e a seção "Verificação de proveniência".

| Estratégia | MRR | Recall@3 | Recall@5 | Latência Média (ms) |
|---|---|---|---|---|
| **Lexical-Only (BM25)** | 0.812 | 0.840 | 0.880 | ~8.4 ms |
| **Vector-Only (Chroma)** | 0.795 | 0.820 | 0.865 | ~34.2 ms |
| **Hybrid RRF (k=10)** | 0.865 | 0.890 | 0.930 | ~42.5 ms |
| **Hybrid RRF (k=60)** | **0.884** | **0.915** | **0.950** | ~41.8 ms |
| **Hybrid RRF (k=100)** | 0.871 | 0.900 | 0.940 | ~42.0 ms |

## Análise e Conclusões para o TCC
1. **Superioridade do Híbrido**: A fusão RRF com $k=60$ superou tanto a busca puramente léxica (+7.2% MRR) quanto a puramente semântica (+8.9% MRR).
2. **Robustez do $k=60$**: O amortecimento $k=60$ mitiga termos com alta pontuação vetorial espúria sem desfavorecer palavras-chave exatas de notas técnicas.
3. **Viabilidade Local-First**: A sobrecarga de latência adicional do RRF em memória foi de < 1 ms sobre o tempo de embedding do ChromaDB, mantendo a resposta total interativa.
