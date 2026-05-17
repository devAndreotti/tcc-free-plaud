# Como estruturar um backend Python 3.12 com uv, Typer, Pydantic e Pytest para um projeto RAG local-first

Este guia descreve uma forma sólida de começar o backend do projeto **free-plaud** sem antecipar complexidade desnecessária. A proposta combina **Python 3.12**, **uv**, **Typer**, **Pydantic** e **Pytest** dentro de um desenho orientado a domínio, adequado para um pipeline experimental de RAG com foco em execução local, benchmark e evolução incremental.

## Princípios que devem guiar a implementação

A melhor abordagem para esse tipo de projeto é tratar o backend como um **monólito modular**. Isso significa que o código fica no mesmo projeto Python, mas com fronteiras explícitas entre os módulos de ingestão, estruturação de notas, recuperação, benchmark e persistência. Esse arranjo reduz atrito de desenvolvimento, facilita testes integrados e mantém espaço para refatoração futura caso algum módulo precise virar serviço independente.

Também é importante respeitar o princípio **local-first**. Em vez de espalhar dados e estados em vários lugares, o backend deve centralizar seus artefatos em diretórios locais previsíveis, como `data/corpus`, `data/datasets` e `data/results`. Assim, o pipeline experimental se torna reproduzível, observável e mais compatível com o processo científico do TCC.

## Estrutura recomendada de pastas

```text
free-plaud/
├── data/
│   ├── corpus/
│   ├── datasets/
│   └── results/
├── docs/
│   └── arquitetura/
├── pipeline/
│   ├── .gitignore
│   ├── .python-version
│   ├── README.md
│   ├── pyproject.toml
│   ├── src/
│   │   └── free_plaud/
│   │       ├── app/
│   │       ├── benchmark/
│   │       ├── ingest/
│   │       ├── notes/
│   │       ├── providers/
│   │       ├── retrieval/
│   │       ├── storage/
│   │       └── cli.py
│   └── tests/
└── README.md
```

Essa organização é melhor do que concentrar tudo na raiz porque separa claramente o **projeto Python executável** do restante da documentação e do futuro frontend. Além disso, o uso do **layout em `src/`** reduz ambiguidades de import durante testes, o que é amplamente recomendado em projetos Python com empacotamento moderno [1].

## Responsabilidade de cada módulo

| Módulo | Responsabilidade principal | O que evitar |
|---|---|---|
| `app` | configuração, caminhos, logging e utilidades transversais | lógica de domínio do RAG |
| `ingest` | descobrir arquivos, validar entrada e carregar conteúdo bruto | chamar provedores diretamente |
| `notes` | modelar nota, estruturar conteúdo e gerar Markdown | persistir vetores |
| `retrieval` | chunking, indexação, busca e composição de contexto | conhecer detalhes de UI |
| `benchmark` | datasets, métricas, runners e relatórios | depender da interface |
| `storage` | encapsular SQLite e store vetorial local | conter regra de negócio experimental |
| `providers` | contratos e adaptadores para embeddings, resposta, visão e transcrição | vazar SDKs para o resto da base |

A separação acima é útil porque mantém a arquitetura flexível. Se amanhã você trocar o store vetorial ou o modelo de embedding, a maior parte do sistema continua intacta. Se o benchmark precisar de uma malha maior de experimentos, essa evolução acontece em `benchmark/` sem impactar ingestão ou CLI.

## Arquivos iniciais mais importantes

| Arquivo | Papel |
|---|---|
| `pipeline/pyproject.toml` | define metadados, dependências, script da CLI e configuração de testes |
| `pipeline/.python-version` | fixa o Python 3.12 para o projeto |
| `pipeline/src/free_plaud/cli.py` | compõe a CLI raiz e registra subcomandos |
| `pipeline/src/free_plaud/app/config.py` | centraliza configuração com Pydantic Settings |
| `pipeline/src/free_plaud/ingest/loaders.py` | primeiro ponto de leitura de artefatos locais |
| `pipeline/src/free_plaud/notes/schemas.py` | define a entidade central de conhecimento |
| `pipeline/src/free_plaud/retrieval/chunking.py` | fornece chunking determinístico e testável |
| `pipeline/src/free_plaud/benchmark/runners.py` | concentra a execução de cenários experimentais |
| `pipeline/src/free_plaud/storage/vector.py` | define a fronteira do store vetorial local |
| `pipeline/tests/` | garante feedback rápido desde o início |

## Como configurar com uv da melhor forma

O `uv` deve ser tratado como a interface principal de ambiente e dependências. O fluxo recomendado é inicializar o projeto, declarar dependências no `pyproject.toml`, sincronizar o ambiente e usar `uv run` para comandos locais. A documentação oficial destaca que `uv` mantém o ambiente sincronizado com `pyproject.toml` e `uv.lock`, melhorando reprodutibilidade do projeto [2].

| Tarefa | Comando recomendado |
|---|---|
| sincronizar ambiente | `uv sync` |
| executar CLI | `uv run free-plaud --help` |
| rodar testes | `uv run pytest` |
| adicionar dependência | `uv add nome-da-lib` |
| adicionar dependência de desenvolvimento | `uv add --dev nome-da-lib` |

O ideal é manter `uv.lock` versionado no repositório sempre que o backend começar a ser instalado de forma reprodutível entre máquinas. Mesmo no começo do projeto, isso reduz divergências de ambiente e facilita replicar experimentos do TCC.

## Como organizar a CLI com Typer

A CLI deve ser a interface operacional principal do backend enquanto não existir interface gráfica madura. Para isso, a melhor prática é criar uma **aplicação raiz** e anexar subaplicações por domínio. A própria documentação do Typer recomenda esse estilo para CLIs com múltiplos comandos, o que combina naturalmente com módulos como `ingest`, `notes`, `retrieval`, `benchmark` e `storage` [3].

Em vez de criar uma função monolítica para tudo, o mais saudável é ter um pequeno `cli.py` em cada módulo com responsabilidades diretas. Dessa forma, `free-plaud ingest show`, `free-plaud notes build` e `free-plaud benchmark run-demo` continuam coesos e fáceis de expandir.

## Como usar Pydantic corretamente

O papel do Pydantic aqui não é apenas validar payloads externos. Ele deve ser usado para **modelar entidades do domínio** e para **configuração tipada**. `Settings` precisa concentrar diretórios, parâmetros de chunking, `top_k` padrão e caminhos de persistência. Já modelos como `Note`, `Chunk` e `BenchmarkSample` devem explicitar a forma dos dados que circulam pelo pipeline.

A vantagem prática é dupla. Primeiro, você reduz estados implícitos e erros silenciosos. Segundo, prepara o terreno para serialização, testes e migrações futuras com muito menos retrabalho.

## Como pensar o benchmark desde o início

Em um projeto de RAG aplicado a TCC, benchmark não é acessório; ele é parte do valor científico do backend. Por isso, o módulo `benchmark/` precisa existir desde o scaffold, mesmo que inicialmente trabalhe com poucos cenários e métricas simples. A arquitetura deve facilitar medições como **Recall@k**, **MRR**, latência média e comparação entre variações de chunking, embeddings e `top_k`.

A decisão mais importante é manter benchmark **fora da interface**. Ele deve poder rodar por script ou CLI, produzir tabelas e registrar seus artefatos em `data/results`. Esse desacoplamento evita que a avaliação experimental fique refém de decisões visuais ou do ciclo do frontend.

## Ordem recomendada de evolução

| Etapa | Entrega esperada |
|---|---|
| Fundação | configuração, CLI, testes e diretórios locais |
| Core textual | `.txt`, `.md`, `.pdf`, nota Markdown e chunking |
| Recuperação | indexação local, busca e resposta com citação |
| Benchmark | datasets, métricas e relatórios comparativos |
| Multimodal | áudio, imagem e OCR/visão |
| Interface | UI local e, depois, shell desktop |

Essa ordem reduz retrabalho porque primeiro estabiliza o núcleo experimental do sistema. Somente depois faz sentido adicionar camadas de interface e empacotamento.

## O que vale a pena melhorar logo após o scaffold

Assim que a base estiver funcionando, o próximo passo mais produtivo é substituir os stubs por integrações reais em pontos estratégicos. O parsing de PDF pode ganhar implementação robusta, `storage/vector.py` pode receber um adaptador de ChromaDB, e o benchmark pode exportar relatórios mais detalhados em Markdown e CSV. Em paralelo, você pode adicionar `ruff`, `mypy` e `pre-commit` para elevar a disciplina do backend sem alterar seu desenho principal.

## Referências

[1] Pytest Documentation. *Good Integration Practices*. Disponível em: <https://docs.pytest.org/en/stable/explanation/goodpractices.html>.

[2] Astral. *Working on projects | uv*. Disponível em: <https://docs.astral.sh/uv/guides/projects/>.

[3] Typer Documentation. *Commands*. Disponível em: <https://typer.tiangolo.com/tutorial/commands/>.
