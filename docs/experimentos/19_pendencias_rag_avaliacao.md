# 19 - Pendências da rodada reranker / extração / faithfulness / multi-trecho

## Status

Implementado e testado com provedores falsos. **Nada foi medido com modelo real.** Esta rodada foi feita em um
container sem Ollama e sem os modelos baixados, então nenhum número de qualidade (MRR, Recall, faithfulness,
comparação de modelos) existe ainda. Cada resultado abaixo está `NÃO MEDIDO` até alguém rodar na máquina com GPU.

## O que entrou

| Item | Onde | Padrão |
| --- | --- | --- |
| Reranker cross-encoder | `retrieval/rerank.py`, `corpus/ask.py`, `benchmark compare --rerank-model` | desligado (`rerank_model` vazio) |
| Extração estruturada (decisões, ações, tópicos) | `notes/extraction.py`, ligada em `corpus/service.py` | desligada (`extract_structure = false`) |
| Faithfulness com juiz LLM | `benchmark/faithfulness.py`, `benchmark faithfulness` | fora do gate, offline |
| Comparação de modelos de resposta | `benchmark/model_compare.py`, `benchmark compare-models` | manual |
| Dataset multi-trecho | `data/datasets/multi_trecho/` (60 perguntas) | manual |

## Decisão de revisão: `score` não é sobrescrito pelo reranker

O primeiro rascunho gravava o logit do cross-encoder em `SearchHit.score`. `corpus/ask.py` e `retrieval/rag.py`
comparam `score` com limiares calibrados na escala RRF/vetor (`min_vector_score`, `support_direct_score`). Ligar o
reranker moveria a decisão de abstenção sem ninguém perceber. O logit agora vai em `SearchHit.rerank_score` e o
`score` fica intacto.

## Pendências (em ordem de valor para o TCC)

1. **Métrica não mede perguntas que juntam trechos.** `_is_relevant` (`benchmark/runners.py`) exige todos os
   `expected_terms` num único chunk de 800/120. No dataset `multi_trecho`:
   - `unica` (10): pontuável.
   - `mt-nota` (10): 0 por construção, nenhum chunk tem os dois termos.
   - `mt-notas` (10): só a nota principal é cobrada, o segundo trecho nunca entra na conta.
   Falta uma métrica de cobertura de termos somada entre os chunks do top-k. Pelo `AGENTS.md`, mudar o scorer
   exige criar um lote novo de perguntas; o lote atual não deve ser ajustado depois de ver métricas.
2. **Ablação com modelo real (na máquina com GPU):**
   ```bash
   python -m escolio benchmark compare --suite ../data/datasets/manual_validation/suite.json --export
   python -m escolio benchmark compare --suite ../data/datasets/manual_validation/suite.json --rerank-model BAAI/bge-reranker-v2-m3 --export
   ```
   Reportar MRR, Recall@k e F1 de abstenção com IC bootstrap. `NÃO MEDIDO`.
3. **Faithfulness real.** Gerar os JSONs com `--registrar-respostas` (os antigos, como `bench_qchat.json`, não têm
   resposta nem trechos) e rodar `benchmark faithfulness` com um juiz forte. Commitar os JSONs com `git add -f`
   (`data/results/` está no `.gitignore`). `NÃO MEDIDO`.
4. **Comparar qchat (3B) com 7B:** `benchmark compare-models`. `NÃO MEDIDO`.
5. **Reconciliar números dos experimentos 15 e 17.** O exp. 15 reporta MRR 0,884 (híbrido, k=60) e o exp. 17 reporta
   0,942 para a mesma estratégia. Provavelmente suítes ou profundidades diferentes; confirmar antes de citar.
   O exp. 15 também não traz IC nem a suíte usada.
6. **Guarda do estruturador é fraca.** `lexical_groundedness >= 0,5` aceita item que reorganiza fatos reais. Tópicos
   não passam por guarda. Considerar checar a entidade (nome, data) separadamente e usar o juiz de faithfulness.
7. **Camadas.** `notes/extraction.py` importa `_content_tokens` privado de `benchmark/metrics.py`; promover a
   utilitário compartilhado. `benchmark/faithfulness.py` importa três helpers privados de `providers/answer.py`.
8. **Extração usa `get_settings()` global**, não as settings resolvidas da vault, no caminho em lote.
9. **Faithfulness tem viés conhecido.** Chunk citado fora dos hits de profundidade 10 some do contexto e a afirmação
   conta como não suportada. A divisão em sentenças quebra em abreviações (`Dr.`).
10. **Dívida de tamanho.** `benchmark/runners.py` (~750 linhas), `corpus/service.py` (~2.000) e `corpus/ask.py`
    (~980) passam do `maxFileLines: 300` de `.quality-gate/policy.json`.
11. **Fora do que foi pedido, mas apontado na análise:** o áudio descarta timestamps e locutores antes do chunking
    (`load_document` entrega só `cleaned_text`), e o chunking por janela de caracteres corta no meio de falas.
    Nenhum conjunto de avaliação cobre transcrição de áudio.

## Como validar sem modelo

`uv run pytest` e `uv run ruff check src tests` rodam tudo com provedores falsos (9 testes de
`test_audio_capture.py` precisam de `libportaudio2`, que o CI instala).
