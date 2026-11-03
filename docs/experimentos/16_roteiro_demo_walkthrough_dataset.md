# Roteiro de demonstração para a banca: Escólio

Roteiro cronometrado para a apresentação do TCC, com base no código da branch `fechamento/roteiro` (atualizado em 2026-11-02).

Cada tela, botão, rótulo e comando citado foi conferido no código, com arquivo e linha. O que não foi confirmado está marcado como **a confirmar no ensaio**. Nenhuma pergunta de demonstração foi rodada no app ainda: todas estão **a ensaiar**.

---

## 1. Visão geral (7 a 10 minutos)

| Bloco | Conteúdo | Tempo |
|:---:|:---|:---:|
| 1 | Preparação na véspera (fora do tempo) | não conta |
| 2 | Diagnóstico, com abertura | 1:30 |
| 3 | Indexação: Fila e grafo | 1:00 |
| 4 | Pergunta com citação | 2:30 |
| 5 | Pergunta sem resposta | 1:00 |
| 6 | Benchmark e fechamento | 2:00 |
| 7 | Plano B (só se houver falha) | fora do tempo |

Tempo alvo: 8 minutos. Se o Ollama demorar, o teto é 10 minutos.

---

## 2. Bloco 1: Preparação na véspera

Fazer tudo isto antes do dia da banca. Nada disto entra no tempo da apresentação.

- [ ] **Desligar a indexação de subpastas antes de indexar a vault.** A pasta `samples/manual validetion/` tem uma subpasta `new/` com notas `.md`, um currículo e uma carta de apresentação em PDF. Nada disso faz parte da validação. A indexação usa `corpus_recursive_default`, que vale `True` por padrão (`pipeline/src/escolio/app/config.py:92`), e a indexação pela UI não passa a opção (`pipeline/src/escolio/corpus/jobs.py:108`). Comando, dentro de `pipeline/`:

  ```powershell
  uv run escolio config set corpus_recursive_default false
  ```

  Ver `pipeline/src/escolio/config_cli.py:45-46`. A configuração parece ser global, então vale para todas as vaults: **a confirmar no ensaio**. Não encontrei um campo "Indexar subpastas" na tela de Configurações; o rótulo existe só em `pipeline/src/escolio/app/settings_specs.py:134-137`.

- [ ] **Criar a vault do demo.** Botão "Nova vault" na barra lateral (`UI/src/components/Sidebar.tsx:261`). Nome sugerido: `Escólio demo`. O botão de confirmação é "Criar vault" (`UI/src/components/VaultDialog.tsx:87`). A forma de escolher a pasta `samples/manual validetion/` no diálogo é **a confirmar no ensaio**: o backend cria a vault com `createVault(name, icon, color, folders)` (`UI/main.py:154`), mas o caminho exato da tela para escolher a pasta não foi conferido.

- [ ] **Indexar a pasta na Fila.** Escolher a pasta com "Escolher pasta" (`UI/src/components/QueuePanel.tsx:259`) e depois clicar em "Indexar" (`QueuePanel.tsx:261`). Conferir em "Notas" (`UI/src/components/NotesPanel.tsx:249`) se as notas do conjunto de validação aparecem.

- [ ] **Abrir o Ollama com o modelo de resposta.** O modelo usado nos experimentos é `qchat:latest` (Exp 21, comandos). Na aba "Fontes de IA" (`UI/src/components/SettingsModal.tsx:86`), o cartão do Ollama aponta para `localhost:11434` (`UI/src/components/AiSourcesPane.tsx:15`). Como escolher o modelo na tela é **a confirmar no ensaio**. No PC do autor, o ícone do Ollama não volta sozinho depois de reiniciar: abrir pelo `explorer.exe`.

- [ ] **Liberar memória.** A máquina tem 16 GB. O Exp 21 registra que uma rodada completa do benchmark com IA foi encerrada por falta de memória (`docs/experimentos/21_abstencao_e_faithfulness_com_ia.md`, seção Comandos). Fechar navegador e apps pesados antes de abrir o app.

- [ ] **Rodar o benchmark na véspera, se houver tempo.** Botão "Rodar comparação" (`UI/src/components/BenchmarkPanel.tsx:240`), com a suíte escolhida pelo botão "Selecionar suite" (`BenchmarkPanel.tsx:259`), em `data/datasets/manual_validation/suite.json`. O resultado da aba **não é recarregado** ao reabrir o app: o estado começa vazio (`BenchmarkPanel.tsx:145`). Por isso, no dia, ou a aba é mostrada na mesma sessão, ou se usa o arquivo exportado (ver Plano B). O tempo de uma rodada é **a confirmar no ensaio**; o Exp 21 cita cerca de 14 minutos para as três estratégias com IA.

- [ ] **Conferir o diagnóstico no terminal.** `.\es.ps1 doctor` (`es.ps1`, caso `doctor`, linha 78), que chama `escolio doctor` (`pipeline/src/escolio/cli.py:39`).

- [ ] **Abrir o app com antecedência.** `tcc app` é um alias desta máquina do autor para `.\es.ps1 app`. O `app` roda `npm --prefix UI run build` antes de abrir a janela PyWebView (`es.ps1`, caso `app`, linha 71). Esperar a janela carregar antes da banca.

### Cola de comandos (terminal)

```powershell
.\es.ps1 doctor                 # diagnóstico do ambiente (es.ps1:78)
tcc app                         # alias desta máquina para .\es.ps1 app (es.ps1:71)
.\es.ps1 bench compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json" --export
```

`es.ps1` entra na pasta `pipeline/` antes de executar o comando (função `Invoke-InPipeline`). Por isso, um caminho relativo como `data/datasets/...` não funciona no `bench`: usar o caminho absoluto, ou `../data/...` quando se roda `uv run` direto dentro de `pipeline/`. O Exp 20 usa `../data/...`.

---

## 3. Bloco 2: Diagnóstico (1:30, com abertura)

**Abertura (30 s).** Fala sugerida: "O Escólio é um assistente de perguntas sobre as minhas notas, que roda no meu computador. Cada resposta traz a fonte. Vou mostrar o que está funcionando, depois uma pergunta com resposta, uma sem resposta e o benchmark."

**Ação (1 min).**

1. Clicar no indicador "Corpus" da barra lateral (`UI/src/components/Sidebar.tsx:344`). Ele abre as Configurações na aba "Diagnóstico" (`UI/src/components/SettingsModal.tsx:84`, e o conteúdo `SettingsModal.tsx:735-755`). O painel lista as verificações com o nome de cada uma (`UI/src/components/DoctorPanel.tsx:95`), por exemplo "Banco de notas (SQLite)".
2. Alternativa no terminal: `.\es.ps1 doctor` (`es.ps1`, linha 78).

A barra lateral tem quatro vistas: Perguntar, Notas, Fila e Benchmark (`UI/src/components/Sidebar.tsx:44-47`). O diagnóstico não é uma vista própria: fica em Configurações.

---

## 4. Bloco 3: Indexação, Fila e grafo (1:00)

**Fila (30 s).** Abrir a vista "Fila" da barra lateral (`Sidebar.tsx:46`).

- A seção "Pastas no corpus" mostra as pastas indexadas e a contagem de notas (`UI/src/components/QueuePanel.tsx:69`).
- O botão "Reindexar" fica em cada pasta (`QueuePanel.tsx:90`). Mostrar, sem apertar.
- A lista "Ignorados na indexação" aparece em `UI/src/components/IgnoredFiles.tsx:44`.

**Não reindexar ao vivo.** O indicador "Ao vivo" aparece só enquanto um job de indexação está rodando (`UI/src/components/GraphPanel.tsx:154-159`; o estado vem de `UI/src/hooks/useCorpusGraph.ts:172-175`). Numa vault já indexada, ele não aparece. Reindexar ao vivo só faz sentido se o ensaio mostrar que a vault termina em tempo curto: **a confirmar no ensaio**. Se não, mostrar o grafo parado e explicar que o indicador aparece durante a indexação.

**Grafo (30 s).** Botão "Grafos" no cabeçalho (`UI/src/components/Header.tsx:192-198`). Abre o painel lateral com três modos: Pastas, Links e Ambos (`UI/src/components/GraphPanel.tsx:21-25`). O desenho usa Canvas 2D (`UI/src/components/ForceGraph.tsx:2` e `:111`).

**O grafo é 2D, não 3D.** O texto antigo do roteiro dizia "3D/2D". Não usar "3D".

---

## 5. Bloco 4: Pergunta com citação (2:30)

**Pergunta (P1):** "Quando o componente MAJOR deve ser incrementado?"

Digitar na aba "Perguntar" (`Sidebar.tsx:44`).

**Resposta esperada:** MAJOR é incrementado quando há mudanças incompatíveis com versões anteriores (breaking changes). Fonte: `samples/manual validetion/01_frontmatter_yaml.md`, seção "1. O que é SemVer", linha 22.

**Citação (1 min).**

1. A resposta traz a lista "Fontes" (`UI/src/components/MessageBubble.tsx:391`). Cada card mostra o título da nota, o trecho citado (`MessageBubble.tsx:422`) e a posição em caracteres, `char_start–char_end` (`MessageBubble.tsx:423-425`).
2. Clicar no título do card abre o botão "Abrir … no trecho citado" (`MessageBubble.tsx:414`). A nota abre na visualização de trechos, com o trecho citado destacado (`UI/src/components/NoteDetailView.tsx:244`, `highlightChunkId`). A cor do destaque é **a confirmar no ensaio** (o roteiro antigo dizia amarelo).

**Fala.** "Cada afirmação tem uma fonte, e quem confere clica e vai ao trecho exato."

**Honestidade (obrigatória na fala).** A citação pode ser conferida, mas o modelo de 3 bilhões de parâmetros às vezes associa um valor ou uma data à entidade errada. O Exp 21 registrou isso (2026-11-01).

---

## 6. Bloco 5: Pergunta sem resposta (1:00)

**Pergunta (N1):** "Qual é a política de home office da empresa?"

Os termos não aparecem em nenhum documento de `samples/manual validetion/`. A resposta correta é abster-se.

**Resposta esperada.**

- Rótulo "Sem resposta" no cabeçalho da mensagem (`UI/src/components/MessageBubble.tsx:505`).
- Título "Não encontrei isso no vault." (`MessageBubble.tsx:222`).
- Em "Detalhes técnicos", o motivo da abstenção (`MessageBubble.tsx:229-233`).
- Se a busca não foi léxica, aparece o botão "Buscar só por palavra-chave" (`MessageBubble.tsx:237`).

**Fala honesta (obrigatória).** "A abstenção não é 100%. Na versão final com IA, medida em 2026-11-01 (Exp 21), o sistema respondeu 6 de 34 perguntas sem resposta <!-- atualizar-exp22 -->. Com só trechos, medido em 2026-10-31 (Exp 20), respondeu 13 de 34 <!-- atualizar-exp22 -->."

**Se o modelo responder mesmo assim.** Não é falha da apresentação. Mostrar a citação e dizer que esta pergunta é um dos casos em que a regra não pegou, que aparece na medição.

---

## 7. Bloco 6: Benchmark e fechamento (2:00)

**Tela (1 min).** Aba "Benchmark" da barra lateral (`Sidebar.tsx:47`; título em `UI/src/components/BenchmarkPanel.tsx:234`). Mostrar o resultado já existente na sessão. **Não apertar "Rodar comparação"** (`BenchmarkPanel.tsx:240`) ao vivo.

Seções a mostrar:

- "Resultado por estratégia" (`BenchmarkPanel.tsx:298`), com MRR (`:13`) e "Latência p50" (`:324`).
- "Recall@k" (`BenchmarkPanel.tsx:365`).
- "Responder ou se abster" (`BenchmarkPanel.tsx:381-396`), com as colunas "Responde quando há resposta", "Se abstém quando não há" e "Decisão certa".

**O que os números significam (1 min).** Fonte: Exp 20, medido em 2026-10-31. Suíte de 10 notas, 39 perguntas positivas e 34 negativas. Resposta extrativa, sem geração por modelo de linguagem.

| Estratégia | MRR (IC 95%) | Recall@3 | Latência média por consulta |
|:---|:---:|:---:|:---:|
| Léxica (SQLite FTS5, BM25) | 0.910 [0.833; 0.962] | 1.000 | 1.2 ms |
| Vetorial (ChromaDB) | 0.816 [0.709; 0.915] | 0.923 | 69 ms |
| Híbrida RRF (k = 60) | 0.915 [0.842; 0.974] | 1.000 | 69 ms |

- **MRR** é a média do inverso da posição da primeira nota certa (`pipeline/src/escolio/benchmark/metrics.py:19-23`). Quanto mais perto de 1, mais cedo a nota certa aparece.
- **Recall@3** é a fração das perguntas em que a nota certa está entre os 3 primeiros resultados (`metrics.py:12`).
- **Leitura.** A léxica e a híbrida empatam: os intervalos quase se sobrepõem. A fusão não supera a léxica de forma distinguível nesta suíte. A híbrida supera a vetorial pura em MRR.
- **Negativas.** Com o extrativo, 13 de 34 foram respondidas em cada estratégia (Exp 20, 2026-10-31) <!-- atualizar-exp22 -->.
- **Latência.** A tela mostra p50 (`BenchmarkPanel.tsx:324`), e o Exp 20 reporta média. Os dois são **a confirmar no ensaio**: não é a mesma métrica.

**Fechamento (30 s).** "Os números vêm de uma suíte pequena, com gabarito feito pelo autor. Não afirmo que a híbrida é superior em geral."

---

## 8. Bloco 7: Plano B

Usar só quando houver falha. Não entra no tempo.

- **O Ollama cai ou não responde.** O app passa para a resposta extrativa e registra a limitação "A IA falhou; usando resposta extrativa. Erro: …" (`pipeline/src/escolio/corpus/ask_generation.py:47-48` e `:101-108`). A limitação aparece na seção "Limitações" da resposta (`MessageBubble.tsx:439`). Ação: seguir o roteiro e dizer que a resposta saiu sem modelo. Também é possível trocar para "Só trechos" (`UI/src/components/AiSourcesPane.tsx:14`; seletor "Como responder" em `UI/src/components/AnswerPicker.tsx:114-120`).

- **A indexação demora ou trava.** Não reindexar. Usar a vault já indexada na véspera: o chat responde a partir do corpus já indexado (`UI/main.py:14`). Não iniciar nova indexação durante a banca.

- **O microfone falha.** Pular o bloco de voz. O roteiro principal não depende de voz. Se for mostrar, Configurações, aba "Voz", botão "Testar microfone" (`UI/src/components/MicTest.tsx:76`). O teste grava 3 segundos e não guarda nem transcreve o áudio, segundo o próprio texto da tela.

- **O benchmark sumiu (o app foi reiniciado).** Não rodar ao vivo. Mostrar o resultado exportado na véspera (`--export`, `pipeline/src/escolio/benchmark/cli.py:183`). Que o arquivo fique em `data/results` é **a confirmar no ensaio**.

- **Memória baixa.** Fechar todos os apps que não são o Escólio. Não reindexar nem rodar benchmark.

---

## 9. Perguntas de demonstração (todas a ensaiar)

Todas as respostas foram conferidas nos documentos de `samples/manual validetion/`. Nenhuma foi rodada no app.

### Positivas

| # | Pergunta | Documento e trecho | Resposta esperada |
|:---:|:---|:---|:---|
| P1 | Quando o componente MAJOR deve ser incrementado? | `01_frontmatter_yaml.md`, seção "1. O que é SemVer", linha 22 | Quando há mudanças incompatíveis com versões anteriores (breaking changes). |
| P2 | Qual tipo de SCD preserva o histórico completo adicionando nova linha? | `10_documento_longo_modelagem_dados.md`, seção "1.3 Slowly Changing Dimensions (SCD)", linha 41 | SCD Tipo 2 (Adicionar linha). |
| P3 | Quais ferramentas geram changelog automático a partir dos commits? | `01_frontmatter_yaml.md`, seção "3.2 Conventional Commits e CHANGELOG automático", linha 91 | commitizen ou git-cliff. |

Reserva, se P1 falhar: "Qual é o erro mais prejudicial ao versionar um pacote?" Fonte: `01_frontmatter_yaml.md`, seção "4. Erros Comuns e Como Evitá-los", linha 97 (incrementar MINOR para um breaking change).

### Sem resposta

| # | Pergunta | Por que deve ser abstenção | Resposta esperada |
|:---:|:---|:---|:---|
| N1 | Qual é a política de home office da empresa? (`neg2-14`) | Nenhum documento de `samples/manual validetion/` cita home office. | Sem resposta. |
| N2 | Quando acontece a festa de fim de ano da equipe? (`neg2-15`) | Nenhum documento cita festa nem fim de ano. | Sem resposta. |

As perguntas `neg2-*` foram escritas depois do ajuste da regra e medidas sem ajuste, segundo `data/datasets/manual_validation/README.md`. As `neg-*` foram usadas para calibrar a regra: não usar como prova de abstenção na banca.

---

## 10. Possíveis perguntas da banca

**Por que a abstenção não é 100%?**
A regra combina vocabulário e validação da resposta gerada. Com só trechos, o Exp 20 respondeu 13 de 34 perguntas sem resposta (2026-10-31) <!-- atualizar-exp22 -->. Com IA, a versão final respondeu 6 de 34 (Exp 21, 2026-11-01) <!-- atualizar-exp22 -->, ao custo de positivas: 38 de 39 no extrativo e 33 de 39 na versão final. Exigir span em toda resposta zerou as negativas, mas derrubou 11 positivas, então foi descartado (Exp 21). A regra foi calibrada com parte das negativas; as `neg2-*` foram medidas sem ajuste.

**Por que local-first?**
Os dados e os índices (SQLite e ChromaDB) ficam no computador do usuário. O Ollama roda na máquina (`UI/src/components/AiSourcesPane.tsx:15`). O app também aceita provedores na nuvem (OpenAI, OpenRouter, Groq, Gemini; `AiSourcesPane.tsx:8-11`), mas é uma escolha explícita: o padrão de resposta é o extrativo, sem modelo (`pipeline/src/escolio/app/config.py:73-74`). O modelo de embedding padrão é `chroma-default` (`config.py:68`); se ele roda sem rede depois do primeiro uso, é **a confirmar no ensaio**.

**O que é RRF?**
Reciprocal Rank Fusion. Junta a ordem da busca léxica e a da vetorial: cada resultado recebe 1/(k + posição) em cada ranking, e as pontuações são somadas (`pipeline/src/escolio/retrieval/search.py:420`). Os padrões são k = 60, peso léxico 1.5 e peso vetorial 1.0 (`search.py:10-12`). A vantagem é não precisar normalizar as pontuações das duas buscas, que estão em escalas diferentes. Nesta suíte, a fusão empata com a léxica (Exp 20).

**O que o benchmark não mede?**
1. Não tem gabarito independente: as perguntas e o gabarito são do autor (Exp 20, limitações).
2. A suíte é pequena: 10 notas, 39 perguntas positivas e 34 negativas. O intervalo do MRR é largo.
3. O recall satura na léxica e na híbrida, então a métrica pouco separa as duas.
4. Faithfulness não foi medida no Exp 20. No Exp 21, o juiz é um modelo de 3B e a auditoria foi feita por uma pessoa.
5. Na IA, há uma rodada por configuração. O ruído entre rodadas é de cerca de ±3 perguntas em 39 (Exp 21).
6. Não mede uso real nem outras máquinas.
7. O MRR de 0.942 do Exp 17 não foi reconciliado com o 0.915 do Exp 20 (Exp 20, relação com outros experimentos).

**A IA inventa informação?**
Às vezes. No Exp 21, após auditoria manual, cerca de 34 das 39 afirmações geradas (≈ 87%) estavam sustentadas pelos trechos citados. Foram 5 alucinações reais, como o caso `docker-04`, em que o modelo respondeu "SCD Tipo 1" trazendo um trecho de outro documento (a resposta correta é `tmpfs`). Por isso `docker-04` não entra na demonstração.

---

## 11. Observações para o autor (não falar na banca sem conferir)

- No Exp 21, a linha "IA, checagem de span só como segunda chance (versão final)" da tabela de abstenção diz 33/39 positivas, 6/34 negativas e **60/73** decisões certas. Mas 33 + (34 − 6) = 61, não 60. Conferir no JSON da rodada antes de citar "60 de 73" <!-- atualizar-exp22 -->.
- Os números de abstenção deste roteiro têm o comentário `<!-- atualizar-exp22 -->` e devem ser atualizados quando o Exp 22 sair.

---

## 12. Fontes dos números

- `docs/experimentos/20_benchmark_recuperacao_reproduzido.md`, medido em 2026-10-31.
- `docs/experimentos/21_abstencao_e_faithfulness_com_ia.md`, medido em 2026-11-01.
- `data/datasets/manual_validation/README.md` e `suite.json`, para a origem das perguntas.
