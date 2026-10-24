# Decisão técnica: cache do catálogo de produtos

**Data:** 27/08/2025
**Autor:** Diego Sampaio
**Status:** aprovada

## Problema

O endpoint de listagem do catálogo bate no PostgreSQL em toda requisição, e no pico passa de 900 consultas por segundo. A maior parte dos dados muda devagar, então o cache faz sentido, mas o time ainda não tinha decidido onde guardar nem como invalidar.

## Opções consideradas

1. Memcached: simples, mas a política de eviction não deixa controlar por prefixo, e a gente precisa invalidar por grupo de categoria.
2. Redis com TTL: o time já usa Redis no projeto de sessão, então ninguém precisa aprender ferramenta nova.
3. Cache em memória por instância: descartada. Com 6 pods, a consistência vira bagunça e cada um responde uma coisa diferente.

## Decisão

Vamos com Redis. As chaves seguem o formato cat:v3:{categoria_id}:{pagina}. O TTL da listagem é de 15 minutos. Já o preço tem TTL de 60 segundos, porque preço muda rápido e não pode ficar defasado por muito tempo.

A versão do prefixo está no nome da chave de propósito. Quando o formato muda, a gente sobe para v4 e deixa a v3 expirar sozinha, sem migração.

## Stampede

Quando uma chave expira e 300 requisições chegam juntas, o banco leva o golpe inteiro. Para evitar isso usamos single-flight: um lock chamado lock:catalogo com expiração de 5 segundos. Quem não pega o lock espera 50 ms e tenta ler o cache de novo. Se ainda não tiver nada, aí sim consulta o banco.

## Invalidação

Quando a categoria muda, o publicador apaga as chaves cat:v3:{categoria_id}:* usando SCAN, nunca KEYS, porque KEYS trava o Redis em produção. Esse aprendizado veio de um incidente de 2024 que ninguém quer repetir.

## Riscos

A tela de preço pode mostrar dados de até 60 segundos atrás. A Carla, de produto, aceitou esse risco por escrito, desde que o carrinho sempre consulte o preço no momento do checkout.

## Revisão

Revisar a decisão em 30/11/2025, olhando o hit rate e o número de consultas ao banco. A meta é hit rate acima de 85%. Se ficar abaixo disso por duas semanas seguidas, reavaliamos o TTL da listagem.
