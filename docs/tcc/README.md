# Documentacao Academica do TCC

## Objetivo

Esta pasta concentra o material academico do projeto.

Ela nao e a fonte principal de implementacao do backend, mas e a fonte principal para:

- escrita do TCC
- perguntas de pesquisa
- preparo de defesa
- apoio bibliografico

## Estrutura

### `texto/`

Texto-base do trabalho.

Arquivo principal:

- `texto/TCC.md`

### `perguntas/`

Perguntas que orientam:

- recorte de pesquisa
- condicao de pronto
- defesa e banca

Arquivos principais:

- `perguntas/Perguntas_a_Serem_Respondidas.md`
- `perguntas/Perguntas_do_TCC.md`

### `apoio/`

Material academico auxiliar.

Use para:

- notas de pesquisa
- analises intermediarias
- revisao bibliografica em Markdown

### `fontes_editaveis/`

Arquivos de edicao externa, como `.docx`.

Regra:

- `.md` continua sendo melhor para historico no Git
- `.docx` fica aqui como fonte editavel ou artefato de exportacao

## Ordem recomendada de leitura

### Para escrita do TCC

1. `texto/TCC.md`
2. `perguntas/Perguntas_a_Serem_Respondidas.md`
3. `perguntas/Perguntas_do_TCC.md`
4. `apoio/`
5. `../experimentos/`

### Para implementacao

Por padrao, nao comecar por esta pasta.

Seguir:

1. `../../AGENTS.md`
2. `../ORDEM_DE_LEITURA_IA.md`
3. `../arquitetura/`
4. `../../Sprints/`

## Regra pratica

Se uma mudanca alterar:

- escopo academico
- pergunta de pesquisa
- contribuicao do trabalho

entao o arquivo principal a revisar e:

- `texto/TCC.md`
