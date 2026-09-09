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

A calibração empírica do projeto (Experimentos 07 e 15, `docs/experimentos/07_calibracao_fusao_hibrida.md` e `docs/experimentos/15_calibracao_rrf_tcc.md`) testou $k \in \{10, 60, 100\}$ mantendo $w_{vector}=1.0$ fixo. O valor $k=60$ apresentou o melhor equilíbrio entre as três configurações, com MRR de 0.884 contra 0.865 ($k=10$) e 0.871 ($k=100$). Valores baixos de $k$ super-ponderam o topo do ranking de cada método individual, amplificando ruído de qualquer um dos lados; valores altos achatam demais as diferenças de posição, aproximando o resultado de uma média simples e reduzindo poder discriminativo.

Complementarmente, o Experimento 07 calibrou os pesos $w_m$ mantendo $k=60$ fixo: elevar $w_{lexical}$ de 1.0 para 1.5 (com $w_{vector}=1.0$) eliminou o gap de MRR do híbrido em relação à busca léxica pura nessa suíte (0.96875 em ambas, Recall@3 = 1.0), sem regressão de cobertura. Esse ajuste reflete uma característica do corpus em português técnico: termos exatos (nomes de tecnologias, cláusulas contratuais, identificadores) têm alto valor de recuperação e são mais bem capturados por BM25 do que por similaridade de cosseno em embeddings. Os parâmetros calibrados $w_{lexical}=1.5$, $w_{vector}=1.0$, $k=60$ foram promovidos a padrão do projeto.

## Resultados Empíricos & Avaliação Experimental

Com o objetivo de responder às perguntas centrais de pesquisa sobre o impacto das decisões de recuperação (P2 e P3), foram executados benchmarks controlados comparando estratégias léxicas puras, vetoriais puras e fusão híbrida com amortecimento calibrado (Experimento 15):

### Tabela de Comparação Experimental de Recuperação

| Estratégia de Recuperação | MRR | Recall@3 | Recall@5 | Latência Média |
|---|---|---|---|---|
| **Léxica Pura (SQLite FTS5 BM25)** | 0.812 | 0.840 | 0.880 | ~8.4 ms |
| **Vetorial Pura (ChromaDB)** | 0.795 | 0.820 | 0.865 | ~34.2 ms |
| **Híbrida RRF (k=10)** | 0.865 | 0.890 | 0.930 | ~42.5 ms |
| **Híbrida RRF (k=60 - Padrão)** | **0.884** | **0.915** | **0.950** | **~41.8 ms** |
| **Híbrida RRF (k=100)** | 0.871 | 0.900 | 0.940 | ~42.0 ms |

### Análise dos Resultados

1. **Superioridade do RAG Híbrido**: A combinação de BM25 e embeddings vetoriais através do Reciprocal Rank Fusion superou ambas as abordagens isoladas (+7.2% no MRR frente ao BM25 e +8.9% frente à busca vetorial).
2. **Calibração do Fator $k=60$**: O amortecimento $k=60$ demonstrou o melhor equilíbrio, prevenindo que documentos com alta similaridade semântica genérica se sobreponham a termos técnicos exatos requeridos pelo usuário.
3. **Eficiência e Local-First**: A sobrecarga do algoritmo de fusão RRF em memória foi desprezível (< 1 ms), mantendo a latência total dentro dos limites interativos para uso em computadores pessoais.

---

## Respostas às Perguntas de Pesquisa

### P1: A recuperação híbrida (BM25 + vetores) apresenta vantagem sobre a recuperação isolada?

Sim. Os dados do Experimento 15 confirmam empiricamente essa vantagem: a fusão híbrida RRF ($k=60$) atingiu MRR de 0.884 e Recall@5 de 0.950, superando tanto a recuperação léxica isolada (MRR 0.812, Recall@5 0.880) quanto a vetorial isolada (MRR 0.795, Recall@5 0.865). O ganho não é incidental — decorre da complementaridade estrutural entre os dois métodos: BM25 tem alta precisão para termos exatos (identificadores técnicos, nomes próprios, cláusulas), enquanto embeddings vetoriais capturam similaridade semântica quando a formulação da pergunta não usa as mesmas palavras do documento-fonte. O Experimento 07 reforça essa conclusão em uma segunda suíte: a fusão calibrada ($w_{lexical}=1.5$) igualou o MRR da busca léxica pura (0.96875) sem abrir mão da cobertura semântica adicional do componente vetorial, o que a recuperação puramente léxica não oferece em consultas parafraseadas. O custo é uma latência adicional de aproximadamente 30 ms (majoritariamente do cálculo de embeddings), julgado aceitável por permanecer dentro da faixa interativa (< 50 ms) para uso pessoal local.

### P2: Qual o impacto das estratégias de chunking e da preservação de spans/lineage?

A preservação estrita de spans de caracteres (offset exato no documento de origem) demonstrou impacto direto na qualidade percebida das respostas, não apenas na recuperação. O Experimento 11 (`docs/experimentos/11_poda_span_minimo_suficiente.md`) mostra que, mantendo retrieval e chunking constantes, refinar a poda do span citado — sem alterar `chunk_size` ou `overlap` — reduziu o tamanho médio das respostas em até 84% (ex.: `paper-03` caiu de 603 para 97 caracteres) eliminando ruído administrativo (headings, anexos, cláusulas adjacentes) e mantendo os testes de guardrail (108 casos) passando integralmente. Isso indica que o valor de um pipeline de citação obrigatória não está apenas em recuperar o chunk correto, mas em rastrear o span mínimo suficiente dentro dele até o caractere exato — sem esse rastreamento (`start_char`/`end_char` na persistência SQLite FTS5), a poda de resposta seria impossível de fazer com segurança factual. Quanto à granularidade de chunking em si, a configuração `chunk_size=800`/`overlap=120` foi mantida como baseline estável ao longo de todos os experimentos de retrieval (03, 07, 15) por não ter sido identificada evidência de que outra granularidade testada indiretamente (via mudança de embedding, Experimento 03) alterasse esse parâmetro de forma isolada — o chunking mostrou-se um fator de segundo grau frente ao método de recuperação e à poda de span.

### P3: Modelos de embedding e LLM locais são viáveis frente a alternativas em nuvem? Quais os trade-offs?

A viabilidade é condicional, não incondicional. No eixo de embeddings, o Experimento 03 (`docs/experimentos/03_embeddings_alternativos_suite_baseline.md`) testou dois modelos locais multilíngues (`paraphrase-multilingual-MiniLM-L12-v2` e `paraphrase-multilingual-mpnet-base-v2`) contra o baseline `chroma-default`, e ambos tiveram desempenho pior (MRR 0.615 e 0.531, respectivamente, contra 0.792 do baseline) — ou seja, nem todo modelo local "mais moderno" ou "mais pesado" supera um baseline já ajustado ao domínio; a escolha de embedding exige validação empírica por suíte, não apenas por especificação de tamanho de modelo. No eixo de geração (LLM), a arquitetura do projeto (`docs/plano_execucao/HANDOFF_RAG_GENERATIVO_LOCAL_API_E_GIT.md`) adota um provider OpenAI-compatible que abstrai Ollama, LM Studio e APIs de nuvem (OpenAI) atrás da mesma interface, permitindo trocar o backend generativo sem alterar o núcleo RAG. Isso viabiliza o uso 100% local (Ollama/LM Studio), preservando a premissa local-first do projeto, mas com trade-off de qualidade de geração variável conforme o modelo local escolhido — mitigado pelo desenho do sistema, em que o LLM só participa após retrieval e citação já validados (nunca antes), e uma falha do provider local sempre recai em resposta extrativa determinística, sem interromper o fluxo. Assim, o trade-off central não é "local versus nuvem" em abstrato, mas a necessidade de validação empírica por componente (embedding e modelo generativo) e a garantia arquitetural de que a ausência ou fraqueza de um LLM local nunca compromete a factualidade da resposta.

## Conclusões do Trabalho

1. **Viabilidade sem Fine-Tuning**: Confirmou-se a hipótese H1 de que modelos genéricos acoplados a um pipeline híbrido bem estruturado entregam alta fidelidade sem necessidade de retreinamento de pesos.
2. **Mitigação de Alucinações**: A obrigatoriedade de citação com checagem de inclusão determinística de spans de texto eliminou completamente respostas fabricadas não sustentadas pelo acervo.
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
