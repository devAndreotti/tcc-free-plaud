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

## Conclusões do Trabalho

1. **Viabilidade sem Fine-Tuning**: Confirmou-se a hipótese H1 de que modelos genéricos acoplados a um pipeline híbrido bem estruturado entregam alta fidelidade sem necessidade de retreinamento de pesos.
2. **Mitigação de Alucinações**: A obrigatoriedade de citação com checagem de inclusão determinística de spans de texto eliminou completamente respostas fabricadas não sustentadas pelo acervo.
3. **Arquitetura Replicável**: A separação entre núcleo analítico (`pipeline/`) e camadas de apresentação permitiu reutilização em CLI, terminal TUI e GUI desktop nativa.
