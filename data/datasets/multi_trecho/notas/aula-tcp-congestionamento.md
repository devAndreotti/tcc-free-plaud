# Aula 11 - Controle de congestionamento no TCP

**Data:** 02/10/2025
**Disciplina:** Redes de Computadores
**Professora:** Vanessa Okada

Pessoal, quem perdeu a aula 10 pode pegar o slide no drive, mas a parte de hoje cai na prova, então prestem atenção nos números.

## Slow start

A janela de congestionamento, o cwnd, começa em 10 MSS. Esse valor vem da RFC 6928 e substituiu o antigo padrão de 1 segmento. Depois disso a janela dobra a cada RTT, até bater no ssthresh. A partir daí entra em congestion avoidance e cresce uma unidade por RTT, bem mais devagar.

A Vanessa fez a conta no quadro: com RTT de 100 ms, a janela sai de 10 para 1280 segmentos em uns 700 ms. Ninguém acredita até ver a conta, então façam em casa.

## Perda

Se der timeout, o TCP volta o cwnd para 1 e o ssthresh vira metade da janela atual. Já se chegarem três ACKs duplicados, acontece o fast retransmit, seguido de fast recovery, e a janela não zera. Essa diferença é a que mais cai em prova, porque muita gente decora só uma das duas situações.

## Alternativas

O BBR, desenvolvido pelo Google, estima a banda disponível e o RTT mínimo, em vez de usar a perda como sinal de congestionamento. A Vanessa comentou que ele é usado em boa parte do tráfego de vídeo, mas que o comportamento mudou de uma versão para outra e ela não quer afirmar detalhes sem conferir.

Um aluno perguntou sobre o Cubic, que é o padrão em muitos sistemas Linux. A Vanessa disse que ele usa uma função cúbica para a janela e que vale ler o artigo original antes de citar números.

## Laboratório

Lab 3: capturar uma transferência grande com curl no Wireshark e salvar a captura como lab3.pcapng. Depois medir o tempo até o cwnd estabilizar. A entrega é até 09/10/2025, pelo sistema da disciplina, sem prorrogação.

## Avaliação

A prova P2 é no dia 16/10/2025 e cai tudo desta aula e da anterior. A Vanessa disse que a questão de cálculo de janela é quase certa, então treinem o exemplo do quadro até ficar automático.
