# Experimento 18: faithfulness semântica com juiz LLM

> **Status: NÃO MEDIDO.** O método e o código estão prontos e testados com juiz falso. Nenhum número real foi medido. Os resultados abaixo ficam em aberto até que um juiz forte rode offline e os JSONs sejam commitados em `data/results/`.

## Objetivo

Medir se a resposta do chat é suportada pelos trechos que ela cita, com um juiz LLM em vez de sobreposição lexical. Complementa o `lexical_groundedness` (experimento 17), que só mede ancoragem de termos e não consegue distinguir uma afirmação errada com as mesmas palavras de uma correta.

## Método

Inspirado no RAGAS (Es et al., 2023, arXiv:2309.15217), implementado sem dependências novas em `pipeline/src/escolio/benchmark/faithfulness.py`:

1. **Afirmações.** `split_claims` quebra a resposta em sentenças e remove os marcadores `[n]`. É determinístico.
2. **Veredito.** Para cada afirmação, o juiz recebe o prompt em português (`faithfulness-pt-v1`) com os trechos citados e responde `SUPORTADO` ou `NAO_SUPORTADO`. A temperatura é 0. `parse_verdict` tolera caixa, acentos, markdown e texto em volta. Se o juiz repetir as opções, vale a última.
3. **Score.** Fração das afirmações suportadas. Resposta sem afirmações vale 1,0, e evidência vazia com afirmações vale 0,0, como no `lexical_groundedness`.
4. **Agregação.** Por estratégia (lexical, vector, hybrid), com intervalo bootstrap percentil de 95% de `metrics.bootstrap_ci`, sobre o score por resposta.

Os contextos de cada resposta são os trechos citados pela própria resposta, dentro dos hits de profundidade 10 da passada no corpus. O `benchmark compare` só grava esses textos quando recebe `--registrar-respostas`. Sem a flag, o JSON não tem resposta nem trecho, e `benchmark faithfulness` recusa o arquivo.

## Limitações

- **Juiz pequeno em português é ruidoso.** Um juiz de 3B pode aprovar afirmações que não estão nos trechos; isso ainda não foi medido. Antes de usar qualquer número, é preciso rotular à mão uma amostra de afirmações e medir a concordância do juiz com esses rótulos. Essa calibração ainda não foi feita.
- **Sensibilidade ao prompt.** Mudar a instrução muda o resultado. Qualquer mudança deve virar uma nova versão em `PROMPT_VERSION`.
- **Decomposição por sentença é heurística.** Abreviações (`Dr.`) e listas longas podem quebrar uma afirmação em duas ou juntar duas em uma.
- **Veredito ilegível conta como não suportado.** Ele aparece em `unparsed_count`, e vale olhar esse número antes de interpretar o score.
- **Viés contra respostas com citação incompleta.** Se o chunk citado não estiver nos hits de profundidade 10, o contexto falta e a afirmação conta como não suportada.
- **Mede suporte, não verdade.** Uma afirmação suportada pelos trechos pode estar errada se o trecho estiver errado.
- **Respostas extrativas também são julgadas.** Elas devem ficar perto de 1,0. Se não ficarem, o problema está no juiz ou na decomposição, não na resposta.

## Como rodar

Fora do gate do CI. Os testes (`tests/test_faithfulness.py` e `tests/test_faithfulness_relatorio.py`) usam juiz falso e não tocam a rede. O subcomando de juiz real não roda no CI e não é um critério de aceite.

A partir de `pipeline/`, com o Python do venv:

```bash
python -m escolio benchmark compare --suite ../data/datasets/manual_validation/suite.json --answer-provider ollama --answer-model qchat:latest --registrar-respostas > ../data/results/bench_qchat_respostas.json
python -m escolio benchmark faithfulness --results ../data/results/bench_qchat_respostas.json --judge-model <modelo-juiz> --judge-base-url http://localhost:11434/v1 --saida ../data/results/faithfulness_qchat.json
```

Use um modelo juiz mais forte que o gerador e registre o modelo escolhido no commit. Os JSONs de `compare` e `faithfulness` vão para `data/results/`. Os JSONs antigos de `bench_qchat.json` não têm resposta gravada e precisam ser gerados de novo com `--registrar-respostas`.

## Resultados

| Estratégia | Respostas | Afirmações | Suportadas | Ilegíveis | Faithfulness média | IC 95% |
|---|---:|---:|---:|---:|---:|---|
| lexical | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO |
| vector | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO |
| hybrid | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO | NÃO MEDIDO |

Calibração do juiz (concordância com rótulos manuais): NÃO MEDIDO.
