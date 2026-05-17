---
tags:
- tcc
- defesa
- banca
- perguntas
---

# Perguntas do TCC

## Como usar este documento

Este arquivo é um guia de defesa.

Para cada pergunta difícil, o ideal é ter:

- uma resposta curta
- 2 ou 3 pontos de sustentação
- uma admissão honesta de limite quando necessário

## 1. Contribuição científica

### "Qual é a contribuição científica real?"

Resposta curta:

> A contribuição é a avaliação empírica de um pipeline RAG para PKM pessoal em português brasileiro, com foco em chunking, recuperação e embeddings.

Sustentação:

- o cruzamento `PKM + RAG + português brasileiro` é pouco explorado
- o trabalho compara configurações em vez de apenas montar produto
- os resultados viram diretrizes replicáveis

### "Isso não é só integração de APIs?"

Resposta curta:

> Não. A parte científica está no desenho experimental e na comparação controlada das configurações.

Sustentação:

- métricas objetivas
- dataset delimitado
- fatores experimentais definidos
- comparação sistemática entre configurações

## 2. Metodologia

### "Por que esse dataset é suficiente?"

Resposta curta:

> Ele é suficiente para comparação relativa entre configurações, não para generalização universal.

Sustentação:

- essa limitação é explicitamente documentada
- o objetivo do TCC é comparar alternativas dentro do corpus escolhido
- a proposta privilegia reprodutibilidade e baixo custo de coleta

Limite honesto:

> O dataset é pequeno e não sustenta generalização ampla.

### "Não há viés porque os autores criaram as perguntas?"

Resposta curta:

> Há risco de viés, e ele precisa ser documentado como ameaça à validade, não escondido.

Sustentação:

- as perguntas podem ser definidas antes da rodada experimental
- a comparação entre configurações ainda continua útil
- o TCC não depende de afirmar neutralidade total

## 3. Decisões técnicas

### "Por que backend em Python e não começar por Tauri?"

Resposta curta:

> Porque o risco científico do projeto está no pipeline e no benchmark, não no shell desktop.

Sustentação:

- Python acelera iteração experimental
- ecossistema de IA e benchmark é melhor
- reduz dispersão prematura em I/O, empacotamento e UI

### "Por que Tauri ainda faz sentido então?"

Resposta curta:

> Porque continua sendo a melhor casca de produto para um app local-first leve, mas entra depois do núcleo validado.

Sustentação:

- binário menor
- boa integração local
- reuso de frontend web

### "Por que RAG e não mandar tudo no contexto?"

Resposta curta:

> Porque custo, privacidade e degradação de qualidade tornam isso ruim conforme o acervo cresce.

Sustentação:

- menos tokens por consulta
- menos dados enviados ao provedor
- melhor controle sobre contexto recuperado

## 4. Embeddings e recuperação

### "Por que comparar embeddings?"

Resposta curta:

> Porque não existe consenso para PKM em português brasileiro, e escolher sem medir seria arbitrário.

Sustentação:

- corpora usuais de benchmark não representam bem esse domínio
- a comparação reaproveita o mesmo dataset da P2
- o custo analítico compensa

### "Por que esses modelos e não outros?"

Resposta curta:

> Porque cobrem categorias relevantes: proprietário, open source, leve e robusto.

Sustentação:

- `multilingual-e5-large` como referência multilingual
- `text-embedding-3-small` e `large` como par comparável
- `nomic-embed-text` como opção local/open source

## 5. Produto e relevância

### "Qual é a relevância prática?"

Resposta curta:

> Reduzir a fricção entre capturar informação e conseguir recuperá-la depois.

Sustentação:

- estudantes gravam conteúdo e não revisitam
- profissionais abandonam PKM por disciplina manual alta
- a proposta combina automação de captura com recuperação fundamentada

### "Por que isso é um TCC e não só um projeto no GitHub?"

Resposta curta:

> Porque o trabalho não entrega só um sistema; ele investiga quais configurações funcionam e em que condições.

Sustentação:

- pergunta de pesquisa
- métricas
- experimento
- análise de limitações

## 6. Escopo

### "Isso é realmente multimodal?"

Resposta curta:

> Sim, arquiteturalmente. Mas a avaliação pode priorizar áudio como modalidade principal, com imagem e texto como suporte.

Sustentação:

- o pipeline suporta áudio, imagem e texto
- o TCC pode declarar a assimetria de avaliação como limitação

### "Por que guardrails não são pergunta central?"

Resposta curta:

> Porque no modelo BYOK puro o modelo de ameaça é fraco para virar contribuição científica principal.

Sustentação:

- o usuário já controla a própria chave
- ainda assim os guardrails podem e devem existir na implementação
- o tema volta a ganhar força se houver gerenciamento centralizado de credenciais

## 7. Limites que vale admitir antes

1. dataset pequeno
2. possível viés de construção de perguntas
3. foco maior em áudio do que nas outras modalidades
4. dependência de API externa
5. comparação de embeddings representativa, mas não exaustiva

## 8. Como se preparar de verdade

Antes da banca, garantir que cada resposta acima consiga apontar para:

- uma seção do `TCC.md`
- uma decisão arquitetural documentada
- um resultado experimental ou limitação explicitamente assumida
