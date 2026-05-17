# Requisitos funcionais e requisitos de negócio do projeto `tcc-free-plaud`

## Objetivo deste documento

Este documento organiza, em formato de requisitos, as necessidades identificadas na documentação do projeto `tcc-free-plaud`. O foco está em duas frentes. A primeira reúne os **requisitos funcionais**, isto é, aquilo que o sistema precisa fazer na parte de código, interface, processamento e persistência. A segunda reúne os **requisitos de negócio**, ou seja, as regras, objetivos e restrições que justificam por que o sistema deve existir e como ele deve ser orientado enquanto artefato de TCC e produto experimental [1] [2] [3] [4] [5] [6] [7].

## 1. Visão geral do sistema

O projeto propõe um sistema **local-first** para captura multimodal, estruturação automática em Markdown e recuperação semântica de conhecimento pessoal em português brasileiro. O sistema deve receber entradas como texto, PDF, áudio e imagem, transformá-las em notas estruturadas, indexá-las em banco vetorial local e permitir consultas em linguagem natural por meio de RAG com citação obrigatória [1] [2] [3].

| Aspecto | Síntese |
| --- | --- |
| Domínio | Captura e recuperação de conhecimento pessoal |
| Paradigma | Local-first com BYOK |
| Entradas previstas | Texto, Markdown, PDF, áudio e imagem |
| Saídas principais | Nota Markdown, índice vetorial, resposta com citação, resultados de benchmark |
| Núcleo científico | Avaliação empírica de chunking, recuperação e embeddings |

## 2. Requisitos funcionais

Os requisitos funcionais abaixo descrevem comportamentos esperados do software. Eles foram escritos em formato objetivo, pensando tanto em documentação de produto quanto em futura implementação.

### 2.1 Requisitos funcionais de entrada e ingestão

| ID | Requisito funcional | Prioridade |
| --- | --- | --- |
| RF-01 | O software deve permitir a entrada de conteúdo por meio de arquivos de texto (`.txt`), Markdown (`.md`) e PDF (`.pdf`) [1] [3] [4]. | Alta |
| RF-02 | O software deve suportar, em fases posteriores, a entrada de arquivos de áudio e imagem para processamento multimodal [1] [2] [3] [4]. | Alta |
| RF-03 | O software deve possuir um mecanismo para descobrir arquivos de entrada em pasta monitorada ou origem configurada pelo usuário [3] [5]. | Alta |
| RF-04 | O software deve validar o tipo e o formato do arquivo antes de iniciar o processamento [3]. | Alta |
| RF-05 | O software deve decidir automaticamente qual pipeline aplicar conforme o tipo de arquivo recebido [3]. | Alta |
| RF-06 | O software deve extrair o conteúdo bruto do arquivo de entrada para posterior estruturação [3]. | Alta |
| RF-07 | O software deve registrar falhas de ingestão e permitir reprocessamento de itens com erro [5]. | Média |

### 2.2 Requisitos funcionais de processamento e estruturação

| ID | Requisito funcional | Prioridade |
| --- | --- | --- |
| RF-08 | O software deve transformar o conteúdo extraído em uma nota Markdown estruturada e consistente [1] [2] [3]. | Alta |
| RF-09 | O software deve aplicar um schema padronizado para a nota gerada, incluindo metadados mínimos do conteúdo processado [3]. | Alta |
| RF-10 | O software deve gerar frontmatter e corpo textual estruturado na nota Markdown final [3]. | Alta |
| RF-11 | O software deve armazenar o texto bruto separadamente da nota estruturada, sem misturar os dois conteúdos no mesmo campo lógico [3]. | Alta |
| RF-12 | O software deve registrar metadados como tipo de fonte, caminho de origem, título, resumo, tópicos, tarefas, tags, provedor e modelo utilizados no processamento [3]. | Média |
| RF-13 | O software deve permitir futura adaptação do processo de estruturação para diferentes provedores de IA, sem acoplamento rígido a um único fornecedor [2] [3]. | Alta |

### 2.3 Requisitos funcionais de indexação e recuperação

| ID | Requisito funcional | Prioridade |
| --- | --- | --- |
| RF-14 | O software deve realizar segmentação do conteúdo em chunks para fins de recuperação semântica [1] [2] [3]. | Alta |
| RF-15 | O software deve permitir configuração dos parâmetros de chunking, incluindo tamanho do chunk e overlap [1] [2] [3]. | Alta |
| RF-16 | O software deve gerar embeddings para os chunks estruturados [1] [2] [3]. | Alta |
| RF-17 | O software deve indexar os embeddings em banco vetorial local [1] [2] [3]. | Alta |
| RF-18 | O software deve usar ChromaDB como baseline inicial de persistência vetorial [1] [3]. | Alta |
| RF-19 | O software deve manter vínculo rastreável entre chunk, nota de origem e experimento relacionado [3]. | Alta |
| RF-20 | O software deve recuperar chunks relevantes a partir de uma consulta em linguagem natural [1] [2] [3]. | Alta |
| RF-21 | O software deve permitir ajuste do parâmetro `top-k` na recuperação [1] [2] [3]. | Alta |
| RF-22 | O software deve aplicar thresholds configuráveis para controle da recuperação e das respostas [1] [3] [5]. | Média |

### 2.4 Requisitos funcionais de resposta e AutoRAG

| ID | Requisito funcional | Prioridade |
| --- | --- | --- |
| RF-23 | O software deve permitir ao usuário fazer perguntas em linguagem natural sobre o acervo processado [1] [2] [5]. | Alta |
| RF-24 | O software deve gerar respostas baseadas no conteúdo recuperado do acervo, utilizando RAG [1] [2] [3]. | Alta |
| RF-25 | O software deve exibir citações obrigatórias na resposta gerada [1] [2] [3] [5]. | Alta |
| RF-26 | O software deve permitir inspeção dos chunks recuperados que sustentaram a resposta [5]. | Média |
| RF-27 | O software deve indicar ausência de base suficiente quando não houver evidência adequada para responder [2] [6]. | Alta |
| RF-28 | O software deve registrar qual modelo e qual configuração participaram da geração da resposta [3]. | Média |

### 2.5 Requisitos funcionais de benchmark e avaliação experimental

| ID | Requisito funcional | Prioridade |
| --- | --- | --- |
| RF-29 | O software deve permitir execução de benchmarks independentes da interface gráfica [1] [3]. | Alta |
| RF-30 | O software deve aceitar datasets de avaliação compostos por pares pergunta/resposta e configurações experimentais [1] [2] [3]. | Alta |
| RF-31 | O software deve comparar diferentes configurações de chunking, recuperação e embeddings [1] [2] [3] [6]. | Alta |
| RF-32 | O software deve calcular métricas como MRR, Recall@3, Recall@5, Recall@10 e latência [1] [2] [3]. | Alta |
| RF-33 | O software deve possibilitar exportação de resultados experimentais em arquivos e tabelas reaproveitáveis [1] [3] [5]. | Alta |
| RF-34 | O software deve registrar cada execução experimental com identificador, parâmetros e métricas associadas [3]. | Alta |

### 2.6 Requisitos funcionais de configuração e provedores

| ID | Requisito funcional | Prioridade |
| --- | --- | --- |
| RF-35 | O software deve possuir uma camada de configuração para definir pasta de entrada, pasta de saída, provedor, modelo, embedding e thresholds [1] [3] [5]. | Alta |
| RF-36 | O software deve operar no modelo BYOK, utilizando credenciais fornecidas pelo próprio usuário [1] [2]. | Alta |
| RF-37 | O software deve encapsular chamadas externas em adaptadores específicos para transcrição, visão, estruturação, embeddings e resposta [3]. | Alta |
| RF-38 | O software deve permitir troca futura entre provedores sem necessidade de reescrever o restante do sistema [1] [2] [3]. | Alta |

### 2.7 Requisitos funcionais de persistência, logs e rastreabilidade

| ID | Requisito funcional | Prioridade |
| --- | --- | --- |
| RF-39 | O software deve persistir metadados, logs de processamento e execuções de benchmark em SQLite [1] [3]. | Alta |
| RF-40 | O software deve persistir o índice vetorial localmente [1] [2] [3]. | Alta |
| RF-41 | O software deve registrar tempo por etapa de processamento sempre que possível [2] [5]. | Média |
| RF-42 | O software deve permitir rastrear a origem da informação usada em cada resposta [1] [2] [3]. | Alta |
| RF-43 | O software deve armazenar resultados experimentais de forma reproduzível e passível de inspeção posterior [1] [2] [3]. | Alta |

### 2.8 Requisitos funcionais de interface e operação

| ID | Requisito funcional | Prioridade |
| --- | --- | --- |
| RF-44 | O software deve oferecer, em estágio inicial, operação via CLI e scripts locais [1] [3] [5]. | Alta |
| RF-45 | O software deve evoluir para um dashboard web local após existir backend mínimo funcional [1] [2] [5]. | Média |
| RF-46 | O software deve possuir uma tela ou área de dashboard com resumo do sistema, incluindo pasta monitorada, fila, últimos processamentos, status do vetor e status das configurações [5]. | Média |
| RF-47 | O software deve possuir uma tela ou área para visualização da fila de processamento, erros, reprocessamento e tempo por etapa [5]. | Média |
| RF-48 | O software deve possuir uma tela ou área para visualização de notas geradas, Markdown bruto e metadados associados [5]. | Média |
| RF-49 | O software deve possuir uma tela ou área de chat para consulta ao acervo com exibição da resposta e das citações [5]. | Média |
| RF-50 | O software deve possuir uma tela ou área de benchmark para configurar experimentos, rodar lotes, comparar métricas e exportar resultados [5]. | Média |
| RF-51 | O software deve possuir uma tela ou área de configurações para gerenciamento dos parâmetros operacionais do sistema [5]. | Média |

### 2.9 Requisitos funcionais de qualidade e testes

| ID | Requisito funcional | Prioridade |
| --- | --- | --- |
| RF-52 | O software deve possuir testes automatizados para parsing de texto e PDF [3]. | Alta |
| RF-53 | O software deve possuir testes automatizados para validação do schema da nota [3]. | Alta |
| RF-54 | O software deve possuir testes automatizados para chunking [3]. | Alta |
| RF-55 | O software deve possuir testes automatizados para indexação e recuperação [3]. | Alta |
| RF-56 | O software deve possuir testes automatizados para resposta com citação obrigatória [3]. | Alta |
| RF-57 | O software deve possuir testes automatizados para o runner de benchmark [3]. | Alta |

## 3. Requisitos de negócio

Os requisitos de negócio expressam a finalidade maior do projeto, o valor que ele deve entregar e as restrições estratégicas que não podem ser perdidas ao longo da implementação.

### 3.1 Requisitos de negócio centrais

| ID | Requisito de negócio | Justificativa |
| --- | --- | --- |
| RN-01 | O projeto deve reduzir a fricção entre capturar informação e recuperar conhecimento posteriormente [1] [2] [6]. | Esta é a dor central identificada no problema do TCC. |
| RN-02 | O projeto deve apoiar usuários que trabalham com conhecimento pessoal e profissional em português brasileiro [1] [2]. | O recorte linguístico e de uso faz parte da contribuição do trabalho. |
| RN-03 | O projeto deve priorizar recuperação confiável e fundamentada, e não apenas geração textual plausível [1] [2] [6]. | O valor do sistema depende de confiança, explicabilidade e citação. |
| RN-04 | O projeto deve gerar um artefato que seja útil como software e válido como experimento de TCC [1] [2] [3] [4]. | O sistema não é só produto; também é instrumento de investigação. |
| RN-05 | O projeto deve permitir comparação empírica entre configurações técnicas em vez de depender de escolhas arbitrárias [1] [2] [6]. | A contribuição científica está na avaliação controlada. |

### 3.2 Requisitos de negócio ligados ao escopo do TCC

| ID | Requisito de negócio | Justificativa |
| --- | --- | --- |
| RN-06 | O núcleo do projeto deve ser o pipeline experimental, e não a casca desktop ou o refinamento visual [1] [2] [4] [5]. | A prioridade científica está no backend, recuperação e benchmark. |
| RN-07 | O projeto deve demonstrar ao menos uma fatia funcional completa do fluxo: ingestão, nota estruturada, indexação e resposta com citação [1] [3]. | Este é o marco mínimo para sair da fase conceitual. |
| RN-08 | O projeto deve produzir benchmark executável com resultados comparáveis [1] [2] [3]. | Sem benchmark, a parte científica fica enfraquecida. |
| RN-09 | O projeto deve manter coerência entre problema, método, arquitetura e conclusões [2]. | Isso é condição de sucesso explícita do TCC. |
| RN-10 | O projeto deve documentar limitações de forma honesta, como tamanho de dataset, viés e assimetria entre modalidades [2] [6]. | A defesa acadêmica depende dessa transparência. |

### 3.3 Requisitos de negócio ligados à arquitetura e operação

| ID | Requisito de negócio | Justificativa |
| --- | --- | --- |
| RN-11 | O sistema deve operar com persistência local de notas, configurações e índice vetorial [1] [2] [4]. | Isso materializa a proposta local-first. |
| RN-12 | O sistema deve evitar acoplamento rígido a um único provedor de IA [1] [2] [3]. | Isso reduz risco técnico e aumenta longevidade do projeto. |
| RN-13 | O sistema deve usar chaves do próprio usuário em vez de depender de infraestrutura central de credenciais [1] [2]. | Isso está alinhado ao modelo BYOK e ao escopo atual. |
| RN-14 | O sistema deve ser reproduzível o suficiente para permitir avaliação e demonstração perante orientador e banca [2] [5] [6]. | O projeto precisa ser demonstrável e analisável. |
| RN-15 | O sistema deve ser implementado em etapas, com prioridade para o core textual antes da multimodalidade completa, interface rica e shell desktop [1] [3] [4] [5]. | A ordem de implementação existe para reduzir dispersão e risco. |

### 3.4 Requisitos de negócio ligados ao valor prático

| ID | Requisito de negócio | Justificativa |
| --- | --- | --- |
| RN-16 | O sistema deve servir a cenários reais de reaproveitamento de notas, documentos e registros pessoais [1] [2] [6]. | A proposta precisa ser mais do que uma prova artificial de laboratório. |
| RN-17 | O sistema deve permitir respostas com rastreabilidade suficiente para aumentar a confiança do usuário [1] [2] [6]. | Sem rastreabilidade, o valor prático do sistema cai. |
| RN-18 | O sistema deve apoiar evolução futura para áudio, imagem, interface local e shell desktop sem comprometer o núcleo experimental [1] [3] [4] [5]. | O crescimento do produto não pode destruir o foco do TCC. |

## 4. Regras de prioridade para implementação

A documentação do projeto sugere uma hierarquia bastante clara de prioridade. O primeiro bloco é obrigatório para o TCC mínimo viável; o segundo fortalece a avaliação; e o terceiro melhora a apresentação e o produto, mas não deve consumir o tempo principal do trabalho [1] [3] [4] [5].

| Nível | O que entra | Prioridade |
| --- | --- | --- |
| Núcleo obrigatório | Ingestão textual/PDF, nota Markdown, chunking, embeddings, indexação, pergunta com citação, benchmark básico | Máxima |
| Extensão importante | Áudio, imagem, métricas mais amplas, visualização de chunks, página de benchmark | Alta |
| Extensão secundária | Polimento visual, Tauri completo, refinamentos amplos de UX | Média/Baixa |

## 5. Síntese final

A leitura do projeto mostra que ele já possui uma base muito clara para derivar requisitos. Em termos funcionais, o sistema precisa **receber conteúdo**, **processá-lo**, **estruturá-lo como nota**, **indexá-lo semanticamente**, **responder perguntas com citação** e **medir desempenho experimental** [1] [2] [3] [5]. Em termos de negócio, o projeto precisa permanecer fiel a cinco ideias centrais: **reduzir fricção**, **operar local-first**, **ser explicável**, **servir ao TCC como experimento defensável** e **evitar dispersão em interface e produto antes da validação do núcleo** [1] [2] [4] [6].

Esses requisitos podem ser usados como base para documentação do projeto, modelagem de backlog, escrita de TCC e alinhamento entre quem for desenvolver as partes do sistema.

## References

[1]: file:///mnt/desktop/tcc-free-plaud/README.md "README.md do projeto tcc-free-plaud"
[2]: file:///mnt/desktop/tcc-free-plaud/docs/tcc/texto/TCC.md "Documento principal do TCC"
[3]: file:///mnt/desktop/tcc-free-plaud/docs/arquitetura/Arquitetura_Backend.md "Arquitetura Backend"
[4]: file:///mnt/desktop/tcc-free-plaud/docs/arquitetura/Arquitetura.md "Arquitetura do Sistema"
[5]: file:///mnt/desktop/tcc-free-plaud/docs/arquitetura/Arquitetura_Frontend.md "Arquitetura Frontend"
[6]: file:///mnt/desktop/tcc-free-plaud/docs/tcc/perguntas/Perguntas_do_TCC.md "Perguntas do TCC"
[7]: file:///mnt/desktop/tcc-free-plaud/docs/tcc/perguntas/Perguntas_a_Serem_Respondidas.md "Perguntas a Serem Respondidas"
