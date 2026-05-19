# Handoff - Poda de resposta para span minimo suficiente

## Objetivo

Implementar uma slice pequena em `rag.py` para reduzir verbosidade do `ask`
sem mexer em retrieval, chunking ou benchmark.

A meta aqui nao e "responder melhor em geral".

A meta e mais estreita:

1. manter a melhora de completude obtida na slice de `claim quality`
2. remover heading, anexo, frase generica e contexto excedente quando a resposta exata ja esta presente
3. preservar grounding, citations e `no_answer`

## Veredito senior

O plano anterior estava **direcionalmente correto**, mas estreito demais.

Problema do plano anterior:

1. usava so 4 casos como alvo
2. isso e suficiente para justificar a slice
3. mas nao e suficiente para provar que a poda nao vai estragar respostas que ja estavam boas ou parcialmente boas

Correcao:

- manter os 4 casos-raiz
- ampliar a bateria para cobrir **todos os 4 arquivos da suite real**
- separar claramente:
  - casos de melhoria obrigatoria
  - casos de estabilidade
  - casos de preservacao de nuance
  - casos negativos de `no_answer`

## Contexto validado

A slice anterior registrada em `docs/experimentos/10_melhoria_claim_quality.md`
provou duas coisas:

1. a causa raiz principal nao era o chunker
2. a nova selecao de claims melhorou factualidade, mas ainda devolve spans grandes demais

Casos onde isso ficou claro:

- `ata-03`
- `paper-03`
- `paper-04`
- `contrato-03`

Estado atual:

- retrieval esta estavel
- benchmark esta estavel
- completude factual melhorou
- resposta ainda vem com ruido como:
  - headings
  - prefixos de anexo
  - frase introdutoria desnecessaria
  - duas ou tres linhas quando uma bastaria

Conclusao:

- o gargalo agora esta em **span pruning**
- nao em retrieval
- nao em chunking

## O que esta fora de escopo

Nao tocar nesta slice:

- `pipeline/src/free_plaud/retrieval/chunking.py`
- `pipeline/src/free_plaud/retrieval/indexer.py`
- `pipeline/src/free_plaud/retrieval/search.py`
- `pipeline/src/free_plaud/storage/vector.py`
- benchmark
- pesos de hybrid
- cleaner do Obsidian

Tambem nao abrir nesta slice:

- LLM
- answer multi-file
- reranking vetorial
- mudanca de schema de `Chunk` ou `Note`

## Arquivos-alvo

Pode tocar:

- `pipeline/src/free_plaud/retrieval/rag.py`
- `pipeline/tests/test_rag.py`

Deve registrar resultado em:

- `docs/experimentos/11_poda_span_minimo_suficiente.md`

## Leitura minima antes de codar

1. `AGENTS.md`
2. `docs/ORDEM_DE_LEITURA_IA.md`
3. `docs/arquitetura/Arquitetura_Backend.md`
4. `docs/experimentos/10_melhoria_claim_quality.md`
5. `pipeline/src/free_plaud/retrieval/rag.py`
6. `pipeline/tests/test_rag.py`

## Skills sugeridas

Usar:

- `akita-way`
- `senior-second-pass`
- `adversarial-delivery-auditor`

Papel de cada uma:

- `akita-way`: manter slice pequena, com teste antes da mudanca
- `senior-second-pass`: revisar se a heuristica nova nao mascara problema real
- `adversarial-delivery-auditor`: tentar quebrar respostas positivas e negativas depois da implementacao

## Hipotese tecnica

Hoje o pipeline ja encontra claims melhores, mas a composicao final ainda aceita
spans mais longos do que o necessario.

Os sinais mais provaveis:

1. `_line_candidates()` gera combinacoes uteis para completude, mas algumas variantes continuam longas demais
2. `_rank_claim_candidates()` premia matches e completude, mas ainda nao premia bastante o **span minimo suficiente**
3. a poda final do texto escolhido ainda esta fraca

Entao a ordem correta e:

1. preservar o ranking atual
2. introduzir heuristica de poda minima
3. validar que nao piorou `no_answer`

## Matriz de validacao correta

### Grupo A - Casos de melhoria obrigatoria

Estes sao os 4 casos onde a slice precisa melhorar a resposta, nao so preservar:

- `ata-03`
- `paper-03`
- `paper-04`
- `contrato-03`

### Grupo B - Casos de estabilidade em respostas ja boas

Estes casos ja estavam razoaveis e nao podem piorar:

- `ata-01`
- `ata-02`
- `ata-04`
- `paper-01`
- `paper-02`
- `contrato-01`
- `dw-03`
- `dw-04`

Objetivo:

- a poda nao pode remover o termo tecnico central
- a poda nao pode apagar valor numerico ou entidade principal

### Grupo C - Casos de preservacao de nuance

Estes casos sao mais perigosos para poda agressiva:

- `contrato-02`
- `contrato-04`
- `dw-01`
- `dw-02`

Objetivo:

- nao cortar qualificadores que mudam o significado
- nao trocar resposta precisa por frase curta, mas incompleta

Exemplos:

- `contrato-02` nao pode perder `obrigação de confidencialidade`
- `contrato-04` nao pode virar so `2h` sem manter o contexto de `Prioridade Crítica`
- `dw-02` nao pode perder a parte de `preserva o histórico completo`

### Grupo D - Casos negativos obrigatorios

Obrigatorio revalidar ao menos dois casos negativos/adversariais ja usados nos experimentos:

1. `Quais tecnologias o candidato domina para desenvolver apps mobile?`
2. `Qual banco relacional foi escolhido para autenticar o painel web?`

Objetivo:

- poda de span nao pode reabrir falso positivo no `ask`
- `no_answer` precisa continuar estavel

### Grupo E - Suite inteira do ask

Antes de implementar e depois de implementar, gerar artefato com os pares:

- `sample_id`
- `question`
- `status`
- `answer`
- `reason_for_no_answer`
- `chunk_ids`

Cobertura minima:

- as `16` queries da suite real

Artefatos recomendados:

- `data/results/ask_suite_span_prune_before.json`
- `data/results/ask_suite_span_prune_after.json`

Isso fecha baseline e evita avaliar a slice so por quatro exemplos.

## Direcao de implementacao

### Fase 1 - Travar comportamento em teste

Adicionar testes dirigidos em `test_rag.py` para provar:

1. se a resposta util esta numa linha curta e especifica, ela deve vencer o span maior
2. se o claim contem heading + resposta, preferir so a parte informativa quando isso nao destruir grounding
3. se o chunk contem "ANEXO", "OBJETIVO DA SESSAO", "ESPECIFICACOES TECNICAS" e a resposta vem depois, nao devolver o prefixo inteiro
4. se a resposta depende de duas linhas adjacentes, manter as duas
5. se a resposta vetorial e fraca, `no_answer` continua funcionando

Casos a transformar em teste automatizado obrigatorio:

### Melhoria obrigatoria

- `ata-03`
- `paper-03`
- `paper-04`
- `contrato-03`

### Guardrail de estabilidade

- `ata-01`
- `paper-02`
- `contrato-01`
- `dw-03`

### Guardrail de nuance

- `contrato-02`
- `dw-02`

### Guardrail de abstention

- caso vetorial fraco que hoje deve continuar `no_answer`

### Fase 2 - Implementar poda local

Implementar em `rag.py`, sem reescrever o modulo inteiro.

Direcoes aceitaveis:

1. helper dedicado, por exemplo:
   - `_trim_claim_span(...)`
   - `_is_claim_prefix_noise(...)`
   - `_split_heading_prefix(...)`
2. poda depois da escolha do candidato, nao antes do retrieval
3. remover prefixo ruidoso somente quando:
   - a parte restante preserva termos da pergunta
   - a parte restante continua legivel
   - a citation segue apontando para o mesmo chunk

Heuristicas boas para considerar:

- cortar prefixo antes de `:` ou `-` quando o prefixo for heading administrativo
- remover marcador de anexo quando a resposta valida vem depois
- preferir menor variante que ainda:
  - mantem termos-chave da pergunta
  - mantem entidades tecnicas
  - mantem pares/listas pedidos

### Fase 3 - Tentar quebrar

Obrigatorio testar:

1. pergunta positiva de lista
2. pergunta positiva de valor unico
3. pergunta com heading no chunk
4. pergunta vetorial que deveria dar `no_answer`
5. pergunta onde qualifier juridico/tecnico nao pode sumir
6. suite inteira do `ask` antes/depois
7. benchmark compare como guardrail

## O que nao fazer

1. nao simplificar demais e perder o segundo item de uma lista
2. nao podar spans antes de verificar cobertura da pergunta
3. nao mover logica para `search.py`
4. nao tocar chunking para resolver verbosidade
5. nao mexer em hybrid calibration

## Criterio de sucesso

Aceitar a slice se:

1. `ata-03` continuar contendo `notificações de email` e `logs de auditoria`
2. `paper-03` continuar contendo `nomic-embed-text-v1.5`, mas sem arrastar texto desnecessario de infraestrutura
3. `paper-04` continuar apontando `chunking semântico` para documentos sem estrutura formal, com menos sobra
4. `contrato-03` continuar trazendo `React + Node.js` e `Python + PostgreSQL`, com menos heading/anexo
5. `ata-01`, `paper-02`, `contrato-01` e `dw-03` nao perderem seus termos centrais
6. `contrato-02`, `contrato-04` e `dw-02` nao perderem qualificadores semanticamente necessarios
7. `no_answer` vetorial nao regredir
8. benchmark continuar:
   - `lexical MRR = 0.96875`
   - `vector MRR = 0.7916666666666666`
   - `hybrid MRR = 0.96875`
   - `hybrid Recall@3 = 1.0`

## Comandos obrigatorios

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud
git status --short --branch
```

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline

$tmp = Join-Path $env:TEMP ("tcc-free-plaud-span-prune-focused-" + [guid]::NewGuid().ToString())
uv run pytest --basetemp $tmp tests\test_rag.py tests\test_benchmark.py tests\test_chunking.py -q

$tmp = Join-Path $env:TEMP ("tcc-free-plaud-span-prune-all-" + [guid]::NewGuid().ToString())
uv run pytest --basetemp $tmp -q

uv run free-plaud benchmark compare `
  --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

Opcional, mas recomendado para fechar evidencia:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
uv run python -m free_plaud.benchmark.export_ask_suite_baseline
```

Se esse helper nao existir, gerar artefato com script local temporario e registrar o comando no experimento.

## Artefato obrigatorio

Depois da implementacao, registrar:

- o que mudou
- testes executados
- comparacao da suite inteira do `ask`
- casos antes/depois
- falhas remanescentes

Arquivo:

- `docs/experimentos/11_poda_span_minimo_suficiente.md`

## Branch e commits sugeridos

Branch:

```text
feat/ask-minimal-span
```

Commits:

1. `test: adicionar casos de poda de span no ask`
2. `fix: podar resposta para span minimo suficiente`
3. `docs: registrar experimento de poda de span`

## Veredito desta proposta

Esta e a proxima slice correta porque:

- ataca o gargalo real observado agora
- preserva retrieval e benchmark
- continua pequena o bastante para validar sem contaminar outras camadas
- agora traz bateria suficiente para provar que a poda nao estragou respostas ja boas

Nao reabrir chunking antes de terminar esta rodada.
