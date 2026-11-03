# Lote cego de perguntas

Lote de avaliação escrito para medir o Escólio sem viés de calibração.

## Como foi escrito

Foi escrito por um agente de IA que só leu os 10 documentos de `samples/manual validetion/`. O agente não viu as perguntas antigas, o código, a regra de abstenção nem as métricas. Os autores do TCC ainda não revisaram este lote.

## Composição

- 39 perguntas positivas: 4 por documento, exceto `09_nota_muito_curta` (3). Cada `expected_terms` é copiado literalmente do trecho que responde, inclusive o ruído de OCR do documento 06. Pelo menos metade das perguntas de cada documento é paráfrase.
- 40 perguntas negativas (`negativas.json`), com resposta ausente dos 10 documentos: 15 `quase-acerto`, 13 `fora-do-dominio` e 12 `vocabulario-presente`.
- `suite.json` liga cada documento ao seu conjunto de perguntas e aponta para as negativas.

## Congelamento

O lote foi congelado antes da primeira medição. Não deve ser ajustado depois de ver resultados: nenhuma pergunta, termo ou rótulo pode ser trocado para melhorar ou piorar um número. Se houver erro de escrita, registrar o erro e a correção separadamente, sem reaproveitar a medição anterior.
