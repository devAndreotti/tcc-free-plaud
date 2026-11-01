# Experimento 21: Abstenção e faithfulness com IA local (qchat)

**Data da medição:** 2026-11-01. **Código:** branch `fix/escolio-ollama-validacao`. **Modelo de resposta:** `qchat:latest` (Qwen 2.5 3B ajustado), Ollama local. **Juiz de faithfulness:** `qwen2.5:3b`.

## Perguntas

1. Com a IA ligada, o chat responde as positivas e recusa as negativas melhor que o modo extrativo?
2. Uma checagem semântica (o modelo copia do trecho a informação pedida) melhora a abstenção?
3. Quanto das respostas geradas é sustentado pelos trechos citados?

## Comandos

Linha de base, as três estratégias (cerca de 14 min):

```bash
cd pipeline
uv run escolio benchmark compare --suite ../data/datasets/manual_validation/suite.json \
  --answer-provider ollama --answer-model qchat:latest --answer-base-url http://localhost:11434/v1 \
  --registrar-respostas
```

As rodadas do código novo usaram só a estratégia híbrida (a padrão do chat), porque a rodada completa foi encerrada por falta de memória na máquina de 16 GB. O recorte foi feito trocando `escolio.benchmark.run_corpus.STRATEGIES` por `('hybrid',)` antes de chamar o mesmo comando.

Faithfulness (sobre o JSON gravado com `--registrar-respostas`):

```bash
uv run escolio benchmark faithfulness --results <compare.json> --judge-model qwen2.5:3b \
  --judge-base-url http://localhost:11434/v1 --saida <faith.json> --estrategia hybrid
```

## Suíte

`data/datasets/manual_validation`: 10 notas, 39 perguntas positivas e 34 negativas (sem resposta em nenhuma nota).

## Resultado 1: abstenção (estratégia híbrida)

| Configuração | Positivas respondidas | Negativas respondidas | Decisões certas |
|---|---|---|---|
| Extrativo, sem IA (Experimento 20) | 38/39 | 13/34 | 59/73 (81%) |
| IA, código anterior | 35/39 | 6/34 | 63/73 (86%) |
| IA, checagem de span em **toda** resposta | 24/39 | 0/34 | 58/73 (79%) |
| IA, checagem de span só como segunda chance (versão final) | 33/39 | 6/34 | 60/73 (82%) |

Leitura:

- A IA reduz as negativas respondidas de 13 para 6 em 34, ao custo de 3 positivas. O ganho vem do sentinela `NAO_ENCONTRADO` e da validação da resposta gerada.
- Exigir o span em toda resposta zera as negativas, mas derruba 11 positivas: o modelo de 3B responde NAO demais quando recebe trechos técnicos longos. Essa variante foi descartada.
- Na versão final, a checagem só roda para a pergunta que a regra de vocabulário recusaria (um termo da pergunta não existe no corpus). Fora disso, o fluxo é o mesmo do código anterior.
- **Ruído entre rodadas.** As diferenças entre "código anterior" e "versão final" (33 contra 35 positivas) vêm todas da etapa de geração, que é igual nas duas versões: a mesma pergunta recebe o sentinela numa rodada e uma resposta na outra (`semver-02`, `semver-03`, `semver-04`, `monitor-04`, `contrato-01`, `contrato-03`). Nenhuma delas passou pela checagem de span. Com uma rodada por versão, diferenças de ±3 perguntas não são distinguíveis do ruído.
- Esta suíte não tem positiva que a regra de vocabulário recuse (a regra foi calibrada nela), então o ganho da segunda chance não aparece aqui. Ele aparece na bateria abaixo.

## Resultado 2: paráfrases (bateria manual, 5 notas sintéticas)

| Pergunta | Antes | Versão final |
|---|---|---|
| Quem vai coordenar a mudança de servidor? ("responsável" na nota) | recusada | "O analista Paulo Nogueira vai coordenar a mudança de servidor [1]." |
| Qual a temperatura de assamento do pão? ("assar a 220 graus") | recusada | frase com "220 graus" |
| Quanto custa a passagem do tram 28 e qual a melhor época para ir a Lisboa? | recusada | as duas partes, citadas |
| Qual a temperatura de assamento do pão e quem coordena a migração? (duas notas) | recusada | recusada |
| 5 negativas (população de Recife, gols em 2014, preço do Vega, dose para crianças, responsável do "projeto Vega") | recusadas | recusadas |

Antes da implementação, a checagem foi comparada em 16 pares (6 paráfrases, 10 negativas) com três formulações:

| Formulação | Acertos |
|---|---|
| Pergunta de sim ou não ("o texto fala disso?") | 6–7/16 (o modelo diz NAO para quase tudo) |
| Sinônimos gerados pelo LLM + checagem lexical | 7/11 |
| Similaridade de embeddings entre termo e palavras do trecho | sem limiar que separe (0,52 numa positiva contra 0,58 numa negativa) |
| **Copiar do trecho a informação pedida ou escrever NAO** | **15/16** |

O erro restante foi uma negativa com o mesmo vocabulário do trecho: perguntado sobre o orçamento do "projeto de migração", o modelo copiou o orçamento de outro projeto.

## Resultado 3: faithfulness das respostas geradas

Juiz `qwen2.5:3b` sobre as 39 respostas da versão final:

| Tipo de resposta | Respostas | Afirmações sustentadas segundo o juiz |
|---|---|---|
| Gerada pela IA | 29 | 25/39 (média por resposta 0,61) |
| Extrativa (cópia literal, serve de calibração) | 10 | 9/10 (0,90) |

O juiz reprova 1 em 10 afirmações que são cópias literais, então ele é estrito demais. As 15 reprovações foram conferidas uma a uma contra os trechos registrados no JSON (auditoria feita por uma pessoa, sem segundo avaliador):

- **10 sustentadas, erro do juiz.** Exemplo: "Adotar Apache Kafka como message broker padrão da plataforma." é cópia do documento.
- **5 alucinações reais.**
  - `docker-04`: resposta "SCD Tipo 1 (Sobrescrever)", trazida de outro documento. A correta é `tmpfs`.
  - `monitor-02`: R$ 4.200 atribuído ao Datadog, junto com outra frase dizendo que não há custo informado.
  - `neg2-19`: a data da próxima sessão é apresentada como data da migração.
  - `neg2-09`: versão do dbt inventada.

Com a auditoria, cerca de **34 de 39 afirmações geradas (≈ 87%)** estão sustentadas pelos trechos. O padrão das falhas é associar um valor ou uma data à entidade errada, e as checagens lexicais não pegam isso, porque o valor existe no trecho.

## Limitações

- Uma rodada por configuração. O ruído entre rodadas da IA é de cerca de ±3 perguntas em 39.
- As rodadas finais mediram só a estratégia híbrida.
- O juiz é um modelo de 3B, e a auditoria manual foi feita por uma pessoa só.
- A bateria de paráfrases é pequena (4 perguntas) e foi escrita por quem implementou a checagem.
- Latência: a checagem de span só roda para a pergunta que o vocabulário recusaria, e soma de 1 a 4 chamadas ao modelo nesses casos.
