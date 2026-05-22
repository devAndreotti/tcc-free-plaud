# Documentacao do Projeto

## Objetivo

Esta pasta concentra a documentacao do projeto em camadas diferentes.

O objetivo desta organizacao e separar:

- fonte de verdade tecnica
- planejamento e ordem de execucao
- guias operacionais
- historico experimental
- material academico

## Mapa rapido

### `arquitetura/`

Fonte de verdade tecnica do projeto.

Use quando precisar entender:

- desenho geral do sistema
- backend
- frontend
- fronteiras entre camadas

Arquivos principais:

- `Arquitetura.md`
- `Arquitetura_Backend.md`
- `Arquitetura_Frontend.md`

### `planejamento/`

Planejamento macro e priorizacao.

Use quando precisar entender:

- ordem de execucao
- metodologia de entrega
- requisitos e prioridades

Arquivos principais:

- `Plano_de_Arranque.md`
- `Metodologia_Akita_Git.md`

### `plano_execucao/`

Guia operacional do projeto.

Use quando precisar:

- seguir a ordem das sprints
- lembrar o estado atual do backend
- alinhar backend e frontend

Arquivos principais:

- `PLANO_BACKEND_PESSOAL.md`
- `CONTRATOS_FRONT_BACK.md`
- `HANDOFF_FRONTEND_JOAO.md`
- `HANDOFF_OBSIDIAN_CLEANER.md`
- `HANDOFF_CHUNKING_IMPROVEMENTS.md`
- `HANDOFF_PODA_SPAN_MINIMO_SUFICIENTE.md`
- `HANDOFF_VALIDACAO_RETRIEVAL_DISTRIBUIDO.md`
- `HANDOFF_MELHORIA_RANKING_FALSO_POSITIVO.md`
- `HANDOFF_TCC_TUI_TEXTUAL.md`
- `HANDOFF_TUI_TEXTUAL_VISUAL_REFINEMENT.md`
- `HANDOFF_CORPUS_INDEX_E_ASK_MULTI_DOCUMENTO.md`

### `experimentos/`

Registro experimental reaproveitavel no TCC.

Use para:

- guardar comparacoes tecnicas
- registrar comandos e resultados
- citar numeros depois no texto do TCC

Regra:

- um arquivo novo por experimento relevante
- numeracao sequencial `01`, `02`, `03`...

### `referencias_ia/`

Material auxiliar e guias de apoio.

Nao e fonte de verdade.

Use apenas como apoio tecnico quando:

- a arquitetura oficial nao basta
- houver necessidade de contexto adicional

### `tcc/`

Zona academica.

Use para:

- texto do TCC
- perguntas de pesquisa
- notas bibliograficas
- material de escrita academica

Nao e a fonte principal de implementacao.

### `ORDEM_DE_LEITURA_IA.md`

Contrato minimo de leitura para IA e agentes de codigo.

Este arquivo existe para reduzir leitura excessiva e evitar que a IA consulte a pasta errada.

## Ordem recomendada de uso

### Para implementacao backend

1. `../AGENTS.md`
2. `ORDEM_DE_LEITURA_IA.md`
3. `arquitetura/Arquitetura_Backend.md`
4. pasta relevante em `../Sprints/`

### Para implementacao frontend

1. `../AGENTS.md`
2. `ORDEM_DE_LEITURA_IA.md`
3. `arquitetura/Arquitetura_Frontend.md`
4. `plano_execucao/CONTRATOS_FRONT_BACK.md`
5. pasta relevante em `../Sprints/`

### Para escrita do TCC

1. `tcc/`
2. `experimentos/`
3. `arquitetura/`

## Regras praticas

1. `arquitetura/` define como o projeto deve funcionar.
2. `planejamento/` define prioridade e sequencia.
3. `plano_execucao/` traduz isso em execucao do dia a dia.
4. `experimentos/` registra o que foi medido ou comparado.
5. `tcc/` serve ao texto academico, nao ao caminho principal de implementacao.

## Estado atual

Hoje o backend foi implementado ate a Sprint 07, e o projeto esta em fase de calibracao experimental do retrieval antes da integracao com UI.

Para esse ponto especifico, ver:

- `plano_execucao/PLANO_BACKEND_PESSOAL.md`
- `experimentos/`
- `../Sprints/STATUS.md`
