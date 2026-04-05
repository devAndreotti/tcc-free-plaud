---
tags:
- tcc
- arquitetura
- sistema
---

# Arquitetura do Sistema

## Objetivo deste documento

Este arquivo descreve a arquitetura do sistema em nível macro.

Ele responde:

- o que o sistema precisa fazer
- quais módulos existem
- qual a ordem correta de implementação
- como backend, frontend e casca desktop se relacionam

Os detalhes ficam em:

- [`Arquitetura_Backend.md`](Arquitetura_Backend.md)
- [`Arquitetura_Frontend.md`](Arquitetura_Frontend.md)

## Visão do sistema

O sistema tem quatro responsabilidades principais:

1. capturar arquivos multimodais
2. transformar esse material em notas Markdown bem estruturadas
3. indexar o conhecimento em banco vetorial local
4. responder perguntas em linguagem natural com citação obrigatória

Em termos de produto, o alvo é um app desktop.
Em termos de TCC, o núcleo é o pipeline experimental que sustenta as perguntas de pesquisa.

## Princípios arquiteturais

### 1. Benchmark-first

O projeto não deve começar pela interface final.
O que precisa ser provado primeiro é:

- ingestão
- estruturação
- recuperação
- métrica

### 2. Local-first

O sistema deve manter:

- notas em arquivo local
- índice vetorial local
- configurações locais

Chamadas externas devem ser restritas ao uso de APIs do provedor configurado pelo usuário.

### 3. BYOK e abstração de provedores

O sistema não deve nascer acoplado a um único provedor de IA.
Precisa existir uma camada de adaptadores para:

- transcrição
- OCR / visão
- estruturação
- embeddings
- resposta RAG

### 4. Casca desktop depois

O shell desktop é importante para o produto, mas secundário para a validação científica.
Por isso, a ordem correta é:

1. backend e benchmark
2. interface local reutilizável
3. empacotamento com Tauri

## Módulos do sistema

```text
Entrada -> Pipeline -> Nota Markdown -> Indexação -> RAG -> Benchmark
```

### Entrada

- áudio
- imagem
- texto
- PDF

### Pipeline

- extração
- limpeza
- estruturação em nota
- enriquecimento com metadados

### Saída primária

- nota Markdown
- frontmatter
- log de processamento

### Indexação

- chunking
- embeddings
- armazenamento vetorial

### RAG

- embedding da pergunta
- recuperação de chunks
- montagem de contexto
- resposta com citação obrigatória

### Benchmark

- MRR
- Recall@k
- latência
- comparação de embeddings
- variação de parâmetros de chunking/recuperação

## Ordem recomendada de implementação

### Fase 0 - Fundação

- `README.md`
- `CLAUDE.md`
- docs arquiteturais
- estratégia de git

### Fase 1 - Core textual

- ingestão de `.txt`, `.md` e `.pdf`
- estruturação em nota
- indexação vetorial
- pergunta e resposta com citação

### Fase 2 - Benchmark

- datasets
- harness de experimento
- exportação de resultados

### Fase 3 - Multimodal

- áudio
- imagem

### Fase 4 - Interface

- dashboard
- fila
- chat
- benchmark
- configurações

### Fase 5 - Desktop shell

- Tauri
- monitor de pasta
- integração local entre UI e backend

## Decisões atuais

### Backend

Começar com Python.

Motivo:

- menor risco
- ecossistema de IA mais maduro
- facilita benchmark e scripts experimentais
- reduz dispersão de esforço antes da banca

### Frontend

Usar React + TypeScript, mas somente depois do núcleo experimental mínimo.

### Desktop

Manter Tauri como alvo de produto, não como ponto de partida.

## Lacunas ainda abertas

1. vetor local final: ChromaDB como baseline ou comparação posterior com LanceDB
2. P3 final: embeddings ou degradação com escala
3. estratégia final de OCR: usar API multimodal apenas ou fallback local
4. momento exato de introduzir Tauri no cronograma

## Documento operacional relacionado

Para transformar esta arquitetura em trabalho executável, usar:

- [`Plano_de_Arranque.md`](Plano_de_Arranque.md)
- [`Metodologia_Akita_Git.md`](Metodologia_Akita_Git.md)
