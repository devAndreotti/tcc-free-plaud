# Guia Prático de Modelagem de Dados para Data Warehouses Modernos

**Contexto:** Material de estudo para o módulo de Engenharia de Dados — Trilha Avançada  
**Última revisão:** março de 2025  
**Autor:** equipe de capacitação interna

---

## Introdução

A modelagem de dados para data warehouses atravessou transformações profundas na última década. O que antes era um domínio dominado quase exclusivamente pelo modelo dimensional de Ralph Kimball e pelo modelo normalizado de Bill Inmon hoje convive com abordagens modernas como Data Vault, One Big Table e as arquiteturas Lakehouse. Cada uma dessas abordagens reflete uma filosofia diferente sobre o que priorizar: flexibilidade para mudanças, performance de consulta, auditabilidade histórica ou simplicidade operacional.

Este guia não pretende declarar um vencedor. O objetivo é apresentar as principais abordagens com honestidade sobre suas vantagens e limitações, de modo que engenheiros de dados possam tomar decisões informadas de acordo com o contexto específico de cada projeto.

---

## 1. Fundamentos de Modelagem Dimensional

### 1.1 O Modelo Star Schema

O modelo estrela (star schema) é a base da abordagem de Kimball e continua sendo, décadas depois de sua formalização, a escolha mais comum para camadas de consumo analítico em data warehouses. Sua estrutura é elegantemente simples: uma tabela fato central, que contém métricas quantitativas e chaves estrangeiras, rodeada por tabelas dimensão que fornecem contexto descritivo.

A tabela fato registra eventos ou transações mensuráveis. Em um data warehouse de e-commerce, por exemplo, a tabela `fato_pedido` registraria cada item de pedido com sua quantidade, valor unitário e desconto aplicado, além de chaves para as dimensões de produto, cliente, data e canal de venda. As métricas ficam na fato; os atributos descritivos ficam nas dimensões.

As vantagens do star schema são conhecidas: queries analíticas tendem a ser performáticas porque o modelo desnormalizadoda dimensão evita joins em cadeia, e a estrutura é intuitiva o suficiente para que analistas de negócio consigam entender o modelo sem conhecimento profundo de banco de dados. A desvantagem principal é a redundância de dados nas dimensões — o nome e o endereço de um cliente aparecem em todas as linhas da fato, não em uma tabela separada normalizada.

### 1.2 Snowflake Schema

O modelo snowflake (snowflake schema) é uma variação normalizada do star schema. As dimensões são decompostas em tabelas adicionais: em vez de armazenar diretamente a categoria de produto na dimensão `dim_produto`, cria-se uma tabela separada `dim_categoria_produto` com uma chave estrangeira na dimensão principal.

O resultado é um modelo que ocupa menos espaço em disco e tem menos redundância de dados, mas que exige mais joins nas queries. Na prática, a maioria das ferramentas analíticas modernas (Redshift, BigQuery, Snowflake) têm otimizadores de query suficientemente bons para tornar o custo dos joins aceitável. O snowflake é mais comum em organizações com equipes de engenharia que priorizam integridade de dados e em sistemas onde o volume de dados das dimensões é muito grande.

### 1.3 Slowly Changing Dimensions (SCD)

Um dos problemas mais clássicos de modelagem dimensional é o tratamento de mudanças em atributos de dimensão ao longo do tempo — as chamadas Slowly Changing Dimensions (SCD). Considere o caso de um cliente que muda de endereço: como preservar a informação de que as compras antigas foram feitas enquanto o cliente morava no endereço anterior?

Existem várias estratégias, conhecidas como tipos de SCD:

- **SCD Tipo 1 (Sobrescrever):** O atributo é simplesmente atualizado. Não há histórico. Adequado para correções de erros ou atributos onde o histórico não tem relevância analítica.

- **SCD Tipo 2 (Adicionar linha):** Uma nova linha é inserida para o cliente com o novo endereço, e a linha anterior é marcada como inativa (geralmente com colunas `valid_from`, `valid_to` e `is_current`). Preserva o histórico completo, mas aumenta o volume da dimensão e complica queries que precisam do estado atual.

- **SCD Tipo 3 (Adicionar coluna):** Colunas adicionais são adicionadas para armazenar o valor anterior (`endereco_anterior`, `endereco_atual`). Preserva apenas a penúltima versão, não o histórico completo. Raramente usado na prática.

- **SCD Tipo 4 (Tabela histórica):** A dimensão principal armazena apenas o estado atual; uma tabela separada de histórico registra todas as versões anteriores. Combina a simplicidade de queries de estado atual com a preservação de histórico.

---

## 2. O Modelo Data Vault

### 2.1 Filosofia e Estrutura

O Data Vault foi desenvolvido por Dan Linstedt no final dos anos 1990 e ganhou popularidade crescente a partir de 2010 como resposta às limitações do modelo Kimball em cenários de alta volatilidade de fontes e requisitos de auditabilidade completa. A filosofia central do Data Vault é que o data warehouse deve ser um repositório histórico e auditável de dados brutos, sem transformações de negócio — essas ficam na camada de apresentação.

A estrutura do Data Vault é composta por três tipos de tabelas:

**Hubs (Hubs):** Armazenam as chaves de negócio únicas de cada entidade. Um hub de cliente conteria apenas o `customer_id` de negócio, a data de carga e a fonte do dado. Nada mais. A justificativa é que a chave de negócio é o que identifica unicamente uma entidade, independentemente de qual sistema a gerou.

**Links (Links):** Representam relacionamentos entre hubs. Um link entre cliente e pedido conteria as chaves de ambos os hubs, a data de carga e a fonte. Links permitem representar relacionamentos muitos-para-muitos sem nenhuma alteração na estrutura de hubs.

**Satélites (Satellites):** Armazenam os atributos descritivos e seu histórico. Todo atributo mutável fica em um satélite com `load_date` e `load_end_date`, garantindo que qualquer estado histórico seja reproduzível. Um hub de cliente teria satélites separados para dados de contato, dados demográficos e dados de preferência — permitindo que cada satélite seja atualizado de forma independente.

### 2.2 Vantagens e Limitações

As principais vantagens do Data Vault são:

1. **Auditabilidade total:** Todo dado carregado é preservado com sua fonte e timestamp. Nada é sobrescrito, apenas novos registros são adicionados.
2. **Resiliência a mudanças:** Adicionar uma nova fonte de dados raramente exige modificar tabelas existentes — geralmente basta adicionar novos satélites.
3. **Paralelismo de carga:** A estrutura do Data Vault é altamente paralelizável, o que é uma vantagem significativa em cargas volumosas.

As limitações são igualmente importantes de considerar:

1. **Complexidade de modelagem:** Criar e manter um Data Vault exige uma equipe disciplinada e ferramentas de geração de código. Projetos pequenos raramente justificam o overhead.
2. **Performance de consulta:** Queries analíticas em Data Vault puro são pesadas — geralmente exigem vários joins entre hubs, links e satélites. A prática recomendada é criar uma camada de Data Marts (usando star schema ou similar) sobre o Data Vault para consumo analítico.
3. **Curva de aprendizado:** A abordagem exige treinamento e mudança de mentalidade significativos em relação ao modelo Kimball.

---

## 3. Arquiteturas Lakehouse e o Papel da Modelagem

### 3.1 Delta Lake, Iceberg e a Convergência de Data Lake e DW

A arquitetura Lakehouse — popularizada pelo Databricks com o Delta Lake e pela Apache Foundation com o Apache Iceberg — representa uma tentativa de combinar a flexibilidade e o baixo custo de armazenamento dos data lakes com as garantias transacionais e de performance dos data warehouses tradicionais.

Em um Lakehouse, os dados são armazenados em formatos abertos (Parquet, ORC) em armazenamento de objetos (S3, GCS, Azure Blob), mas com uma camada transacional sobre eles que oferece:

- Operações ACID (atomicidade, consistência, isolamento, durabilidade)
- Time travel (consultar o estado dos dados em qualquer ponto no passado)
- Schema evolution sem necessidade de reescrever todos os dados
- Z-ordering e outras técnicas de otimização de leitura

### 3.2 Impacto na Modelagem

A questão relevante para este guia é: como a arquitetura Lakehouse afeta as decisões de modelagem? A resposta curta é: menos do que se poderia imaginar.

A maioria das equipes que adota Lakehouse ainda precisa decidir sobre a estrutura lógica dos dados: star schema, Data Vault ou outro. O que muda é a tecnologia de implementação, não a necessidade de modelagem. Delta Lake e Iceberg resolvem problemas de infraestrutura; eles não substituem decisões sobre granularidade, definição de métricas ou tratamento de SCDs.

Uma tendência observável é o uso de padrões como o Medallion Architecture (camadas Bronze → Silver → Gold), que divide o pipeline de dados em estágios progressivos de refinamento, cada um com suas próprias decisões de modelagem. A camada Bronze armazena dados brutos; a Silver aplica limpeza e padronização; a Gold implementa o modelo analítico final (tipicamente star schema ou Data Vault + Data Marts).

---

## 4. Boas Práticas e Anti-Padrões

### 4.1 Boas Práticas Universais

Independentemente da abordagem de modelagem escolhida, algumas práticas são recomendadas em todos os contextos:

**Surrogate keys para tabelas fato e dimensão:** Nunca use chaves de negócio diretamente como chaves primárias em tabelas de data warehouse. Chaves de negócio mudam, são reutilizadas e variam entre sistemas fonte. Uma surrogate key (geralmente um inteiro sequencial ou UUID) garante estabilidade das referências internas.

**Documentação embutida no modelo:** Use ferramentas como dbt para documentar o propósito de cada tabela, o significado de cada coluna e as regras de transformação aplicadas diretamente no código. Documentação separada do código envelhece mal.

**Testes de qualidade de dados:** Implemente testes automáticos para invariantes do modelo: unicidade de chaves, integridade referencial, ausência de valores nulos em colunas obrigatórias, validade de intervalos de data em SCDs. Dados incorretos descobertos pelos usuários finais são muito mais custosos do que os detectados no pipeline.

**Separação clara entre camada de integração e camada de apresentação:** A camada de integração (ou staging) deve ser o mais fiel possível às fontes, com transformações mínimas. A camada de apresentação (data marts, camada Gold) é onde as regras de negócio são aplicadas. Misturar essas responsabilidades em uma única camada cria modelos frágeis e difíceis de manter.

### 4.2 Anti-Padrões Comuns

**A tabela fato "genérica":** Criar uma única tabela fato com dezenas de colunas numéricas e uma coluna de "tipo de evento" para discriminar o que cada linha representa é um anti-padrão clássico. Resulta em tabelas esparsas (a maioria das colunas são nulas para qualquer tipo de evento específico) e queries confusas.

**Dimensões sem data de validade:** Usar SCD Tipo 1 sem consciência — simplesmente sobrescrever atributos dimensionais sem avaliar se o histórico tem valor analítico — é um erro que só é descoberto quando alguém precisa analisar "como eram os dados antes da mudança" e descobre que essa informação foi destruída.

**Transformações de negócio na camada de ingestão:** Aplicar regras de negócio complexas nos ETLs de carga de dados brutos torna o pipeline frágil e dificulta o reprocessamento. Regras de negócio mudam; dados históricos brutos, idealmente, não.

---

## 5. Escolhendo a Abordagem Certa

A tabela a seguir resume as recomendações para seleção de abordagem com base no contexto do projeto:

| Contexto                                    | Abordagem recomendada       | Justificativa                                      |
|---------------------------------------------|-----------------------------|----------------------------------------------------|
| Time pequeno, requisitos estáveis           | Star Schema (Kimball)       | Simplicidade, ampla base de conhecimento disponível |
| Alta variabilidade de fontes e requisitos   | Data Vault + Data Marts     | Resiliência a mudanças, auditabilidade              |
| Dados semi-estruturados, volume alto        | Lakehouse + Medallion       | Flexibilidade de schema, custo de armazenamento     |
| Análise ad-hoc por usuários de negócio      | Star Schema desnormalizado  | Facilidade de compreensão, performance de query     |
| Compliance e auditoria regulatória          | Data Vault                  | Rastreabilidade completa de todo dado carregado     |
| Prototipagem e exploração inicial           | One Big Table ou Flat Files | Velocidade de iteração, baixo overhead de setup     |

---

## 6. Ferramentas do Ecossistema Moderno

### 6.1 dbt (data build tool)

O dbt tornou-se o padrão de facto para a camada de transformação em data warehouses modernos. Ele permite escrever transformações em SQL (ou Python, na versão recente), com suporte a testes automáticos, documentação, lineage e versionamento. A filosofia do dbt é que analistas e engenheiros de dados devem ser capazes de contribuir para o pipeline de transformação sem precisar gerenciar infraestrutura.

Para modelagem dimensional, existem pacotes dbt que automatizam partes do processo, como o `dbt_utils` e o `dbt_date`. Para Data Vault, existe o `dbtvault`, que gera automaticamente o código SQL para hubs, links e satélites a partir de configurações YAML.

### 6.2 Great Expectations e Soda

Ferramentas de qualidade de dados como Great Expectations e Soda permitem definir e executar suítes de testes sobre os dados em qualquer camada do pipeline. São complementares ao dbt e representam a implementação prática do princípio de "testes de qualidade de dados" mencionado nas boas práticas.

### 6.3 DataHub e OpenMetadata

Ferramentas de catalogação e governança como DataHub (LinkedIn) e OpenMetadata permitem criar um catálogo centralizado de todos os ativos de dados da organização, com lineage automático, documentação e controle de acesso. São especialmente relevantes em organizações com múltiplos times de dados produzindo e consumindo dados de forma descentralizada.

---

## Considerações Finais

A escolha de uma abordagem de modelagem de dados não é uma decisão técnica pura — é uma decisão organizacional que reflete as prioridades, a maturidade e os recursos disponíveis da equipe. Um Data Vault implementado por uma equipe pequena sem experiência prévia pode ser mais custoso e frágil do que um star schema bem cuidado pelo mesmo time.

O conselho mais duradouro é: comece com a abordagem mais simples que satisfaz os requisitos atuais, documente as decisões de modelagem com o contexto que as motivou, e reavalie conforme o contexto muda. Modelos de dados evoluem — a questão não é se precisará mudar, mas se a mudança será gerenciável quando chegar.
