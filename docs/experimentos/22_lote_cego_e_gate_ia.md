# Experimento 22: Lote cego e gate da IA (Emerald)

**Data da medição:** 2026-11-02. **Código:** commit `f8844d8` (branch `fechamento/lote-cego`), que contém a correção de normalização `77ea26d` e o lote cego congelado. Nenhum arquivo de código, pergunta, termo, limiar ou prompt foi alterado para esta medição.

**Isto é medição, não calibração.** Resultado ruim ficou como resultado.

## Perguntas

1. A correção de normalização `77ea26d` piorou a recuperação ou a abstenção, com IA ou sem IA (gate da IA, que nunca tinha passado pelo compare com IA)?
2. Quanto o desempenho cai do lote calibrado (`manual_validation`) para o lote cego (`lote_cego`)?

## Avisos sobre validade

- **O lote cego foi escrito por um agente de IA** que só leu os 10 documentos. Os autores do TCC ainda não revisaram as perguntas nem o gabarito. Não há rotulagem independente.
- **A máquina difere dos Experimentos 20 e 21.** Estes usaram o notebook Windows (16 GB, RTX 2050); esta medição usou o Emerald: Intel i5-4690, 23 GB de RAM, GTX 1060 6 GB, Linux, Python 3.12. Outros processos (testes Playwright de outros agentes) podiam estar rodando na mesma máquina. Por isso **a latência não é reportada como resultado**.
- O Ollama do Emerald foi baixado como tarball e rodou no espaço do usuário, na porta 11435.
- Uma rodada por configuração sem IA, três com IA. O ruído entre rodadas com IA é conhecido (Experimento 21: cerca de ±3 perguntas).

## Ambiente e modelo

| Item | Windows (referência) | Emerald (esta medição) |
|---|---|---|
| Ollama | 0.40.3 | 0.40.3 (tarball oficial `ollama-linux-amd64.tar.zst`) |
| `qwen2.5:3b` (digest do manifesto) | `357c53fb659c…` | `357c53fb659c…` (igual) |
| `qchat:latest` (digest do manifesto) | `3f8f057e4bcd…` | `47504b2922e6…` (**diferente**) |
| Camadas de `qchat` (modelo, system, template, licença, params) | `5ee4f07cdb9b`, `66b9ea09bd5b`, `eb4402837c78`, `b5c0e5cf74cf`, `62e6482c1e76` | as mesmas cinco |
| Parâmetros | temperature 0.7, top_p 0.9, num_ctx 8192, num_gpu 99 | idem |
| GPU | RTX 2050 4 GB | GTX 1060 6 GB (log: `offloaded 37/37 layers to GPU`) |

O `qchat` do Emerald foi criado com `ollama create qchat -f Modelfile.qchat` (`FROM qwen2.5:3b` mais os quatro `PARAMETER` acima). **O digest do manifesto difere do Windows**, e o plano mandava parar nesse caso. Segui porque as cinco camadas de conteúdo são byte a byte as mesmas (mesmos digests de blob); a diferença está só no blob de configuração do manifesto, que no Windows traz `"architecture":"amd64","os":"linux"` e no Emerald não traz esses dois campos. Não verifiquei o `Modelfile` do Windows além da saída de `api/show`, de onde reconstruí os parâmetros. Registro como divergência do plano.

O embedding efetivo de todas as rodadas foi `chroma-default` (campo `embedding_model` de cada JSON), em CPU, o mesmo do Experimento 20. Os valores de MRR abaixo têm portanto referência com o mesmo modelo.

## Comandos

Worktree de medição em `f8844d8` (limpa antes e depois), rodando de `pipeline/` com `PYTHONPATH=src` e o venv do clone descartável:

```bash
# A (manual_validation, sem IA, 3 estratégias) e C (lote_cego, sem IA)
python -m escolio benchmark compare --suite ../data/datasets/<suite>/suite.json

# B (manual_validation) e D (lote_cego): IA, só híbrida, 3 rodadas cada
python hybrid_only.py benchmark compare --suite ../data/datasets/<suite>/suite.json \
  --answer-provider ollama --answer-model qchat:latest \
  --answer-base-url http://127.0.0.1:11435/v1 --registrar-respostas

# E: faithfulness sobre a 1ª rodada de D
python -m escolio benchmark faithfulness --results D1_lote_ia.json --judge-model qwen2.5:3b \
  --judge-base-url http://127.0.0.1:11435/v1 --saida E_faith_lote.json --estrategia hybrid
```

`hybrid_only.py` só troca `escolio.benchmark.run_corpus.STRATEGIES` por `('hybrid',)` antes de chamar o `app` da CLI (mesmo recorte do Experimento 21, sem alterar código do repositório). Configuração registrada: `top_k=3`, `chunk_size=800`, `overlap=120`, RRF `k=60`, `lexical_weight=1.5`, `vector_weight=1.0`, pools 9 e 24. As rodadas rodaram em sequência, uma por vez. Scripts e JSONs ficam em `data/results/experimentos/22_lote_cego/` (pasta ignorada pelo git).

## Suítes

| | `manual_validation` (calibrado) | `lote_cego` |
|---|---|---|
| Notas | 10 | 10 (as mesmas) |
| Positivas | 39 | 37 |
| Negativas | 34 | 39 (14 quase-acerto, 13 fora-do-dominio, 12 vocabulario-presente) |

## Resultado 1: sem IA (modo extrativo)

Corpus completo, 3 estratégias. "Resp." = decisão de resposta do chat.

| Suíte | Estratégia | Positivas resp. | Negativas resp. | Decisões certas | MRR | Recall@3 | Recall@5 |
|---|---|---|---|---|---|---|---|
| A manual | léxica | 39/39 | 14/34 | 59/73 | 0,9139 | 0,9744 | 0,9744 |
| A manual | vetorial | 38/39 | 13/34 | 59/73 | 0,9359 | 1,0000 | 1,0000 |
| A manual | **híbrida** | **38/39** | **13/34** | **59/73** | **0,9444** | **1,0000** | **1,0000** |
| C lote cego | léxica | 19/37 | 21/39 | 37/76 | 0,7719 | 0,9189 | 0,9459 |
| C lote cego | vetorial | 19/37 | 19/39 | 39/76 | 0,8165 | 0,8378 | 0,9459 |
| C lote cego | **híbrida** | **19/37** | **19/39** | **39/76** | **0,8108** | **0,9459** | **0,9459** |

Além do corpus completo, o `compare` grava um resumo por nota (recuperação dentro de cada nota isolada, que é a tabela do Experimento 20):

| Suíte | Estratégia | MRR por nota | Recall@3 por nota |
|---|---|---|---|
| A manual | léxica | 0,9103 | 1,0000 |
| A manual | vetorial | 0,7906 | 0,8974 |
| A manual | híbrida | 0,9145 | 1,0000 |
| C lote cego | léxica | 0,7793 | 0,8919 |
| C lote cego | vetorial | 0,6667 | 0,7568 |
| C lote cego | híbrida | 0,7613 | 0,8378 |

## Resultado 2: gate da IA (híbrida, `qchat:latest`)

### `manual_validation` (B, 3 rodadas)

| Rodada | Positivas resp. | Negativas resp. | Decisões certas | Geradas de verdade (pos/neg) | MRR | Recall@3 |
|---|---|---|---|---|---|---|
| B1 | 36/39 | 7/34 | 63/73 | 28 / 4 | 0,9444 | 1,0 |
| B2 | 37/39 | 6/34 | 65/73 | 28 / 3 | 0,9444 | 1,0 |
| B3 | 36/39 | 3/34 | 67/73 | 27 / 2 | 0,9444 | 1,0 |
| mín / máx / mediana | 36 / 37 / 36 | 3 / 7 / 6 | 63 / 67 / 65 | | | |

Perguntas que mudaram de decisão entre as 3 rodadas: **8** (`semver-02`, `ingest-01`, `ata-02`, `paper-02`, `neg2-01`, `neg2-02`, `neg2-11`, `neg2-23`).

### `lote_cego` (D, 3 rodadas)

| Rodada | Positivas resp. | Negativas resp. | Decisões certas | Geradas de verdade (pos/neg) | MRR | Recall@3 |
|---|---|---|---|---|---|---|
| D1 | 26/37 | 11/39 | 54/76 | 18 / 5 | 0,8108 | 0,9459 |
| D2 | 25/37 | 10/39 | 54/76 | 17 / 7 | 0,8108 | 0,9459 |
| D3 | 25/37 | 11/39 | 53/76 | 16 / 8 | 0,8108 | 0,9459 |
| mín / máx / mediana | 25 / 26 / 25 | 10 / 11 / 11 | 53 / 54 / 54 | | | |

Perguntas que mudaram de decisão entre as 3 rodadas: **5** (`lc-03-a`, `lcn-02`, `lcn-08`, `lcn-13`, `lcn-38`).

## Resultado 3: lote cego contra lote calibrado

Taxas (mediana das 3 rodadas com IA; sem IA, a única rodada):

| | Calibrado (manual) | Cego | Variação |
|---|---|---|---|
| Sem IA: positivas respondidas | 38/39 (97%) | 19/37 (51%) | -46 pontos |
| Sem IA: negativas respondidas | 13/34 (38%) | 19/39 (49%) | +10 pontos |
| Sem IA: decisões certas | 59/73 (81%) | 39/76 (51%) | -30 pontos |
| Com IA: positivas respondidas | 36/39 (92%) | 25/37 (68%) | -25 pontos |
| Com IA: negativas respondidas | 6/34 (18%) | 11/39 (28%) | +11 pontos |
| Com IA: decisões certas | 65/73 (89%) | 54/76 (71%) | -18 pontos |
| Recuperação híbrida: MRR / Recall@3 | 0,944 / 1,000 | 0,811 / 0,946 | -0,134 / -0,054 |

Abstenção nas negativas do lote cego (negativas **não** respondidas), com intervalo de Wilson de 95%:

| Configuração | Abstenção | IC 95% (Wilson) |
|---|---|---|
| Sem IA, híbrida | 20/39 = 51,3% | [36,2%; 66,1%] |
| IA, D1 | 28/39 = 71,8% | [56,2%; 83,5%] |
| IA, D2 | 29/39 = 74,4% | [58,9%; 85,4%] |
| IA, D3 | 28/39 = 71,8% | [56,2%; 83,5%] |

Para comparação, no lote calibrado com IA a abstenção foi 27/34 a 31/34 (79% a 91%; ICs de 63% a 92% e de 77% a 97%). Os intervalos do cego e do calibrado se sobrepõem em parte, com 34 e 39 negativas; a queda é visível no ponto central, mas o tamanho das amostras não a torna conclusiva só pela abstenção. A queda nas positivas respondidas é mais clara: IC 95% de D1 em 26/37 é [54%; 83%], contra [80%; 97%] de B1 em 36/39.

### Negativas respondidas por subtipo (lote cego)

| Subtipo (n) | Sem IA | D1 | D2 | D3 |
|---|---|---|---|---|
| quase-acerto (14) | 13 | 9 | 8 | 8 |
| vocabulario-presente (12) | 5 | 2 | 2 | 3 |
| fora-do-dominio (13) | 1 | 0 | 0 | 0 |

O ponto fraco é o `quase-acerto` (pergunta sobre algo que a nota quase diz): 8 a 9 de 14 respondidas com IA. O modelo e a regra de vocabulário recusam bem o que é claramente de fora e razoavelmente o que só repete vocabulário, mas não o que está ao lado da resposta.

## Conferência das saídas cruas

Li as 76 respostas de D1 (37 positivas e 39 negativas, com os campos `answered`, `generated`, `discard_reason`), mais os contadores de B1. Conclusões:

- **Nenhuma rodada colapsou para `[1]`.** As respostas geradas têm texto próprio.
- **A métrica "respondida" conta fallback extrativo.** Em D1, das 26 positivas respondidas, 18 foram geradas de verdade e 8 vieram do fallback (descartes `echoed_question` 2, `unsupported_anchor` 2, `empty_generated_answer` 2, `unsupported_number` 2). Das 11 negativas respondidas, 5 foram geradas e 6 vieram do fallback (`unsupported_anchor` 3, `unsupported_number` 1, `empty_generated_answer` 1, `low_claim_overlap` 1). Ou seja, mais da metade das negativas "respondidas" são trechos copiados porque a resposta do modelo foi descartada, não afirmações do modelo. Em B1: 28 de 36 positivas e 4 de 7 negativas geradas.
- Entre as respostas geradas há ecos da própria pergunta no início (`lc-01-b`, `lc-09-b`) e sentinelas corretos (`generated_no_answer_sentinel`: 10 descartes em D1).
- **Negativas respondidas com valor errado, geradas pelo modelo** (o padrão do Experimento 21, valor associado à entidade errada):
  - `lcn-10` (MRR@10 do chunking semântico em e-mails): respondeu "97,3". Esse número é o tempo de indexação em segundos do método semântico, não um MRR.
  - `lcn-04` (data de aprovação do ADR-2025-07): respondeu "25 de março de 2025", que é a data da reunião; a aprovação formal é só pauta futura na ata.
  - `lcn-03` (custo do Thanos): respondeu R$ 18.700, que é a licença do Datadog.
  - `lcn-09`: texto genérico sobre partições, sem o tamanho pedido.
- Positivas geradas corretas, por exemplo `lc-03-a` (Rafael), `lc-07-a` (0,81), `lc-10-b` (Dan Linstedt), `lc-10-c` (Bronze, Silver e Gold). Positivas recusadas sem falha de recuperação (rank 1 na recuperação, mas sem resposta): `lc-01-c`, `lc-01-d`, `lc-04-b`, `lc-04-c`, `lc-05-c`, `lc-07-b`, `lc-09-a`, entre outras.
- Não revisei D2 e D3 pergunta a pergunta, só os contadores e a lista de perguntas que mudaram.

## Resultado 4: faithfulness (E)

Juiz `qwen2.5:3b` sobre a resposta da híbrida em D1: 37 respostas, 44 afirmações, 23 sustentadas (**52%** das afirmações), média por resposta 0,563, IC 95% [0,405; 0,725]. Inclui respostas do fallback extrativo e das negativas respondidas. **Não auditei as reprovações uma a uma**, ao contrário do Experimento 21. Há pelo menos uma reprovação que é erro do juiz: `lc-01-a` ("a Opção C é a recomendação para quem usa pyproject.toml...") foi marcada como não sustentada, mas confere com o gabarito. O número é portanto um piso; não é comparável com os 87% auditados do Experimento 21.

## Leitura

### Gate da IA: a correção de normalização não piorou nada medível

- **Sem IA (A contra Experimento 20):** híbrida idêntica nas decisões: 38/39, 13/34, 59/73. MRR da híbrida no corpus 0,9444 e Recall@3 1,0, iguais à medição posterior à correção feita no Windows (0,9444 e 1,0). Por nota: híbrida 0,9145 (Experimento 20: 0,915), léxica 0,9103 (0,910). A vetorial por nota ficou em 0,7906, contra 0,816 do Experimento 20 (Recall@3 0,897 contra 0,923, uma pergunta). Não consegui separar efeito da normalização de efeito de máquina ou do ONNX em CPU nessa diferença, e ela não aparece na híbrida.
- **Com IA (B contra Experimento 21):** 36–37/39, 3–7/34 e 63–67/73, contra 33/39, 6/34 e "60/73" da versão final do Experimento 21. A tabela do Experimento 21 não fecha aritmeticamente (33 + (34 − 6) = 61, mas diz 60/73); não tenho o JSON dele para decidir, e usei os números como escritos. Os números atuais estão no mesmo patamar ou um pouco melhores nas positivas (+3 a +4 contra a versão final, e ±3 é o ruído conhecido), e as negativas ficaram na mesma faixa. **Não há sinal de piora.** Também não dá para atribuir a melhora à correção: não há rodada da mesma máquina sem ela.
- **Veredito do gate: passa**, no sentido de que não há regressão detectável acima do ruído, com ressalvas (máquina diferente, três rodadas, uma estratégia).

### Lote cego: o desempenho cai

- A queda é o achado principal. Sem IA, o chat responde só metade das positivas do cego (51%) contra 97% do calibrado, e responde 49% das negativas. Com IA, 68% das positivas contra 92%, e 28% das negativas contra 18%. As decisões certas caem de 89% para 71% com IA e de 81% para 51% sem IA.
- A recuperação também cai (MRR 0,944 para 0,811; Recall@3 1,0 para 0,946). Duas positivas do cego nunca entram no top 3 da híbrida: `lc-04-d` ("Quando o comitê volta a se reunir?", sem resultado) e `lc-07-d` (posição 6). Parte das positivas recusadas, porém, tem a nota certa em primeiro lugar e é recusada pela regra de abstenção ou pelo modelo, não por falha de recuperação.
- A regra de vocabulário foi calibrada no lote antigo, e o cego tem mais paráfrase: é coerente que a regra recuse positivas que usam outras palavras. Esta medição não separa quanto da queda vem da regra e quanto do modelo.
- Sem IA, a abstenção nas negativas do cego (51%) é pior que a da IA (72% a 74%), e a IA melhora tanto positivas respondidas quanto negativas recusadas em relação ao extrativo no cego.
- Com 37 positivas e 39 negativas e três rodadas, os intervalos são largos. A direção é consistente em todas as métricas, mas os números exatos não devem ser citados sem o intervalo.

## Dúvidas sobre o lote

Registradas sem corrigir nem refazer:

- `lcn-03` ("Qual o custo mensal estimado do Thanos?"): a nota de monitoramento cita o Thanos como complemento do Prometheus + Grafana, cujo custo estimado é R$ 4.200. A negativa pode ser lida como parcialmente respondível; é ambígua.
- `lcn-04` ("data em que o ADR-2025-07 foi aprovado formalmente"): a ata tem "Data: 25 de março de 2025" e fala em apresentar o ADR "para aprovação formal". O rótulo de negativa é defensável, mas a resposta que o modelo deu mostra que a pergunta induz erro.
- `lc-04-d` ("Quando o comitê volta a se reunir?", esperado "22 de abril de 2025"): nenhuma estratégia a recupera no top 10, apesar de o termo esperado existir na seção "Pendências para próxima sessão". Não investiguei se é a fragmentação, a pergunta ou o vocabulário; não afirmo erro do lote.
- `lcn-06` (nome do gestor do contrato): a cláusula 3.2 cita "designar um gestor do contrato"; a resposta correta é a ausência do nome, mas a cláusula é relacionada.

Não encontrei erro de escrita evidente (termo esperado ausente do texto) nas perguntas que li.

## Limitações

- Três rodadas com IA, só estratégia híbrida, e uma rodada sem IA por suíte.
- Máquina diferente, possivelmente com carga de outros processos; latência não reportada.
- Digest do manifesto do `qchat` diferente do Windows (conteúdo idêntico, ver acima).
- Faithfulness sem auditoria manual.
- Lote cego escrito por IA, sem revisão dos autores, congelado antes da medição e não modificado.
- A tabela do Experimento 21 não fecha aritmeticamente (33 + 28 = 61, escrito 60/73); a comparação com ela herda essa incerteza.

## Reprodução em 2026-11-04

**Rodada:** `cmp-187e76fca758` (`data/results/cmp-187e76fca758.json`), iniciada às 17:43Z. Usou o mesmo serviço do botão "Medir também a resposta da IA" do painel Benchmark (`run_benchmark_compare(..., answer=True, keep_answers=True)`), com Ollama e `qchat:latest`. Levou 1.109 s para as três estratégias com IA, dos quais 411 s foram da híbrida. A referência sem IA do mesmo dia é `cmp-32377de15bdf`. O lote cego não foi alterado: `git diff f8844d8 main -- data/datasets/lote_cego` está vazio. **Também aqui é medição, não calibração.**

As condições não são as mesmas de D1 a D3:

- **Máquina:** o notebook Windows (RTX 2050 4 GB), não o Emerald. O log do Ollama do Windows mostra as chamadas a `qchat:latest` a partir de 14:43 (horário local). É o `qchat` de manifesto `3f8f057e4bcd…`, com as mesmas cinco camadas (ver "Ambiente e modelo").
- **`top_k=4` e pools 12/32**, que vêm da configuração do app (`retrieval_top_k=4`). A CLI do Experimento 22 usou `top_k=3` e pools 9/24. A IA recebe portanto até 4 trechos, e não 3. A posição da nota certa é a mesma nas 37 positivas, porque a profundidade da recuperação é 10 nos dois casos. Sem IA, a mudança não alterou nenhuma decisão: `cmp-32377de15bdf` (`top_k=4`) e C (`top_k=3`) decidiram igual nas 76 perguntas.
- **Código:** entre `f8844d8` e a `main` atual, `pipeline/src` só ganhou progresso, histórico e subtipos no benchmark, além de um lock na abertura do Chroma. O prompt, a regra de abstenção e os limiares são os mesmos.
- O app roda as três estratégias com IA, e o Experimento 22 rodou só a híbrida. Comparo só a híbrida.

### Exp 22 × reprodução (híbrida, lote cego)

| Métrica | D1 | D2 | D3 | Exp 22 (mediana) | Reprodução |
|---|---|---|---|---|---|
| **Decisões certas, com IA** | 54/76 | 54/76 | 53/76 | **54/76 (71%)** | **54/76 (71,1%)** |
| Positivas respondidas | 26/37 | 25/37 | 25/37 | 25/37 (68%) | 22/37 (59,5%) |
| Negativas recusadas | 28/39 | 29/39 | 28/39 | 28/39 (72%) | 32/39 (82,1%) |
| Negativas respondidas: quase-acerto (14) | 9 | 8 | 8 | 8 | 6 |
| Negativas respondidas: vocabulario-presente (12) | 2 | 2 | 3 | 2 | 1 |
| Negativas respondidas: fora-do-dominio (13) | 0 | 0 | 0 | 0 | 0 |
| Geradas de verdade (pos/neg) | 18 / 5 | 17 / 7 | 16 / 8 | | 15 / 3 |
| Sentinela `generated_no_answer_sentinel` | 10 | 11 | 10 | | 16 |
| MRR / Recall@3 | 0,8108 / 0,9459 | idem | idem | 0,811 / 0,946 | 0,8108 / 0,9459 (35/37) |
| **Decisões certas, sem IA** (C × `cmp-32377de15bdf`) | | | | **39/76 (51%)** | **39/76 (51,3%)**, mesmas 76 decisões |

As linhas por subtipo contam **negativas respondidas**, que são erros, como a tabela "Negativas respondidas por subtipo". Em acertos, a reprodução recusou 8/14 das quase-acerto, 11/12 das vocabulario-presente e 13/13 das fora-do-dominio. IC 95% de Wilson da reprodução: decisões certas [60,0%; 80,0%], positivas respondidas [43,5%; 73,7%], abstenção nas negativas [67,3%; 91,0%].

Pergunta a pergunta, comparando os JSONs de `data/results/experimentos/22_lote_cego/`:

- A reprodução tomou a mesma decisão que D1 em 68 das 76 perguntas, que D2 em 66 e que D3 em 65. Entre si, D1, D2 e D3 concordam em 71 a 75 de 76.
- Das 71 perguntas com a mesma decisão nas três rodadas do Experimento 22, a reprodução manteve 64. As outras 7 passaram todas de respondida para recusada: as positivas `lc-05-b`, `lc-06-a`, `lc-06-b` e `lc-08-c` e as negativas `lcn-06`, `lcn-09` e `lcn-33`. Nenhuma pergunta recusada nas três rodadas foi respondida agora.
- Das 5 perguntas que já variavam no Experimento 22, a reprodução respondeu `lc-03-a` e `lcn-02` e recusou `lcn-08`, `lcn-13` e `lcn-38`.

### Leitura

- **O total bate.** São 54/76 (71,1%), igual a D1 e D2 e dentro da faixa de 53 a 54 do Experimento 22. Sem IA, a reprodução é exata: 39/76, com as mesmas decisões nas 76 perguntas. A recuperação também é idêntica: MRR 0,8108, Recall@3 35/37 e as mesmas duas positivas fora do top 3 (`lc-04-d` e `lc-07-d`).
- **A composição não bate.** A reprodução foi mais conservadora. Respondeu 3 a 4 positivas a menos (22 contra 25 a 26) e 3 a 4 negativas a menos (7 contra 10 a 11), e os dois efeitos se anularam no total. Cada lado fica dentro do ruído conhecido de cerca de ±3 perguntas (Experimento 21). A direção, porém, é uma só: as 7 mudanças em relação ao consenso de D1 a D3 foram todas para recusa, e o modelo devolveu o sentinela de "sem resposta" 16 vezes, contra 10 a 11. Por isso a concordância com D1 a D3 (65 a 68 de 76) é menor que a concordância entre elas (71 a 75).
- Esta rodada não separa a causa. Pode ser o quarto trecho no contexto (`top_k=4`), a máquina e a GPU ou simplesmente o sorteio da temperatura 0,7.
- **Os subtipos mantêm a ordem.** `quase-acerto` continua o ponto fraco (6 de 14 respondidas, contra 8 a 9), e `fora-do-dominio` continua com 0 de 13.
- Os erros de valor se repetem. `lcn-03` respondeu de novo R$ 18.700, que é a licença do Datadog. `lcn-10` respondeu "0,81", outro valor errado (em D1 tinha sido 97,3). `lcn-07` conta como respondida, embora o texto gerado diga que a garantia não está mencionada no contrato: a métrica conta como resposta uma recusa escrita em texto livre.
- Fallback extrativo: das 22 positivas respondidas, 15 foram geradas e 7 vieram do fallback. Das 7 negativas respondidas, 3 foram geradas e 4 vieram do fallback.
- **Para o texto do TCC:** com IA, 71% de decisões certas em duas medições independentes, em máquinas e dias diferentes (quatro rodadas no total, de 53 a 54 de 76). Sem IA, 51%, idêntico nas duas. A taxa de positivas respondidas com IA variou de 59% a 70% entre as rodadas e não deve ser citada sem essa faixa.
- Latência e faithfulness não foram medidas nesta rodada.

### A suíte manual pelo app

A rodada `cmp-64e82a972b97` (2026-11-04, 00:59Z) passou a suíte manual pelo mesmo caminho do app: `top_k=4`, `qchat:latest`, notebook Windows. Deu **58/73 (79,5%)** de decisões certas, com 33/39 positivas respondidas e 25/34 negativas recusadas. No calibrado do Experimento 22, com `top_k=3`, foram 63 a 67 de 73 (mediana de 89%), com 36 a 37 de 39 positivas e 27 a 31 de 34 negativas.

É uma rodada só, e ela muda `top_k`, máquina e sorteio ao mesmo tempo, então não separa a causa. Mas é o número que o histórico do app mostra e que "Copiar tabela para o TCC" copia. Ao citar 89%, diga que é a mediana do Experimento 22 com `top_k=3`.
