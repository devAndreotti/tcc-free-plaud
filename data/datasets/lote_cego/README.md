# Lote cego de perguntas

Lote de avaliação escrito para medir o Escólio sem viés de calibração.

## Como foi escrito

Foi escrito por um agente de IA que só leu os 10 documentos de `samples/manual validetion/`. O agente não viu as perguntas antigas, o código, a regra de abstenção nem as métricas. Os autores do TCC ainda não revisaram este lote.

## Composição

- 37 perguntas positivas: 4 por documento, exceto `05_estudo_docker_fragmentado` e `07_pdf_tecnico_estruturado` (3 cada) e `09_nota_muito_curta` (3). Cada `expected_terms` é copiado literalmente do trecho que responde, inclusive o ruído de OCR do documento 06. O autor buscou paráfrase em pelo menos metade das perguntas de cada documento; isso não foi medido.
- 39 perguntas negativas (`negativas.json`), com resposta ausente dos 10 documentos, conferida por releitura: 14 `quase-acerto`, 13 `fora-do-dominio` e 12 `vocabulario-presente`.
- `suite.json` liga cada documento ao seu conjunto de perguntas e aponta para as negativas.

## Revisão antes do congelamento

Antes de qualquer medição, um segundo agente comparou o lote com as perguntas antigas e com o texto normalizado. Nenhum termo esperado se perdeu na normalização. Saíram três perguntas:

- `lc-05-a`: praticamente igual a uma pergunta do lote antigo (similaridade 0,97).
- `lc-07-c`: paráfrase de uma pergunta do lote antigo (similaridade 0,80).
- `lcn-15`: ambígua, porque a nota cita "5s" como hipótese para produção.

Os demais identificadores não foram renumerados.

## Congelamento

O lote foi congelado antes da primeira medição. Não deve ser ajustado depois de ver resultados: nenhuma pergunta, termo ou rótulo pode ser trocado para melhorar ou piorar um número. Se houver erro de escrita, registrar o erro e a correção separadamente, sem reaproveitar a medição anterior.
