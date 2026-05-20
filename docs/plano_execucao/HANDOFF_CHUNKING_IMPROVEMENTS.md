# Handoff - Revisao critica das propostas de melhoria de chunking

## Objetivo

Registrar, com base em evidencia de runtime, se a proposta de `title injection` + `heading-aware chunking`
ataca a causa raiz real dos erros observados no `ask`.

Este arquivo substitui a leitura ingenua do handoff externo. A implementacao futura deve seguir este
documento, nao o rascunho original.

## Veredito senior

O handoff original esta **direcionalmente util**, mas a conclusao principal dele esta **errada como causa raiz**.

Resumo:

1. os casos citados como prova de problema de chunking nao sustentam essa tese
2. em 3 dos 4 exemplos, o chunk recuperado ja contem a resposta correta
3. o erro dominante esta em `rag.py`, na selecao e composicao do claim
4. `heading-aware chunking` ainda pode ser um experimento valido
5. `title injection` nao esta provado e nao deve entrar como default nem como primeira correcao

## O que foi testado

### Leitura obrigatoria usada na analise

1. `pipeline/src/free_plaud/retrieval/chunking.py`
2. `pipeline/src/free_plaud/retrieval/indexer.py`
3. `pipeline/src/free_plaud/retrieval/models.py`
4. `pipeline/src/free_plaud/notes/schemas.py`
5. `pipeline/src/free_plaud/notes/normalizer.py`
6. `pipeline/src/free_plaud/retrieval/rag.py`
7. `pipeline/src/free_plaud/retrieval/search.py`

### Comandos executados

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline

$tmp = Join-Path $env:TEMP ("tcc-free-plaud-chunking-review-" + [guid]::NewGuid().ToString())
uv run pytest --basetemp $tmp tests\test_chunking.py tests\test_rag.py tests\test_benchmark.py -q

uv run free-plaud benchmark compare `
  --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

Resultado observado:

- `37 passed`
- `lexical MRR = 0.96875`
- `hybrid MRR = 0.96875`
- `hybrid Recall@3 = 1.0`

### Casos investigados

- `ata-03`
- `paper-03`
- `paper-04`
- `contrato-03`

## Evidencia encontrada

### Caso 1 - `ata-03`

Pergunta:

```text
Quais topicos de baixo risco iniciariam o rollout?
```

Top hit atual:

- `04-ata-metadados-longos::v1::ofs-003400-004200::8c5b8714a7`
- cobertura lexical: `1.00`

Trecho do chunk:

```text
A terceira condicionante é que a adoção começa com dois tópicos de baixo risco — notificações de email e logs de auditoria — antes de migrar os eventos de negócio críticos.
...
3. Iniciar rollout em Q2/2025, começando pelos tópicos de menor risco.
```

Conclusao:

- o chunk **ja contem a resposta certa**
- o `ask` escolhe a frase errada dentro do mesmo chunk
- isso aponta para **claim selection**, nao para chunking

### Caso 2 - `paper-03`

Pergunta:

```text
Qual modelo de embedding foi usado nos experimentos?
```

Top hits atuais:

1. chunk da secao semantica, com texto geral sobre embeddings
2. chunk da secao `3.3 Infraestrutura`, com a resposta exata

Trecho do hit relevante:

```text
O índice vetorial foi implementado com ChromaDB e os embeddings gerados com `nomic-embed-text-v1.5`.
```

Conclusao:

- aqui existe, sim, um problema de ranking/claim
- mas `title injection` nao ajudaria materialmente
- o `title` do documento e global e generico para todos os chunks
- o problema e: o sistema nao promoveu o chunk da infraestrutura nem escolheu o claim correto

### Caso 3 - `paper-04`

Pergunta:

```text
Qual estrategia e recomendada para documentos sem estrutura formal?
```

Top hits atuais:

- hit 1: secao `Discussao`, com a recomendacao geral
- hit 2: continua a mesma linha de raciocinio e contem a frase correta

Trecho relevante no documento:

```text
Para documentos sem estrutura formal — como e-mails, notas pessoais e transcrições — o chunking semântico oferece ganhos mais expressivos.
```

Conclusao:

- este e o unico dos quatro casos em que `heading-aware chunking` pode ter valor real
- mesmo assim, o caso ainda nao prova que `title injection` seja necessario

### Caso 4 - `contrato-03`

Pergunta:

```text
Quais tecnologias aparecem no Portal do colaborador e no modulo financeiro?
```

Top hit atual:

- `08-pdf-problematico-contrato::v1::ofs-004080-004748::6f5720c3e1`
- cobertura lexical: `0.67`

Trecho do chunk:

```text
- Portal do colaborador (React + Node.js)
- Módulo financeiro (Python + PostgreSQL)
```

Conclusao:

- a resposta esta inteira no mesmo chunk
- o `ask` devolve so a primeira parte
- de novo: erro de **claim extraction/completeness**, nao de chunking

## Diagnostico correto

### O que o handoff original acertou

- `heading-aware chunking` e uma hipotese tecnica plausivel para documentos estruturados
- expor estrategia de chunking no benchmark e no CLI e um desenho razoavel
- `models.py`, `schemas.py` e `normalizer.py` realmente nao deveriam ser tocados cedo

### O que o handoff original errou

#### 1. Causa raiz superestimada

Os exemplos escolhidos nao sustentam que o chunker atual seja o principal culpado.

Em `ata-03` e `contrato-03`, o chunk certo ja esta no topo e ja contem a resposta.

#### 2. `title injection` sem prova

Problemas:

- injeta ruido em todos os embeddings
- muda o texto embedado de todos os chunks
- pode alterar benchmark forte atual sem necessidade
- o titulo do documento nao resolve perguntas intra-documento como as citadas

Hoje isso e hipotese fraca, nao correcao justificada.

#### 3. Sequenciamento ruim

O handoff tenta atacar chunking antes de atacar a camada que esta claramente errando:

- `_best_claim_text(...)`
- `_build_claims(...)`
- composicao final em `rag.py`

#### 4. Branch e estado desatualizados

O handoff externo assume:

- branch `feat/hybrid-retrieval`
- repo em outro ponto do fluxo

Isso nao reflete necessariamente o estado real de trabalho atual.

## Recomendacao de implementacao

### Fase 1 - Corrigir o problema real primeiro

Alvo:

- `pipeline/src/free_plaud/retrieval/rag.py`

Foco:

1. melhorar selecao de claim dentro do chunk
2. melhorar completude de respostas com listas ou pares
3. evitar escolher frase generica quando a resposta exata esta no mesmo chunk

Casos-alvo obrigatorios:

- `ata-03`
- `paper-03`
- `paper-04`
- `contrato-03`

### Fase 2 - So depois avaliar chunking

Se, depois da Fase 1, ainda houver evidencias reais de chunk truncado ou fronteira ruim, ai sim:

1. adicionar `heading-aware chunking`
2. manter `fixed_char_window` como default
3. comparar no benchmark
4. registrar ganho ou regressao

### Fase 3 - `title injection` so se houver prova

Nao implementar agora.

So abrir esta hipotese se houver evidencia de que:

- o problema e multi-file open retrieval
- chunks semanticamente parecidos entre documentos diferentes estao confundindo ranking
- o titulo do documento melhora ranking sem degradar benchmark e latencia

Hoje isso nao foi provado.

## Plano reescrito

### Slice correta agora

**Nao implementar `title injection` agora.**

Implementar primeiro uma slice de `answer quality` com testes dirigidos pelos casos acima.

### Escopo da slice recomendada

Arquivos a tocar:

- `pipeline/src/free_plaud/retrieval/rag.py`
- `pipeline/tests/test_rag.py`

Arquivos que nao devem ser tocados nesta slice:

- `pipeline/src/free_plaud/retrieval/chunking.py`
- `pipeline/src/free_plaud/retrieval/indexer.py`
- `pipeline/src/free_plaud/retrieval/models.py`
- `pipeline/src/free_plaud/notes/schemas.py`
- `pipeline/src/free_plaud/notes/normalizer.py`
- `pipeline/src/free_plaud/retrieval/search.py`

### Comportamentos a adicionar em teste

1. se o chunk contem uma lista com dois itens pedidos, a resposta deve citar os dois
2. se existe no mesmo chunk uma frase generica e outra frase exata, preferir a exata
3. se a pergunta pede um campo tecnico explicito (`modelo de embedding`), nao responder com hardware ou custo
4. se a resposta depende da linha seguinte ao heading, combinar corretamente sem colagem ruim

### Critério de sucesso

- `ata-03` passa com `notificações de email` e `logs de auditoria`
- `paper-03` passa com `nomic-embed-text-v1.5`
- `paper-04` passa com `chunking semântico`
- `contrato-03` passa com `React + Node.js` e `Python + PostgreSQL`
- benchmark de retrieval continua estavel

## Se quiser testar chunking depois

So como experimento controlado.

### Slice experimental aceitavel

1. adicionar `heading-aware chunking`
2. expor `--chunking-strategy fixed|heading` no benchmark
3. nao mudar default
4. registrar em `docs/experimentos/10_chunking_heading_aware.md`

### Critério do experimento

- provar melhora em `MRR` ou em casos concretos
- sem regressao no baseline atual
- sem usar `title injection`

## O que nao fazer

- nao assumir que os erros citados sao “obviamente chunking”
- nao embutir prefixo de titulo em todos os chunks sem prova
- nao alterar `Chunk` ou `Note`
- nao trocar default de chunking antes do benchmark
- nao misturar correcoes de `rag.py` com experimento de chunking na mesma slice

## Branch sugerida

Para o problema real:

```text
feat/ask-claim-quality
```

Para experimento posterior de chunking:

```text
feat/chunking-heading-experiment
```

## Commits sugeridos

Para a slice correta agora:

1. `test: adicionar casos de claim quality no ask`
2. `fix: melhorar selecao de claims no rag`
3. `docs: registrar validacao da melhoria no ask`

Para o experimento posterior:

1. `feat: adicionar estrategia heading-aware no chunker`
2. `feat: expor chunking-strategy no benchmark`
3. `docs: registrar experimento de chunking`
