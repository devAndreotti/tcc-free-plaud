# Avaliação de Estratégias de Chunking para Pipelines RAG em Documentos Técnicos Longos

**Autores:** Bruno Takahashi¹, Renata Vasconcelos², André Lopes¹  
**¹** Laboratório de Engenharia de Software — Universidade Estadual do Centro-Oeste  
**²** Departamento de Ciência da Computação — Universidade Federal de Minas Gerais  
**Contato:** bruno.takahashi@lab.uesc.br  
**Publicação:** Workshop Brasileiro de Recuperação de Informação e PLN (WBRIP 2025)

---

## Resumo

A eficácia de sistemas de Recuperação Aumentada por Geração (RAG) depende criticamente da qualidade dos fragmentos (chunks) utilizados na indexação dos documentos. Estratégias ingênuas de chunking por tamanho fixo frequentemente fragmentam conceitos em fronteiras arbitrárias, degradando a qualidade da recuperação. Neste trabalho, avaliamos cinco estratégias de chunking — tamanho fixo, por sentença, por parágrafo, hierárquico e semântico — sobre um corpus de 800 documentos técnicos em português brasileiro, medindo seu impacto no MRR@10 e na fidelidade das respostas geradas. Os resultados indicam que o chunking semântico supera as demais estratégias em qualidade de recuperação (MRR@10 médio de 0,81), mas com custo computacional 4,7× maior que o chunking por parágrafo, que oferece o melhor trade-off geral.

**Palavras-chave:** RAG, chunking, recuperação de informação, NLP, português brasileiro.

---

## 1. Introdução

Sistemas de Recuperação Aumentada por Geração (RAG) tornaram-se uma das abordagens mais adotadas para dotar modelos de linguagem de acesso a bases de conhecimento específicas sem a necessidade de fine-tuning contínuo. A arquitetura básica de um pipeline RAG compreende três etapas: a indexação dos documentos em uma base vetorial, a recuperação dos fragmentos mais relevantes dado uma consulta e a geração da resposta pelo modelo de linguagem condicionada nos fragmentos recuperados.

A etapa de indexação, frequentemente tratada como detalhe de implementação, tem impacto direto e significativo na qualidade do sistema. A granularidade e a coerência semântica dos fragmentos determinam se o sistema consegue recuperar informações precisas ou apenas aproximações ruidosas do conteúdo relevante.

Apesar da importância prática do chunking, a literatura em português sobre o tema é escassa. A maior parte dos trabalhos avalia corpora em inglês ou usa documentos curtos onde a estratégia de chunking tem impacto marginal. Este trabalho preenche essa lacuna ao avaliar sistematicamente cinco estratégias em documentos técnicos longos — como manuais, especificações de requisitos e relatórios científicos — em português brasileiro.

### 1.1 Contribuições

As principais contribuições deste trabalho são:

1. Uma avaliação empírica sistemática de cinco estratégias de chunking em corpus técnico em português.
2. Uma análise do trade-off entre qualidade de recuperação e custo computacional de indexação.
3. Um conjunto de diretrizes práticas para seleção de estratégia de chunking com base no perfil dos documentos.
4. Disponibilização pública do corpus de avaliação e dos scripts de benchmarking.

---

## 2. Estratégias de Chunking Avaliadas

### 2.1 Tamanho Fixo (TF)

A estratégia de tamanho fixo divide o documento em janelas de N tokens com sobreposição de M tokens entre janelas consecutivas. Neste experimento, utilizamos N=512 e M=64, valores comumente recomendados na documentação de frameworks como LangChain e LlamaIndex.

É a estratégia mais simples de implementar, mas apresenta a maior taxa de fragmentação semântica — dividir uma tabela ou uma enumeração no meio é comum e prejudica severamente a coerência do fragmento.

### 2.2 Por Sentença (PS)

A estratégia por sentença utiliza um detector de fronteiras de sentença para dividir o texto. Implementamos usando o modelo `pt_core_news_lg` do spaCy. Sentenças muito curtas (< 20 tokens) são agrupadas com a seguinte para evitar fragmentos sem conteúdo significativo.

Apresenta boa coerência local, mas perde contexto inter-sentencial. Consultas que requerem síntese de várias sentenças próximas tendem a não ser bem atendidas.

### 2.3 Por Parágrafo (PP)

A estratégia por parágrafo utiliza as fronteiras explícitas de parágrafos (linhas em branco no texto) como delimitadores. Parágrafos muito longos (> 800 tokens) são subdivididos usando a estratégia por sentença como fallback.

É a estratégia com melhor relação custo-benefício na maioria dos cenários testados.

### 2.4 Hierárquico (HR)

O chunking hierárquico cria fragmentos em dois níveis: seções (L1) e parágrafos dentro de cada seção (L2). Cada fragmento L2 carrega como metadado o título da seção L1 correspondente, enriquecendo o contexto disponível durante a recuperação.

Essa estratégia é especialmente eficaz para documentos com estrutura clara de headings, como especificações técnicas e artigos científicos.

### 2.5 Semântico (SM)

O chunking semântico utiliza embeddings de sentença para identificar pontos de quebra onde a similaridade entre sentenças consecutivas cai abaixo de um limiar. A implementação usa o algoritmo de detectar "vales" na curva de similaridade, agrupando sentenças semanticamente coesas em um mesmo fragmento.

É computacionalmente mais custoso, pois exige geração de embeddings durante a indexação, mas produz fragmentos com maior coerência semântica independentemente da estrutura explícita do documento.

---

## 3. Metodologia Experimental

### 3.1 Corpus

O corpus foi composto por 800 documentos técnicos em português brasileiro, coletados de quatro fontes:

| Fonte                          | Documentos | Tokens médios | Domínio          |
|-------------------------------|------------|---------------|------------------|
| Repositórios GitHub (READMEs) | 200        | 1.240         | Documentação     |
| Editais públicos (gov.br)     | 200        | 4.870         | Administrativo   |
| Artigos BRACIS (2020–2024)    | 200        | 6.320         | Acadêmico        |
| Manuais técnicos (open source)| 200        | 9.140         | Técnico          |

### 3.2 Conjunto de Avaliação

Foram elaboradas 400 consultas de avaliação, distribuídas igualmente entre os quatro domínios. Para cada consulta, foram anotados manualmente até 5 fragmentos relevantes do corpus. O processo de anotação foi realizado por dois revisores independentes; casos de divergência foram resolvidos por consenso.

### 3.3 Infraestrutura

Todos os experimentos foram executados em uma máquina com CPU Intel Xeon E5-2680 v4 (28 núcleos), 128 GB RAM e sem GPU dedicada. O índice vetorial foi implementado com ChromaDB e os embeddings gerados com `nomic-embed-text-v1.5`.

---

## 4. Resultados

### 4.1 Qualidade de Recuperação (MRR@10)

| Estratégia    | READMEs | Editais | Acadêmico | Manuais | Média |
|---------------|---------|---------|-----------|---------|-------|
| Fixo (TF)     | 0,61    | 0,54    | 0,63      | 0,58    | 0,59  |
| Sentença (PS) | 0,67    | 0,61    | 0,69      | 0,64    | 0,65  |
| Parágrafo (PP)| 0,74    | 0,70    | 0,76      | 0,73    | 0,73  |
| Hierárquico (HR)| 0,77  | 0,74    | 0,81      | 0,78    | 0,78  |
| Semântico (SM)| 0,80    | 0,77    | 0,85      | 0,82    | 0,81  |

### 4.2 Custo de Indexação (segundos por 100 documentos)

| Estratégia    | Tempo de indexação (s) | Fator relativo ao PP |
|---------------|------------------------|----------------------|
| Fixo (TF)     | 8,2                    | 0,4×                 |
| Sentença (PS) | 31,4                   | 1,5×                 |
| Parágrafo (PP)| 20,6                   | 1,0× (base)          |
| Hierárquico (HR)| 28,1                 | 1,4×                 |
| Semântico (SM)| 97,3                   | 4,7×                 |

---

## 5. Discussão

Os resultados mostram que o ganho marginal de qualidade entre as estratégias hierárquica e semântica (0,03 pontos de MRR@10) não justifica o aumento de 3,5× no tempo de indexação na maioria dos cenários práticos. A estratégia hierárquica é, portanto, a recomendação padrão para documentos com estrutura explícita de headings.

Para documentos sem estrutura formal — como e-mails, notas pessoais e transcrições — o chunking semântico oferece ganhos mais expressivos, dado que não há headings para guiar o chunking hierárquico.

O chunking por tamanho fixo mostrou desempenho consistentemente inferior. Seu único caso de uso justificado é quando o tempo de indexação é um requisito crítico e a qualidade de recuperação pode ser sacrificada — cenário incomum em sistemas de notas pessoais.

---

## 6. Conclusão

Este trabalho demonstrou empiricamente que a escolha da estratégia de chunking tem impacto mensurável e significativo na qualidade de sistemas RAG. O chunking por parágrafo oferece o melhor trade-off geral, enquanto o hierárquico é preferível para documentos bem estruturados. A estratégia semântica é recomendada apenas quando a qualidade máxima de recuperação é requisito e o custo computacional de indexação é aceitável.

Como trabalho futuro, planejamos avaliar estratégias de chunking adaptativas que selecionam automaticamente a granularidade com base em características do documento, como comprimento médio de parágrafo, densidade de headings e tipo de conteúdo detectado.

---

## Referências

LEWIS, P. et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS*, 2020.

CHEN, J. et al. Benchmarking Large Language Models in Retrieval-Augmented Generation. *arXiv*, 2023.

ZHANG, P. et al. Optimizing Retrieval-Augmented Generation: An Overview of Methods and Metrics. *arXiv*, 2024.

SOUZA, F.; NOGUEIRA, R.; LOTUFO, R. BERTimbau: Pretrained BERT Models for Brazilian Portuguese. *BRACIS*, 2020.
