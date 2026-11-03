# Roteiro de demonstração para a banca: Escólio

Roteiro cronometrado para a apresentação do TCC, atualizado em 2026-11-02.

As telas, botões e comandos citados foram conferidos no código nessa data. O que não foi confirmado está marcado como **a confirmar no ensaio**. Nenhuma pergunta de demonstração foi rodada no app ainda: todas estão **a ensaiar**.

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

- [ ] **Separar os documentos da demo.** A pasta `samples/manual validetion/` tem uma subpasta `new/` com notas, um currículo e uma carta em PDF, que não fazem parte da validação, e a indexação entra em subpastas por padrão. Em vez de mudar essa configuração, que parece global, copiar só os 10 documentos da suíte para uma pasta própria. Na raiz do repositório:

  ```powershell
  $demo = "$HOME\Documents\Escolio-demo"
  New-Item -ItemType Directory -Force $demo | Out-Null
  (Get-Content data\datasets\manual_validation\suite.json -Raw -Encoding UTF8 | ConvertFrom-Json).cases |
    ForEach-Object { Copy-Item -LiteralPath $_.document_path -Destination $demo }
  ```

- [ ] **Criar a vault da demo.** Botão "Nova vault" na barra lateral, nome sugerido `Escólio demo`, confirmar em "Criar vault". Como escolher a pasta no diálogo é **a confirmar no ensaio**.

- [ ] **Indexar a pasta na Fila.** "Escolher pasta" e depois "Indexar". Conferir em "Notas" se aparecem as 10 notas.

- [ ] **Abrir o Ollama com o modelo de resposta.** O modelo usado nos experimentos é `qchat:latest` (Exp 21, comandos). Na aba "Fontes de IA", o cartão do Ollama aponta para `localhost:11434`. Como escolher o modelo na tela é **a confirmar no ensaio**. No PC do autor, o ícone do Ollama não volta sozinho depois de reiniciar: abrir pelo `explorer.exe`.

- [ ] **Liberar memória.** A máquina tem 16 GB. O Exp 21 registra que uma rodada completa do benchmark com IA foi encerrada por falta de memória. Fechar navegador e apps pesados antes de abrir o app.

- [ ] **Rodar o benchmark na véspera, se houver tempo.** Botão "Rodar comparação", com a suíte escolhida pelo botão "Selecionar suite", em `data/datasets/manual_validation/suite.json`. O resultado da aba **não é recarregado** ao reabrir o app: o estado começa vazio. Por isso, no dia, ou a aba é mostrada na mesma sessão, ou se usa o arquivo exportado (ver Plano B). O tempo de uma rodada é **a confirmar no ensaio**; o Exp 21 cita cerca de 14 minutos para as três estratégias com IA.

- [ ] **Conferir o diagnóstico no terminal.** `.\es.ps1 doctor`, que chama `escolio doctor`.

- [ ] **Abrir o app com antecedência.** `tcc app` é um alias desta máquina do autor para `.\es.ps1 app`. O `app` roda `npm --prefix UI run build` antes de abrir a janela PyWebView. Esperar a janela carregar antes da banca.

### Cola de comandos (terminal)

```powershell
.\es.ps1 doctor                 # diagnóstico do ambiente
tcc app                         # alias desta máquina para .\es.ps1 app
.\es.ps1 bench compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json" --export
```

`es.ps1` entra na pasta `pipeline/` antes de executar o comando (função `Invoke-InPipeline`). Por isso, um caminho relativo como `data/datasets/...` não funciona no `bench`: usar o caminho absoluto, ou `../data/...` quando se roda `uv run` direto dentro de `pipeline/`. O Exp 20 usa `../data/...`.

---

## 3. Bloco 2: Diagnóstico (1:30, com abertura)

**Abertura (30 s).** Fala sugerida: "O Escólio é um assistente de perguntas sobre as minhas notas, que roda no meu computador. Cada resposta traz a fonte. Vou mostrar o que está funcionando, depois uma pergunta com resposta, uma sem resposta e o benchmark."

**Ação (1 min).**

1. Clicar no indicador "Corpus" da barra lateral. Ele abre as Configurações na aba "Diagnóstico". O painel lista as verificações com o nome de cada uma, por exemplo "Banco de notas (SQLite)".
2. Alternativa no terminal: `.\es.ps1 doctor`.

A barra lateral tem quatro vistas: Perguntar, Notas, Fila e Benchmark. O diagnóstico não é uma vista própria: fica em Configurações.

---

## 4. Bloco 3: Indexação, Fila e grafo (1:00)

**Fila (30 s).** Abrir a vista "Fila" da barra lateral.

- A seção "Pastas no corpus" mostra as pastas indexadas e a contagem de notas.
- O botão "Reindexar" fica em cada pasta. Mostrar, sem apertar.
- A lista "Ignorados na indexação" mostra o que ficou de fora.

**Não reindexar ao vivo.** O indicador "Ao vivo" aparece só enquanto um job de indexação está rodando. Numa vault já indexada, ele não aparece. Reindexar ao vivo só faz sentido se o ensaio mostrar que a vault termina em tempo curto: **a confirmar no ensaio**. Se não, mostrar o grafo parado e explicar que o indicador aparece durante a indexação.

**Grafo (30 s).** Botão "Grafos" no cabeçalho. Abre o painel lateral com três modos: Pastas, Links e Ambos. O desenho usa Canvas 2D.

**O grafo é 2D, não 3D.** O texto antigo do roteiro dizia "3D/2D". Não usar "3D".

---

## 5. Bloco 4: Pergunta com citação (2:30)

**Pergunta (P1):** "Quando o componente MAJOR deve ser incrementado?"

Digitar na aba "Perguntar".

**Resposta esperada:** MAJOR é incrementado quando há mudanças incompatíveis com versões anteriores (breaking changes). Fonte: `samples/manual validetion/01_frontmatter_yaml.md`, seção "1. O que é SemVer", linha 22.

**Citação (1 min).**

1. A resposta traz a lista "Fontes". Cada card mostra o título da nota, o trecho citado e a posição em caracteres, `char_start–char_end`.
2. Clicar no título do card abre o botão "Abrir … no trecho citado". A nota abre na visualização de trechos, com o trecho citado destacado. A cor do destaque é **a confirmar no ensaio** (o roteiro antigo dizia amarelo).

**Fala.** "Cada afirmação tem uma fonte, e quem confere clica e vai ao trecho exato."

**Honestidade (obrigatória na fala).** A citação pode ser conferida, mas o modelo de 3 bilhões de parâmetros às vezes associa um valor ou uma data à entidade errada. O Exp 21 registrou isso (2026-11-01).

---

## 6. Bloco 5: Pergunta sem resposta (1:00)

**Pergunta (N1):** "Qual é a política de home office da empresa?"

Os termos não aparecem em nenhum documento de `samples/manual validetion/`. A resposta correta é abster-se.

**Resposta esperada.**

- Rótulo "Sem resposta" no cabeçalho da mensagem.
- Título "Não encontrei isso no vault.".
- Em "Detalhes técnicos", o motivo da abstenção.
- Se a busca não foi léxica, aparece o botão "Buscar só por palavra-chave".

**Fala honesta (obrigatória).** "A abstenção não é 100%. Num lote de perguntas escrito sem olhar o sistema, medido em 2026-11-02 (Exp 22), o app com IA ainda respondeu 10 ou 11 de 39 perguntas sem resposta; sem IA, 19 de 39. No lote usado na calibração, com IA, foram de 3 a 7 de 34."

**Se o modelo responder mesmo assim.** Não é falha da apresentação. Mostrar a citação e dizer que esta pergunta é um dos casos em que a regra não pegou, que aparece na medição.

---

## 7. Bloco 6: Benchmark e fechamento (2:00)

**Tela (1 min).** Aba "Benchmark" da barra lateral. Mostrar o resultado já existente na sessão. **Não apertar "Rodar comparação"** ao vivo.

Seções a mostrar:

- "Resultado por estratégia", com MRR e "Latência p50".
- "Recall@k".
- "Responder ou se abster", com as colunas "Responde quando há resposta", "Se abstém quando não há" e "Decisão certa".

**O que os números significam (1 min).** Fonte: Exp 20, medido em 2026-10-31. Suíte de 10 notas, 39 perguntas positivas e 34 negativas. Resposta extrativa, sem geração por modelo de linguagem.

| Estratégia | MRR (IC 95%) | Recall@3 | Latência média por consulta |
|:---|:---:|:---:|:---:|
| Léxica (SQLite FTS5, BM25) | 0.910 [0.833; 0.962] | 1.000 | 1.2 ms |
| Vetorial (ChromaDB) | 0.816 [0.709; 0.915] | 0.923 | 69 ms |
| Híbrida RRF (k = 60) | 0.915 [0.842; 0.974] | 1.000 | 69 ms |

- **MRR** é a média do inverso da posição da primeira nota certa. Quanto mais perto de 1, mais cedo a nota certa aparece.
- **Recall@3** é a fração das perguntas em que a nota certa está entre os 3 primeiros resultados.
- **Leitura.** A léxica e a híbrida empatam: os intervalos quase se sobrepõem. A fusão não supera a léxica de forma distinguível nesta suíte. A híbrida supera a vetorial pura em MRR.
- **Corpus completo.** A tabela é o resumo por nota. Buscando em todas as notas, a híbrida dá MRR 0,944 e Recall@3 1,000 no lote calibrado, e MRR 0,811 e Recall@3 0,946 no lote cego (Exp 22, 2026-11-02). Qual dos dois a tela mostra é **a confirmar no ensaio**.
- **Negativas.** Sem IA, a híbrida respondeu 13 de 34 no lote calibrado (Exp 20 e 22) e 19 de 39 no lote cego (Exp 22).
- **Latência.** A tela mostra p50, e o Exp 20 reporta média. Os dois são **a confirmar no ensaio**: não é a mesma métrica.

**Fechamento (30 s).** "Os números vêm de uma suíte pequena, com gabarito feito pelo autor. Não afirmo que a híbrida é superior em geral."

---

## 8. Bloco 7: Plano B

Usar só quando houver falha. Não entra no tempo.

- **O Ollama cai ou não responde.** O app passa para a resposta extrativa e registra a limitação "A IA falhou; usando resposta extrativa. Erro: …". A limitação aparece na seção "Limitações" da resposta. Ação: seguir o roteiro e dizer que a resposta saiu sem modelo. Também é possível trocar para "Só trechos".

- **A indexação demora ou trava.** Não reindexar. Usar a vault já indexada na véspera: o chat responde a partir do corpus já indexado. Não iniciar nova indexação durante a banca.

- **O microfone falha.** Pular o bloco de voz. O roteiro principal não depende de voz. Se for mostrar, Configurações, aba "Voz", botão "Testar microfone". O teste grava 3 segundos e não guarda nem transcreve o áudio, segundo o próprio texto da tela.

- **O benchmark sumiu (o app foi reiniciado).** Não rodar ao vivo. Mostrar o resultado exportado na véspera. Que o arquivo fique em `data/results` é **a confirmar no ensaio**.

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
A regra combina vocabulário e validação da resposta gerada, e recusar mais também derruba respostas certas: exigir span em toda resposta zerou as negativas, mas derrubou 11 positivas, e foi descartado (Exp 21). No lote cego, com IA, a abstenção ficou entre 72% e 74% (IC 95% de 56% a 85%). O ponto fraco é a pergunta sobre algo que a nota quase diz: 8 ou 9 de 14 foram respondidas (Exp 22).

**O resultado se sustenta em perguntas novas?**
Só em parte, e é por isso que medimos. A regra foi calibrada no lote antigo. Num lote novo, congelado antes da medição e escrito por um agente de IA que só leu os documentos, as decisões certas com IA caíram de 89% para 71%, e sem IA, de 81% para 51%. A recuperação também caiu, de MRR 0,944 para 0,811. O lote cego tem mais paráfrase, e a medição não separa o quanto vem da regra e o quanto vem do modelo. Os intervalos são largos, com 37 positivas e 39 negativas (Exp 22).

**Por que local-first?**
Os dados e os índices (SQLite e ChromaDB) ficam no computador do usuário. O Ollama roda na máquina. O app também aceita provedores na nuvem, mas é uma escolha explícita: o padrão de resposta é o extrativo, sem modelo. O modelo de embedding padrão é `chroma-default`; se ele roda sem rede depois do primeiro uso, é **a confirmar no ensaio**.

**O que é RRF?**
Reciprocal Rank Fusion. Junta a ordem da busca léxica e a da vetorial: cada resultado recebe 1/(k + posição) em cada ranking, e as pontuações são somadas. Os padrões são k = 60, peso léxico 1.5 e peso vetorial 1.0. A vantagem é não precisar normalizar as pontuações das duas buscas, que estão em escalas diferentes. Nesta suíte, a fusão empata com a léxica (Exp 20).

**O que o benchmark não mede?**
1. Não tem gabarito independente: o lote calibrado é do autor (Exp 20, limitações), e o lote cego foi escrito por um agente de IA, sem revisão humana (Exp 22).
2. A suíte é pequena: 10 notas, 39 perguntas positivas e 34 negativas. O intervalo do MRR é largo.
3. O recall satura na léxica e na híbrida, então a métrica pouco separa as duas.
4. Faithfulness não foi medida no Exp 20. No Exp 21, o juiz é um modelo de 3B e a auditoria foi feita por uma pessoa.
5. Na IA, há três rodadas por lote. Entre elas, 8 perguntas mudaram de decisão no lote calibrado e 5 no lote cego (Exp 22).
6. Não mede uso real nem outras máquinas.
7. Dois MRR aparecem nos documentos porque medem coisas diferentes: 0,915 é por nota isolada, e 0,944, no corpus completo (Exp 22).

**A IA inventa informação?**
Às vezes. No Exp 21, após auditoria manual, cerca de 34 das 39 afirmações geradas (≈ 87%) estavam sustentadas pelos trechos citados. Foram 5 alucinações reais, como o caso `docker-04`, em que o modelo respondeu "SCD Tipo 1" trazendo um trecho de outro documento (a resposta correta é `tmpfs`). Por isso `docker-04` não entra na demonstração.

---

## 11. Observações para o autor (não falar na banca sem conferir)

- No Exp 21, a linha "IA, checagem de span só como segunda chance (versão final)" da tabela de abstenção diz 33/39 positivas, 6/34 negativas e **60/73** decisões certas. Mas 33 + (34 − 6) = 61, não 60. O JSON dessa rodada não está na máquina, então não cite "60 de 73"; use os números do Exp 22.
- O lote cego ainda não foi revisado pelos autores. Revise as perguntas antes de citar esses números no texto final, sem trocar nenhuma depois de ver o resultado. O Exp 22 lista as quatro de que há dúvida.

---

## 12. Fontes dos números

- `docs/experimentos/20_benchmark_recuperacao_reproduzido.md`, medido em 2026-10-31.
- `docs/experimentos/21_abstencao_e_faithfulness_com_ia.md`, medido em 2026-11-01.
- `docs/experimentos/22_lote_cego_e_gate_ia.md`, medido em 2026-11-02.
- `data/datasets/manual_validation/README.md` e `suite.json`, para a origem das perguntas.
