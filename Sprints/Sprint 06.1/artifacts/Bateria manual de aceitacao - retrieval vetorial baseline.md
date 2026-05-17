# Bateria manual de aceitacao - retrieval vetorial baseline

**Autor:** Codex  
**Data:** 2026-04-14

## Objetivo

Esta bateria existe para validar se a Sprint 06.1 esta aceitavel como baseline de infraestrutura vetorial antes da Sprint 06.2.

Ela nao mede ainda a qualidade final do `ask`.
Ela mede se a busca vetorial:

- indexa de forma estavel
- retorna chunks plausivelmente relevantes em consultas boas
- expõe claramente onde ainda traz ruido em consultas negativas

## Regra de leitura

Uma saida boa nesta sprint nao significa “retrieval final pronto”.

Nesta fase, a barra correta e:

- indexacao funcionando
- busca vetorial persistente
- hits razoavelmente uteis em perguntas positivas
- deteccao clara de que perguntas negativas ainda geram ruido

Se isso acontecer, a 06.1 esta aceita.
O que faltar entra como backlog direto da 06.2.

## Como rodar

### 1. Indexar o arquivo

```powershell
uv run free-plaud retrieval index "C:\caminho\arquivo.md" --chunk-size 600 --overlap 120
```

### 2. Consultar semanticamente

```powershell
uv run free-plaud retrieval semantic-search --query "pergunta" --top-k 3 --note-id "note-id"
```

## Criterios de avaliacao

### Saida boa

- o top-1 ou top-3 trazem chunks claramente ligados ao tema da pergunta
- as respostas positivas mostram ao menos um hit com alta plausibilidade humana
- o retrieval preserva `chunk_id`, offsets e score
- os resultados fazem sentido suficiente para sustentar a Sprint 06.2

### Saida ruim

- perguntas positivas trazem chunks sem relacao clara com a pergunta
- top-3 dominado por ruído
- score sem diferenca perceptivel entre relevante e irrelevante
- perguntas negativas parecem “boas” demais sem qualquer freio de evidência

## Bateria recomendada

### Caso 1 - Documento tecnico longo

Arquivo:

- `samples/manual validetion/07_pdf_tecnico_estruturado.md`

Perguntas positivas:

- `Qual estrategia oferece o melhor trade-off geral?`
- `Qual estrategia foi pior?`

Pergunta negativa:

- `Como funciona OCR juridico?`

Esperado:

- perguntas positivas devem trazer chunks sobre estrategias, tabelas comparativas e conclusoes
- a pergunta negativa provavelmente ainda vai trazer ruido

Leitura:

- se o positivo vier razoavel e o negativo ainda vier ruidoso, a 06.1 esta coerente

### Caso 2 - Ata tecnica

Arquivo:

- `samples/manual validetion/04_ata_metadados_longos.txt`

Perguntas positivas:

- `Qual tecnologia foi escolhida pelo comite?`
- `Quais condicionantes ficaram registradas?`

Pergunta negativa:

- `Como organizar notas pessoais no Obsidian?`

Esperado:

- as perguntas positivas devem recuperar chunks sobre Kafka e condicionantes
- a pergunta negativa nao deveria ser convincente, mesmo que ainda recupere ruido

### Caso 3 - Nota pessoal/roteiro

Arquivo:

- `samples/manual validetion/new/Ousion Prep.md`

Perguntas positivas:

- `Qual e o seu diferencial real?`
- `Como falar das lacunas?`

Pergunta negativa:

- `Como funciona Kafka com replay de mensagens?`

Esperado:

- se a pergunta positiva ainda recuperar ruido demais, isso indica necessidade de deduplicacao e estrategia melhor na 06.2
- a pergunta negativa nao deve ser tratada como evidência forte

### Caso 4 - CV

Arquivo:

- `samples/manual validetion/new/Ricardo Andreotti - CV.pdf`

Perguntas positivas:

- `Qual e o resumo profissional?`
- `Quais tecnologias ele usa?`

Pergunta negativa:

- `Qual o algoritmo de chunking usado no projeto?`

Esperado:

- positivos devem recuperar resumo profissional e stack
- negativo deve evidenciar que ainda falta threshold/gate de evidência

## Gate para aceitar a Sprint 06.1

Aceitar a sprint se:

1. a indexacao vetorial estiver funcionando
2. consultas positivas trouxerem top-3 plausivel na maioria dos casos
3. os resultados preservarem metadados e offsets
4. ficar claro quais falhas devem ser tratadas na 06.2

Nao aceitar a sprint se:

1. consultas positivas falharem sistematicamente
2. o retrieval vetorial trouxer ruido indistinguivel ate em casos bons
3. a persistencia vetorial for instavel

## Leitura atual da bateria

Pelo estado atual observado:

- `07_pdf_tecnico_estruturado.md`: aceitavel
- `04_ata_metadados_longos.txt`: aceitavel
- `Ousion Prep.md`: fraco para perguntas abertas
- `Ricardo Andreotti - CV.pdf`: aceitavel em positivo, fraco em negativo

## Conclusao operacional

A Sprint 06.1 pode ser considerada:

- **aceitavel como baseline de infraestrutura vetorial**
- **nao aceitavel ainda como retrieval final de qualidade**

Isso significa:

- seguir para a Sprint 06.2
- levar para a 06.2 os temas:
  - threshold de evidência vetorial
  - distancia bruta no hit
  - deduplicacao
  - integracao do `ask` com retrieval semantico
  - melhor gate para perguntas negativas
