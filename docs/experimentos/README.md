# Registro de Experimentos

## Objetivo

Esta pasta existe para registrar experimentos tecnicos do backend de forma reaproveitavel no TCC.

Ela deve servir para:

- guardar o historico de testes relevantes
- registrar configuracoes e resultados
- facilitar citacao posterior no texto do TCC
- evitar que comparacoes importantes fiquem so no terminal ou no chat

## Regra de organizacao

Cada experimento relevante deve gerar um novo arquivo Markdown numerado.

Padrao:

```text
01_nome_curto_do_experimento.md
02_nome_curto_do_experimento.md
03_nome_curto_do_experimento.md
```

## Conteudo minimo por experimento

Cada arquivo deve registrar, no minimo:

1. objetivo
2. hipotese ou pergunta
3. corpus ou suite usada
4. comando executado
5. configuracoes relevantes
6. resultados
7. interpretacao tecnica
8. proximos passos

## Regra pratica

Se um teste gerou uma decisao tecnica, uma comparacao importante ou um numero que pode aparecer no TCC, ele deve entrar aqui.

## Pendencias

- **Experimento 15 (`15_calibracao_rrf_tcc.md`): proveniencia nao verificada.** Os numeros (MRR 0.884 / Recall@3 0.915 / Recall@5 0.950 para RRF k=60) nao foram reproduzidos em 2026-10-25 (commit `4e18932`): nem na suite atual (MRR hibrido 0.942 na passada no corpus, o mesmo do exp. 17), nem na suite de 4 casos de `88e4fc8`, nem com o codigo de `88e4fc8`. Nao ha script, config, saida ou teste que os gere, e os Recall@k so podem ser fracoes de N=200 consultas, nao de 39 nem de 16. Acao: achar a origem ou refazer a medicao com suite, profundidade, pesos e IC declarados. Detalhes no proprio doc 15.
