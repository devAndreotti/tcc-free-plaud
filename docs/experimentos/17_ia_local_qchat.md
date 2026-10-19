# Experimento 17: IA local (qchat) contra a resposta extrativa

> **Correção (2026-10-19):** a medição de 2026-10-19 abaixo vale para a abstenção, mas não para o texto gerado. Com a instrução de `[n]` do prompt antigo, o qchat respondeu só o marcador (`[1]`) em 34 de 39 perguntas positivas, e a validação aceitava isso. A seção "Correção" traz as saídas cruas e a decisão. A medição oficial com o prompt e a validação atuais está na seção "Medição oficial (2026-10-19, Emerald)".

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

### Medição oficial (2026-10-19, Emerald)

Rodada completa do `benchmark compare` no código da branch `feat/seletor-e-qualidade` (commit `f25e096`), com o prompt V2 e a validação atual.

- **Máquina:** Emerald-Fusion, GTX 1060 6 GB (37/37 camadas na GPU), Ollama 0.40.3.
- **Modelo:** `qchat:latest` criado com o Modelfile do PC e base `qwen2.5:3b`, o mesmo blob (`sha256-5ee4f07c…`).
- **Extrativo:** igual à base (léxica 1,0 / 0,822; vetorial 0,974 / 0,808; híbrida 0,974 / 0,808).
- **Tempo:** o run qchat inteiro levou 132 s. Não compare com os tempos do PC, que rodou sob pressão de memória.

| Estratégia | Positivas com texto gerado | Negativas com texto gerado (erro) | Positivas respondidas | Accuracy | MRR | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical | 32/39 | 2/34 | 0,897 | 0,890 | 0,914 | 835 ms | 1277 ms |
| vetorial | 31/39 | 3/34 | 0,872 | 0,890 | 0,936 | 614 ms | 1122 ms |
| híbrida | 33/39 | 2/34 | 0,923 | 0,918 | 0,942 | 422 ms | 1110 ms |

Na híbrida, comparada ao extrativo:
- Positivas respondidas: 36/39 contra 38/39. São 2 a menos.
- Negativas respondidas: 3/34 contra 13/34. O modelo se abstém mais.
- Accuracy: 0,918 contra 0,808.

Motivos de descarte na híbrida (todas as perguntas): `generated_no_answer_sentinel` 12, `unsupported_number` 2, `unsupported_anchor` 2. `empty_generated_answer` e `echoed_title`: 0.

Positivas sem texto na híbrida (6):
- "Quando o componente MAJOR deve ser incrementado?": a recuperação se absteve antes de chamar o modelo.
- "O que acontece quando dois arquivos tem conteudo identico?" e "Qual e o valor total do contrato?": `NAO_ENCONTRADO`.
- "Qual o custo mensal estimado do Datadog?" e "Qual modelo de embedding foi usado nos experimentos?": `unsupported_anchor`.
- "Qual e o prazo de confidencialidade apos o encerramento da vigencia?": `unsupported_number`.

Negativas com texto na híbrida (2). São erros do modelo que a validação não pegou:
- "Qual versao do dbt e usada no guia de modelagem de dados?"
- "Qual equipe vai migrar os microservicos legados e em qual data?"

Critério combinado para o merge (≥ 30 positivas com texto, zero `empty_generated_answer`, ≤ 3 negativas com texto): atendido nas três estratégias.

Limite: uma rodada por estratégia, com temperatura 0,2. Diferença de 1 ou 2 perguntas está no ruído.

## Probe com a validação nova (2026-10-19)

Busca léxica sobre as 73 perguntas (39 positivas, 34 negativas), `qchat:latest`, temperatura 0,2, `top_k` 3, uma rodada por variante. A validação já inclui a abstenção por `NAO_ENCONTRADO` em qualquer posição e o descarte `echoed_title`. Script fora do repositório: `C:\Users\ricar\.claude\jobs\2a72c0ca\tmp\qualidade\probe_qualidade.py`.

| Variante do prompt | Positivas: frase completa (≥ 8 palavras) | Positivas: frase curta | Título copiado | Só marcador | `NAO_ENCONTRADO` | Gerada aceita | Rejeitada pela validação | Abstenção | Negativas respondidas com texto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V2 (prompt atual) | 24 | 11 | 0 | 0 | 4 | 31 | 4 | 4 | 1 de 34 |

- Latência p50 da resposta: 3,1 s.
- Motivos de descarte nas positivas: `generated_no_answer_sentinel` 4, `unsupported_anchor` 3, `unsupported_number` 1.
- A negativa respondida foi aceita: a resposta dá uma data ("Data agendada para 22 de abril de 2025 [1]") e não nomeia a equipe que a pergunta pede.
- Lidas as respostas aceitas: a maioria responde à pergunta ("A estratégia recomendada para documentos sem estrutura formal é o chunking semântico [1]"). Quatro problemas aparecem:
  - "DECISÕES TOMADAS" para uma pergunta de prazo: linha de seção do corpo da nota, sem `#`, que a regra de título não cobre.
  - "A biblioteca que detecta o encoding do arquivo é a `file_hash`": resposta que não responde à pergunta; `file_hash` aparece no contexto, mas o trecho fala do cálculo do hash.
  - Marcadores que não são `[n]` ficam no texto: "[7c6cfb14a5]" (id de trecho copiado do cabeçalho) e "[4.3]".
  - Texto com letras separadas: "Cust o estim ado mens al (licença): R$ 18.700".
- Não medidas nesta rodada: V3 e V4. A V3 foi tentada duas vezes: na primeira, com 1,19 GB livres, a checagem de memória barrou o processo antes de começar; na segunda, começou com 1,57 GB livres e o Claude Code a interrompeu durante a execução, por memória crítica, sem gravar saída. A V4 não foi tentada. Sem medição, o prompt não mudou.

## Interpretação técnica (corrigida)

- A validação não bloqueava `[1]`. A taxa "aceitas" da primeira rodada (38/38) não tinha significado.
- Accuracy mede abstenção: a resposta extrativa conta como resposta. Para avaliar o texto gerado, olhe as saídas cruas ou a contagem de respostas com texto.
- Com o prompt da medição, pedir `[n]` no texto fez o modelo de 3B responder só o marcador. Por isso a conclusão antiga "pedir [n] não piorou nada" estava errada.
- Os outros hits no contexto também atrapalham o modelo de 3B: a configuração 3 recusou 8 perguntas positivas (medido com o prompt antigo).
- Limite: 73 perguntas sobre 10 notas. Uma pergunta a mais ou a menos muda a accuracy em cerca de 1,4 ponto.

## Próximos passos

- Repetir a medição três vezes para medir a variação.
- Ver as 2 negativas com texto na híbrida e as 6 positivas sem texto (lista acima).
