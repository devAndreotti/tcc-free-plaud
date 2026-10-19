# Experimento 17: IA local (qchat) contra a resposta extrativa

## Objetivo

Medir se a resposta escrita pela IA local melhora o chat em relação à resposta extrativa, e quanto ela custa em latência. A IA é o Ollama com `qchat:latest` (Qwen 2.5 3B numa RTX 2050 de 4 GB). O experimento também decide duas mudanças da onda 3: pedir citações `[n]` no texto e entregar ao modelo todos os trechos recuperados, não só os dos claims.

## Pergunta

1. A validação (`validate_generated_answer`) aceita as respostas do qchat, ou as troca pela extrativa?
2. A IA responde menos perguntas que não têm resposta no corpus (negativas)? Quantas positivas ela deixa de responder?
3. Pedir `[n]` e entregar os outros trechos recuperados muda esses números?

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
- **Validação, em ordem:** o sentinela `NAO_ENCONTRADO` vira abstenção. Eco de metadados, número sem suporte, nome sem suporte ou sobreposição abaixo de 0,35 fazem a resposta voltar para a extrativa.
- **Configurações medidas:** quatro, todas na mesma suíte, em 2026-10-19:
  1. extrativo, sem IA;
  2. qchat com só os trechos dos claims, sem pedir `[n]`, que é o código antes da onda 3;
  3. qchat com os trechos dos claims e depois os outros hits recuperados (até 6000 caracteres), pedindo `[n]`; foi a primeira versão da onda 3;
  4. qchat com só os trechos dos claims, pedindo `[n]`; é a versão final.
- **Medição da versão final:** a configuração 4 foi medida com o laço dos outros hits desligado por um patch de uma linha. O comportamento é o mesmo do código final, que tirou esse laço.

## Resultados

### Versão final contra a extrativa (`report-ia`)

| Estratégia | Modo | Positivas respondidas | Accuracy | MRR | Aceitas pela validação | Motivos de descarte | p50 (ms) | p95 (ms) |
|---|---|---:|---:|---:|---:|---|---:|---:|
| lexical | Extractive | 1,000 | 0,822 | 0,914 | — | — | 21 | 83 |
| lexical | Generativo | 0,923 | 0,932 | 0,914 | 1,000 (38/38) | generated_no_answer_sentinel: 14 | 2775 | 3290 |
| vector | Extractive | 0,974 | 0,808 | 0,936 | — | — | 123 | 211 |
| vector | Generativo | 0,897 | 0,918 | 0,936 | 1,000 (37/37) | generated_no_answer_sentinel: 14 | 2812 | 3209 |
| hybrid | Extractive | 0,974 | 0,808 | 0,942 | — | — | 135 | 210 |
| hybrid | Generativo | 0,923 | 0,932 | 0,942 | 1,000 (38/38) | generated_no_answer_sentinel: 13 | 2826 | 3364 |

"Aceitas pela validação" divide as respostas geradas aceitas pelas respostas `answer`. Os motivos incluem as negativas que o próprio modelo recusou. p50 e p95 medem a pergunta inteira, com recuperação e resposta.

### As quatro configurações (híbrida, a estratégia padrão do app)

| Configuração | Positivas respondidas | Negativas respondidas (erro) | Accuracy | `NAO_ENCONTRADO` em positivas | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|
| Extrativo | 38/39 | 13/34 | 0,808 | — | 135 ms | 210 ms |
| qchat, só claims, sem `[n]` | 35/39 | 3/34 | 0,904 | 3 | 3,1 s | 3,9 s |
| qchat, claims + outros hits, com `[n]` | 30/39 | 7/34 | 0,781 | 8 | 3,0 s | 4,7 s |
| **qchat, só claims, com `[n]` (final)** | **36/39** | **2/34** | **0,932** | 2 | 2,8 s | 3,4 s |

As outras estratégias seguem o mesmo padrão. Na vetorial, a accuracy passa de 0,863 com os outros hits para 0,918 com só os claims. Na lexical, passa de 0,781 para 0,932.

## Interpretação técnica

- **A validação quase nunca troca a resposta.** Na versão final, aceitou 38 de 38 respostas geradas na híbrida e não descartou nenhuma por número ou nome sem suporte. Quem decide o resultado é o próprio modelo, quando responde `NAO_ENCONTRADO`.
- **A IA troca cobertura por precisão.** Responde só 2 das 34 perguntas sem resposta no corpus, contra 13 da extrativa. Em troca, recusa 2 positivas (`contrato-01` e `ingest-03`). A accuracy de abstenção sobe de 0,808 para 0,932.
- **Os outros hits atrapalham o modelo de 3B.** Com eles no contexto, o qchat recusou 8 positivas cujo trecho certo estava em 1º lugar, como "Qual o valor do REDIS_TIMEOUT em staging?", e voltou a responder negativas. Por isso a versão final só manda os trechos dos claims.
- **Pedir `[n]` não piorou nada.** A accuracy foi de 0,904 para 0,932, diferença dentro da variação da temperatura 0,2.
- **Custo:** a pergunta passa de ~135 ms para 2,8 s (p50) e 3,4 s (p95), com o modelo quente. Na tela, o streaming mostra o texto chegando antes disso.
- **Limites:** cada configuração rodou uma vez, com temperatura 0,2, então diferenças de 1 ou 2 perguntas estão dentro do ruído. A suíte tem 73 perguntas sobre 10 notas.

## Próximos passos

- Repetir a configuração final três vezes, ou com temperatura 0 no benchmark, para medir a variação.
- Ver por que `contrato-01` e `ingest-03` são recusadas: o trecho do claim pode não ter a resposta inteira.
- Rodar o mesmo protocolo com outros modelos que cabem na VRAM, como o `qwen2.5:3b` sem ajuste.
