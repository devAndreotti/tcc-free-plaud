# Experimento 17: IA local (qchat) contra a resposta extrativa

> **Correção (2026-10-19):** a medição de 2026-10-19 abaixo vale para a abstenção, mas não para o texto gerado. Com a instrução de `[n]` do prompt antigo, o qchat respondeu só o marcador (`[1]`) em 34 de 39 perguntas positivas, e a validação aceitava isso. A seção "Correção" traz as saídas cruas e a decisão. A medição oficial com o prompt novo está pendente.

## Objetivo

Medir se a resposta escrita pela IA local melhora o chat em relação à resposta extrativa, e quanto ela custa em latência. A IA é o Ollama com `qchat:latest` (Qwen 2.5 3B numa RTX 2050 de 4 GB). O experimento também decide duas mudanças da onda 3: pedir citações `[n]` no texto e entregar ao modelo todos os trechos recuperados, não só os dos claims.

## Pergunta

1. A validação (`validate_generated_answer`) aceita as respostas do qchat, ou as troca pela extrativa?
2. A IA responde menos perguntas que não têm resposta no corpus (negativas)? Quantas positivas ela deixa de responder?
3. Pedir `[n]` e entregar os outros trechos recuperados muda esses números?
4. A IA escreve texto de verdade, ou só devolve marcadores? (acrescentada depois da medição, ver a correção)

## Suíte e corpus

`data/datasets/manual_validation/suite.json` (`manual-validation-retrieval-suite`): 10 notas num corpus só, 39 perguntas positivas e 34 negativas, profundidade de recuperação 10. É a mesma passada no corpus do gate de abstenção do `benchmark compare`.

## Comando

A partir de `pipeline/`, com o Python do venv:

```bash
python -m escolio benchmark compare --suite ../data/datasets/manual_validation/suite.json > ../data/results/bench_extractive.json
python -m escolio benchmark compare --suite ../data/datasets/manual_validation/suite.json --answer-provider ollama --answer-model qchat:latest > ../data/results/bench_qchat.json
python -m escolio benchmark report-ia --extractive ../data/results/bench_extractive.json --generativo ../data/results/bench_qchat.json --saida relatorio.md
```

## Configurações

- **Modelo:** Ollama 0.40.3 com `qchat:latest`, que é o qwen2.5:3b Q4_K_M com `num_gpu 99` e `num_ctx 8192`. Roda 100% na VRAM, com temperatura 0,2 e o modelo aquecido antes de cada rodada.
- **Máquina:** i5-12450H, 16 GB de RAM, RTX 2050 4 GB.
- **Validação, em ordem:** resposta sem texto (só marcadores) cai para a extrativa. O sentinela `NAO_ENCONTRADO` vira abstenção. Eco de metadados, número sem suporte, nome sem suporte ou sobreposição abaixo de 0,35 também fazem a resposta voltar para a extrativa.
- **Configurações medidas em 2026-10-19:**
  1. extrativo, sem IA;
  2. qchat com só os trechos dos claims, sem pedir `[n]`, que é o código antes da onda 3;
  3. qchat com os trechos dos claims e depois os outros hits recuperados (até 6000 caracteres), pedindo `[n]`; foi a primeira versão da onda 3;
  4. qchat com só os trechos dos claims, pedindo `[n]`; era a versão final até a correção abaixo.

## Resultados da medição de 2026-10-19 (válidos só para a abstenção)

> As colunas "Aceitas pela validação" desta rodada contam respostas `[1]`, não texto. Não use para avaliar o texto gerado.

### Relatório (`report-ia`), configuração 4

| Estratégia | Modo | Positivas respondidas | Accuracy | MRR | Aceitas pela validação | Motivos de descarte | p50 (ms) | p95 (ms) |
|---|---|---:|---:|---:|---:|---|---:|---:|
| lexical | Extractive | 1,000 | 0,822 | 0,914 | — | — | 21 | 83 |
| lexical | Generativo | 0,923 | 0,932 | 0,914 | 1,000 (38/38) | generated_no_answer_sentinel: 14 | 2775 | 3290 |
| vector | Extractive | 0,974 | 0,808 | 0,936 | — | — | 123 | 211 |
| vector | Generativo | 0,897 | 0,918 | 0,936 | 1,000 (37/37) | generated_no_answer_sentinel: 14 | 2812 | 3209 |
| hybrid | Extractive | 0,974 | 0,808 | 0,942 | — | — | 135 | 210 |
| hybrid | Generativo | 0,923 | 0,932 | 0,942 | 1,000 (38/38) | generated_no_answer_sentinel: 13 | 2826 | 3364 |

### As quatro configurações (híbrida)

| Configuração | Positivas respondidas | Negativas respondidas (erro) | Accuracy | `NAO_ENCONTRADO` em positivas | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|
| Extrativo | 38/39 | 13/34 | 0,808 | — | 135 ms | 210 ms |
| qchat, só claims, sem `[n]` | 35/39 | 3/34 | 0,904 | 3 | 3,1 s | 3,9 s |
| qchat, claims + outros hits, com `[n]` | 30/39 | 7/34 | 0,781 | 8 | 3,0 s | 4,7 s |
| qchat, só claims, com `[n]` (até a correção) | 36/39 | 2/34 | 0,932 | 2 | 2,8 s | 3,4 s |

## Correção: a IA respondia só `[n]`

### O que aconteceu

- Pergunta real "o que é VLAN?": a tela mostrou `[1] VLAN - Aplicativos Mútuos`.
- Pergunta real "como foi o setup local da Unidas?": a resposta crua do qchat foi só `[1]`.
- A validação checa o texto sem os marcadores. Sem texto, não há o que checar, então `[1]` foi aceito como resposta gerada.
- A accuracy não avalia texto: resposta extrativa de fallback conta como respondida.

### Saídas cruas por variante do prompt

Busca léxica, 73 perguntas, `qchat:latest`, temperatura 0,2:

| Variante do prompt | Positivas com texto gerado | Positivas com só marcador | Positivas com texto rejeitado pela validação | Positivas recusadas (`NAO_ENCONTRADO`) | Negativas respondidas por engano |
|---|---:|---:|---:|---:|---:|
| V0: "termine cada frase com [1]" (prompt da medição) | 2 | 34 | 0 | 3 | 3 |
| V1: sem a linha de `[n]` | 33 | 0 | 1 | 5 | 3 |
| **V2: frases completas com `[n]` no fim (adotada)** | **31** | **0** | **4** | **4** | **1** |

### Decisão

Adotada a V2. O modelo escreve texto, mantém as citações `[n]` (item 8 do plano) e erra 1 negativa, contra 3 da V0 e da V1. A V1 tem taxa de texto parecida, mas não cita as fontes no texto.

O prompt da V2 está em `GROUNDED_SYSTEM_PROMPT` (`pipeline/src/escolio/providers/answer.py`). Respostas sem texto agora caem para a extrativa (`empty_generated_answer`).

### Medição oficial: pendente

O `benchmark compare` com qchat (híbrida, vetorial e léxica) não terminou: o Claude Code encerrou o processo por falta de memória, e o arquivo gerado ficou incompleto. As tabelas da correção vêm da busca léxica, com as saídas cruas. Rodar de novo com memória livre e atualizar a seção de resultados.

## Interpretação técnica (corrigida)

- A validação não bloqueava `[1]`. A taxa "aceitas" da primeira rodada (38/38) não tinha significado.
- Accuracy mede abstenção: a resposta extrativa conta como resposta. Para avaliar o texto gerado, olhe as saídas cruas ou a contagem de respostas com texto.
- Com o prompt da medição, pedir `[n]` no texto fez o modelo de 3B responder só o marcador. Por isso a conclusão antiga "pedir [n] não piorou nada" estava errada.
- Os outros hits no contexto também atrapalham o modelo de 3B: a configuração 3 recusou 8 perguntas positivas (medido com o prompt antigo).
- Limite: 73 perguntas sobre 10 notas. Uma pergunta a mais ou a menos muda a accuracy em cerca de 1,4 ponto.

## Próximos passos

- Medição oficial com qchat (`benchmark compare --answer-provider ollama`) quando houver memória livre; atualizar a seção de resultados.
- Repetir a medição três vezes para medir a variação.
- Ver a negativa respondida por engano com a V2.
- Ver por que `contrato-01` e `ingest-03` são recusadas.
