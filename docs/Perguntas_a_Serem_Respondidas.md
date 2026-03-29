---
tags:
- tcc
- pesquisa
- perguntas
- checklist
---

# Perguntas a Serem Respondidas

## Objetivo deste documento

Este arquivo não é um banco de respostas prontas.
Ele é uma lista de perguntas que o projeto precisa conseguir responder com evidência até a banca.

## 1. Perguntas de pesquisa

### P1 - Qualidade do pipeline

Pergunta:

> O pipeline consegue produzir notas suficientemente úteis a partir de entradas reais em português brasileiro?

Evidências esperadas:

- WER por categoria
- latência por etapa
- avaliação da nota estruturada

Status atual:

- desenho definido
- implementação pendente

### P2 - Qualidade da recuperação

Pergunta:

> O AutoRAG recupera informação correta com qualidade suficiente para uso real?

Evidências esperadas:

- MRR
- Recall@k
- faithfulness
- taxa de alucinação / resposta sem base

Status atual:

- desenho definido
- implementação pendente

### P3a - Embeddings

Pergunta:

> O modelo de embedding muda significativamente a qualidade da recuperação?

Evidências esperadas:

- comparação controlada entre modelos
- mesma base de perguntas
- mesmas métricas da P2

Status atual:

- modelos candidatos definidos
- benchmark pendente

### P3b - Escala

Pergunta:

> Como a qualidade e a latência se comportam com o crescimento do acervo?

Evidências esperadas:

- experimentos com corpus em escalas diferentes
- curvas de latência
- curvas de qualidade

Status atual:

- opção em aberto com orientador

## 2. Perguntas de engenharia

### Arquitetura

1. O backend vai nascer em Python antes do shell desktop?
2. O benchmark fica isolado da interface?
3. O sistema está desacoplado de um provedor único?

Resposta desejada hoje:

- sim
- sim
- sim

### Dados

1. Qual será o schema da nota?
2. Qual banco vetorial será o baseline?
3. Onde ficam logs e resultados experimentais?

Resposta desejada hoje:

- schema único e validado
- ChromaDB como baseline
- SQLite + CSV/resultados versionados quando fizer sentido

### Interface

1. A UI entra só depois do core textual?
2. O frontend mostra benchmark, citações e fila de processamento?
3. A direção visual tem referências reais em `inspirations`?

Resposta desejada hoje:

- sim
- sim
- ainda não, pasta vazia

## 3. Perguntas de banca

O trabalho precisa conseguir responder bem:

1. Qual é a contribuição científica real?
2. Onde está a Ciência da Computação além de chamar API?
3. Por que esse dataset é válido para um TCC?
4. Por que a arquitetura escolhida faz sentido?
5. Por que o projeto começa pelo backend e não pelo desktop?
6. Quais são as limitações honestas do estudo?

Documento complementar:

- [`Perguntas_do_TCC.md`](Perguntas_do_TCC.md)

## 4. Perguntas de produto e escopo

1. O que entra no TCC obrigatoriamente?
2. O que fica para depois da banca?
3. O que é necessário para demonstração convincente?

Resposta desejada hoje:

- entra: pipeline, RAG, benchmark, docs e demonstração
- fica para depois: refinamentos amplos de UX, multiusuário, app mobile, features fora do escopo
- demonstração convincente: ingestão, nota, indexação, pergunta com citação, benchmark mínimo

## 5. Perguntas ainda em aberto

1. P3 final será embeddings ou escala?
2. Tauri entra ainda no TCC ou fica como casca final apenas se sobrar tempo?
3. Quais referências reais vão popular `inspirations`?
4. Qual provedor será o baseline experimental principal?

## 6. Condição de pronto

Este arquivo estará "respondido" quando cada pergunta acima apontar para:

- código funcionando
- métrica coletada
- seção escrita no TCC
- argumento defensável na banca
