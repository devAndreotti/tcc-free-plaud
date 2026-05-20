# Handoff - Melhoria de ranking e filtro de falso positivo

## Objetivo

Este arquivo orienta uma IA a reduzir falso positivo na busca aberta do backend atual.

Problema observado no experimento `08`:

- `semantic-search` sem `--note-id` ainda puxa chunks irrelevantes
- isso acontece mesmo quando `term_coverage` e baixo ou zero
- answer layer segura parte do problema com `no_answer`
- retrieval bruto ainda entrega ruido demais

Escopo desta slice:

- melhorar **busca aberta**
- reduzir lixo no top-k
- preservar recuperacao valida
- nao mexer em frontend
- nao mexer em LLM
- nao misturar com multi-document answer

Objetivo real:

> melhorar ranking e filtro do retrieval aberto sem derrubar casos validos.

## Veredito senior sobre esta slice

Diagnostico:

- problema alvo e **open retrieval**
- problema alvo **nao** e benchmark per-note
- problema alvo **nao** e answer layer

Consequencia:

- `benchmark compare` entra como guardrail de nao regressao
- `benchmark compare` **nao** e prova principal de sucesso desta slice
- prova principal precisa vir de consultas abertas em collection compartilhada

## Skills recomendadas

Se a IA suportar skills locais, usar:

- `caveman:caveman`
- `akita-way`
- `adversarial-delivery-auditor`

Opcional no fechamento:

- `senior-second-pass`

## Leitura minima obrigatoria

Ler apenas:

1. `AGENTS.md`
2. `docs/ORDEM_DE_LEITURA_IA.md`
3. `docs/arquitetura/Arquitetura_Backend.md`
4. `Sprints/STATUS.md`
5. `docs/experimentos/08_validacao_retrieval_distribuido.md`

Nao ler `docs/tcc/`, salvo mudanca explicita de escopo.

## Regra de escopo

Antes de propor alteracao, validar contra codigo real em:

- `pipeline/src/free_plaud/retrieval/search.py`
- `pipeline/src/free_plaud/retrieval/rag.py`
- `pipeline/src/free_plaud/storage/vector.py`
- `pipeline/src/free_plaud/retrieval/cli.py`
- `pipeline/src/free_plaud/benchmark/runners.py`

Nao assumir que problema esta no benchmark.
Foco aqui e retrieval aberto.

Tambem nao assumir que mudar `semantic_search()` globalmente e seguro.

Hoje:

- `semantic_search()` alimenta busca vetorial base
- `semantic_search()` toca CLI aberta
- `semantic_search()` tambem participa do comportamento vetorial atual

Portanto esta slice deve preferir:

1. criar camada de reranking/filtro para **busca aberta**
2. ou expor parametros especificos para fluxo aberto
3. so depois promover para caminho compartilhado, se prova ficar boa

## Hipotese tecnica atual

Pelo experimento `08`, problema principal parece ser:

1. score vetorial sozinho aceita chunks com relacao semantica fraca
2. `matched_terms` e `term_coverage` ainda nao pesam o suficiente na busca aberta
3. retrieval aberto sem `note-id` nao diferencia bem:
   - hit semanticamente relevante
   - hit semanticamente tangencial
   - hit praticamente lixo

Hipotese de trabalho:

> filtro leve + reranking lexical-aware na busca aberta deve reduzir falso positivo sem perder recuperacao valida.

Hipotese secundaria:

> melhor lugar para isso talvez nao seja `semantic_search()` cru, e sim camada `open_search` ou equivalente em cima dele.

## Regra de abertura

Antes de qualquer edicao:

1. rodar `git status`
2. verificar branch atual
3. se houver dirty tree relevante de outro trabalho, parar e reportar

Excecao conhecida:

- `samples/` pode permanecer nao versionado

## Collections obrigatorias

Usar collections isoladas para experimento.

Sugestao:

- `validation_real_false_positive_<data>`
- `validation_ctrl_false_positive_<data>`

Nao reutilizar collection padrao.

## O que deve ser medido

Nao basta rodar um caso e "parecer melhor".

Comparar antes e depois em 4 frentes:

### 1. Casos positivos

Perguntas que devem continuar recuperando contexto correto.

### 2. Casos negativos

Perguntas irrelevantes que hoje puxam lixo.

### 3. Casos mistos

Perguntas abertas com parte correta e parte ausente, para ver se filtro corta demais.

### 4. Guardrail de regressao

Suite atual deve continuar estavel em:

- `lexical`
- `vector`
- `hybrid`

Mas isso entra como **guardrail**, nao como prova principal.

## Metricas minimas

Registrar para cada consulta:

- `note_id`
- `chunk_id`
- `score`
- `distance`
- `matched_terms`
- `term_coverage`
- `strategy`
- posicao no ranking

Comparar:

- quantidade de hits com `term_coverage = 0`
- quantidade de hits com `matched_terms = []`
- quantidade de hits sem anchor nomeado quando query tiver anchor nomeado
- qualidade do top 1
- qualidade do top 3
- comportamento de `no_answer` no `ask`
- latencia media

Metricas principais desta slice:

1. `open_noise_at_5`
   - quantos hits do top 5 sao lixo
2. `open_anchor_miss_at_5`
   - quantos hits do top 5 ignoram anchor nomeado obrigatorio
3. `open_relevant_top1`
   - se top 1 continua correto em query positiva
4. `open_relevant_top3`
   - se top 3 ainda contem chunks necessarios

## Criterio de sucesso

Mudanca so pode ser aceita se:

1. reduzir hits lixo em consultas negativas
2. manter recuperacao correta nos casos positivos
3. nao degradar `Recall@3` relevante da suite atual
4. nao quebrar `hybrid` calibrado

Objetivo minimo:

- cortar forte hits com `term_coverage = 0` em busca aberta
- manter `hybrid` e `lexical` baseline atuais

Meta melhor:

- eliminar ou reduzir fortemente hits com `matched_terms = []`
- manter hit relevante no top 1 ou top 3 nos casos positivos

## Candidatos de implementacao

Implementar em ordem, menor risco primeiro.

### Fase 1 - Reranking leve na busca aberta

Escopo:

- mexer primeiro em **fluxo aberto**
- nao mexer ainda no contrato de `ask`
- evitar alterar benchmark per-note por efeito colateral

Forma preferida:

1. criar helper de reranking para busca aberta
2. ligar helper no comando `retrieval semantic-search`
3. manter comportamento atual de `ask` e benchmark o mais intacto possivel nesta rodada

Ideias validas:

1. penalizar hits com `matched_terms = []`
2. penalizar hits com `term_coverage = 0`
3. penalizar hits sem anchors nomeados quando query tiver anchors nomeados
4. promover hits com combinacao melhor de:
   - score vetorial
   - matched terms
   - term coverage

Meta:

- rerank antes de filtrar duro

### Fase 2 - Filtro minimo de evidência

Se reranking leve nao bastar:

1. descartar hits abaixo de limiar minimo de `term_coverage`
2. ou exigir pelo menos `1` matched term quando query tiver termos normalizados suficientes
3. ou exigir anchor nomeado quando query contiver anchor nomeado

Meta:

- impedir top-k cheio de lixo
- sem matar query curta demais

### Fase 3 - Thresholds configuraveis

Se precisar de calibracao:

- expor knobs primeiro no CLI aberto
- expor no benchmark so se benchmark passar a cobrir caso aberto
- nao abrir configuracao espalhada em toda a base

Exemplos de knobs:

- `min-term-coverage`
- `min-matched-terms`
- `require-named-anchor`

## O que nao fazer agora

- nao partir para reranker complexo
- nao partir para LLM judge
- nao alterar chunking nesta slice
- nao misturar com multi-document answer
- nao mexer no frontend
- nao usar `benchmark compare` como prova primaria desta melhora
- nao empurrar filtro global para `ask` sem medir regressao

## Fluxo obrigatorio

### Etapa 1 - Reproduzir baseline ruim

Rodar:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
$tmp = "D:\Dev\Repos\Own\tcc-free-plaud\.pytest-tmp-$([guid]::NewGuid().ToString())"
uv run pytest --basetemp $tmp -q
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

Depois reproduzir baseline aberto com collection isolada e corpus conhecido.

Usar mesma base do experimento `08` ou recriar explicitamente.

Rodar pelo menos:

```powershell
$env:FREE_PLAUD_VECTOR_COLLECTION_NAME='validation_real_false_positive_<data>'
uv run free-plaud retrieval semantic-search --query "Quais tecnologias o candidato domina para desenvolver apps mobile?" --top-k 5
```

Registrar ranking atual antes de editar.

Registrar em tabela:

- rank
- note_id
- score
- distance
- matched_terms
- term_coverage

### Etapa 2 - Montar bateria de queries

Usar pelo menos:

#### Positivas

1. `Qual message broker foi adotado como padrao da plataforma?`
2. `Qual message broker foi adotado e qual padrao divide o pipeline nas camadas Bronze, Silver e Gold?`

#### Negativas

1. `Quais tecnologias o candidato domina para desenvolver apps mobile?`
2. `Qual banco relacional foi escolhido para autenticar o painel web?`

#### Mistas

1. `Qual message broker foi adotado e qual custo mensal foi aprovado?`
2. `Qual equipe ficou responsavel pelo runbook e qual linguagem foi escolhida para o app mobile?`

Obrigatorio:

- pelo menos `2` queries devem usar corpus controlado
- pelo menos `2` queries devem usar corpus real
- queries devem ser repetidas exatamente no antes e depois

## Testes obrigatorios

Antes de aceitar mudanca, adicionar:

### Teste unitario

Cobrir pelo menos:

1. hit com `matched_terms = []` perde prioridade para hit com evidência lexical
2. hit com `term_coverage = 0` nao sobe para top 1 quando existe hit melhor
3. query com anchor nomeado favorece hit que preserva anchor

### Teste de integração

Cobrir pelo menos:

1. busca aberta com corpus pequeno multi-file
2. caso negativo que antes puxava lixo
3. caso positivo que precisa continuar top 1 ou top 3

### Etapa 3 - Implementar menor mudanca possivel

Ordem obrigatoria:

1. helper/local path de reranking aberto
2. filtro minimo
3. knobs de calibracao, se ainda necessario
4. so depois avaliar promover para shared path

Nao pular direto para filtro agressivo.

### Etapa 4 - Revalidar

Rodar:

- `pytest`
- `benchmark compare`
- bateria manual de queries abertas

Reexecutar exatamente:

```powershell
uv run free-plaud retrieval semantic-search --query "Quais tecnologias o candidato domina para desenvolver apps mobile?" --top-k 5
uv run free-plaud retrieval semantic-search --query "Qual banco relacional foi escolhido para autenticar o painel web?" --top-k 5
uv run free-plaud retrieval semantic-search --query "Qual message broker foi adotado como padrao da plataforma?" --top-k 5
```

Comparar antes/depois com tabela objetiva.

### Etapa 5 - Registrar experimento

Gerar artefato em:

- `docs/experimentos/09_melhoria_ranking_falso_positivo.md`

Esse arquivo deve conter:

1. baseline ruim
2. mudanca implementada
3. queries usadas
4. resultados antes
5. resultados depois
6. regressao ou nao regressao
7. conclusao
8. decisao: local-path only ou promoted to shared path

## Estrutura da resposta final esperada

### 1. Mudanca aplicada

Qual regra de ranking/filtro foi introduzida.
Onde ela foi introduzida:

- helper novo?
- `semantic_search()` global?
- CLI apenas?

### 2. Evidencia antes/depois

Mostrar queries, hits e metricas.

### 3. Impacto em casos positivos

Provar que nao matou recuperacao valida.

### 4. Impacto em casos negativos

Provar que reduziu lixo.

### 5. Veredito

Responder objetivamente:

1. retrieval aberto melhorou?
2. falso positivo caiu?
3. recuperacao valida foi preservada?
4. mudanca ficou confinada ao fluxo aberto ou impactou shared path?
5. precisa de outra rodada ou ja ficou aceitavel?

## Regra de honestidade tecnica

Se mudanca:

- corta lixo
- mas derruba hits validos

entao ela **nao** deve ser promovida.

Conclusao correta:

- filtro agressivo demais
- precisa recalibrar

Nao aceitar conclusao vaga como:

- `parece melhor`
- `deve estar melhor`

Aceitar apenas com comparacao real de dados.
