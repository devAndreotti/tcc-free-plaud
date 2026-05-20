# Handoff - Validacao de Retrieval Distribuido

## Objetivo

Este arquivo existe para orientar uma IA a validar, com evidencia real de runtime, se o backend atual ja sustenta:

- indexacao correta
- persistencia vetorial
- retrieval semantico
- retrieval multi-chunk
- retrieval multi-file
- grounding
- context stitching
- `no_answer`

O foco aqui **nao** e frontend.
O foco aqui **nao** e TCC textual.
O foco aqui **nao** e LLM.

O foco aqui e:

> provar o que o pipeline atual realmente faz em cenarios de recuperacao contextual distribuida.

## Quando usar este handoff

Usar este arquivo quando a tarefa for:

- auditar o RAG atual
- validar o banco vetorial
- testar retrieval semantico real
- descobrir se multi-file retrieval existe de fato
- descobrir se o answer layer atual consegue costurar contexto distribuido

Nao usar este arquivo para:

- implementar UI
- escrever texto do TCC
- mexer em audio/imagem
- fazer refatoracao ampla sem evidencia

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

Nao ler `docs/tcc/`, salvo se a tarefa mudar explicitamente para contexto academico.

## Regra de escopo

Antes de tirar conclusao, validar contra codigo real em:

- `pipeline/src/free_plaud/retrieval/search.py`
- `pipeline/src/free_plaud/retrieval/rag.py`
- `pipeline/src/free_plaud/retrieval/indexer.py`
- `pipeline/src/free_plaud/storage/vector.py`
- `pipeline/src/free_plaud/benchmark/runners.py`

Nao confiar apenas em documentacao textual.

## Regra de abertura

Antes de qualquer comando:

1. rodar `git status`
2. verificar branch atual
3. se houver dirty tree relevante de outro trabalho, parar e reportar

Excecao conhecida:

- `samples/` pode continuar nao versionado como corpus local de validacao

## Ajuste operacional obrigatorio

Esta validacao deve usar uma collection vetorial isolada.

Antes de indexar arquivos para auditoria:

1. definir um `FREE_PLAUD_VECTOR_COLLECTION_NAME` exclusivo para a sessao
2. nao reutilizar a collection padrao caso ela contenha lixo de testes anteriores

Objetivo:

- evitar falso positivo por corpus residual
- garantir que multi-file retrieval observado veio apenas dos arquivos da auditoria

## Camadas de validacao

Esta auditoria deve separar claramente 3 camadas.

### Camada A - Indexacao e armazenamento vetorial

Verificar se:

- arquivos sao carregados corretamente
- notas sao estruturadas
- chunks sao gerados
- embeddings sao persistidos
- banco vetorial contem os chunks indexados
- `note_id`, `chunk_id`, offsets e metadados estao coerentes

### Camada B - Retrieval

Verificar se:

- busca vetorial traz contexto semanticamente relacionado
- varios chunks relevantes aparecem juntos
- retrieval multi-file funciona quando varios arquivos sao indexados na mesma collection
- ranking faz sentido
- ha falso positivo
- ha falso negativo

### Camada C - Answer layer

Verificar se:

- `retrieval ask` responde com grounding e citacoes
- `no_answer` aparece quando deveria
- a resposta depende ou nao de multiplos arquivos

Se multi-file answer nao for suportado pelo design atual, isso deve ser declarado explicitamente.

## Regra importante

Nao assumir que:

- `benchmark compare`
- ou `hybrid`

ja provam retrieval distribuido entre arquivos.

Isso deve ser validado explicitamente.

## Fluxo obrigatorio

### Etapa 1 - Baseline do projeto

Rodar:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud\pipeline
$tmp = "D:\Dev\Repos\Own\tcc-free-plaud\.pytest-tmp-$([guid]::NewGuid().ToString())"
uv run pytest --basetemp $tmp -q
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

Registrar:

- branch
- suite status
- `lexical`
- `vector`
- `hybrid`

### Etapa 2 - Persistencia vetorial real

Rodar:

```powershell
uv run free-plaud storage init
```

Depois indexar pelo menos 3 arquivos reais:

```powershell
uv run free-plaud retrieval index "<arquivo1>"
uv run free-plaud retrieval index "<arquivo2>"
uv run free-plaud retrieval index "<arquivo3>"
```

Verificar:

- `chunks_indexed`
- `vector_entries_count`
- persistencia em `data/results/vector_store`
- collection efetivamente isolada para a auditoria

### Etapa 3 - Retrieval single-file e multi-file

Executar consultas:

- com `--note-id`, para controle single-file
- sem `--note-id`, para retrieval multi-file

Exemplos:

```powershell
uv run free-plaud retrieval semantic-search --query "..." --top-k 5 --note-id "<note_id>"
uv run free-plaud retrieval semantic-search --query "..." --top-k 8
```

Cobrir 4 tipos de pergunta:

1. respondida por 1 chunk
2. respondida por multiplos chunks no mesmo arquivo
3. respondida por contexto distribuido entre arquivos
4. irrelevante ou fora de escopo

### Etapa 4 - Corpus temporario controlado, se necessario

Se `samples/` nao tiver um caso distribuido forte, criar corpus temporario nao versionado com 3 arquivos:

- arquivo A com contexto base
- arquivo B com detalhe operacional
- arquivo C com restricao ou complemento

Depois:

- indexar os 3
- testar `semantic-search`
- testar `ask`

Objetivo:

- provar ou refutar retrieval distribuido
- provar ou refutar answer multi-file

### Etapa 5 - Answer layer

Rodar:

```powershell
uv run free-plaud retrieval ask "<arquivo>" --question "..." --strategy lexical
uv run free-plaud retrieval ask "<arquivo>" --question "..." --strategy vector
uv run free-plaud retrieval ask "<arquivo>" --question "..." --strategy hybrid
```

Se o `ask` atual for arquiteturalmente limitado a uma `Note` por vez, isso deve ser dito explicitamente.

Nao tratar isso como bug acidental.
Tratar como limite de design atual, se confirmado por codigo e runtime.

## Artefato de saida obrigatorio

Esta auditoria deve gerar um registro reaproveitavel em:

- `docs/experimentos/08_validacao_retrieval_distribuido.md`

Esse arquivo deve conter:

1. objetivo
2. corpus usado
3. configuracao da collection
4. comandos executados
5. casos testados
6. evidencias
7. falhas encontradas
8. veredito

## Evidencias obrigatorias

Para cada caso relevante, registrar:

- pergunta
- arquivos envolvidos
- `note_id`
- `chunk_id`
- score
- distance
- matched terms
- term coverage
- strategy
- resposta final
- passou ou falhou

## Estrutura esperada da resposta final

### 1. O que funciona hoje

- indexing
- chunking
- vector storage
- semantic retrieval
- hybrid retrieval
- grounding
- `no_answer`

### 2. O que nao funciona ou funciona parcialmente

- multi-file retrieval
- multi-file answer
- context stitching
- ranking
- falso positivo
- falso negativo

### 3. Evidencias concretas

Comando, pergunta, chunks, score, arquivos e resultado.

### 4. Diagnostico tecnico

Dizer se limite principal esta em:

- chunking
- overlap
- persistencia vetorial
- ranking
- filtro de evidencia
- design atual do `ask`
- falta de orquestracao multi-document

### 5. Veredito

Responder objetivamente:

1. embeddings estao persistidos corretamente?
2. chunks estao recuperaveis?
3. busca vetorial traz contexto semanticamente relacionado?
4. retrieval multi-file existe de fato?
5. answer multi-file existe de fato?
6. o sistema atual ja se comporta como RAG contextual distribuido funcional?

### 6. Proximo passo recomendado

Sem refatorar ainda.

Apenas dizer qual gargalo principal vem primeiro:

- retrieval
- ranking
- multi-document orchestration
- chunking
- answer layer

## Regra de entrega

Nao aceitar conclusao vaga como:

- "parece funcionar"
- "esta quase pronto"

Aceitar apenas conclusao com:

- comandos rodados
- outputs relevantes
- casos positivos
- casos negativos
- falhas reais
- distincao clara entre:
  - funciona
  - funciona parcialmente
  - nao implementado por design

## Observacao final

Se a auditoria mostrar que:

- vector retrieval multi-file funciona
- mas o answer layer nao costura multi-file

entao a conclusao correta nao e "RAG falhou".

A conclusao correta e:

> retrieval distribuido existe parcialmente, mas answer orchestration multi-document ainda nao e suportada pelo desenho atual.

## Regra final de honestidade tecnica

Se a auditoria provar que:

- o banco vetorial funciona
- semantic-search multi-file funciona
- mas `ask` nao costura multi-file

entao o veredito correto e:

- retrieval distribuido parcial: **sim**
- answer distribuido de nivel RAG funcional de producao: **nao ainda**
