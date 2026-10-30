# Aula 06 - Particionamento e formato colunar

**Data:** 04/04/2025
**Disciplina:** Engenharia de Dados II
**Professor:** Heitor Rocha

Bom, pessoal, hoje a gente fala de como organizar arquivo no data lake sem sofrer depois. Quem mexeu com CSV gigante sabe a dor.

## Formatos colunares

Parquet guarda os dados por coluna. Se a query pede só 3 colunas de 80, o scan lê uma fração do arquivo. Além disso comprime melhor, porque valores parecidos ficam juntos. O ORC é parecido e aparece bastante no ecossistema Hive. O Avro é por linha, então é mais útil pra escrita de stream do que pra analytics.

O Heitor insistiu que CSV não é formato de analytics. Pode ser de intercâmbio, mas quem faz query em cima de CSV está pagando juros.

## Particionamento

Partição é basicamente pasta. Se você particiona por ano_mes, uma query com filtro de data pula as pastas que não interessam, e isso se chama partition pruning. Mas cuidado com a cardinalidade. Particionar por cliente_id com 2 milhões de clientes gera milhões de arquivinhos pequenos, e aí o problema vira small files, que mata o planejador.

A regra de bolso que o Heitor passou é mirar entre 128 MB e 1 GB por arquivo. Abaixo disso o overhead de abrir arquivo domina, e acima disso o paralelismo fica ruim. Ele mostrou um gráfico de um job que caiu de 40 minutos pra 6 só ajustando o tamanho dos arquivos.

## Data skew

Se 1% dos clientes concentra 40% dos eventos, o job particionado por cliente_id vai ter um executor trabalhando muito mais que os outros, e os demais ficam esperando. Isso é data skew. A solução mais comum é o salting: adicionar um sufixo aleatório na chave quente, espalhar o trabalho e agregar no final. O Heitor disse que dá trabalho, mas funciona.

## Exercício

Pegar o arquivo vendas_2024.csv, que tem uns 9 GB, converter para Parquet particionado por ano_mes e comparar o tempo de uma query que filtra março de 2024 antes e depois. A entrega é até 18/04/2025. Quem usar Delta Lake ganha um ponto extra, mas o Heitor avisou que não é obrigatório e que a nota base já cobre o exercício.

Dúvidas pelo fórum da disciplina. Não mandem e-mail pessoal para o professor, por favor.
