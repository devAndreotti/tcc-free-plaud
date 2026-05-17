# 05 - Roteiro de Demo em 5 Minutos

## Objetivo

Este roteiro existe para demonstrar o backend atual de forma curta, objetiva e repetivel.

Ele foi pensado para:

- orientacao
- pre-banca
- banca
- apresentacao rapida de progresso

## Escopo da demo

A demo prova cinco coisas:

1. o backend roda sem UI
2. ele ingere e estrutura documento
3. ele gera chunks e persiste artefatos
4. ele responde pergunta com citacao
5. ele compara retrieval lexical vs vetorial

## Pre-condicoes

Executar antes:

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud
cd pipeline
uv sync
```

Arquivo garantido no repositorio:

- `D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md`

Para a parte de benchmark comparativo, a pasta `samples/` precisa existir no ambiente local.

## Roteiro de 5 minutos

### 1. Mostrar que o backend esta configurado

Comando:

```powershell
uv run free-plaud doctor
```

Falar:

- o projeto roda como CLI
- os diretorios de dados, notas, SQLite e vector store estao definidos
- o embedding baseline atual e `chroma-default`

### 2. Mostrar ingestao e nota canonica

Comandos:

```powershell
uv run free-plaud ingest show "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"
uv run free-plaud notes save "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"
```

Falar:

- o sistema le um documento local
- gera uma nota estruturada
- salva `.md` e `.meta.json`
- isso cria o artefato canonico que sustenta o resto do pipeline

### 3. Mostrar chunking com offsets

Comando:

```powershell
uv run free-plaud retrieval chunks "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"
```

Falar:

- o documento e quebrado em chunks
- cada chunk tem `chunk_id`, offsets e rastreabilidade
- isso prepara retrieval e citacao auditavel

### 4. Mostrar ask lexical ou vetorial

Comando recomendado:

```powershell
uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md" --question "Qual e o papel do backend?"
```

Opcional vetorial:

```powershell
uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md" --question "Qual e o papel do backend?" --strategy vector
```

Falar:

- a resposta sai em JSON estruturado
- ha `claims`, `citations` e `latency_ms`
- quando a base nao sustenta a resposta, o sistema pode se abster

### 5. Mostrar benchmark comparativo

Comando:

```powershell
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

Falar:

- o benchmark e reproduzivel
- ele compara `lexical` vs `vector`
- hoje, no corpus real local, `lexical` ainda vence `vector`

## Numeros que vale citar

No baseline atual da suite real:

- `lexical`: `MRR 0.96875`, `Recall@3 1.0`
- `vector`: `MRR 0.7916666666666666`, `Recall@3 0.9375`

Interpretacao curta:

- o pipeline vetorial esta implementado
- ele funciona
- mas ainda nao supera o baseline lexical no corpus real atual

## Versao ultra-curta da fala

```text
O backend do TCC roda sem interface, ingere documentos locais, transforma o texto em nota canonica, gera chunks com offsets, responde perguntas com citacao e ainda executa benchmark reproduzivel comparando retrieval lexical e vetorial.

Hoje o sistema ja e um artefato experimental funcional. O proximo passo nao e interface; e melhorar a qualidade do retrieval vetorial para ele competir melhor com o baseline lexical.
```

## Fallback se o benchmark real nao puder ser mostrado

Se a pasta `samples/` nao estiver disponivel:

```powershell
uv run free-plaud benchmark run-demo "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"
```

Falar:

- o runner de benchmark existe
- o modo demo mostra o fluxo fim a fim
- a comparacao real depende do corpus local de validacao

## Sequencia mais segura para banca

Se precisar reduzir risco operacional, usar apenas:

1. `doctor`
2. `notes save`
3. `retrieval ask`
4. `benchmark compare` ou `benchmark run-demo`

## Referencias internas

Para validacao mais completa, ver:

- `D:\Dev\Repos\Own\tcc-free-plaud\docs\experimentos\04_matriz_testes_manuais_tcc_demo.md`
- `D:\Dev\Repos\Own\tcc-free-plaud\docs\experimentos\01_lexical_vs_vector_suite_baseline.md`
- `D:\Dev\Repos\Own\tcc-free-plaud\docs\experimentos\02_calibracao_retrieval_vetorial.md`
