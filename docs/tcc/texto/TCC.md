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
2. indexar essas notas em banco vetorial local
3. permitir consulta em linguagem natural com respostas fundamentadas no acervo
4. medir o impacto de parâmetros de chunking, recuperação e embeddings
5. documentar uma arquitetura replicável para esse tipo de sistema

## Artefato do trabalho

O artefato esperado é um sistema com cinco blocos:

1. monitor de entrada
2. pipeline de processamento
3. geração de nota Markdown
4. indexação vetorial local
5. AutoRAG com benchmark integrado

O shell desktop é desejável, mas o valor principal do TCC está no pipeline e no módulo experimental.

## Perguntas de pesquisa

### P1 - Qualidade do pipeline

> O pipeline consegue produzir notas de qualidade satisfatória a partir de entradas reais em português brasileiro?

Métricas principais:

- WER para áudio
- latência por etapa
- avaliação da estruturação da nota
- comparação entre modalidades

### P2 - Qualidade da recuperação

> O AutoRAG recupera informação correta com precisão suficiente para uso real?

Métricas principais:

- MRR
- Recall@k
- faithfulness
- taxa de resposta sem base adequada

### P3a - Comparação de embeddings

> O modelo de embedding afeta significativamente a qualidade da recuperação nesse contexto?

Comparativo inicial:

- `multilingual-e5-large`
- `text-embedding-3-small`
- `text-embedding-3-large`
- `nomic-embed-text`

### P3b - Escala

> Como qualidade e latência se comportam com o crescimento do acervo?

Observação:

Essa pergunta permanece como alternativa ou extensão, dependendo da decisão final com o orientador.

## Hipóteses de trabalho

### H1

Um pipeline sem fine-tuning é capaz de gerar notas utilizáveis em português brasileiro a partir de entradas reais.

### H2

As decisões de chunking e recuperação impactam significativamente a qualidade do AutoRAG.

### H3

A escolha do modelo de embedding altera a recuperação de forma relevante em corpora de PKM pessoal em português.

## Lacuna que o trabalho ataca

O diferencial do projeto não é apenas usar RAG ou usar LLM.

O ponto principal é investigar um recorte pouco tratado de forma empírica:

- PKM pessoal
- português brasileiro
- entradas multimodais
- embeddings e recuperação avaliados de forma controlada

Benchmarks mais comuns tratam:

- domínio jurídico
- domínio jornalístico
- inglês
- corpora mais padronizados do que um acervo pessoal

## Estratégia metodológica

### Recorte experimental

O trabalho vai avaliar o sistema em um corpus delimitado e reprodutível, combinando:

- documentos reais da UNIP
- documentos corporativos anonimizados
- entradas produzidas pelos autores para áudio e imagem

### P1 - Dados previstos

- 30 áudios
- 15 imagens
- 15 documentos

### P2 - Dados previstos

- 50 pares pergunta/resposta
- categorias: direta, inferida e negativa

### Fatores experimentais para P2

- chunk size: `256`, `512`, `1024`
- overlap: `0%`, `10%`, `20%`
- top-k: `3`, `5`, `10`

O desenho pode usar design fracionário para reduzir custo sem perder comparabilidade útil.

## Posicionamento técnico atual

### Estratégia de implementação

O projeto deve começar pelo backend e benchmark, não pela interface final.

Ordem recomendada:

1. core textual
2. recuperação vetorial
3. benchmark
4. áudio e imagem
5. interface
6. casca desktop

### Tecnologias sugeridas para o arranque

- backend: `Python 3.12`
- ambiente: `uv`
- CLI: `Typer`
- configuração: `Pydantic`
- metadados: `SQLite`
- vetor local: `ChromaDB`
- testes: `Pytest`
- frontend futuro: `React + TypeScript + Vite + Tailwind`
- desktop futuro: `Tauri`

## Contribuições esperadas

### Técnica

Diretrizes empíricas para configurar pipelines RAG de PKM em português brasileiro.

### Aplicada

Comparação de embeddings em um contexto pouco explorado na literatura.

### Arquitetural

Referência replicável de sistema local-first com BYOK, notas Markdown e vetor local.

### Prática

Demonstração de que modelos de propósito geral podem sustentar um caso de uso real sem fine-tuning.

## Fora do escopo desta versão

- multiusuário
- app mobile nativo
- diarização avançada
- analytics sofisticado de uso
- múltiplos destinos além de Markdown local
- gerência centralizada de API key

## Guardrails

Guardrails fazem parte da implementação, mas não são hoje a pergunta central de pesquisa.

Motivo:

- no modelo BYOK puro, o modelo de ameaça é relativamente fraco

Mesmo assim, vale implementar:

- sanitização básica anti-injection
- citação obrigatória
- threshold para declarar ausência de informação

## Riscos principais

1. dispersão excessiva com shell desktop cedo demais
2. dataset pequeno demais para sustentar afirmações fortes
3. acoplamento prematuro a um provedor específico
4. tempo gasto com UI em detrimento do benchmark

## Critério de sucesso do TCC

Ao final, o trabalho precisa conseguir demonstrar:

1. uma fatia funcional do pipeline
2. um benchmark executável
3. resultados comparativos defensáveis
4. uma narrativa coerente entre problema, método, arquitetura e conclusões

## Próximos passos imediatos

1. consolidar baseline do repositório e do git
2. implementar o core textual
3. fechar o primeiro marco de RAG com citação
4. subir o harness de benchmark
5. decidir P3 final com base no cronograma real
