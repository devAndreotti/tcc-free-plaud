# Análise do pré-projeto do TCC e plano de execução

## Objetivo deste documento

Este documento consolida a análise do **modelo de pré-projeto** enviado e do conteúdo já existente no repositório `tcc-free-plaud`, com o objetivo de responder, de forma prática, **o que precisa ser feito**, **como fazer**, **quais tópicos devem ser pesquisados**, **quais materiais já podem ser reaproveitados** e **como dividir o trabalho entre duas pessoas**. A estrutura obrigatória do pré-projeto foi extraída do modelo em PDF, enquanto o conteúdo temático, metodológico e técnico foi identificado nos arquivos do próprio projeto [1] [2] [3] [4] [5] [6] [7].

## 1. O que o modelo de pré-projeto exige

O modelo deixa claro que o pré-projeto deve conter, no mínimo, **capa**, **folha de rosto**, **sumário**, **introdução com tema e problematização**, **justificativa**, **objetivos**, **metodologia da pesquisa**, **cronograma** e **referências** [1]. Além disso, o PDF também orienta o tom de algumas seções. A introdução deve apresentar o assunto, justificar o mérito do tema e terminar com a formulação do problema de pesquisa, preferencialmente em forma de pergunta. A justificativa deve explicar por que o trabalho é importante e quais contribuições práticas e teóricas são esperadas. A metodologia deve explicitar tipo de pesquisa, universo/amostra, instrumentos de coleta e método de análise, e o cronograma deve distribuir as atividades ao longo dos meses [1].

| Parte do pré-projeto | O que o modelo pede | Grau de detalhe esperado |
| --- | --- | --- |
| Capa | Instituição, curso, tema, autor, cidade e ano | Formal, sem conteúdo analítico |
| Folha de rosto | Tema, autor, descrição do pré-projeto, orientador, cidade e ano | Formal, institucional |
| Sumário | Estrutura do documento | Deve seguir as seções obrigatórias |
| Introdução e problematização | Apresentar o tema, contextualizar e formular a questão-problema | Texto corrido, com encadeamento lógico |
| Justificativa | Explicar relevância prática e teórica | Texto argumentativo |
| Objetivos | Um objetivo geral e vários específicos | Verbos no infinitivo |
| Metodologia | Tipo de pesquisa, dados, coleta e análise | Texto técnico-acadêmico |
| Cronograma | Atividades por mês | Tabela simples |
| Referências | Materiais efetivamente citados | Conforme norma institucional |

## 2. O que o projeto já tem pronto ou quase pronto

O repositório já está surpreendentemente maduro em termos de **delimitação conceitual**. O `README.md` e o arquivo `docs/TCC.md` já apresentam de forma clara o problema, a proposta do sistema, o objetivo geral, os objetivos específicos, as perguntas de pesquisa, o escopo, os riscos e o critério de sucesso do trabalho [2] [3]. Em termos práticos, isso significa que vocês **não estão começando do zero**; o que falta agora é transformar material técnico e de planejamento em **redação acadêmica de pré-projeto**.

O tema do TCC já está bem definido: trata-se do **desenvolvimento e avaliação de um pipeline de IA para captura multimodal e recuperação semântica de conhecimento pessoal**, com ênfase em arquitetura **local-first**, uso de **RAG com citação obrigatória**, indexação vetorial local, processamento de conteúdo em **Markdown** e avaliação em **português brasileiro** [2] [3]. O problema central também já está bem formulado: usuários capturam informação em áudio, imagem, texto e PDF, mas perdem valor desse material porque a transformação em conhecimento pesquisável ainda exige disciplina manual excessiva [2] [3].

| Conteúdo necessário no pré-projeto | Situação no repositório | Fonte principal |
| --- | --- | --- |
| Tema do trabalho | Já definido | `docs/TCC.md` [3] |
| Problema de pesquisa | Já definido | `README.md`, `docs/TCC.md` [2] [3] |
| Objetivo geral | Já definido | `docs/TCC.md` [3] |
| Objetivos específicos | Já definidos | `docs/TCC.md` [3] |
| Perguntas de pesquisa | Já definidas | `README.md`, `docs/TCC.md`, `docs/Perguntas_a_Serem_Respondidas.md` [2] [3] [4] |
| Estratégia metodológica inicial | Já esboçada | `docs/TCC.md`, `docs/Arquitetura.md` [3] [5] |
| Cronograma operacional | Já existe base forte | `docs/Plano_de_Arranque.md` [6] |
| Argumentos para defesa e relevância científica | Já existem | `docs/Perguntas_do_TCC.md` [7] |
| Revisão bibliográfica inicial | Já existe | `docs/revisao_bibliografica_rag_tcc.md` [8] |

## 3. O que ainda precisa ser feito

O principal trabalho agora não é inventar o projeto, mas sim **converter o que já existe em formato adequado ao pré-projeto**. Em outras palavras, a maior lacuna atual é de **organização, redação e enquadramento acadêmico**, e não de ausência de ideia.

A capa e a folha de rosto ainda dependem de preenchimento manual, porque o repositório não traz dados institucionais, nomes completos dos autores, nome do orientador, cidade oficial e ano final do documento. Isso é um preenchimento simples, mas obrigatório [1]. Já o corpo do texto precisa ser produzido com base no material existente, sobretudo a partir de `docs/TCC.md`, `README.md`, `docs/Perguntas_do_TCC.md`, `docs/Perguntas_a_Serem_Respondidas.md`, `docs/Plano_de_Arranque.md` e da revisão bibliográfica [2] [3] [4] [6] [7] [8].

| Item pendente | Situação atual | O que fazer |
| --- | --- | --- |
| Dados formais da capa | Ausentes no repositório | Preencher manualmente |
| Dados formais da folha de rosto | Ausentes no repositório | Preencher manualmente |
| Texto acadêmico da introdução | Conteúdo existe, mas disperso | Reescrever em linguagem contínua |
| Formulação final da questão-problema | Existe em essência | Escolher uma formulação central única |
| Justificativa | Base forte já existente | Sintetizar relevância prática e teórica |
| Metodologia em formato acadêmico | Desenho técnico já existe | Traduzir para tipo de pesquisa, corpus, coleta e análise |
| Cronograma em tabela mensal | Base operacional existe | Adaptar ao calendário real da disciplina/TCC |
| Referências em norma da faculdade | Base existe, formatação final não | Normalizar conforme padrão exigido |
| Decisão sobre a terceira frente analítica | Ainda em aberto | Confirmar com o orientador se será embeddings ou escala |

## 4. Como fazer, seção por seção

### 4.1 Introdução – tema e problematização

A introdução deve começar pela dor real que motiva o trabalho: estudantes e profissionais acumulam conhecimento em diferentes mídias, mas raramente conseguem recuperar esse material com eficiência depois. Em seguida, o texto deve mostrar que o problema não é apenas armazenamento, e sim **estruturação e recuperação semântica confiável**. Depois disso, a introdução pode apresentar a proposta do projeto: um pipeline de IA local-first capaz de transformar entradas multimodais em notas Markdown e responder perguntas com base no acervo, usando RAG com citação obrigatória [2] [3] [5].

A parte final da introdução deve apresentar a **questão-problema**. A formulação mais alinhada com o material atual seria algo próximo de: **em que medida um pipeline de IA local-first, baseado em RAG, é capaz de capturar, estruturar e recuperar conhecimento pessoal em português brasileiro com qualidade suficiente para uso prático?** Essa formulação está coerente com o problema, com os objetivos e com as perguntas já mapeadas no projeto [2] [3] [4].

### 4.2 Justificativa

A justificativa já tem base muito forte no material existente. O trabalho é relevante porque enfrenta uma dificuldade concreta de produtividade e gestão do conhecimento. Ao mesmo tempo, ele também possui valor acadêmico porque não pretende apenas montar uma aplicação, mas **avaliar empiricamente** como decisões de chunking, embeddings e recuperação afetam a qualidade do sistema em português brasileiro [3] [7] [8].

Do ponto de vista teórico, a revisão bibliográfica já mostra que RAG é um campo importante para mitigar limitações de modelos puramente paramétricos, sobretudo em cenários que exigem rastreabilidade, atualização e fundamentação documental. Também mostra que há uma lacuna interessante no cruzamento entre **PKM pessoal**, **português brasileiro**, **multimodalidade** e **avaliação controlada de configurações** [8]. Portanto, a justificativa pode ser dividida em dois blocos: um bloco de relevância prática e um bloco de relevância científica.

### 4.3 Objetivos

Esta é a parte mais simples, porque os objetivos já estão praticamente prontos. O objetivo geral pode ser reaproveitado com ajustes mínimos, e os específicos já estão em formato muito próximo do adequado [3]. Apenas convém revisar a redação para manter paralelismo verbal e clareza acadêmica.

| Tipo | Formulação recomendada |
| --- | --- |
| Objetivo geral | Desenvolver e avaliar um pipeline de inteligência artificial para captura multimodal e recuperação semântica de conhecimento pessoal em português brasileiro, com infraestrutura local e respostas fundamentadas por citação. |
| Objetivo específico 1 | Estruturar entradas multimodais em notas Markdown consistentes. |
| Objetivo específico 2 | Indexar essas notas em banco vetorial local. |
| Objetivo específico 3 | Permitir consultas em linguagem natural com respostas fundamentadas no acervo. |
| Objetivo específico 4 | Medir o impacto de parâmetros de chunking, recuperação e embeddings. |
| Objetivo específico 5 | Documentar uma arquitetura replicável para esse tipo de sistema. |

### 4.4 Metodologia da pesquisa

A metodologia precisa traduzir o que hoje aparece como desenho técnico em linguagem acadêmica. A proposta, pelo que já está documentado, é compatível com uma **pesquisa aplicada**, de natureza **experimental**, com desenvolvimento de artefato computacional e avaliação comparativa de configurações [3] [4] [5]. O corpus previsto reúne documentos reais, materiais anonimizados e entradas produzidas pelos autores, enquanto a avaliação inclui métricas como **WER**, **latência**, **MRR**, **Recall@k** e **faithfulness** [3] [4].

Aqui o texto deve deixar explícito: qual é o tipo de pesquisa; qual é o corpus; quais instrumentos serão usados; como os dados serão coletados; e como os resultados serão analisados. Como o modelo pede universo/amostra quando houver dado empírico, vocês podem descrever o corpus previsto e dizer que ele será composto por documentos textuais, PDFs, imagens e áudios delimitados para experimentação [1] [3].

Uma redação metodológica coerente seria apresentar, em sequência, os seguintes elementos.

| Elemento metodológico | Como descrever |
| --- | --- |
| Natureza da pesquisa | Aplicada, com desenvolvimento de artefato computacional |
| Abordagem | Predominantemente experimental e comparativa |
| Objeto de estudo | Pipeline de IA para captura e recuperação de conhecimento pessoal |
| Corpus | Conjunto delimitado de documentos, áudios e imagens em português brasileiro |
| Coleta | Ingestão de arquivos e criação de pares pergunta/resposta para benchmark |
| Variáveis | Chunk size, overlap, top-k e modelo de embedding |
| Métricas | WER, latência, MRR, Recall@k, faithfulness |
| Análise | Comparação entre configurações e interpretação dos resultados |

### 4.5 Cronograma

O cronograma pode ser construído a partir do `Plano_de_Arranque.md`, mas deve ser adaptado à lógica acadêmica do TCC. Em vez de reproduzir exatamente as semanas de implementação, o ideal é converter isso em blocos mensais, incluindo atividades de revisão bibliográfica, redação do pré-projeto, desenvolvimento, experimentação, análise e escrita final [6].

A estrutura abaixo já é suficiente como ponto de partida e pode ser ajustada conforme o calendário da disciplina.

| Atividade | Mês 1 | Mês 2 | Mês 3 | Mês 4 | Mês 5 | Mês 6 |
| --- | --- | --- | --- | --- | --- | --- |
| Revisão bibliográfica e refinamento do tema | X | X |  |  |  |  |
| Redação e ajuste do pré-projeto | X |  |  |  |  |  |
| Implementação do core textual |  | X | X |  |  |  |
| Recuperação vetorial e RAG com citação |  |  | X | X |  |  |
| Benchmark e coleta de métricas |  |  |  | X | X |  |
| Ajustes multimodais e validação |  |  |  | X | X |  |
| Análise dos resultados |  |  |  |  | X | X |
| Redação final do TCC |  |  |  |  | X | X |

## 5. Tópicos que vocês devem pesquisar

Embora já exista bastante material pronto, ainda há pontos que merecem pesquisa complementar para fortalecer o pré-projeto e, principalmente, a continuidade do TCC. O ideal é separar o que é **pesquisa obrigatória agora** do que pode ser deixado para a fase de desenvolvimento e benchmark.

### 5.1 Pesquisa obrigatória agora

Neste momento, vocês devem pesquisar apenas o que fortalece diretamente o texto do pré-projeto. Isso inclui a caracterização acadêmica do problema, a fundamentação mínima sobre RAG, recuperação semântica, embeddings multilíngues, chunking, avaliação de sistemas RAG e trabalhos próximos em PKM ou gestão documental [8]. Também é importante verificar a **norma de referências da instituição**, porque o modelo diz que as referências devem seguir as regras da faculdade/UFPel [1].

| Tema de pesquisa | Por que é importante agora |
| --- | --- |
| RAG e respostas fundamentadas | Sustenta a justificativa e a proposta do sistema |
| PKM e recuperação de conhecimento pessoal | Mostra relevância do problema estudado |
| Chunking | Sustenta uma das variáveis centrais do experimento |
| Embeddings multilíngues | Sustenta a escolha metodológica para português brasileiro |
| Métricas de avaliação RAG | Fundamenta a metodologia |
| Trabalhos próximos com Obsidian/Markdown/PDF | Mostra viabilidade técnica e lacuna acadêmica |
| Norma institucional de referências | Necessária para formatar corretamente o pré-projeto |

### 5.2 Pesquisa que pode ser reaproveitada dos arquivos já existentes

A boa notícia é que vários desses tópicos **já foram pesquisados** no próprio repositório. A revisão bibliográfica existente já cobre arquitetura RAG, bancos vetoriais, chunking, embeddings, frameworks e projetos open source relacionados ao problema do TCC [8]. Portanto, antes de sair procurando novas fontes, vocês devem minerar bem esse arquivo e extrair dele argumentos, conceitos e referências.

| Tópico | Arquivo que já ajuda muito | Observação |
| --- | --- | --- |
| Fundamentação sobre RAG | `docs/revisao_bibliografica_rag_tcc.md` | Reaproveitar para justificativa e base teórica |
| Problema e objetivo do trabalho | `docs/TCC.md` | Usar como espinha dorsal do texto |
| Perguntas de pesquisa | `docs/Perguntas_a_Serem_Respondidas.md` | Útil para coerência metodológica |
| Defesa da relevância científica | `docs/Perguntas_do_TCC.md` | Excelente para justificar o valor do TCC |
| Arquitetura e recorte técnico | `docs/Arquitetura.md` | Útil para metodologia e descrição do artefato |
| Cronograma inicial | `docs/Plano_de_Arranque.md` | Base direta para o cronograma acadêmico |

## 6. Estratégia mais eficiente para transformar isso em pré-projeto

A forma mais inteligente de executar este trabalho é usar o `docs/TCC.md` como **coluna vertebral**, porque ele já contém tema, problema, objetivos, hipótese, escopo, estratégia metodológica e contribuições esperadas [3]. Em seguida, a revisão bibliográfica deve ser usada para robustecer a justificativa e alimentar as referências [8]. O documento `Perguntas_do_TCC.md` deve servir como filtro argumentativo: tudo que estiver no pré-projeto precisa ser defensável perante a banca, e esse arquivo já antecipa várias objeções relevantes [7].

Em termos práticos, a sequência de execução ideal é a seguinte.

| Ordem | Ação recomendada | Resultado esperado |
| --- | --- | --- |
| 1 | Definir o título provisório do trabalho | Tema estabilizado |
| 2 | Fechar a pergunta-problema central | Introdução coerente |
| 3 | Copiar e adaptar objetivo geral e específicos | Seção de objetivos pronta |
| 4 | Sintetizar a justificativa com base na revisão e nos argumentos do projeto | Seção de justificativa pronta |
| 5 | Redigir a metodologia em linguagem acadêmica | Método claro e defensável |
| 6 | Montar o cronograma em tabela | Planejamento formalizado |
| 7 | Normalizar as referências | Documento finalizável |

## 7. Como dividir o trabalho entre duas pessoas

A melhor divisão não é por capítulos isolados de forma rígida, mas por **frentes complementares**. Uma pessoa deve assumir a frente **acadêmica-conceitual**, enquanto a outra assume a frente **metodológica-técnica**. Depois, os dois revisam o documento inteiro juntos para unificar estilo, vocabulário e coerência.

### Divisão recomendada

| Pessoa | Frente principal | Entregas sugeridas |
| --- | --- | --- |
| Pessoa 1 | Contexto, problema, justificativa e referências | Introdução, problematização, justificativa, revisão das referências e padronização acadêmica |
| Pessoa 2 | Objetivos, metodologia, cronograma e alinhamento técnico | Objetivos, metodologia da pesquisa, cronograma e consistência com a arquitetura já definida |

Essa divisão funciona bem porque a primeira frente exige mais leitura, síntese bibliográfica e construção argumentativa, enquanto a segunda exige mais atenção ao desenho do experimento, ao artefato e à execução do trabalho [3] [5] [6] [7] [8].

### Divisão operacional por etapas

| Etapa | Pessoa 1 | Pessoa 2 | Entrega conjunta |
| --- | --- | --- | --- |
| Levantamento do material | Minerar `revisao_bibliografica_rag_tcc.md` e `Perguntas_do_TCC.md` | Minerar `TCC.md`, `Arquitetura.md` e `Plano_de_Arranque.md` | Mapa comum do conteúdo reutilizável |
| Redação inicial | Introdução e justificativa | Objetivos e metodologia | Primeira versão do texto |
| Planejamento | Apoiar com coerência argumentativa | Montar cronograma | Estrutura final completa |
| Revisão | Ajustar estilo, clareza e referências | Ajustar coerência técnica e metodologia | Versão final unificada |

## 8. Divisão alternativa, se vocês quiserem equilibrar melhor o esforço

Se os dois quiserem participar tanto da parte escrita quanto da parte técnica, uma alternativa é dividir por **macroblocos do documento**, mas mantendo revisão cruzada obrigatória.

| Bloco | Responsável principal | Revisor principal |
| --- | --- | --- |
| Capa, folha de rosto e sumário | Pessoa 2 | Pessoa 1 |
| Introdução e problematização | Pessoa 1 | Pessoa 2 |
| Justificativa | Pessoa 1 | Pessoa 2 |
| Objetivos | Pessoa 2 | Pessoa 1 |
| Metodologia | Pessoa 2 | Pessoa 1 |
| Cronograma | Pessoa 2 | Pessoa 1 |
| Referências | Pessoa 1 | Pessoa 2 |

Essa segunda divisão é boa quando ambos querem participar do texto inteiro, mas ela exige mais coordenação. A primeira divisão, por frentes, tende a ser mais rápida e mais eficiente.

## 9. O que eu faria primeiro, na prática

Se a ideia é ganhar velocidade imediatamente, o melhor caminho é seguir esta ordem de execução já no próximo encontro de vocês. Primeiro, fechar o **título provisório** e a **questão-problema**. Depois, copiar do `docs/TCC.md` o objetivo geral e os específicos para uma versão inicial do pré-projeto. Em seguida, usar a revisão bibliográfica e o arquivo `Perguntas_do_TCC.md` para escrever a justificativa. Por fim, transformar o desenho já existente em uma metodologia acadêmica enxuta e adaptar o `Plano_de_Arranque.md` para um cronograma compatível com o calendário do curso [3] [6] [7] [8].

| Prioridade | Tarefa | Fonte-base |
| --- | --- | --- |
| Alta | Fechar título e pergunta-problema | `docs/TCC.md`, `README.md` [2] [3] |
| Alta | Redigir objetivos | `docs/TCC.md` [3] |
| Alta | Redigir justificativa | `docs/revisao_bibliografica_rag_tcc.md`, `docs/Perguntas_do_TCC.md` [7] [8] |
| Alta | Redigir metodologia | `docs/TCC.md`, `docs/Arquitetura.md`, `docs/Perguntas_a_Serem_Respondidas.md` [3] [4] [5] |
| Média | Montar cronograma | `docs/Plano_de_Arranque.md` [6] |
| Média | Ajustar referências | revisão bibliográfica + norma da instituição [1] [8] |

## 10. Conclusão

Em resumo, o projeto já tem **tema, problema, objetivos, perguntas de pesquisa, estratégia técnica e base bibliográfica** suficientemente maduros para produzir um bom pré-projeto [2] [3] [4] [5] [6] [7] [8]. O que falta agora é **organizar**, **escrever academicamente** e **formatar segundo o modelo** [1]. Portanto, a maior parte do esforço de vocês deve ir para transformar material técnico já existente em um texto curto, coerente, defensável e bem formatado.

Se vocês seguirem a estratégia de aproveitar `docs/TCC.md` como eixo central, usar a revisão bibliográfica como base da justificativa e dividir o trabalho entre uma frente argumentativa e outra metodológica, o pré-projeto tende a sair com muito menos retrabalho e com maior consistência entre o que será prometido agora e o que realmente poderá ser implementado depois [3] [6] [7] [8].

## References

[1]: file:///home/ubuntu/upload/Modelo-de-pre-projeto.pdf "Modelo de pré-projeto de TCC"
[2]: file:///mnt/desktop/tcc-free-plaud/README.md "README.md do projeto tcc-free-plaud"
[3]: file:///mnt/desktop/tcc-free-plaud/docs/TCC.md "Documento principal do TCC"
[4]: file:///mnt/desktop/tcc-free-plaud/docs/Perguntas_a_Serem_Respondidas.md "Perguntas a Serem Respondidas"
[5]: file:///mnt/desktop/tcc-free-plaud/docs/Arquitetura.md "Arquitetura do Sistema"
[6]: file:///mnt/desktop/tcc-free-plaud/docs/Plano_de_Arranque.md "Plano de Arranque"
[7]: file:///mnt/desktop/tcc-free-plaud/docs/Perguntas_do_TCC.md "Perguntas do TCC"
[8]: file:///mnt/desktop/tcc-free-plaud/docs/revisao_bibliografica_rag_tcc.md "Revisão bibliográfica RAG TCC"
