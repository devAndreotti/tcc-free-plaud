# Visão Geral da Arquitetura (Architecture Overview)

Este documento descreve o estado atual da arquitetura do projeto `tcc-free-plaud`. O objetivo principal é manter um registro estruturado dos componentes do sistema para o consumo eficiente de informações pelo assistente de IA, reduzindo a necessidade de análise contínua do código fonte.

## Visão Geral

O projeto consiste em uma aplicação Desktop construída com **PyWebView** (Python) no backend, renderizando uma interface **React (TypeScript + Vite)** no frontend. 

A arquitetura atual foca em validar o core experimental do pipeline (ingestão, indexação, e RAG com citações) através de uma interface visual simples e local-first.

## Estrutura de Pastas Principal

- `UI/`: Contém todo o ecossistema frontend (React, Vite, Tailwind CSS).
  - `UI/main.py`: O ponto de entrada da aplicação backend Python (PyWebView). Inicia a UI e expõe os métodos nativos.
  - `UI/src/`: Código fonte do frontend React.
    - `components/`: Componentes visuais do React (Chat, Sidebar, Header, etc).
    - `services/`: Serviços de comunicação, especificamente a *bridge* que conecta o React aos métodos Python.
    - `contexts/`: Gerenciamento de estado global da aplicação (ex: VaultContext).
- `docs/`: Documentação arquitetural original do projeto e notas de pesquisa do TCC.
- `.agents/`: Workflows e skills para o assistente de IA focado na metodologia Akita.

## Fluxo de Comunicação (Bridge)

O frontend não tem acesso direto ao sistema de arquivos devido a limitações de segurança do navegador embutido. A comunicação com o sistema operacional ocorre através do `UI/src/services/bridge.ts`, que invoca métodos expostos em `window.pywebview.api`.

Quando executado localmente (desenvolvimento), o `bridge.ts` fornece mocks para simular as respostas do backend, permitindo o desenvolvimento da interface independentemente do motor Python.
