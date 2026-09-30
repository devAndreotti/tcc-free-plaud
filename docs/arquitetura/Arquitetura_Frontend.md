---
tags:
- tcc
- arquitetura
- frontend
- ui
---

# Arquitetura Frontend

## Papel do frontend

O frontend não é a parte principal da contribuição científica, mas é importante para:

- demonstrar o artefato
- operar o pipeline sem fricção
- visualizar fila, chat e benchmark
- tornar a proposta convincente na apresentação final

## Estratégia recomendada

### Regra principal

Não construir a interface final antes de existir um backend mínimo funcional.

O frontend deve entrar em camadas:

1. zero UI, apenas CLI e scripts
2. dashboard web local
3. shell desktop com Tauri

## Stack recomendada

- `React`
- `TypeScript`
- `Vite`
- `Tailwind CSS`
- `Zustand` para estado local de UI

### Opcional

- `shadcn/ui` se acelerar a entrega sem virar dependência de customização pesada
- `TanStack Query` se o frontend passar a conversar com endpoints locais mais ricos

## Superfícies da interface

### 1. Dashboard

Resumo do sistema:

- pasta monitorada
- itens na fila
- últimos processamentos
- status do vetor
- status das chaves/configurações

### 2. Queue / Processing

Tela para:

- ver arquivos aguardando
- ver erros
- reprocessar itens
- inspecionar tempo por etapa

### 3. Notes / Corpus

Tela para:

- visualizar notas geradas
- abrir Markdown bruto
- checar metadados
- validar se a estruturação está coerente

### 4. AutoRAG Chat

Tela para:

- fazer perguntas
- ver resposta
- ver citações
- inspecionar chunks recuperados

### 5. Benchmark

Tela para:

- escolher configurações de experimento
- rodar batches
- comparar métricas
- exportar resultados

### 6. Settings

Tela para:

- pasta de entrada
- pasta de saída
- provedor
- modelo
- embedding
- thresholds

## Estratégia visual

### Direção desejada

O app precisa parecer:

- técnico
- confiável
- discreto
- pesquisável
- mais ferramenta de conhecimento do que app de moda

### O que evitar

- visual genérico de dashboard AI
- glassmorphism gratuito
- gradientes aleatórios
- UI mais sofisticada do que os dados que ela exibe

### Direção implementada (UI v2)

A interface desktop segue a linha "instrumento de pesquisa": feita para ler e verificar, não para parecer um app de IA.

- **Tokens** em `UI/src/index.css`: grafite com leve viés violeta e um único acento violeta. Não há gradientes nem brilhos decorativos. Cores semânticas (`--ok`, `--warn`, `--err`) ficam separadas do acento. O `App.css` não usa cores literais, só tokens e `color-mix`.
- **Tema claro e escuro** reais: `:root` é o escuro e `:root[data-theme="light"]` redefine só os tokens. A escolha (Escuro, Claro ou Sistema) é salva em `localStorage` e aplicada antes do primeiro render (`UI/src/theme.ts`).
- **Tipografia com papéis**: IBM Plex Sans na interface, Source Serif 4 na leitura (respostas e notas) e IBM Plex Mono nos dados (ids de chunk, ms, métricas). Sem rede, cada pilha cai para fontes do sistema.
- **Sidebar**: recolhida (64 px, ícones com tooltip) ou expandida (232 px, rótulos), com Ctrl+B. Todos os botões da coluna compartilham o mesmo formato. Configurações fica logo abaixo da navegação; recolhida, abre as seções ao passar o mouse. O rodapé mostra a saúde do corpus (Doctor) e o vault monitorado.
- **Primitivas CSS** compartilhadas (`.btn`, `.switch`, `.popover`, `.pill`, `.card`, `.data-table`, `.page-head`) entre Notas, Fila, Benchmark e Configurações.

### Como chegar na direção visual

Usar a pasta:

- `D:\Dev\Repos\tcc-free-plaud\.agents\inspirations`

com a skill local:

- `inspiration-to-theme`

para transformar referências reais em:

- paleta
- tipografia
- superfícies
- tokens de interface
- regras de composição

## Estratégia de implementação

### Fase 1 - UI mínima

- dashboard básico
- fila simples
- chat simples

Objetivo:

- demonstrar funcionamento
- expor o pipeline
- não competir com o backend por tempo

### Fase 2 - UI de validação

- benchmark page
- visualização de citações
- inspeção de chunks

Objetivo:

- ajudar na análise experimental
- facilitar demonstração para orientador e banca

### Fase 3 - polimento

- ajustes de layout
- direção visual baseada em inspirations
- refinamento de estados vazios, loading e erro

## Integração com o backend

No início, o frontend deve conversar com:

- comandos locais
- arquivos de resultado
- uma camada leve de API local ou IPC

Só depois vale acoplar totalmente ao shell desktop.

Na evolução atual, a UI React dentro do PyWebView deixa de responder apenas mock:

- `UI/main.py` importa o pacote `free_plaud` pelo `pipeline/src`
- o chat chama `corpus ask` real usando a estratégia padrão configurada
- o modal de configurações salva `FREE_PLAUD_ANSWER_API_KEY` em `pipeline/.env`
- a pasta selecionada no modal pode ser indexada no corpus local
- a tela Notes agrupa as notas pela pasta relativa ao vault e abre cada uma em modo leitura
  (Markdown renderizado). O interruptor "Mostrar chunks" troca a leitura pelos trechos indexados,
  com índice, tokens, faixa de caracteres e sobreposição. Apagar confirma num popover; o backend
  mantém a confirmação textual, enviada pela UI só depois do clique. Reindexar parte do
  `source_path` persistido
- a tela Fila inicia indexação de pasta como job em background por processo e consulta o
  progresso. Mostra as etapas (descoberta, leitura, embedding, gravação, commit), uma barra por
  resultado (indexadas, inalteradas, com falha, ignoradas), taxa, ETA, modo de commit e tempo por
  etapa, além das falhas com código. Também solicita cancelamento cooperativo
- o chat chama `askCorpus(message, strategy)`, que devolve o `AskResponse` estruturado: afirmações
  com apoio direto ou parcial, citações com faixa de caracteres, limitações, estratégia, top-k,
  provedor e latência. Cada afirmação ganha nota de rodapé ligada à fonte, e "sem resposta" mostra
  o motivo do backend. A estratégia (híbrida, vetorial ou lexical) é escolhida por pergunta. O
  `sendMessage` em texto continua como fallback para backends antigos e para os mocks de E2E
- o Benchmark abre com uma frase que responde qual estratégia usar (maior Recall@5, com desempate
  por MRR e latência), destaca a melhor de cada coluna e desenha Recall@k com eixo de 0 a 1
- settings de frontend, TUI e menu terminal passam a consumir o catálogo canônico de
  `free_plaud.app.settings_catalog`, evitando rótulos divergentes para `top_k`,
  `chunk_size`, `overlap`, provider, device e segredo local
- o modal de configurações lista modelos expostos pelo provider configurado via backend,
  sem vazar API key e sem acessar endpoints locais direto pelo React

O modo `npm run dev` continua mockado porque não há IPC PyWebView no navegador comum. Para validar
a integração real, é necessário gerar o build e abrir `UI/main.py` pelo ambiente do pipeline com
extra `desktop`.

## Estrutura sugerida

```text
src/
├── app/
├── components/
├── features/
│   ├── dashboard/
│   ├── queue/
│   ├── notes/
│   ├── chat/
│   ├── benchmark/
│   └── settings/
├── lib/
├── stores/
└── styles/
```

## Primeiro objetivo de frontend

O primeiro milestone de frontend não é "bonito".

É:

> conseguir mostrar a fila, disparar uma pergunta no AutoRAG e exibir a resposta com citação.

Se isso existir, a interface já cumpre sua função de prova de artefato.
