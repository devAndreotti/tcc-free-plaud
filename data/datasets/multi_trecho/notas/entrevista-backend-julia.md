# Entrevista técnica - vaga Backend Pleno

**Data:** 18/06/2025
**Candidata:** Júlia Neves
**Entrevistadores:** Marcos Pimenta e Rafaela Duarte

## Abertura

A Júlia chegou no horário e começou falando da experiência com FastAPI e com filas. Contou que trabalhou dois anos num marketplace pequeno e que a maior parte do que aprendeu foi debugando produção sozinha. A Rafaela perguntou por que ela quer sair, e a resposta foi falta de code review e de alguém pra discutir decisão de arquitetura.

## Desafio técnico (take-home)

O desafio pedia uma API de cupons com limite de 100 requisições por minuto por cliente. A Júlia usou sliding window com Redis e deixou o limite em configuração, o que foi um ponto positivo. Ela esqueceu de tratar o caso em que o Redis cai. Quando a Rafaela perguntou, ela respondeu que faria fail-open com alerta, e a Rafaela acha que essa resposta é razoável para esse tipo de limite.

O código tinha testes unitários, mas nenhum teste de concorrência. O Marcos mencionou isso logo no início da discussão.

## Avaliação técnica

- Modelagem de dados: boa. Usou índice composto em cupom_codigo e usado_em, o que faz sentido para a consulta de histórico.
- Concorrência: entendeu a race condition no resgate do cupom, mas a primeira versão fazia SELECT antes do UPDATE sem lock. O Marcos apontou, e ela corrigiu com UPDATE condicional na hora, o que foi bem visto.
- Observabilidade: falou de logs estruturados e de métricas por rota, mas não lembrou de tracing distribuído. Ficou como ponto a estudar.
- Comunicação: clara e objetiva. Pediu feedback no meio da entrevista, algo que a Rafaela anotou como sinal positivo.

## Parecer

Nota final de 4 de 5 nas duas rubricas técnicas. Recomendação: avançar para a rodada com o time de produto. A Rafaela quer que a Júlia apresente o desafio para o Diego, que é do time de pagamentos, porque ele pode avaliar melhor a parte de concorrência.

O Marcos ressaltou que o nível é pleno, mas que ela tem potencial de sênior em uns dois anos se mantiver o ritmo de estudo.

## Encaminhamento

Retorno para a candidata pelo RH até 25/06/2025. A faixa salarial não entra nesta ata e deve ser tratada pelo RH com a própria Júlia.
