# Notas de pesquisa para revisão bibliográfica do TCC sobre RAG

## Contexto do projeto

Com base em `/mnt/desktop/tcc-free-plaud/docs/tcc/texto/TCC.md`, o trabalho investiga um pipeline **local-first** para captura multimodal e recuperação semântica de conhecimento pessoal em português brasileiro, com foco em notas Markdown, banco vetorial local e RAG com citação obrigatória.

## Acesso à pasta do projeto

O diretório `/mnt/desktop/tcc-free-plaud` está acessível no sandbox. Foram identificados os seguintes arquivos relevantes:

- `README.md`
- `docs/arquitetura/Arquitetura.md`
- `docs/arquitetura/Arquitetura_Backend.md`
- `docs/arquitetura/Arquitetura_Frontend.md`
- `docs/Metodologia_Akita_Git.md`
- `docs/tcc/perguntas/Perguntas_a_Serem_Respondidas.md`
- `docs/tcc/perguntas/Perguntas_do_TCC.md`
- `docs/planejamento/Plano_de_Arranque.md`
- `docs/tcc/texto/TCC.md`

## Fonte acadêmica já aberta

### Cheng et al. (2025) — *A Survey on Knowledge-Oriented Retrieval-Augmented Generation*

URL: <https://arxiv.org/html/2503.10677v2>

Principais pontos extraídos da introdução e resumo:

1. **RAG** é apresentado como a integração entre recuperação de informação e modelos generativos, com uso de fontes externas como documentos, bases de dados e dados estruturados.
2. A motivação central é superar limitações de LLMs isolados, especialmente desatualização factual, falta de conhecimento de domínio e dificuldade com entidades raras.
3. O survey estrutura RAG em componentes fundamentais como **mecanismos de recuperação**, **processos de geração** e **integração entre ambos**.
4. O texto destaca desafios recorrentes: **seleção de conhecimento**, **eficiência de recuperação**, **alinhamento entre conteúdo recuperado e objetivo gerativo** e **raciocínio em contexto**.
5. O survey é potencialmente útil como referência panorâmica para a seção de **arquitetura RAG** do TCC.

## Critérios da revisão em andamento

- Janela temporal prioritária: **2022–2025**
- Eixos temáticos: **arquitetura RAG**, **vector databases**, **chunking strategies**, **embedding models**, **ferramentas de desenvolvimento**, **integrações com Obsidian**
- Entregável final: documento Word com **introdução**, **seções por subtópico**, **tabela comparativa das bibliotecas**, e **referências em ABNT**

## Artigo específico sobre chunking

### Gomez-Cabello et al. (2025) — *Comparative Evaluation of Advanced Chunking for Retrieval-Augmented Generation in Large Language Models for Clinical Decision Support*

URL: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12649634/>

Principais achados extraídos do resumo e conteúdo da página:

1. O artigo parte da premissa de que a **qualidade do RAG depende fortemente da segmentação documental antes da indexação**.
2. Foram comparadas quatro estratégias de chunking em pipelines RAG equivalentes: **adaptive length**, **proposition**, **semantic** e uma **baseline fixa dependente de tokens**.
3. O estudo reporta que chunking adaptativo superou a baseline fixa em **acurácia**, **relevância clínica** e métricas de recuperação, incluindo **precision**, **recall** e **F1**.
4. A principal conclusão é que alinhar chunks a **fronteiras lógicas ou semânticas** tende a produzir respostas mais corretas e relevantes do que cortes fixos por tamanho.
5. Embora o estudo esteja situado no domínio clínico, ele é útil ao TCC por oferecer evidência empírica de que **a estratégia de chunking é uma variável experimental crítica** em pipelines RAG.

## Implicações provisórias para o TCC

- Para corpora compostos por **Markdown** e **PDFs**, chunking orientado por estrutura documental e semântica tende a ser mais promissor do que segmentação cega por número de tokens.
- Em acervos pessoais e corporativos, preservar **títulos, seções, listas e contexto local** pode melhorar a recuperação e reduzir respostas alucinatórias.
- A revisão deve tratar chunking como componente de arquitetura, e não como mero detalhe de implementação.

## Survey consolidado sobre arquiteturas RAG

### Gao et al. (2024) — *Retrieval-Augmented Generation for Large Language Models: A Survey*

URL: <https://arxiv.org/abs/2312.10997>
DOI: <https://doi.org/10.48550/arXiv.2312.10997>

Principais pontos extraídos do resumo da página:

1. O survey posiciona o **RAG** como resposta às limitações dos LLMs isolados, especialmente **alucinação**, **desatualização do conhecimento** e **falta de transparência do raciocínio**.
2. Os autores propõem uma taxonomia amplamente citada composta por **Naive RAG**, **Advanced RAG** e **Modular RAG**.
3. O framework é descrito a partir de três componentes centrais: **retrieval**, **generation** e **augmentation**.
4. O survey também destaca a importância de **frameworks de avaliação** e benchmarks para comparar pipelines RAG.
5. Esta referência é particularmente útil para a seção introdutória e para estruturar a seção de **arquitetura RAG** no documento final.

## Síntese provisória da arquitetura RAG para o TCC

A literatura recente converge na ideia de que um pipeline RAG pode ser compreendido como uma arquitetura em camadas. Em sua forma básica, o processo envolve: ingestão documental, segmentação em chunks, vetorização por embeddings, indexação em banco vetorial, recuperação por similaridade e geração condicionada ao contexto recuperado. Surveys recentes indicam que a sofisticação do sistema aumenta quando se adicionam mecanismos como re-ranking, multi-hop retrieval, recuperação híbrida, memória, avaliação automática e modularização do pipeline.

## Estudo recente sobre embeddings multilíngues e QA com RAG

### Oro, Granata e Ruffolo (2025) — *A Comprehensive Evaluation of Embedding Models and LLMs for IR and QA Across English and Italian*

URL: <https://www.mdpi.com/2504-2289/9/5/141>
DOI: <https://doi.org/10.3390/bdcc9050141>

Principais achados extraídos do resumo:

1. O estudo avalia **12 modelos de embedding** e **4 LLMs** em tarefas de recuperação da informação e question answering com pipeline **RAG**.
2. Os resultados mostram que **modelos multilíngues** competem fortemente com modelos específicos de idioma, o que é particularmente relevante para o recorte do TCC em **português brasileiro**.
3. O artigo reporta alto desempenho do **embed-multilingual-v3.0**, com nDCG@10 de **0,90 em inglês** e **0,86 em italiano**.
4. Os autores identificam um trade-off importante entre **relevância da resposta** e **groundedness/factual grounding**, mesmo quando há recuperação externa.
5. Uma conclusão importante é que **o tamanho do modelo não prediz consistentemente o desempenho**, reforçando a necessidade de avaliação empírica no contexto do corpus-alvo.

## Implicações provisórias para o TCC

- Para um corpus em português com notas pessoais e documentos corporativos, faz sentido priorizar **embeddings multilíngues** ou comprovadamente fortes em cenários cross-lingual.
- A avaliação do TCC deve considerar não apenas métricas de recuperação, como **MRR** e **Recall@k**, mas também medidas associadas a **fidelidade** e **fundamentação** da resposta.
- A escolha do embedding model não deve se apoiar somente em popularidade ou tamanho, mas em **desempenho observado no domínio e no idioma de interesse**.

## RAG multilíngue e embeddings para corpora não ingleses

### Ranaldi, Haddow e Birch (2025) — *Multilingual Retrieval-Augmented Generation for Knowledge-Intensive Task*

URL: <https://arxiv.org/html/2504.03616v1>

Principais achados extraídos do resumo e introdução:

1. O paper investiga o desempenho de RAG em múltiplos idiomas, problema ainda menos explorado que o cenário monolíngue em inglês.
2. Os autores comparam estratégias como **tRAG** (tradução da pergunta para inglês antes da recuperação), **MultiRAG** (recuperação multilíngue direta) e **CrossRAG** (tradução dos documentos recuperados para um idioma comum antes da geração).
3. Os resultados indicam que abordagens ingênuas baseadas apenas em tradução de consulta podem reduzir cobertura ou induzir recuperação incorreta.
4. A recuperação multilíngue amplia cobertura, mas pode introduzir inconsistências quando o modelo precisa integrar evidências em idiomas distintos.
5. A proposta **CrossRAG** melhora o desempenho ao reduzir a heterogeneidade linguística na etapa de geração.

### Wang et al. (2024) — *Multilingual E5 Text Embeddings: A Technical Report*

URL: <https://arxiv.org/abs/2402.05672>
DOI: <https://doi.org/10.48550/arXiv.2402.05672>

Principais achados extraídos do resumo da página:

1. O relatório apresenta a família **multilingual E5**, com variantes **small**, **base** e **large**, buscando equilíbrio entre custo de inferência e qualidade vetorial.
2. O treinamento combina **pré-treinamento contrastivo em 1 bilhão de pares multilíngues** e posterior fine-tuning supervisionado.
3. O trabalho enfatiza o objetivo de fornecer embeddings abertos competitivos para recuperação semântica em múltiplos idiomas.
4. A referência é especialmente relevante ao TCC porque o modelo **multilingual-e5-large** já aparece no escopo experimental previsto do projeto.

## Síntese provisória sobre embeddings para o TCC

A literatura mais recente sugere que, para RAG em idiomas além do inglês, a seleção do embedding model é parte central da arquitetura. Modelos multilíngues robustos, como a família E5 e variantes modernas similares, tendem a oferecer uma base mais segura para corpora heterogêneos. No entanto, a escolha final deve considerar o tipo de documento, o idioma predominante, a latência e o comportamento do modelo no domínio específico do corpus.

## Survey sobre bancos vetoriais e integração com LLMs

### Jing et al. (2024/2025) — *When Large Language Models Meet Vector Databases: A Survey*

URL: <https://arxiv.org/abs/2402.01763>
DOI: <https://doi.org/10.48550/arXiv.2402.01763>

Principais pontos extraídos do resumo da página:

1. O survey examina a integração entre **LLMs** e **vector databases (VecDBs)** como resposta a problemas como **alucinação**, **conhecimento desatualizado**, **custos elevados de aplicação** e **limitações de memória**.
2. Os bancos vetoriais são apresentados como infraestrutura para **armazenar, recuperar e gerenciar representações vetoriais de alta dimensionalidade**, fundamentais para operações de recuperação semântica.
3. A contribuição do survey é especialmente útil para o TCC porque conecta a teoria de bancos vetoriais ao uso prático em pipelines **RAG**, em vez de tratar o banco vetorial apenas como componente de armazenamento.
4. A referência reforça que a arquitetura RAG depende não só do modelo gerador, mas também da eficiência de indexação, busca aproximada por vizinhança e gestão do acervo vetorial.

## Síntese provisória sobre vector databases para o TCC

Na literatura recente, os bancos vetoriais aparecem como a base operacional da recuperação densa em sistemas RAG. Seu papel inclui persistir embeddings, permitir busca por similaridade em tempo viável e suportar atualização incremental do acervo. Em aplicações com notas Markdown e documentos PDF, a escolha de um banco vetorial deve considerar suporte a metadados, filtros, persistência local, simplicidade de integração e custo computacional — fatores especialmente relevantes em arquiteturas **local-first** como a proposta do TCC.

## Survey recente sobre avaliação de sistemas RAG

### Gan et al. (2025) — *Retrieval Augmented Generation Evaluation in the Era of Large Language Models: A Comprehensive Survey*

URL: <https://arxiv.org/html/2504.14891v1>

Principais achados extraídos do resumo e introdução:

1. O survey argumenta que avaliar RAG é desafiador porque o sistema combina **componentes de recuperação e geração**, além de depender de **fontes de conhecimento dinâmicas**.
2. Os autores propõem distinguir entre **avaliação interna** e **avaliação externa**.
3. A avaliação interna cobre componentes e métricas ligadas ao pipeline, incluindo **preprocessing**, **retrieval denso ou esparso**, **reranking**, **pruning**, **chunking** e **embedding generation**.
4. A avaliação externa amplia o foco para **segurança**, **eficiência**, **praticidade** e comportamento global do sistema.
5. O survey reforça que o desempenho de um sistema RAG depende não apenas de cada módulo isolado, mas também das **interações entre os componentes**.

## Implicações provisórias para o TCC

- O capítulo de revisão pode relacionar diretamente a literatura de **chunking**, **embeddings** e **retrieval** às métricas previstas no TCC, como **MRR**, **Recall@k**, **faithfulness** e taxa de resposta sem base adequada.
- A discussão metodológica deve explicitar que experimentos com RAG precisam avaliar tanto **qualidade da recuperação** quanto **qualidade da geração fundamentada**.
- Para o contexto de notas pessoais, Obsidian e documentos corporativos, também faz sentido discutir dimensões práticas como **latência**, **rastreabilidade das fontes** e **facilidade de atualização do índice vetorial**.

## Comparação de bibliotecas para RAG com Markdown e PDF

### LlamaIndex — documentação oficial de loading

Fonte: <https://developers.llamaindex.ai/python/framework/module_guides/loading/>

Achados iniciais:

1. O **LlamaIndex** estrutura a ingestão de dados em duas etapas centrais: **loading** e **transformations**.
2. A biblioteca oferece o **SimpleDirectoryReader** como loader nativo para múltiplos tipos de arquivo em diretórios locais, o que é útil para acervos com notas Markdown e documentos exportados para pastas.
3. Para PDFs, a documentação destaca o **LlamaParse** como ferramenta oficial de parsing, indicando uma abordagem mais especializada para documentos complexos.
4. O ecossistema também inclui **Node Parsers** e **Ingestion Pipeline**, o que sugere boa maturidade para pipelines repetíveis de indexação e segmentação.
5. Em termos de posicionamento arquitetural, o LlamaIndex parece enfatizar fortemente o fluxo **documento -> transformação -> node -> índice**, o que é particularmente conveniente para cenários de RAG documental.

### LangChain — documentação oficial de document loaders

Fonte: <https://docs.langchain.com/oss/python/integrations/document_loaders>

Achados iniciais:

1. O **LangChain** define document loaders como uma **interface padronizada** para leitura de dados de diferentes fontes para o formato `Document`.
2. A documentação enfatiza a uniformidade da API por meio de métodos como **`load()`** e **`lazy_load()`**, o que favorece flexibilidade e processamento incremental.
3. O catálogo de integrações mostra ampla variedade de loaders para **PDFs** e outras fontes documentais, incluindo PyPDF, PyMuPDF, PDFPlumber, Amazon Textract e Docling.
4. A arquitetura da documentação sugere um ecossistema muito amplo e modular, com loaders, text splitters, embedding models, vector stores e retrievers como peças independentes.
5. Para uso com Markdown e PDF, o LangChain parece oferecer grande flexibilidade, porém potencialmente com maior necessidade de composição manual do pipeline em comparação com bibliotecas mais opinionated.

## Critérios comparativos provisórios

Os critérios que serão usados na tabela comparativa final incluem: foco primário da biblioteca, loaders para Markdown/PDF, parsing estruturado, pipeline de ingestão, estratégia de chunking, integração com vector stores, facilidade de prototipação, adequação a acervos do Obsidian e adequação a documentos corporativos.

### Haystack — documentação oficial de converters

Fonte: <https://docs.haystack.deepset.ai/docs/converters>

Achados iniciais:

1. O **Haystack** apresenta um conjunto explícito de **Converters** para transformar diferentes formatos em um formato documental unificado.
2. Para o escopo do TCC, destacam-se componentes nativos como **MarkdownToDocument**, **PyPDFToDocument**, **PDFMinerToDocument** e **MultiFileConverter**.
3. A documentação também evidencia suporte a pipelines mais estruturados, com componentes especializados para **Converters**, **Preprocessors**, **Embedders**, **Retrievers**, **Rankers** e **Writers**.
4. Em comparação preliminar com LlamaIndex e LangChain, o Haystack parece adotar uma abordagem bastante **pipeline-oriented**, com blocos explicitamente componíveis.
5. Um diferencial relevante é a presença de conversores que já geram ou preservam saídas em **Markdown GitHub Flavored**, o que pode ser especialmente útil para fluxos envolvendo Obsidian e documentação corporativa.

## Leitura comparativa provisória

- **LlamaIndex** parece mais orientado ao problema de indexação e consulta sobre conhecimento documental, com forte ênfase em ingestão, nodes e índices.
- **LangChain** oferece maior amplitude de integrações e modularidade, sendo vantajoso quando o sistema combina múltiplas fontes, agentes e componentes heterogêneos.
- **Haystack** se destaca por uma modelagem de pipeline muito explícita, com bons componentes de conversão e pré-processamento documental, o que é favorável para pipelines reproduzíveis de ingestão de PDFs e Markdown.

### LangChain — suporte específico a Markdown

Fonte: <https://docs.langchain.com/oss/python/integrations/document_loaders/unstructured_markdown>

Achados adicionais:

1. O **LangChain** oferece o `UnstructuredMarkdownLoader` para leitura de arquivos Markdown.
2. O loader pode operar em modo **`single`**, retornando um único `Document`, ou em modo **`elements`**, no qual o conteúdo é separado em elementos estruturais como `Title` e `NarrativeText`.
3. Essa capacidade é relevante para acervos do **Obsidian**, pois permite preservar parte da estrutura semântica do Markdown antes do chunking posterior.
4. O suporte a `lazy_load()` também favorece indexação incremental e processamento de coleções maiores de notas.
5. Em contrapartida, a dependência do ecossistema `unstructured` pode aumentar a complexidade de instalação e o número de decisões de engenharia necessárias.

### Haystack — tutorial oficial para Markdown e PDF no mesmo pipeline

Fonte: <https://haystack.deepset.ai/tutorials/30_file_type_preprocessing_index_pipeline>

Achados adicionais:

1. O tutorial oficial mostra explicitamente um pipeline de indexação para **`.md`**, **`.pdf`** e **`.txt`** no mesmo fluxo.
2. O uso de **`FileTypeRouter`** permite encaminhar cada tipo de arquivo para seu conversor correspondente, como `MarkdownToDocument` e `PyPDFToDocument`.
3. Após a conversão, o pipeline segue com `DocumentJoiner`, `DocumentCleaner`, `DocumentSplitter`, `SentenceTransformersDocumentEmbedder` e `DocumentWriter`.
4. O exemplo oficial usa **chunking por palavras** com `split_length=150` e `split_overlap=50`, evidenciando uma arquitetura bastante explícita e reprodutível.
5. Para o TCC, esse tutorial é particularmente útil porque demonstra um fluxo muito próximo do problema estudado: ingestão heterogênea de notas e documentos, limpeza, segmentação, embeddings e escrita em document store.

## Refinamento da comparação técnica

- **LlamaIndex** tende a favorecer produtividade em aplicações centradas em conhecimento documental, com forte integração entre ingestão, parsing e indexação.
- **LangChain** oferece excelente modularidade e amplo ecossistema, incluindo suporte estruturado a Markdown e numerosos loaders para PDF, mas pode exigir maior montagem manual da solução.
- **Haystack** apresenta a arquitetura de pipeline mais explícita entre as três, com componentes muito claros para roteamento por tipo de arquivo, conversão, limpeza, splitting, embedding e escrita.

## Projetos open-source no GitHub: Obsidian + RAG/LLMs

### brianpetro/obsidian-smart-connections

Fonte: <https://github.com/brianpetro/obsidian-smart-connections>

Achados principais:

1. O projeto oferece **chat com notas** e descoberta de conteúdo relacionado por meio de **embeddings** dentro do próprio Obsidian.
2. O README destaca o uso de **embeddings locais** por padrão, reforçando uma proposta de privacidade e processamento no dispositivo do usuário.
3. O plugin enfatiza **semantic search** e sugestões contextuais de notas relacionadas, o que o aproxima de um mecanismo de recuperação semântica para bases Markdown pessoais.
4. O projeto também suporta modelos locais e modelos via API, o que o torna flexível, embora nem todo o fluxo descrito corresponda a um pipeline RAG clássico com backend separado.
5. Para o TCC, o principal valor está em mostrar que há demanda real por **busca semântica e chat contextual sobre vaults do Obsidian**, mesmo quando a solução é apresentada mais como plugin de produtividade do que como sistema acadêmico de RAG.

### ParthSareen/obsidian-rag

Fonte: <https://github.com/ParthSareen/obsidian-rag>

Achados principais:

1. O projeto se descreve explicitamente como **local first** e voltado a executar **RAG sobre arquivos Markdown** do Obsidian.
2. A implementação usa **LangChain**, com componentes como `ObsidianLoader`, `OllamaEmbeddings`, `ChatOllama` e `Chroma`.
3. O fluxo central inclui carregar arquivos Markdown de um diretório, vetorizá-los e executar **similarity search** sobre os vetores.
4. O projeto está marcado como **não mantido**, o que reduz seu valor como base tecnológica atual, mas não elimina sua utilidade como evidência histórica de uma linha de solução já explorada pela comunidade.
5. Para a revisão bibliográfica aplicada, ele é um bom exemplo de arquitetura mínima para vaults do Obsidian baseada em **Markdown + embeddings + vector store + geração local**.

### Vasallo94/ObsidianRAG

Fonte: <https://github.com/Vasallo94/ObsidianRAG>

Achados principais:

1. O projeto propõe um sistema RAG para consultar notas do Obsidian com **LangGraph** e **LLMs locais via Ollama**.
2. O README destaca uma arquitetura mais sofisticada do que a de protótipos mínimos, incluindo **plugin nativo do Obsidian**, **backend Python**, **FastAPI**, **LangGraph**, **ChromaDB** e **reranking**.
3. Entre os diferenciais aparecem **hybrid search** (vetorial + BM25), **CrossEncoder reranking**, **GraphRAG** com expansão por `[[wikilinks]]`, suporte multilíngue e **source attribution**.
4. O projeto é especialmente relevante ao TCC porque combina elementos alinhados ao problema de pesquisa: privacidade, processamento local, Markdown nativo do Obsidian, rastreabilidade das fontes e enriquecimento por estrutura de links.
5. Ele oferece uma referência prática importante para discutir como um sistema de RAG sobre notas pessoais pode evoluir de busca semântica simples para uma arquitetura mais robusta, com recuperação híbrida, expansão de contexto e apresentação explícita das fontes.

## Síntese provisória sobre o ecossistema Obsidian + RAG

Os projetos encontrados sugerem três níveis de maturidade no ecossistema. No nível mais simples, aparecem soluções de **busca semântica** e recomendação de notas relacionadas. Em um nível intermediário, surgem protótipos de **RAG local-first** com LangChain, embeddings e armazenamento vetorial. No nível mais avançado, observam-se arquiteturas com **plugin nativo**, **backend dedicado**, **recuperação híbrida**, **reranking**, **GraphRAG** e **atribuição de fontes**. Essa progressão é útil para o TCC porque mostra que o problema possui relevância prática e que as decisões arquiteturais podem ser justificadas com base em soluções reais já adotadas pela comunidade.
