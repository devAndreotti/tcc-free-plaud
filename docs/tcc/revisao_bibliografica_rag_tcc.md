# Revisão bibliográfica sobre Retrieval-Augmented Generation aplicado a anotações pessoais em Obsidian e documentos corporativos

**Autor:** Manus AI  
**Data:** 31 mar. 2026

## Introdução

A evolução recente dos grandes modelos de linguagem tornou viável a construção de sistemas capazes de consultar acervos documentais heterogêneos em linguagem natural. Nesse contexto, a abordagem **Retrieval-Augmented Generation (RAG)** consolidou-se como uma alternativa técnica para mitigar limitações conhecidas dos modelos puramente paramétricos, em especial alucinações, desatualização factual e baixa rastreabilidade das respostas [1] [2] [3] [4]. Em vez de depender exclusivamente do conhecimento embutido nos pesos do modelo, o RAG recupera evidências externas em tempo de inferência e condiciona a geração à informação recuperada.

Esse paradigma é particularmente relevante para dois cenários que convergem no escopo deste TCC. O primeiro é o das **anotações pessoais**, em que o usuário mantém um acervo progressivamente crescente de notas em Markdown, frequentemente organizado em ferramentas como o **Obsidian**, com uso de wikilinks, headings, listas, anexos e fragmentos de texto produzidos ao longo do tempo. O segundo é o dos **documentos corporativos**, normalmente compostos por PDFs, memorandos, políticas, relatórios, atas, procedimentos e documentação operacional, cujo reaproveitamento depende de mecanismos eficazes de indexação, recuperação e citação. Nesses dois casos, o problema central não é apenas armazenar conteúdo, mas **recuperar conhecimento contextualizado, confiável e explicável**.

A literatura recente indica que o desempenho de sistemas RAG não depende de um único componente isolado, mas da coordenação entre ingestão documental, parsing, chunking, embeddings, armazenamento vetorial, recuperação, reranking, composição de contexto e geração final [2] [3] [4] [9]. Em corpora compostos por notas Markdown e PDFs, essa observação torna-se ainda mais importante, porque o valor do sistema depende de como ele preserva estrutura documental, metadados, vínculos semânticos e fronteiras lógicas do conteúdo.

> “Retrieval-Augmented Generation (RAG) has emerged as a powerful paradigm to enhance large language models (LLMs) by conditioning generation on external evidence retrieved at inference time” [4].

Diante desse quadro, esta revisão bibliográfica organiza e discute a literatura publicada entre **2022 e 2025**, complementada por documentação técnica e projetos open-source relevantes, com foco em quatro eixos: **arquitetura RAG**, **vector databases**, **chunking strategies** e **embedding models**. Além disso, compara as bibliotecas **LlamaIndex**, **LangChain** e **Haystack**, com ênfase em fluxos que envolvem **arquivos Markdown e PDFs**, e examina projetos do ecossistema **Obsidian + RAG/LLMs** que ajudam a situar o problema de pesquisa em soluções reais já adotadas pela comunidade.

## 1. Arquitetura RAG

A literatura convergente sobre RAG parte do diagnóstico de que LLMs puros são poderosos para generalização linguística, mas insuficientes quando o sistema precisa operar sobre informação recente, privada, de domínio restrito ou documentalmente verificável [1] [2] [4]. Cheng et al. descrevem o RAG como uma integração entre recuperação e geração baseada em fontes externas, enquanto Gao et al. o apresentam como resposta às limitações de factualidade, transparência e atualização dos modelos paramétricos [1] [2]. Em termos práticos, o RAG desloca parte da inteligência do sistema para o **pipeline de dados**.

Uma formulação bastante influente é a taxonomia de Gao et al., que separa o campo em **Naive RAG**, **Advanced RAG** e **Modular RAG** [2]. O Naive RAG representa a forma mais simples do paradigma: documentos são segmentados, vetorizados, armazenados em um índice e consultados por similaridade; os trechos retornados compõem o prompt usado pelo gerador. O Advanced RAG acrescenta recursos como reranking, query rewriting, recuperação híbrida, filtros, multi-hop retrieval e estratégias para reduzir ruído no contexto. Já o Modular RAG rompe a linearidade do pipeline e trata o sistema como uma composição de módulos especializados, capazes de trocar informação de forma mais flexível.

Sharma propõe outra taxonomia complementar, classificando arquiteturas em **retriever-centric**, **generator-centric**, **hybrid** e **robustness-oriented** [4]. Essa tipologia é útil porque mostra que o avanço do campo já não se limita a melhorar a busca vetorial: há pesquisas voltadas a filtrar contexto, controlar a decodificação, reduzir vulnerabilidade a ruído, lidar com multi-hop reasoning e equilibrar eficiência, grounding e latência [4]. Gan et al., por sua vez, reforçam que a avaliação de um sistema RAG deve considerar tanto os componentes internos quanto o comportamento global do sistema, o que confirma a natureza **sistêmica** da arquitetura [3].

Para o recorte deste TCC, o ponto mais importante é que a arquitetura RAG não pode ser tratada como um simples “chat com documentos”. Em acervos de Obsidian e em repositórios corporativos, a arquitetura precisa resolver pelo menos cinco questões: ingestão de formatos heterogêneos; preservação de estrutura documental; recuperação relevante em português; resposta com evidências explícitas; e atualização incremental do acervo. Isso desloca a discussão para além do LLM em si e torna centrais decisões sobre parsing, chunking, embeddings e armazenamento vetorial [2] [3] [9] [10].

| Dimensão arquitetural | Papel no pipeline RAG | Relevância para Markdown/Obsidian | Relevância para PDFs/documentos corporativos |
| --- | --- | --- | --- |
| Ingestão e parsing | Converter arquivos em unidades textuais tratáveis | Preserva headings, listas, wikilinks e frontmatter | Exige extração confiável de texto, tabelas e seções |
| Chunking | Delimitar unidades de recuperação | Pode respeitar seções e blocos da nota | Pode alinhar chunks a títulos, páginas e tópicos |
| Embeddings | Mapear texto para espaço vetorial | Favorece busca semântica entre notas relacionadas | Favorece recuperação por significado, não só por palavra-chave |
| Vector store | Persistir e consultar vetores com metadados | Viabiliza indexação incremental do vault | Viabiliza filtros por tipo, data, setor e documento |
| Recuperação e reranking | Selecionar contexto relevante | Reduz ruído em notas curtas e fragmentadas | Melhora precisão em documentos longos e redundantes |
| Geração com citação | Produzir resposta fundamentada | Aumenta utilidade do PKM pessoal | É essencial para confiabilidade em uso corporativo |

A partir dessas contribuições, é possível sintetizar o RAG como uma arquitetura em camadas. Em sua forma mais direta, o fluxo inclui **ingestão documental**, **segmentação**, **vetorização**, **indexação**, **recuperação** e **geração condicionada**. Em arquiteturas mais maduras, somam-se componentes de **roteamento por tipo de arquivo**, **recuperação híbrida**, **reranking**, **expansão de contexto**, **avaliação automática**, **mecanismos de segurança** e **módulos de explicabilidade** [2] [3] [4]. Essa leitura é especialmente adequada ao TCC porque o artefato proposto investiga precisamente como decisões de pipeline afetam a qualidade de recuperação e a utilidade do sistema em português brasileiro.

## 2. Vector databases como infraestrutura do RAG

A literatura sobre bancos vetoriais mostra que eles não devem ser entendidos como simples repositórios passivos de embeddings. Jing et al. argumentam que os **vector databases** emergem como resposta a limitações de memória, atualização e factualidade dos LLMs, oferecendo meios eficientes para armazenar, recuperar e gerenciar representações vetoriais de alta dimensionalidade [9]. Em perspectiva semelhante, Ma et al. observam que o crescimento da recuperação semântica em larga escala ultrapassou as capacidades dos SGBDs tradicionais e levou à consolidação de arquiteturas especializadas em vetores, com foco em **armazenamento**, **indexação** e **busca aproximada por vizinhança** [10].

Em sistemas RAG, o banco vetorial é o elo operacional entre a etapa de vetorização e a recuperação contextual. Ele precisa sustentar consultas por similaridade em tempo viável, permitir filtros por metadados, manter persistência e atualização incremental e, idealmente, conviver com estratégias híbridas que combinem busca densa e lexical [9] [10]. Para corpora de notas pessoais e documentos corporativos, essa infraestrutura não é neutra: escolhas ruins de indexação ou metadados reduzem a recuperabilidade do acervo, mesmo quando o modelo de embedding é bom.

A literatura também mostra que a relevância dos bancos vetoriais cresce quando o corpus é heterogêneo. Em um vault de Obsidian, diferentes notas podem variar muito em tamanho, granularidade e densidade semântica; em coleções corporativas, os documentos costumam conter redundância, anexos, texto repetido e seções padronizadas. Nesses cenários, o banco vetorial precisa trabalhar em conjunto com metadados como **arquivo de origem**, **tipo de documento**, **título**, **data**, **tags**, **seção** e, no caso do Obsidian, até mesmo **wikilinks** ou hierarquias lógicas [9] [10].

| Critério técnico | Justificativa em sistemas RAG | Impacto no PKM com Obsidian | Impacto em documentos corporativos |
| --- | --- | --- | --- |
| Busca ANN eficiente | Reduz latência sem perder relevância | Importante para uso interativo no dia a dia | Importante para bases maiores e consultas repetidas |
| Metadados e filtros | Permitem refinar recuperação | Útil para tags, datas e pastas | Útil para setor, tipo documental, vigência e autoria |
| Persistência local | Favorece privacidade e autonomia | Alinha-se a arquitetura local-first | Reduz exposição de dados sensíveis |
| Atualização incremental | Evita reindexações completas | Necessária para vault em constante edição | Necessária para políticas e relatórios atualizados |
| Integração com frameworks | Facilita experimentação e benchmark | Acelera protótipos de PKM | Facilita implantação em pipelines corporativos |

Para o recorte do TCC, essa discussão favorece a adoção de uma visão **arquitetural** do banco vetorial. Mais importante do que a marca do banco é sua adequação ao experimento: persistência local, simplicidade de integração, suporte a metadados e previsibilidade operacional importam mais do que benchmarks genéricos desconectados do corpus-alvo. Em um sistema que precisa responder com citação obrigatória, o banco vetorial também deve facilitar o rastreamento do chunk recuperado, do documento de origem e do caminho da evidência até a resposta final.

## 3. Chunking strategies

A segmentação documental é uma das variáveis mais sensíveis em sistemas RAG. Gan et al. incluem explicitamente **chunking** entre os componentes que devem ser avaliados de modo interno no pipeline, ao lado de retrieval, reranking e embedding generation [3]. Essa observação é importante porque, na prática, o chunking define a unidade básica sobre a qual a recuperação acontece. Se os segmentos forem pequenos demais, o sistema perde contexto; se forem grandes demais, mistura tópicos distintos, aumenta ruído e eleva custo de contexto.

O estudo de Gomez-Cabello et al. oferece evidência empírica relevante ao comparar quatro estratégias: **baseline fixa dependente de tokens**, **adaptive length**, **proposition chunking** e **semantic chunking** [5]. Os autores mostram que estratégias que procuram respeitar fronteiras lógicas ou semânticas tendem a produzir respostas mais precisas e mais relevantes que a segmentação fixa por tamanho. Embora o trabalho esteja ancorado em um domínio clínico, sua implicação é amplamente transferível: o chunking não é um detalhe operacional, mas um componente com forte efeito sobre a qualidade da recuperação e da resposta.

Essa conclusão tem especial peso no caso de notas Markdown e PDFs. Em arquivos Markdown, há estrutura explícita disponível — títulos, subtítulos, listas, checklists, citações, frontmatter e blocos de texto — que pode servir como pista para delimitar chunks mais coerentes. Em PDFs corporativos, a estrutura nem sempre vem limpa, mas continua existindo sob a forma de títulos, subtítulos, seções, cabeçalhos, tabelas e parágrafos. Quando o pipeline ignora essa organização e usa apenas recortes mecânicos por tokens, ele pode quebrar conceitos no meio, misturar seções distintas e comprometer a recuperação.

| Estratégia de chunking | Lógica principal | Vantagens | Limitações | Adequação ao problema do TCC |
| --- | --- | --- | --- | --- |
| Fixo por tokens/palavras | Divide em blocos de tamanho constante | Simples, rápido, reproduzível | Pode cortar ideias e misturar contexto | Útil como baseline experimental |
| Estrutural | Usa headings, seções, listas e blocos | Preserva organização do documento | Depende de parsing adequado | Muito adequado a Markdown e notas do Obsidian |
| Semântico | Agrupa por coerência de significado | Tende a melhorar relevância | Custo maior e maior complexidade | Promissor para notas longas e PDFs densos |
| Adaptativo | Ajusta tamanho conforme o conteúdo | Equilibra contexto e granularidade | Mais difícil de parametrizar | Adequado a corpus heterogêneo |
| Proposition-based | Divide por proposições ou afirmações | Alta precisão em perguntas factuais | Pode fragmentar excesso de contexto | Útil em domínios de alta precisão documental |

Para o TCC, a literatura sugere uma estratégia metodológica clara. Em vez de assumir um único chunk size ideal para todo o corpus, o trabalho deve tratar o chunking como **fator experimental**, comparar baselines simples com alternativas orientadas à estrutura e avaliar o efeito disso em métricas como **MRR**, **Recall@k** e **faithfulness**. Em acervos pessoais e corporativos, é plausível que a melhor solução seja heterogênea: notas curtas podem tolerar chunking mais simples, enquanto notas longas, relatórios e PDFs tendem a se beneficiar de segmentação estrutural ou semântica [3] [5].

Outra implicação importante é que o chunking precisa ser analisado em conjunto com a estratégia de recuperação. Chunks mais longos podem recuperar melhor o contexto global, mas atrapalhar reranking; chunks menores podem favorecer precisão local, mas reduzir capacidade de responder perguntas inferenciais. A revisão, portanto, sustenta a hipótese de que a qualidade do RAG em PKM pessoal não depende só do modelo de embedding, e sim da **interação entre granularidade documental, vetorização e top-k recuperado** [3] [5].

## 4. Embedding models

Os embeddings são o mecanismo que transforma conteúdo textual em vetores comparáveis no espaço semântico. Em sistemas RAG, sua função é central porque a busca densa opera sobre essas representações. Quando o embedding model captura bem similaridade semântica, o sistema encontra trechos relevantes mesmo sem coincidência lexical exata; quando captura mal, a recuperação erra antes mesmo de a geração começar [7] [8]. Por isso, a literatura recente deslocou parte da discussão de “qual LLM usar” para “qual representação vetorial é mais adequada ao idioma, domínio e tipo de documento”.

Wang et al. apresentam a família **multilingual E5**, treinada com pré-treinamento contrastivo em larga escala e posterior fine-tuning supervisionado, com o objetivo de oferecer embeddings abertos competitivos para recuperação semântica multilíngue [8]. Essa contribuição é particularmente importante para o contexto brasileiro, porque corpora de PKM e documentos corporativos frequentemente misturam português, inglês, siglas, nomes próprios, termos técnicos e abreviações. Nesses cenários, modelos multilíngues robustos tendem a oferecer maior estabilidade do que embeddings fortemente centrados apenas em inglês [8].

O estudo de Oro, Granata e Ruffolo reforça esse argumento ao avaliar doze modelos de embedding em tarefas de IR e QA com RAG, mostrando que modelos multilíngues podem competir de forma expressiva com alternativas específicas de idioma, ao mesmo tempo em que evidencia que **tamanho do modelo não prediz desempenho de forma consistente** [7]. Essa conclusão é metodologicamente valiosa para o TCC: a escolha do embedding não deve ser feita por reputação, quantidade de parâmetros ou popularidade em fóruns, mas por **desempenho observado no corpus de interesse**.

A relevância do aspecto linguístico fica ainda mais clara em Ranaldi, Haddow e Birch, que analisam o RAG em cenário multilíngue e mostram que soluções ingênuas baseadas apenas em tradução da consulta podem reduzir cobertura ou gerar recuperação inadequada [6]. Os autores observam que a recuperação multilíngue amplia cobertura, mas pode introduzir inconsistências na etapa de geração, motivo pelo qual propõem estratégias como **CrossRAG** para reduzir a heterogeneidade linguística entre recuperação e geração [6]. Em termos práticos, isso significa que, para um corpus em português brasileiro com possíveis documentos em outros idiomas, a arquitetura deve considerar desde cedo o problema da língua como parte da recuperação, e não como detalhe posterior.

| Critério de escolha do embedding | Justificativa | Implicação para o TCC |
| --- | --- | --- |
| Cobertura multilíngue | Corpus pode conter português, inglês e termos técnicos mistos | Priorizar modelos fortes em recuperação cross-lingual |
| Desempenho em IR | Embedding impacta Recall@k e MRR | Avaliar empiricamente no corpus real |
| Custo e latência | Vetorização e consulta devem ser operacionalmente viáveis | Importante para pipeline local-first |
| Robustez semântica | Notas pessoais costumam ser curtas, ambíguas e fragmentadas | Requer boa sensibilidade semântica |
| Compatibilidade com frameworks | Facilita benchmark e troca de componentes | Favorece experimentação controlada |

Do ponto de vista prático, a revisão sugere que o TCC deve preferir **embeddings multilíngues** como baseline forte e comparar esse baseline com alternativas abertas e, se necessário, proprietárias. O mais importante, porém, é que a avaliação não se limite a medir recuperação bruta. Oro et al. mostram que existem trade-offs entre relevância e groundedness, de modo que embeddings aparentemente bons para ranking podem não maximizar fidelidade da resposta final [7]. Em consequência, o desenho experimental deve integrar métricas de recuperação com métricas de qualidade da resposta fundamentada.

## 5. Ferramentas de desenvolvimento para RAG com Markdown e PDF

A comparação entre **LlamaIndex**, **LangChain** e **Haystack** mostra que as três bibliotecas podem suportar pipelines RAG sobre acervos documentais, mas partem de filosofias distintas. O **LlamaIndex** enfatiza explicitamente a ingestão documental, as transformações e a conversão de documentos em **nodes**, com destaque para o `SimpleDirectoryReader`, os `Node Parsers`, o `Ingestion Pipeline` e a ferramenta oficial `LlamaParse` para parsing de PDFs [11]. Esse desenho torna a biblioteca especialmente atraente quando o problema central é estruturar um corpus documental e transformá-lo em índices consultáveis.

O **LangChain**, por sua vez, organiza o ecossistema em componentes amplamente modulares: document loaders, text splitters, embedding models, vector stores, retrievers e cadeias de execução [12]. Na prática, isso significa mais liberdade para compor soluções específicas, mas também mais decisões de engenharia. O suporte a Markdown é explícito por meio do `UnstructuredMarkdownLoader`, que pode operar em modos como `single` e `elements`, preservando parte da estrutura do arquivo antes das etapas seguintes [13]. Para PDFs, a documentação lista múltiplos loaders e parsers, como PyPDF, PyMuPDF, PDFPlumber e Docling [12].

O **Haystack** adota uma modelagem bastante explícita de pipeline, com componentes separados para **Converters**, **Preprocessors**, **Embedders**, **Retrievers**, **Rankers** e **Writers** [14]. A documentação inclui conversores nativos como `MarkdownToDocument`, `PyPDFToDocument`, `PDFMinerToDocument` e `MultiFileConverter`, além de um tutorial específico mostrando como processar conjuntamente arquivos `.md`, `.pdf` e `.txt` com `FileTypeRouter`, `DocumentJoiner`, `DocumentCleaner`, `DocumentSplitter`, `SentenceTransformersDocumentEmbedder` e `DocumentWriter` [14] [15]. Essa organização é particularmente interessante para pesquisa experimental, porque facilita rastrear e isolar cada etapa do pipeline.

| Critério | LlamaIndex | LangChain | Haystack |
| --- | --- | --- | --- |
| Foco primário | Indexação e consulta sobre conhecimento documental | Orquestração modular de aplicações com LLMs | Pipelines explícitos de NLP/RAG |
| Suporte a Markdown | Forte por ingestão de diretórios e transformação em nodes [11] | Loader específico para Markdown com modos estruturados [13] | `MarkdownToDocument` e roteamento por tipo de arquivo [14] [15] |
| Suporte a PDF | `LlamaParse` como ferramenta oficial de parsing [11] | Vários loaders/parsers integráveis [12] | `PyPDFToDocument`, `PDFMinerToDocument` e outros conversores [14] |
| Modelagem do pipeline | Opinionated, centrada em Documents/Nodes/Indexes [11] | Altamente modular e componível [12] | Pipeline-oriented, com componentes muito explícitos [15] |
| Facilidade de prototipação | Alta para aplicações documentais | Alta, mas com maior montagem manual | Alta para fluxos reprodutíveis e benchmarkáveis |
| Adequação a notas do Obsidian | Boa, sobretudo quando o vault é tratado como corpus documental | Boa, com flexibilidade para loaders e pós-processamento | Boa, especialmente em pipelines heterogêneos com roteamento |
| Adequação a PDFs corporativos | Boa com parsing especializado | Muito boa pela variedade de parsers | Muito boa pela clareza do pipeline de conversão e splitting |

Do ponto de vista metodológico, nenhuma das três bibliotecas é “a melhor” em abstrato. A escolha depende do objetivo do experimento. Se a prioridade for **produtividade em RAG documental**, o LlamaIndex se destaca por aproximar mais diretamente ingestão, parsing e indexação [11]. Se o sistema precisar integrar múltiplas fontes, agentes, ferramentas e componentes heterogêneos, o LangChain oferece maior amplitude de composição [12] [13]. Se o foco estiver em **pipelines reproduzíveis e comparáveis**, sobretudo em um TCC com benchmark, o Haystack apresenta uma clareza estrutural particularmente útil [14] [15].

Para o recorte deste trabalho, a comparação sugere que a decisão deve ser guiada menos por popularidade e mais por alinhamento com o método. Como o TCC pretende avaliar empiricamente o impacto de chunking, recuperação e embeddings, frameworks que tornem essas etapas visíveis, substituíveis e mensuráveis oferecem vantagem analítica. Isso torna Haystack e LangChain especialmente atraentes para experimentação controlada, sem excluir o valor do LlamaIndex como referência importante para ingestão documental e RAG de uso prático.

## 6. Projetos open-source no GitHub integrando Obsidian com RAG ou LLMs

A pesquisa no GitHub revela que o ecossistema de integração entre **Obsidian**, **LLMs** e **RAG** já não é apenas hipotético. Há uma comunidade ativa desenvolvendo plugins e aplicações que transformam vaults em bases consultáveis por busca semântica, chat contextual e recuperação com atribuição de fontes. Embora muitos desses projetos não tenham o rigor experimental de artigos acadêmicos, eles são relevantes para a revisão porque mostram **viabilidade técnica**, **demandas reais de usuários** e **padrões arquiteturais emergentes**.

O projeto **obsidian-smart-connections**, de brianpetro, destaca-se como solução madura de **semantic search** e chat contextual sobre notas, com geração de embeddings locais e ênfase em privacidade [16]. Seu foco principal é conectar notas semanticamente relacionadas e oferecer uma camada de produtividade dentro do próprio Obsidian. Ainda que não represente necessariamente um pipeline RAG clássico completo com backend separado e recuperação híbrida sofisticada, ele evidencia que o problema da descoberta semântica em vaults pessoais é concreto e valorizado pelos usuários.

Já o projeto **obsidian-rag**, de ParthSareen, é mais próximo de um protótipo acadêmico clássico. O repositório se declara **local first**, usa **LangChain**, trabalha diretamente sobre arquivos Markdown e emprega componentes como `ObsidianLoader`, `OllamaEmbeddings`, `ChatOllama` e `Chroma` [17]. Mesmo marcado como não mantido, ele continua sendo um exemplo importante de arquitetura mínima para RAG em Obsidian: carregamento do vault, vetorização, busca por similaridade e geração local.

O projeto **ObsidianRAG**, de Vasallo94, representa um estágio mais avançado de maturidade arquitetural. O README descreve uma solução composta por **plugin nativo do Obsidian**, **backend Python**, **FastAPI**, **LangGraph**, **ChromaDB**, **hybrid search**, **CrossEncoder reranking**, **GraphRAG** com expansão por `[[wikilinks]]`, suporte multilíngue e **source attribution** [18]. Trata-se de um exemplo particularmente útil ao TCC porque combina elementos centrais do problema pesquisado: privacidade, processamento local, explicabilidade, integração com Markdown nativo do Obsidian e exploração da própria topologia de links do vault.

| Projeto | Enfoque principal | Tecnologias/abordagem | Contribuição para o TCC |
| --- | --- | --- | --- |
| `obsidian-smart-connections` [16] | Busca semântica e conexões contextuais entre notas | Embeddings locais, chat e semantic search no próprio plugin | Mostra valor prático da recuperação semântica em PKM |
| `obsidian-rag` [17] | Protótipo local-first de RAG sobre Markdown | LangChain, Ollama, Chroma, ObsidianLoader | Ilustra arquitetura mínima de RAG sobre vault |
| `ObsidianRAG` [18] | Sistema RAG mais completo para Obsidian | Plugin nativo, FastAPI, LangGraph, ChromaDB, reranking, hybrid search, GraphRAG | Aproxima-se fortemente da arquitetura de pesquisa desejada |

A análise conjunta desses projetos sugere uma trajetória de maturidade no ecossistema. O primeiro nível é o da **busca semântica** e recomendação de notas relacionadas; o segundo é o do **RAG local-first mínimo**; o terceiro é o de arquiteturas mais robustas, com backend dedicado, recuperação híbrida, reranking, links estruturais e atribuição explícita de fontes. Essa progressão confirma que o tema do TCC não se resume a uma curiosidade tecnológica: trata-se de um problema real, com crescente demanda em produtividade pessoal e gestão de conhecimento.

Além disso, os projetos open-source reforçam uma conclusão importante da literatura acadêmica: em vaults pessoais, o valor do sistema depende tanto da recuperação quanto da **explicabilidade**. Usuários não querem apenas uma resposta plausível; querem saber **de onde a resposta veio**, quais notas sustentam a conclusão e quão confiável é a associação feita pelo sistema. Essa exigência aproxima o problema de uso pessoal das exigências de ambientes corporativos, em que auditabilidade e rastreabilidade documental são fundamentais [3] [16] [18].

## 7. Síntese crítica para o TCC

A revisão bibliográfica permite sustentar algumas implicações objetivas para o desenho do TCC. Em primeiro lugar, a literatura de surveys mostra que o RAG deve ser tratado como **arquitetura composta**, não como mero acoplamento entre um buscador e um modelo gerador [1] [2] [3] [4]. Isso legitima a estratégia do trabalho de investigar experimentalmente como variações em chunking, embeddings e recuperação afetam a qualidade do sistema em português brasileiro.

Em segundo lugar, a literatura sobre vector databases deixa claro que a recuperação semântica eficiente exige infraestrutura específica para vetores, metadados e atualização incremental [9] [10]. Para um sistema **local-first**, essa conclusão é especialmente útil: mais do que escalar para bilhões de vetores, o TCC precisa de uma base vetorial **reprodutível, persistente, rastreável e simples de operar**. Nesse sentido, a compatibilidade com metadados e a capacidade de reproduzir benchmarks importam mais que promessas genéricas de desempenho em larga escala.

Em terceiro lugar, os estudos sobre chunking indicam que a segmentação deve ser tratada como **variável experimental de primeira ordem** [3] [5]. Em notas do Obsidian, há uma oportunidade de explorar chunking estrutural orientado por headings e blocos lógicos. Em PDFs e documentos corporativos, a segmentação precisa respeitar, sempre que possível, a organização interna do documento. Isso sugere que o TCC pode gerar uma contribuição útil ao mostrar, com dados, em que medida o chunking estrutural supera a segmentação fixa em português.

Em quarto lugar, os trabalhos sobre embeddings e RAG multilíngue indicam que o idioma do corpus não pode ser ignorado [6] [7] [8]. Um acervo pessoal em português brasileiro provavelmente incluirá termos em inglês, nomes próprios, vocabulário técnico e registros informais. Essa mistura favorece o uso de embeddings multilíngues como baseline forte e justifica a comparação entre diferentes famílias de modelos. A avaliação, entretanto, deve observar não apenas relevância na recuperação, mas também fidelidade da resposta e capacidade de sustentar citação.

Por fim, a comparação entre frameworks e os projetos do GitHub sugere uma direção arquitetural plausível para o artefato do TCC: **ingestão heterogênea de Markdown e PDF**, **parsing especializado**, **chunking estrutural ou híbrido**, **embeddings multilíngues**, **vector store local com metadados**, **recuperação híbrida ou reranking**, e **resposta com atribuição explícita de fontes** [11] [12] [14] [15] [18]. Em outras palavras, a literatura apoia diretamente a hipótese de que um sistema local-first pode ser útil sem fine-tuning, desde que o pipeline seja desenhado com atenção às decisões intermediárias.

## Conclusão

A literatura publicada entre 2022 e 2025, complementada por documentação técnica e projetos open-source, mostra que o RAG passou de padrão emergente a **infraestrutura conceitual dominante** para sistemas que exigem respostas contextualizadas e fundamentadas. Em vez de tratar a geração de texto como processo isolado, o campo atual enfatiza a coordenação entre recuperação, representação vetorial, segmentação documental, avaliação e robustez [1] [2] [3] [4].

No contexto específico de **anotações pessoais em Obsidian** e **documentos corporativos**, a revisão aponta que os principais desafios são menos “como usar um LLM” e mais “como construir um pipeline documental confiável”. Isso inclui converter bem arquivos Markdown e PDF, preservar estrutura, escolher embeddings adequados ao idioma, indexar com metadados úteis, recuperar trechos relevantes e devolver respostas com citação verificável [5] [7] [9] [10] [15] [18].

A comparação entre LlamaIndex, LangChain e Haystack mostra que a decisão de framework deve acompanhar o objetivo metodológico do trabalho. Já o exame de projetos open-source do ecossistema Obsidian demonstra que há uma demanda concreta por ferramentas de recuperação semântica e chat contextual sobre vaults pessoais, reforçando a pertinência prática do problema investigado [11] [12] [14] [16] [18].

Assim, esta revisão sustenta a relevância científica e aplicada do TCC. Ela mostra que o problema de pesquisa é atual, tecnicamente justificável e suficientemente delimitado para gerar contribuição útil: identificar, em um corpus local e em português brasileiro, como decisões de **chunking**, **embeddings** e **recuperação** afetam a qualidade de sistemas RAG voltados à gestão de conhecimento pessoal e documental.

## Referências

[1] CHENG, X.; DONG, Z.; SHEN, J.; LIU, Z.; LIU, C.; ZHANG, S.; ARIKAN, B.; ZHANG, Y.; LI, X.; GAO, T.; YAN, Y.; ZHAO, X. **A Survey on Knowledge-Oriented Retrieval-Augmented Generation**. arXiv, 2025. Disponível em: <https://arxiv.org/html/2503.10677v2>. Acesso em: 31 mar. 2026.

[2] GAO, Y.; XIONG, Y.; GAO, X.; JIA, K.; PAN, J.; BI, Y.; DAI, Y.; SUN, J.; GUO, M.; WANG, H. **Retrieval-Augmented Generation for Large Language Models: A Survey**. arXiv, 2024. DOI: <https://doi.org/10.48550/arXiv.2312.10997>. Disponível em: <https://arxiv.org/abs/2312.10997>. Acesso em: 31 mar. 2026.

[3] GAN, A.; YU, H.; ZHANG, K.; YAN, W.; HUANG, Z.; TONG, S.; CHEN, E.; HU, G. **Retrieval Augmented Generation Evaluation in the Era of Large Language Models: A Comprehensive Survey**. arXiv, 2025. Disponível em: <https://arxiv.org/html/2504.14891v1>. Acesso em: 31 mar. 2026.

[4] SHARMA, C. **Retrieval-Augmented Generation: A Comprehensive Survey of Architectures, Enhancements, and Robustness Frontiers**. arXiv, 2025. DOI: <https://doi.org/10.48550/arXiv.2506.00054>. Disponível em: <https://arxiv.org/abs/2506.00054>. Acesso em: 31 mar. 2026.

[5] GOMEZ-CABELLO, C. A.; et al. **Comparative Evaluation of Advanced Chunking for Retrieval-Augmented Generation in Large Language Models for Clinical Decision Support**. *Bioengineering*, 2025. Disponível em: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12649634/>. Acesso em: 31 mar. 2026.

[6] RANALDI, L.; HADDOW, B.; BIRCH, A. **Multilingual Retrieval-Augmented Generation for Knowledge-Intensive Task**. arXiv, 2025. Disponível em: <https://arxiv.org/html/2504.03616v1>. Acesso em: 31 mar. 2026.

[7] ORO, E.; GRANATA, F.; RUFFOLO, M. **A Comprehensive Evaluation of Embedding Models and LLMs for IR and QA Across English and Italian**. *Big Data and Cognitive Computing*, 2025. DOI: <https://doi.org/10.3390/bdcc9050141>. Disponível em: <https://www.mdpi.com/2504-2289/9/5/141>. Acesso em: 31 mar. 2026.

[8] WANG, L.; YANG, N.; HUANG, X.; JIANG, B.; LIN, F.; YANG, S.; ZHOU, H.; ZHOU, Y.; ZHANG, Z.; ZHOU, L. **Multilingual E5 Text Embeddings: A Technical Report**. arXiv, 2024. DOI: <https://doi.org/10.48550/arXiv.2402.05672>. Disponível em: <https://arxiv.org/abs/2402.05672>. Acesso em: 31 mar. 2026.

[9] JING, Z.; SU, Y.; HAN, Y.; YUAN, B.; XU, H.; LIU, C.; CHEN, K.; ZHANG, M. **When Large Language Models Meet Vector Databases: A Survey**. arXiv, 2024. DOI: <https://doi.org/10.48550/arXiv.2402.01763>. Disponível em: <https://arxiv.org/abs/2402.01763>. Acesso em: 31 mar. 2026.

[10] MA, L.; ZHANG, R.; HAN, Y.; YU, S.; WANG, Z.; NING, Z.; ZHANG, J.; XU, P.; LI, P.; QIAO, Z.; JU, W.; CHEN, C.; WANG, D.; LIU, K.; WANG, P.; WANG, P.; FU, Y.; LIU, C.; ZHOU, Y.; LU, C.-T. **A Comprehensive Survey on Vector Database: Storage and Retrieval Technique, Challenge**. arXiv, 2023. DOI: <https://doi.org/10.48550/arXiv.2310.11703>. Disponível em: <https://arxiv.org/abs/2310.11703>. Acesso em: 31 mar. 2026.

[11] LLAMAINDEX. **Loading Data | LlamaIndex OSS Documentation**. 2026. Disponível em: <https://developers.llamaindex.ai/python/framework/module_guides/loading/>. Acesso em: 31 mar. 2026.

[12] LANGCHAIN. **Document loader integrations - Docs by LangChain**. 2026. Disponível em: <https://docs.langchain.com/oss/python/integrations/document_loaders>. Acesso em: 31 mar. 2026.

[13] LANGCHAIN. **UnstructuredMarkdownLoader integration - Docs by LangChain**. 2026. Disponível em: <https://docs.langchain.com/oss/python/integrations/document_loaders/unstructured_markdown>. Acesso em: 31 mar. 2026.

[14] HAYSTACK. **Converters | Haystack Documentation**. 2026. Disponível em: <https://docs.haystack.deepset.ai/docs/converters>. Acesso em: 31 mar. 2026.

[15] HAYSTACK. **Tutorial: Preprocessing Different File Types**. 2026. Disponível em: <https://haystack.deepset.ai/tutorials/30_file_type_preprocessing_index_pipeline>. Acesso em: 31 mar. 2026.

[16] BRIANPETRO. **obsidian-smart-connections: Chat with your notes & see links to related content with AI embeddings**. GitHub, 2026. Disponível em: <https://github.com/brianpetro/obsidian-smart-connections>. Acesso em: 31 mar. 2026.

[17] PARTHSAREEN. **obsidian-rag: Talk to your Obsidian notes!** GitHub, 2026. Disponível em: <https://github.com/ParthSareen/obsidian-rag>. Acesso em: 31 mar. 2026.

[18] VASALLO94. **ObsidianRAG: RAG system to query your Obsidian notes using LangGraph and local LLMs (Ollama)**. GitHub, 2026. Disponível em: <https://github.com/Vasallo94/ObsidianRAG>. Acesso em: 31 mar. 2026.
