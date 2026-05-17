# RAG com citação obrigatória e *no_answer threshold*: arquitetura, política de decisão e exemplos de implementação

**Autor:** Manus AI  
**Data:** 2026-04-05

## Introdução

A forma mais confiável de implementar **RAG para perguntas e respostas** não é tratar a recuperação apenas como um mecanismo de “buscar trechos parecidos”, mas como uma etapa formal de **seleção de evidência**. Na literatura, RAG surgiu justamente para combinar memória paramétrica do modelo com memória não paramétrica recuperada dinamicamente, com ganhos em tarefas intensivas em conhecimento e maior capacidade de atualizar conhecimento sem retreinar o modelo [1]. Em implantações reais, porém, a maior parte dos erros não vem apenas do modelo generativo; ela também emerge de decisões ruins de *chunking*, recuperação excessiva ou insuficiente, ordenação inadequada do contexto e ausência de uma política explícita para **abstenção** quando a evidência é fraca [2] [3].

Em aplicações profissionais e acadêmicas, portanto, um pipeline de RAG de alta qualidade deve impor cinco restrições simultâneas. A primeira é **recuperação top-k calibrada**, pois recuperar pouco contexto reduz cobertura e recuperar contexto demais degrada foco, latência e grounding. A segunda é **montagem de contexto com estrutura e proveniência**, preservando documento, seção, página e identificadores de trecho. A terceira é **resposta estruturada**, para que o modelo não produza texto livre sem disciplina de saída. A quarta é **citação obrigatória no nível da afirmação ou parágrafo**, não apenas no rodapé da resposta. A quinta é uma política explícita de **no_answer** quando o sistema não consegue demonstrar suficiência de evidência [3] [4].

Este documento apresenta uma forma prática de construir esse pipeline, com ênfase em boas práticas de engenharia, desenho de prompts, calibração de limiares e exemplos de saída orientados a cenários profissionais e acadêmicos.

## Princípio central: responder apenas quando a evidência sustenta a resposta

Um erro recorrente em RAG é pressupor que, se houve recuperação, então deve haver resposta. A literatura recente mostra que essa premissa é perigosa. O trabalho sobre **sufficient context** mostra que modelos fortes ainda tendem a responder incorretamente em vez de se abster quando o contexto é insuficiente, e que sinais de suficiência de contexto podem melhorar a decisão seletiva de responder ou abster-se [3]. De modo semelhante, um framework de **citation-enforced RAG** para documentos fiscais mostra que a combinação de recuperação com proveniência, citação rígida e abstention reduz alegações sem suporte e melhora auditabilidade em domínios de alto risco [4].

> Em um sistema RAG confiável, a pergunta correta não é “qual resposta parece plausível?”, mas sim “qual resposta pode ser explicitamente sustentada pelos trechos recuperados?”.

A consequência prática é simples: a arquitetura deve separar com clareza **evidência**, **síntese** e **decisão final**. A evidência vem da recuperação e do *reranking*; a síntese reorganiza essa evidência em uma resposta; a decisão final determina se há base suficiente para entregar a resposta ou se o sistema deve retornar **no_answer**.

## Arquitetura recomendada para um pipeline *ask* de RAG

A arquitetura abaixo é a mais recomendável quando o objetivo é responder perguntas com rastreabilidade documental.

| Etapa | Objetivo | Entrada | Saída | Regra de qualidade |
|---|---|---|---|---|
| 1. Normalização da pergunta | Limpar, classificar e enriquecer a consulta | Pergunta do usuário | Consulta normalizada | Não alterar o sentido da pergunta |
| 2. Recuperação inicial top-k | Maximizar *recall* de evidências candidatas | Consulta normalizada | Lista de candidatos | Priorizar cobertura antes de compressão |
| 3. *Reranking* | Reordenar por relevância fina | Pergunta + candidatos | Lista reranqueada | Remover ruído e duplicação |
| 4. Montagem de contexto | Construir evidência legível e auditável | Top-n reranqueado | Bloco de contexto estruturado | Preservar metadados e trechos literais |
| 5. Geração estruturada | Responder somente com base no contexto | Pergunta + contexto | Resposta em esquema fixo | Toda afirmação deve ser citável |
| 6. Verificação | Checar citações, suporte e completude | Resposta + evidência | Resposta aceita ou rejeitada | Falhou grounding, não entrega |
| 7. Política de decisão | Responder ou retornar *no_answer* | Sinais de evidência | Resultado final | Sem evidência suficiente, abster |

Essa modularização é coerente com estudos de melhores práticas em RAG, que tratam o fluxo como um conjunto de módulos independentes — classificação de consulta, recuperação, *reranking*, *repacking* e compressão — cujas combinações afetam qualidade e latência [2]. Para aplicações corporativas, essa separação é valiosa porque facilita auditoria, *debugging* e *ablation testing*.

## Top-k de recuperação: como escolher sem degradar o sistema

A recuperação inicial deve ser pensada como uma etapa de **alta cobertura**, não como a seleção final da evidência. Em geral, a prática mais robusta é recuperar um **k maior** na primeira fase e reduzir depois com *reranking*. Trabalhos de melhores práticas indicam que o pipeline ganha quando a recuperação, o *reranking* e a reorganização do contexto são tratados como módulos distintos, em vez de condensar tudo em uma única busca vetorial [2].

Na prática, o desenho mais seguro é o seguinte. O sistema recupera um `k_retrieve` relativamente amplo, por exemplo entre 20 e 80 trechos, dependendo do corpus. Em seguida, aplica um *reranker* mais caro para escolher um `k_context` menor, frequentemente entre 4 e 12 trechos para geração final. Esse desenho é preferível porque o retriever inicial privilegia *recall*, enquanto o *reranker* melhora precisão local. A literatura de RAG também enfatiza que o tamanho do contexto e o *chunking* afetam fortemente a relevância e a fidelidade da resposta [2].

### Regra prática de parametrização

| Parâmetro | Papel | Faixa inicial recomendada | Observação |
|---|---|---|---|
| `k_retrieve` | Candidatos brutos do retriever | 20–80 | Ajustar conforme tamanho do corpus e diversidade do domínio |
| `k_rerank` | Quantos candidatos o reranker avalia | Igual a `k_retrieve` ou top 50 | Maior valor aumenta custo, mas melhora precisão |
| `k_context` | Trechos finais enviados ao gerador | 4–12 | Acima disso cresce o risco de ruído e “lost in the middle” [2] |
| `min_distinct_sources` | Fontes independentes mínimas | 1–3 | Útil para evitar resposta baseada em único trecho frágil |
| `max_tokens_context` | Limite de contexto final | Dependente do modelo | Deve deixar espaço para instruções e resposta estruturada |

A melhor prática não é fixar esses valores como dogma, mas **calibrá-los empiricamente**. Em corpus regulatórios ou científicos, nos quais precisão importa mais que cobertura superficial, frequentemente vale reduzir `k_context` e elevar exigências de suporte cruzado. Em bases heterogêneas ou com OCR imperfeito, pode ser melhor elevar `k_retrieve` para recuperar redundância útil [4].

## Montagem de contexto: como transformar trechos em evidência utilizável

A montagem de contexto não deve concatenar trechos de maneira cega. O contexto precisa funcionar como um **dossiê de evidência** legível para o modelo e auditável para humanos. Em implementações orientadas a citação, a recomendação mais forte é manter estratégia **source-first**, isto é, recuperar apenas conteúdo derivado diretamente do documento-fonte, preservando metadados como `doc_id`, página, seção, posição e identificador do trecho [4].

Em termos de estrutura, cada item de contexto deve trazer quatro componentes: o identificador da fonte, o excerto textual, os metadados de localização e, idealmente, um escore de relevância. Essa organização melhora o grounding e reduz a tendência de o modelo usar conhecimento paramétrico fora do corpus [4].

### Exemplo de contexto bem montado

```text
[CHUNK 1]
doc_id: paper_2024_acl_17
section: 4.2 Results
page: 8
score: 0.842
text: "The proposed method improves factual consistency by 6.3 F1 over the baseline on the BioASQ test set."

[CHUNK 2]
doc_id: paper_2024_acl_17
section: 5 Limitations
page: 9
score: 0.801
text: "The gains are limited to factoid questions and should not be generalized to long-form explanation tasks."

[CHUNK 3]
doc_id: paper_2023_survey_02
section: 3.1 Evaluation
page: 5
score: 0.774
text: "Faithfulness and attribution should be evaluated separately, since a correct answer may still be poorly attributed."
```

A montagem também deve fazer **deduplicação semântica**. Se três trechos dizem essencialmente a mesma coisa, o ideal é manter um ou dois, preservando diversidade de evidência. Em casos de pergunta multi-hop, a montagem deve distribuir os trechos de forma que o modelo consiga compor os passos intermediários, em vez de esconder informação crítica no meio de contexto longo [2] [3].

## Resposta estruturada: o modelo precisa de contrato, não de liberdade total

A resposta final deve seguir um **esquema fixo**. Isso evita que o modelo misture resposta, justificativa, incerteza e citações em texto solto. Em produção, o formato ideal é JSON validável; em interfaces humanas, o mesmo conteúdo pode ser renderizado em Markdown.

Um esquema robusto precisa separar, pelo menos, **status da decisão**, **resposta curta**, **afirmações suportadas**, **citações associadas**, **limitações** e **justificativa de no_answer**, quando aplicável. Esse desenho é superior a um único campo `answer` porque obriga o sistema a expor o grau de sustentação de cada afirmação.

### Esquema recomendado de saída

```json
{
  "status": "answer | no_answer",
  "answer": "string | null",
  "claims": [
    {
      "text": "string",
      "citations": ["doc_id:page[:chunk_id]"],
      "support_level": "direct | partial"
    }
  ],
  "limitations": ["string"],
  "reason_for_no_answer": "string | null",
  "used_sources": [
    {
      "doc_id": "string",
      "pages": [1, 2]
    }
  ]
}
```

Esse esquema também facilita avaliação automática. É possível verificar programaticamente se cada `claim` possui ao menos uma citação, se as citações existem no contexto e se o `status` é consistente com os sinais de evidência. Em domínios regulados, essa verificabilidade operacional vale mais do que uma resposta mais “bonita”.

## Citação obrigatória: o requisito deve ser rígido, não estilístico

A maior falha de muitos sistemas “com citações” é que a citação funciona apenas como decoração. O modelo produz a resposta e, depois, anexa referências genéricas. Isso não basta. Em sistemas confiáveis, a citação precisa ser tratada como **restrição de validade**: sem citação válida, a resposta não é aprovada [4].

O padrão mais seguro é exigir citação por **parágrafo** ou por **afirmação atômica**. O trabalho de citation-enforced RAG em documentos fiscais mostra exatamente esse princípio: cada bloco gerado precisa remeter a documento, página e trecho, e saídas sem citação válida devem ser regeneradas ou rejeitadas [4].

### Política recomendada de citação

| Nível de exigência | Como funciona | Quando usar |
|---|---|---|
| Por resposta inteira | Uma lista de fontes ao final | Baixa exigência; não recomendado para produção crítica |
| Por parágrafo | Cada parágrafo cita 1+ fontes | Bom equilíbrio para relatórios e assistentes internos |
| Por afirmação | Cada *claim* traz suas próprias citações | Melhor opção para QA auditável e ambientes regulados |
| Com citação literal | Além da fonte, guarda *span* ou excerto | Ideal para revisão humana e auditoria formal |

A melhor prática é complementar a citação com um **validador pós-geração**. Esse validador deve verificar ao menos quatro aspectos: presença de citação, formato correto, existência da fonte no contexto e plausibilidade mínima de alinhamento entre afirmação e trecho citado. Se uma dessas condições falha, o sistema não deve “deixar passar”.

## Política de *no_answer*: quando a evidência é insuficiente

A política de **no_answer** não deve depender apenas da “sensação de confiança” do modelo gerador. O que a literatura recente sugere é que a decisão de abstenção melhora quando é guiada por sinais explícitos de suficiência de contexto [3] e por sinais de confiança da própria recuperação [4]. Em outras palavras, o sistema deve perguntar: **há evidência suficiente, consistente e citável para responder?**

O desenho mais robusto é usar uma política híbrida, baseada em múltiplos sinais. Nenhum sinal isolado é suficiente em todos os corpora, mas a combinação de sinais tende a ser muito mais estável.

### Sinais úteis para decidir `no_answer`

| Sinal | Interpretação | Uso recomendado |
|---|---|---|
| `top1_similarity` | Força do melhor trecho recuperado | Bom sinal inicial, mas não suficiente sozinho |
| `support_count` | Quantos trechos distintos sustentam a resposta | Crucial para evitar resposta apoiada em evidência frágil |
| `source_diversity` | Quantas fontes independentes corroboram a resposta | Importante em corpora multi-documento |
| `citation_coverage` | Percentual de *claims* com citação válida | Deve ser próximo de 100% para aprovar resposta |
| `context_sufficiency_score` | Estimativa explícita de suficiência | Muito útil para decisão seletiva [3] |
| `contradiction_flag` | Indica conflito entre trechos recuperados | Forte motivo para abstenção ou resposta limitada |
| `generation_refusal_signal` | O gerador declara falta de base | Útil, mas nunca deve ser o único critério |

### Regra híbrida de decisão

Uma política prática e defensável pode ser descrita assim:

```text
Responder somente se:
1. top1_similarity >= T_sim
2. support_count >= T_support
3. citation_coverage == 100%
4. contradiction_flag == false
5. context_sufficiency_score >= T_suff

Caso contrário, retornar status = no_answer.
```

Para iniciar um sistema, uma configuração razoável de prototipagem é usar algo como `T_sim` entre 0.45 e 0.65, `T_support >= 2` para afirmações analíticas e `T_suff` calibrado em conjunto de validação. No entanto, esses números não devem ser tratados como universais. O estudo fiscal citado observou separação útil entre casos respondíveis e não respondíveis por similaridade de recuperação, com boa parte das consultas respondíveis exibindo *top-1 similarity* acima de 0.55 naquele corpus específico [4]. Isso é um **ponto de partida**, não uma lei geral.

## Política de saída para *no_answer*

Um bom `no_answer` não é um fracasso silencioso. Ele deve informar de maneira profissional **por que** a resposta não foi entregue. Essa transparência é enfatizada em frameworks abstention-aware, nos quais a recusa explícita é preferível a inferências especulativas em cenários de alto risco [4].

### Exemplo de saída de `no_answer`

```json
{
  "status": "no_answer",
  "answer": null,
  "claims": [],
  "limitations": [
    "Os trechos recuperados não estabelecem explicitamente a resposta.",
    "Há evidência parcial, mas insuficiente para responder com citação verificável."
  ],
  "reason_for_no_answer": "similaridade abaixo do limiar e cobertura insuficiente de evidência",
  "used_sources": [
    {"doc_id": "policy_manual_v3", "pages": [12]},
    {"doc_id": "faq_internal_2025", "pages": [4]}
  ]
}
```

Em interfaces voltadas ao usuário, essa estrutura pode ser convertida para uma mensagem mais natural, como: “Não encontrei evidência suficiente no corpus para responder com segurança e citação verificável.” O ponto importante é que o sistema não deve inventar uma conclusão apenas para manter fluidez conversacional.

## Exemplo profissional: assistente corporativo de políticas internas

Considere um assistente que responde perguntas sobre política de reembolso de viagens. O corpus contém manual corporativo, memorandos financeiros e FAQ interna. A pergunta é: *“Posso reembolsar jantar com cliente internacional sem aprovação prévia do diretor?”*

O pipeline recomendado funciona assim. Primeiro, o retriever busca os top-40 trechos. Depois, um *reranker* reduz para 6 trechos. Na montagem de contexto, o sistema preserva `doc_id`, seção e página. O gerador recebe instrução explícita para responder apenas com base na evidência e para anexar citações por afirmação. Após a geração, o validador verifica se todas as afirmações possuem citação válida e se a resposta não extrapola o que está nos documentos.

### Exemplo de resposta aprovada

```json
{
  "status": "answer",
  "answer": "Despesas com jantar de negócios internacional podem ser reembolsadas, mas a política exige aprovação prévia do diretor quando o valor excede o limite de alçada do gestor imediato.",
  "claims": [
    {
      "text": "Jantares de negócios internacionais são despesas reembolsáveis.",
      "citations": ["travel_policy_2025:14:chunk_208"],
      "support_level": "direct"
    },
    {
      "text": "Aprovação prévia do diretor é exigida quando o valor excede o limite de alçada do gestor imediato.",
      "citations": ["finance_memo_2025_02:3:chunk_044", "travel_policy_2025:15:chunk_219"],
      "support_level": "direct"
    }
  ],
  "limitations": [
    "O corpus recuperado não informa o valor exato do jantar em questão."
  ],
  "reason_for_no_answer": null,
  "used_sources": [
    {"doc_id": "travel_policy_2025", "pages": [14, 15]},
    {"doc_id": "finance_memo_2025_02", "pages": [3]}
  ]
}
```

Esse exemplo é profissional porque a resposta não diz apenas “sim” ou “não”. Ela expressa a conclusão com condição normativa, cita a base e explicita a limitação residual.

## Exemplo acadêmico: assistente para revisão de literatura

Agora considere uma pergunta acadêmica: *“O artigo X demonstra ganho estatisticamente significativo em factualidade sobre o baseline?”* Nesse cenário, não basta encontrar menções positivas. O sistema precisa localizar resultados, métrica, baseline e, se possível, observação metodológica sobre o escopo do ganho.

A montagem de contexto deve privilegiar trechos de **resultados**, **tabelas textualizadas**, **metodologia de avaliação** e **limitações**. Se apenas a introdução do artigo declara melhora, mas a seção experimental não confirma, o sistema deve se abster ou responder de forma parcial.

### Exemplo de resposta acadêmica aprovada

```json
{
  "status": "answer",
  "answer": "Sim, o artigo relata ganho em factualidade sobre o baseline, mas o efeito está restrito ao conjunto de avaliação utilizado pelos autores e não deve ser generalizado para tarefas long-form sem nova validação.",
  "claims": [
    {
      "text": "O artigo reporta melhora em factualidade em relação ao baseline no conjunto experimental avaliado.",
      "citations": ["paper_2024_acl_17:8:chunk_112"],
      "support_level": "direct"
    },
    {
      "text": "Os próprios autores limitam a generalização dos ganhos para fora do escopo avaliado.",
      "citations": ["paper_2024_acl_17:9:chunk_131"],
      "support_level": "direct"
    }
  ],
  "limitations": [
    "Os trechos recuperados não incluem teste externo independente nem reanálise estatística própria."
  ],
  "reason_for_no_answer": null,
  "used_sources": [
    {"doc_id": "paper_2024_acl_17", "pages": [8, 9]}
  ]
}
```

Esse padrão é academicamente mais sólido porque evita duas distorções frequentes: resumir apenas a introdução e omitir as limitações do estudo.

## Prompt recomendado para geração com citação obrigatória

A instrução ao gerador precisa ser inequívoca. O modelo não deve ser autorizado a completar lacunas com conhecimento paramétrico. Um prompt eficaz é aquele que explicita a fonte exclusiva de informação, o formato de saída e a política de abstenção.

```text
Você é um sistema de QA baseado em evidências.
Responda somente com base nos trechos fornecidos em CONTEXT.
Não use conhecimento externo.
Toda afirmação deve citar pelo menos uma evidência no formato [doc_id:page:chunk_id].
Se a evidência for insuficiente, ambígua, contraditória ou não permitir resposta verificável,
retorne status = no_answer.

Saída obrigatória em JSON com os campos:
status, answer, claims, limitations, reason_for_no_answer, used_sources.

Uma claim só pode aparecer se houver citação válida.
Não invente citações.
```

Essa instrução deve ser acompanhada de um **parser estrito** e de um **validador pós-geração**. Em termos de engenharia, a robustez do pipeline não vem apenas do prompt, mas da combinação de prompt com validação e rejeição automática.

## Pseudocódigo do pipeline recomendado

O fluxo abaixo sintetiza uma implementação profissional.

```python
def ask_rag(question: str) -> dict:
    q = normalize_question(question)

    retrieved = retriever.search(q, top_k=40)
    reranked = reranker.rank(q, retrieved)
    selected = select_context(
        reranked,
        top_n=6,
        max_tokens=2200,
        dedupe=True,
        diversify_sources=True,
    )

    evidence_signals = compute_evidence_signals(q, selected)

    if should_abstain_pre_generation(evidence_signals):
        return {
            "status": "no_answer",
            "answer": None,
            "claims": [],
            "limitations": [
                "Evidência insuficiente antes da geração."
            ],
            "reason_for_no_answer": evidence_signals["reason"],
            "used_sources": summarize_sources(selected),
        }

    raw_output = generator.generate(
        prompt=build_grounded_prompt(q, selected),
        response_format="json"
    )

    parsed = parse_json(raw_output)
    validation = validate_answer(parsed, selected)

    if not validation["ok"]:
        return {
            "status": "no_answer",
            "answer": None,
            "claims": [],
            "limitations": [validation["message"]],
            "reason_for_no_answer": "citation_or_grounding_validation_failed",
            "used_sources": summarize_sources(selected),
        }

    if should_abstain_post_generation(parsed, evidence_signals, validation):
        return {
            "status": "no_answer",
            "answer": None,
            "claims": [],
            "limitations": parsed.get("limitations", []),
            "reason_for_no_answer": "insufficient_evidence_after_validation",
            "used_sources": summarize_sources(selected),
        }

    return parsed
```

O ponto mais importante nesse pseudocódigo é que existem **duas oportunidades de abstenção**: antes da geração, com base nos sinais de evidência, e depois da geração, com base na validação de grounding. Essa redundância é desejável em aplicações sérias.

## Como calibrar o *threshold* de `no_answer`

O limiar correto não deve ser definido “no sentimento”. Ele deve ser calibrado em um conjunto rotulado, contendo pelo menos três classes: **respondível com evidência suficiente**, **parcialmente suportado**, e **não respondível**. O objetivo é identificar o ponto em que a taxa de respostas incorretas cai sem sacrificar demais a cobertura útil.

### Procedimento de calibração

| Etapa | Descrição | Resultado esperado |
|---|---|---|
| 1 | Montar conjunto de validação com perguntas reais | Base representativa do domínio |
| 2 | Rotular suficiência de evidência | Separação entre respondível e não respondível |
| 3 | Medir sinais por pergunta | Similaridade, suporte, diversidade, contradição |
| 4 | Varredura de limiares | Curvas de precisão, cobertura e abstention |
| 5 | Escolher política | Melhor compromisso para o risco do caso de uso |
| 6 | Revalidar periodicamente | Ajuste após mudança de corpus ou modelo |

A literatura sobre *sufficient context* sugere que uma estimativa explícita de suficiência pode ser usada como sinal de **selective generation**, isto é, responder apenas quando a probabilidade de contexto suficiente é alta [3]. Em sistemas corporativos, isso pode ser implementado por meio de um pequeno classificador, de um avaliador auxiliar ou de regras compostas sobre os sinais de recuperação.

## O que medir em avaliação offline

Avaliar RAG com citação obrigatória exige mais do que *accuracy*. É necessário medir **resposta correta**, **atribuição correta** e **abstenção correta** separadamente, pois são fenômenos distintos [3] [4].

### Métricas mínimas recomendadas

| Métrica | O que mede | Por que importa |
|---|---|---|
| Answer Accuracy | Correção da resposta final | Mede utilidade factual |
| Citation Coverage | Percentual de claims com citação válida | Mede disciplina de grounding |
| Citation Support | Se a citação realmente sustenta a claim | Mede confiança auditável |
| Abstention Accuracy | Se o sistema se absteve quando deveria | Mede conservadorismo útil |
| Hallucination Rate | Claims sem base documental | Mede risco residual |
| Context Sufficiency Recall | Capacidade de identificar contexto suficiente | Mede qualidade da política seletiva |

Em termos acadêmicos, vale distinguir **correctness**, **faithfulness/grounding** e **attribution**, pois uma resposta pode até coincidir com a verdade, mas estar mal atribuída ou sustentada por citações inadequadas [3] [4]. Essa distinção é decisiva para sistemas que precisam de auditabilidade.

## Erros frequentes e como evitá-los

Os maiores fracassos de pipelines RAG com citação decorrem menos da ausência de um LLM mais forte e mais de erros de desenho do sistema. O primeiro erro é usar contexto demais sem *reranking*; isso piora foco e aumenta confusão. O segundo é citar fontes ao final da resposta sem mapear claims para evidências. O terceiro é aceitar como “respondida” uma pergunta cuja evidência é apenas parcialmente relacionada. O quarto é não ter uma política de recusa explícita. O quinto é medir apenas qualidade textual, sem medir suporte documental.

### Antipadrões críticos

| Antipadrão | Consequência | Correção |
|---|---|---|
| Recuperar top-k pequeno demais | Perda de evidência relevante | Aumentar `k_retrieve` e reranquear |
| Concatenar contexto sem estrutura | Resposta menos grounded | Montar contexto com metadados e ordem controlada |
| Citação no rodapé apenas | Falsa sensação de auditabilidade | Exigir citação por claim ou parágrafo |
| Sem política de abstention | Hallucinação confiante | Implementar `no_answer` por sinais múltiplos |
| Threshold fixado arbitrariamente | Cobertura ou precisão ruins | Calibrar em conjunto rotulado |
| Avaliar só EM/F1 | Não detecta má atribuição | Medir grounding e abstenção separadamente |

## Recomendação final de desenho

A melhor forma de fazer RAG com **citação obrigatória** e política de **no_answer** é adotar uma arquitetura em que a recuperação serve para coletar evidência, o *reranking* serve para priorizar evidência utilizável, a montagem de contexto serve para preservar proveniência, a geração serve apenas para sintetizar o que está sustentado e a decisão final serve para bloquear respostas não verificáveis. Esse desenho é consistente com a evolução da literatura: RAG melhora acesso a conhecimento atualizado [1]; a qualidade do pipeline depende de escolhas modulares como *chunking*, *reranking* e organização de contexto [2]; a decisão de responder deve considerar **suficiência de contexto** [3]; e a combinação de citação rígida com abstention explícita aumenta auditabilidade e reduz alegações sem suporte [4].

Se o objetivo for construir um sistema sério, a regra operacional deve ser esta: **sem evidência suficiente e citável, não responda**. Em RAG de produção, uma boa abstenção vale mais do que uma resposta eloquente e errada.

## Referências

[1]: https://proceedings.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html "Lewis et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
[2]: https://arxiv.org/html/2407.01219v1 "Wang et al. (2024). Searching for Best Practices in Retrieval-Augmented Generation"
[3]: https://openreview.net/forum?id=Jjr2Odj8DJ "Joren et al. (2025). Sufficient Context: A New Lens on Retrieval Augmented Generation Systems"
[4]: https://arxiv.org/html/2603.14170v1 "Shanivendra (2026). Citation-Enforced RAG for Fiscal Document Intelligence: Cited, Explainable Knowledge Retrieval in Tax Compliance"
