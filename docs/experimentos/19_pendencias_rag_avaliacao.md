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
   python -m escolio benchmark compare --suite ../data/datasets/manual_validation/suite.json --rerank-model BAAI/bge-reranker-v2-m3 --com-baseline --export
   ```
   A segunda linha roda a suíte sem e com o reranker (o principal é o sem) e grava `reranked` e `baseline_ci` no
   mesmo JSON. Reportar MRR, Recall@k e F1 de abstenção com IC bootstrap. `NÃO MEDIDO`.
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

## Atualização: segunda rodada

Entraram depois da primeira versão deste documento (tudo ainda `NÃO MEDIDO` com modelo real):

- **Pendência 1 (métrica entre chunks):** `benchmark/coverage.py` e `benchmark coverage`, com o lote novo
  `data/datasets/multi_trecho_cobertura/` (doc 20). A métrica antiga não foi alterada.
- **Pendência 7 (camadas):** `text_tokens.py` compartilhado e helpers públicos em `providers/answer.py`.
- **Pendência 10 (tamanho):** `benchmark/runners.py` caiu de 737 para 74 linhas (fachada). `corpus/ask.py`
  ainda tem ~820 linhas e `corpus/service.py` ~2.000: continuam acima de 300.
- **Chunking por segmento de fala** (doc 21): `t_start`/`t_end` no chunk e na citação. O `content_hash` de notas de
  áudio com segmentos muda, então elas são reindexadas uma vez.
- **Painel de Benchmark (UI):** seções opcionais de ablação, cobertura e faithfulness. O JSON do `compare` passa a
  gravar esses blocos, opt-in: `--com-baseline` (`reranked` e `baseline_ci`), `--cobertura` (`coverage`) e
  `benchmark faithfulness --mesclar-em` (`faithfulness`). Sem as flags o JSON não muda (teste de regressão com
  golden). Limite: o `runBenchmarkCompare` da UI passa por `benchmark/service.py`, que ainda não recebe essas flags,
  então o painel não mostra as seções nessa rota. Só o JSON do CLI as traz. Veja `docs/experimentos/20` e `18`.
- **Grafo (UI):** seleção por clique com vizinhança em destaque, aviso quando o modo Links não tem ligações, rótulos do
  nó selecionado e dos vizinhos, cor automática por pasta de 1º nível (sem colisão entre até 8 pastas), legenda e
  abertura animada (respeita `prefers-reduced-motion`). Falta navegação por teclado entre nós.

### Ainda aberto
- Medir tudo (itens 2 a 5 acima).
- Ligar `--com-baseline`, `--cobertura` e `--mesclar-em` também em `benchmark/service.py` (rota da UI).
- `ask.py` e `service.py` acima de 300 linhas.
- Validação visual do grafo só com dados reais sem `[[links]]` (103 notas do repo); falta um vault com ligações.

## Status do item 6: guarda do estruturador

Feito em `notes/extraction_guard.py` (chamada por `notes/extraction.py`). Continua desligado por padrão
(`extract_structure = false`); sem a flag, o Markdown não muda.

O que a guarda faz agora:

- **Decisões e ações:** cada nome próprio ou sigla (palavra capitalizada, inclusive a primeira do item), cada número
  com unidade (`R$` conta como unidade) e cada data precisa aparecer na nota. Comparação sem acento e sem caixa;
  números normalizados (`1.500` = `1500`). Só depois entra o limiar lexical (`min_overlap`, 0,5). Item reprovado
  conta em `discarded` e gera um aviso agregado por motivo, sem texto do item.
- **Owner e due:** owner com nome que não está na nota vira `None`. Due com data ou dia da semana que não está na
  nota vira `None`. A tarefa continua.
- **Tópicos:** precisam ter ao menos um termo de conteúdo na nota; tópico só com stopwords é descartado e contado.
- **Parâmetros:** `extract_structure(..., min_overlap=0.5, strict_entities=True)`. Com `strict_entities=False`
  valem só o limiar lexical e a guarda de tópicos.

Testes: `pipeline/tests/test_note_extraction.py`, 28 testes (15 anteriores, um deles com o tópico trocado por um
que a nota sustenta, e 13 novos). Suíte completa: 810 passando, 9 desmarcados (`test_audio_capture.py`).

**Não medido.** Nenhuma métrica de qualidade foi feita: a guarda foi validada só com os casos dos testes e com
sondagens diretas. Não há número de falso positivo ou negativo sobre notas reais.

Limites conhecidos (verificados com sondagens, não estimados):

- **Relação entre entidades não é checada.** `Maria pediu 5 dias` passa quando a nota diz que João pediu e Maria
  aprovou (os dois nomes existem). `Maria rejeitou 5 dias` passa quando a nota diz `Maria pediu 5 dias`
  (o verbo novo é só um termo lexical). Isto é falso negativo, e é a parte que o juiz de faithfulness (doc 18) deveria cobrir.
- **Datas são literais.** `09/09/2025` não bate com `nove de setembro`. Data numérica sem ano na nota não bate com
  item que cita ano.
- **Verbo ou substantivo no início do item** que não aparece na nota em nenhuma caixa é descartado como se fosse
  nome (ex.: `Revisão do relatório` contra `revisado`). É falso positivo. A checagem inclui a primeira palavra
  porque é ela que costuma ser o sujeito (`Maria aprova...`).
- **Unidades fora da lista** (`_UNIT` em `extraction_guard.py`) não são reconhecidas. Ex.: nota `3 cadeiras`
  aceita item `3 dias`.
- **Números saem do cálculo lexical quando são checados.** Isso deixa o limiar lexical mais rígido em itens com
  número, porque o denominador diminui.

## Atualização: terceira rodada

Fechado nesta rodada (nada disso mede qualidade; tudo continua `NÃO MEDIDO` com modelo real):

- **Backend emite os blocos do painel.** `benchmark compare --rerank-model X --com-baseline --cobertura 3,5,10` grava
  `reranked`, `baseline_ci` e `coverage` no JSON; `benchmark faithfulness --mesclar-em` grava `faithfulness`.
  O botão do painel (`run_benchmark_compare`) também os emite quando `rerank_model` está configurado; sem ele o
  resultado é idêntico ao anterior.
- **Estruturador:** guarda por entidades (nomes, números com unidade, datas) e por tópicos (`extraction_guard.py`).
  Limites conhecidos: não checa a relação ("Maria pediu 5 dias" passa se Maria e 5 dias existirem na nota), não
  detecta verbo trocado, e a primeira palavra do item também é checada (descarta alguns itens corretos que abrem
  com verbo).
- **Tamanho de arquivo:** `corpus/ask.py` caiu de 976 para ~300 linhas e `corpus/service.py` de 2.037 para ~905.
  `index_corpus_path` (~690 linhas) segue em `service.py`: cortar mais exige um objeto de execução, em região sensível
  (paralelismo, microbatch, cancelamento).
- **Grafo:** teclado (setas, Enter, Home, Esc), sem sobreposição de rótulos e contraste das notas ≥ 3:1 nos dois temas.
- **E2E:** os 8 specs do Playwright passam. O `03-notes-corpus` falhava por um seletor do próprio teste que casava
  com o botão da vault ("42 notas") em vez do menu Notas.

### Achado sobre o experimento 15
Os números do exp. 15 não têm artefato de origem e não reproduzem (ver o aviso no próprio doc 15). Foram copiados
para `docs/tcc/texto/TCC.md`. **Decisão pendente do autor:** substituir pelos números medidos (híbrida no corpus,
MRR 0,9423, conforme exp. 17) ou remover a afirmação.

### Ainda aberto
- Medir tudo com modelo real (itens 2 a 5 acima).
- `ask.py` (~300 linhas) no limite; `service.py` ainda ~905.
- Grafo: com mais de 8 pastas de 1º nível as cores se repetem; o contexto fora da seleção quase some no tema escuro;
  desempenho com muitos nós e leitor de tela não verificados; nunca validado com `[[links]]` de um vault real.
- CI do PR #149 sem resultado no último commit consultado (o runner é self-hosted).
