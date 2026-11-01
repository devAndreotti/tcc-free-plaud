---
tags:
- tcc
- pesquisa
- rag
- pkm
- ia
---

# Desenvolvimento e Avaliação de um Pipeline de IA para Captura e Recuperação Semântica de Conhecimento Pessoal

## Visão geral

Este trabalho propõe, implementa e avalia um sistema local-first para capturar conhecimento pessoal a partir de áudio, imagem, texto e PDF, transformar esse material em notas Markdown estruturadas e recuperar informações por meio de RAG com citação obrigatória.

O foco do TCC não é apenas construir um produto, mas investigar experimentalmente como certas decisões técnicas afetam a qualidade do sistema em português brasileiro.

## Premissa central

Modelos de linguagem de propósito geral, sem fine-tuning, podem ser suficientes para construir um sistema de PKM pessoal útil, desde que o pipeline seja bem desenhado e seus parâmetros sejam avaliados empiricamente.

## Problema

Muita informação pessoal e profissional é capturada, mas não reaproveitada.

As ferramentas atuais frequentemente exigem:

- captura manual disciplinada
- organização manual constante
- revisão ativa do acervo

Na prática, isso faz com que boa parte do conhecimento já registrado se torne difícil de recuperar quando necessário.

## Objetivo geral

Desenvolver e avaliar um pipeline de IA para captura multimodal e recuperação semântica de conhecimento pessoal em português brasileiro, usando infraestrutura local e chaves de API do próprio usuário.

## Objetivos específicos

1. estruturar entradas multimodais em notas Markdown consistentes
2. indexar essas notas em persistência dual local (SQLite FTS5 + ChromaDB)
3. permitir consulta em linguagem natural com respostas fundamentadas no acervo e citações com spans exatos
4. medir o impacto de parâmetros de chunking, recuperação híbrida (Reciprocal Rank Fusion) e embeddings
5. documentar uma arquitetura replicável para esse tipo de sistema

## Artefato do trabalho

O artefato implementado é composto por cinco módulos centrais:

1. **Ingestão Multimodal**: Faster-Whisper (CUDA 12.8 / CPU) para áudio, extratores PDF e normalizadores Markdown.
2. **Normalização & Sanitização**: Schemas Pydantic com preservação estrita de spans de caracteres.
3. **Persistência Dual Local**: SQLite com extensão FTS5 (BM25 lexical) e ChromaDB (vetorial denso).
4. **AutoRAG Híbrido com RRF**: Fusão por Reciprocal Rank Fusion com amortecimento $k=60$ e verificação determinística de citações.
5. **Harness de Benchmark & Interfaces**: Suíte de avaliação empírica automatizada (MRR, Recall@k), CLI (Typer), TUI (Textual) e Desktop (PyWebView + React 19).

---

## Fundamentação Matemática da Fusão Híbrida (RRF)

A recuperação híbrida combina o ranking léxico (SQLite FTS5 / BM25) e o ranking vetorial (ChromaDB) por meio do algoritmo Reciprocal Rank Fusion (RRF), que agrega as posições de um mesmo documento em listas de ranking distintas sem exigir normalização das escalas de score heterogêneas de cada método. A pontuação final de um documento $d$ é dada por:

$$RRF\_Score(d) = \sum_{m \in \{lexical,\ vector\}} \frac{w_m}{k + rank_m(d)}$$

em que $rank_m(d)$ é a posição de $d$ no ranking do método $m$ (1-indexado), $k$ é a constante de amortecimento e $w_m$ é o peso atribuído ao método. O amortecimento por $k$ é o que torna o RRF robusto: reduz a influência de posições muito altas em uma única lista (evitando que um único método domine o resultado) e evita divisão por valores próximos de zero, problema comum em fusões baseadas diretamente em score bruto.

A calibração do projeto testou $k \in \{10, 60, 100\}$ mantendo $w_{vector}=1.0$ fixo (Experimentos 07 e 15, `docs/experimentos/07_calibracao_fusao_hibrida.md` e `docs/experimentos/15_calibracao_rrf_tcc.md`). O Experimento 15 não é reproduzível e seus valores não foram remedidos; por isso $k=60$ é mantido como padrão do projeto, sem afirmar que seja o ótimo. Valores baixos de $k$ super-ponderam o topo do ranking de cada método individual, amplificando ruído de qualquer um dos lados; valores altos achatam demais as diferenças de posição, aproximando o resultado de uma média simples e reduzindo poder discriminativo.

Complementarmente, o Experimento 07 calibrou os pesos $w_m$ mantendo $k=60$ fixo: elevar $w_{lexical}$ de 1.0 para 1.5 (com $w_{vector}=1.0$) eliminou o gap de MRR do híbrido em relação à busca léxica pura nessa suíte do Experimento 07, não remedida (0.96875 em ambas, Recall@3 = 1.0), sem regressão de cobertura. Esse ajuste reflete uma característica do corpus em português técnico: termos exatos (nomes de tecnologias, cláusulas contratuais, identificadores) têm alto valor de recuperação e são mais bem capturados por BM25 do que por similaridade de cosseno em embeddings. Os parâmetros calibrados $w_{lexical}=1.5$, $w_{vector}=1.0$, $k=60$ foram promovidos a padrão do projeto.

## Resultados Empíricos & Avaliação Experimental

Com o objetivo de responder às perguntas centrais de pesquisa sobre o impacto das decisões de recuperação (P2 e P3), foram executados benchmarks controlados comparando estratégias léxicas puras, vetoriais puras e fusão híbrida com amortecimento $k=60$ (medição reproduzida no Experimento 20, de 2026-10-31):

### Tabela de Comparação Experimental de Recuperação

| Estratégia de Recuperação | MRR (IC 95%) | Recall@3 | Recall@5 | Latência média por consulta |
|---|---|---|---|---|
| **Léxica Pura (SQLite FTS5 BM25)** | 0.910 (0.833; 0.962) | 1.000 | 1.000 | ~1.2 ms |
| **Vetorial Pura (ChromaDB)** | 0.816 (0.709; 0.915) | 0.923 | 0.923 | ~69 ms |
| **Híbrida RRF (k=60, $w_{lexical}=1.5$)** | **0.915** (0.842; 0.974) | **1.000** | **1.000** | ~69 ms |

Suíte: 10 notas e 39 perguntas positivas, `top_k=3`, sem geração por LLM (Experimento 20).

### Análise dos Resultados

1. **Vantagem do híbrido restrita à busca vetorial**: na suíte medida, a fusão RRF superou a busca vetorial pura (MRR 0.915 contra 0.816, +12%), mas não superou de forma distinguível a busca léxica (MRR 0.915 contra 0.910, com intervalos de confiança sobrepostos).
2. **Fator $k=60$**: mantido como padrão do projeto. A comparação com outros valores de $k$ não foi remedida nesta versão, então a afirmação de que $k=60$ é o ótimo não é sustentada pelos dados atuais.
3. **Latência**: a consulta léxica leva ~1 ms e as consultas vetorial e híbrida ~69 ms, no mesmo hardware. A fusão RRF não foi medida isoladamente; a diferença entre vetorial e híbrida está dentro do ruído da medição.

---

## Respostas às Perguntas de Pesquisa

### P1: A recuperação híbrida (BM25 + vetores) apresenta vantagem sobre a recuperação isolada?

Parcialmente. Na suíte medida no Experimento 20 (10 notas, 39 perguntas positivas, `top_k=3`), a fusão híbrida RRF ($k=60$, $w_{lexical}=1.5$) obteve MRR de 0.915 (IC 95% [0.842; 0.974]). Esse valor supera a busca vetorial pura (0.816, IC [0.709; 0.915]), mas fica praticamente igual à busca léxica pura (0.910, IC [0.833; 0.962]), com intervalos sobrepostos. Portanto, nesta suíte, a vantagem do híbrido sobre a vetorial é mensurável e a vantagem sobre a léxica não é. A hipótese de complementaridade entre termos exatos (BM25) e paráfrases (vetores) não foi testada isoladamente: a suíte tem recall saturado na léxica e não separa perguntas parafraseadas. Confirmá-la exige uma suíte maior com esse grupo de perguntas. O Experimento 07, em outra suíte não remedida, reportou igualdade de MRR com a léxica (0.96875); esse resultado não sustenta sozinho uma superioridade do híbrido.

### P2: Qual o impacto das estratégias de chunking e da preservação de spans/lineage?

A preservação estrita de spans de caracteres (offset exato no documento de origem) demonstrou impacto direto na qualidade percebida das respostas, não apenas na recuperação. O Experimento 11 (`docs/experimentos/11_poda_span_minimo_suficiente.md`) mostra que, mantendo retrieval e chunking constantes, refinar a poda do span citado — sem alterar `chunk_size` ou `overlap` — reduziu o texto citado em até 84% no caso mais extremo reportado (`paper-03`, de 603 para 97 caracteres; não há média consolidada) eliminando ruído administrativo (headings, anexos, cláusulas adjacentes) e mantendo os testes de guardrail (108 casos) passando integralmente. Isso indica que o valor de um pipeline de citação obrigatória não está apenas em recuperar o chunk correto, mas em rastrear o span mínimo suficiente dentro dele até o caractere exato — sem esse rastreamento (`char_start`/`char_end` na tabela de trechos do SQLite; a tabela FTS5 indexa apenas o texto), a poda de resposta seria impossível de fazer com segurança factual. Quanto à granularidade de chunking em si, a configuração `chunk_size=800`/`overlap=120` foi mantida como baseline estável ao longo de todos os experimentos de retrieval (03, 07, 15) por não ter sido identificada evidência de que outra granularidade testada indiretamente (via mudança de embedding, Experimento 03) alterasse esse parâmetro de forma isolada — o chunking mostrou-se um fator de segundo grau frente ao método de recuperação e à poda de span.

### P3: Modelos de embedding e LLM locais são viáveis frente a alternativas em nuvem? Quais os trade-offs?

A viabilidade é condicional, não incondicional. No eixo de embeddings, o Experimento 03 (`docs/experimentos/03_embeddings_alternativos_suite_baseline.md`) testou dois modelos locais multilíngues (`paraphrase-multilingual-MiniLM-L12-v2` e `paraphrase-multilingual-mpnet-base-v2`) contra o baseline `chroma-default`, e ambos tiveram desempenho pior (MRR 0.615 e 0.531, respectivamente, contra 0.792 do baseline) — ou seja, nem todo modelo local "mais moderno" ou "mais pesado" supera um baseline já ajustado ao domínio; a escolha de embedding exige validação empírica por suíte, não apenas por especificação de tamanho de modelo. No eixo de geração (LLM), a arquitetura do projeto (`docs/plano_execucao/HANDOFF_RAG_GENERATIVO_LOCAL_API_E_GIT.md`) adota um provider OpenAI-compatible que abstrai Ollama, LM Studio e APIs de nuvem (OpenAI) atrás da mesma interface, permitindo trocar o backend generativo sem alterar o núcleo RAG. Isso viabiliza o uso 100% local (Ollama/LM Studio), preservando a premissa local-first do projeto, mas com trade-off de qualidade de geração variável conforme o modelo local escolhido — mitigado pelo desenho do sistema, em que o LLM só participa após retrieval e citação já validados (nunca antes), e uma falha do provider local sempre recai em resposta extrativa determinística, sem interromper o fluxo. Assim, o trade-off central não é "local versus nuvem" em abstrato, mas a necessidade de validação empírica por componente (embedding e modelo generativo) e o desenho em que a geração só ocorre após recuperação e citação validadas, com fallback extrativo quando o provedor falha. O Experimento 21 (`docs/experimentos/21_abstencao_e_faithfulness_com_ia.md`) mediu esse desenho com um modelo local de 3B (`qchat`, derivado do Qwen 2.5 3B). Com a IA, as perguntas sem resposta no acervo respondidas indevidamente caíram de 13 para 6 em 34. Em troca, 3 a 5 positivas deixaram de ser respondidas (33 a 35 de 39, conforme a rodada, contra 38/39 no modo extrativo). Das afirmações geradas, cerca de 87% (34/39) estão sustentadas pelos trechos citados, segundo auditoria manual. As falhas associam um valor ou uma data à entidade errada. O juiz automático de 3B mostrou-se estrito demais para servir sozinho de métrica: ele reprova 1 em 10 afirmações que são cópias literais do trecho.

## Limitações e Considerações Éticas

- **Validade externa:** a avaliação usa uma suíte pequena (10 notas, 39 perguntas positivas) escrita pelo autor, sem rotulagem independente. Os intervalos de confiança são largos.
- **Geração medida em pequena escala:** a faithfulness das respostas geradas (≈ 87%, Experimento 21) vem de 39 afirmações e de uma auditoria manual feita por uma pessoa só. Com o mesmo modelo, a decisão de responder ou recusar varia em cerca de ±3 perguntas entre rodadas.
- **Abstenção:** parte das perguntas fora do acervo ainda é respondida (6/34 com IA, 13/34 sem IA). A taxa observada deve ser reportada junto com qualquer resultado de recuperação.
- **Paráfrase:** sem IA, uma pergunta que usa um termo ausente do corpus é recusada, mesmo quando a nota diz o mesmo com outras palavras. Com IA, essa pergunta ganha uma segunda chance, mas pergunta dupla que cruza duas notas ainda é recusada.
- **Voz e privacidade:** a transcrição e a indexação são locais. A geração só envia dados a um provedor remoto se ele for configurado explicitamente. A gravação de conversas de terceiros exige consentimento, que é responsabilidade do usuário; o sistema não implementa controle de consentimento nem anonimização de áudio.
- **Hardware:** os tempos medidos referem-se a uma única máquina de desenvolvimento.

## Conclusões do Trabalho

1. **Viabilidade sem Fine-Tuning**: na suíte medida, a recuperação com embeddings genéricos (`chroma-default`) e a busca léxica atingem MRR entre 0,82 e 0,92, sem retreinamento de pesos. Na geração, um modelo local de 3B sem ajuste para a tarefa teve cerca de 87% das afirmações sustentadas (Experimento 21). O número é promissor, mas vem de uma amostra pequena; por isso a hipótese H1, no que se refere à geração, fica parcialmente confirmada.
2. **Mitigação de Alucinações**: a citação obrigatória com checagens determinísticas (sobreposição com os trechos, números e nomes próprios) recusa perguntas fora do acervo e descarta respostas geradas sem suporte lexical. Isso reduz o risco de respostas fabricadas, mas não o elimina. No Experimento 21, cerca de 13% das afirmações geradas não eram sustentadas, e 6 de 34 perguntas sem resposta no acervo foram respondidas mesmo assim. A falha típica, associar um valor que está no trecho à entidade errada, passa pelas checagens lexicais.
3. **Arquitetura Replicável**: A separação entre núcleo analítico (`pipeline/`) e camadas de apresentação permitiu reutilização em CLI, terminal TUI e GUI desktop nativa.

---

## Referências

A fundamentação teórica deste trabalho apoia-se na revisão bibliográfica completa em `docs/tcc/apoio/revisao_bibliografica_rag_tcc.md`, que cobre arquitetura RAG, vector databases, chunking strategies e embedding models (2022-2025), complementada pelos guias técnicos de `docs/referencias_ia/`. Citações centrais:

- GAO, Yunfan et al. **Retrieval-Augmented Generation for Large Language Models: A Survey**. arXiv, 2023. Disponível em: <https://arxiv.org/abs/2312.10997>.
- CORMACK, Gordon V.; CLARKE, Charles L. A.; BUETTCHER, Stefan. **Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods**. In: Proceedings of the 32nd International ACM SIGIR Conference, 2009.
- WANG, Liang et al. **Multilingual E5 Text Embeddings: A Technical Report**. arXiv, 2024. Disponível em: <https://arxiv.org/abs/2402.05672>.
- GOMEZ-CABELLO, Cesar Abraham et al. **Comparative Evaluation of Advanced Chunking for Retrieval-Augmented Generation in Large Language Models for Clinical Decision Support**. *Bioengineering*, v. 12, n. 11, art. 1194, 2025.
- ORO, Ermelinda; GRANATA, Francesco Maria; RUFFOLO, Massimo. **A Comprehensive Evaluation of Embedding Models and LLMs for IR and QA Across English and Italian**. *Big Data and Cognitive Computing*, v. 9, n. 5, art. 141, 2025.

A lista completa de referências numeradas [1]-[18] está disponível em `docs/tcc/apoio/revisao_bibliografica_rag_tcc.md`.
