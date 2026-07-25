# Planejamento da Migração de Banco de Dados

## Status

| Item | Responsável | Prazo | Concluído |
|------|-------------|-------|-----------|
| Backup completo | Pedro | 10/03 | ✅ |
| Script de migração | Ana | 14/03 | ✅ |
| Teste em staging | Rafael | 17/03 | ❌ |
| Janela de manutenção | Pedro | 21/03 | ❌ |
| Rollback documentado | Ana | 21/03 | ❌ |

## Checklist Pré-Migração

- [x] Backup do banco de produção validado (checksum OK)
- [x] Script de migração revisado por dois engenheiros
- [x] Ambiente de staging com cópia real dos dados
- [ ] Dry-run do script em staging sem erros
- [ ] Janela de manutenção comunicada aos usuários
- [ ] Plano de rollback testado em staging
- [ ] Monitoramento pós-migração configurado

## Riscos

### Risco 1

downtime

### Risco 2

perda de dados

### Risco 3

incompatibilidade de schema

### Risco 4

timeout em tabelas grandes

## Notas Rápidas

- confirmar com Pedro
- checar horário do cron
- avisar suporte

---

## Contexto da Migração

A migração foi motivada pelo crescimento da tabela `eventos` no banco de produção, que atingiu 180 milhões de registros em fevereiro de 2025 — volume que começou a impactar a performance de queries analíticas utilizadas nos relatórios semanais. A decisão foi particularmente difícil porque o banco atual (PostgreSQL 13) ainda opera corretamente para as cargas operacionais; o problema é específico para as queries de agregação histórica que varriam a tabela inteira.

A solução adotada combina duas mudanças: a atualização do PostgreSQL 13 para a versão 16, aproveitando as melhorias de paralelismo em queries analíticas, e a criação de uma estratégia de particionamento por intervalo mensal na tabela `eventos`. O particionamento reduz o escopo de cada query de agregação ao período relevante, evitando o full scan que hoje leva entre 40 e 90 segundos dependendo da carga do servidor.

O script de migração foi desenvolvido para operar em dois estágios. O primeiro estágio, executado em background sem downtime, cria a nova estrutura de tabelas e copia os dados históricos em lotes de 100.000 registros, priorizando os lotes mais antigos (com menor probabilidade de sofrer atualizações durante a migração). O segundo estágio, que requer a janela de manutenção de 30 minutos, sincroniza os registros recentes, aplica os índices finais e substitui as views e functions que referenciam a tabela original.

---

## Plano de Rollback

Caso a migração apresente problemas na etapa de sincronização final, o procedimento de rollback consiste em:

1. Reverter o apontamento das views para a tabela original (`eventos_legacy`).
2. Desativar os triggers criados na nova estrutura.
3. Notificar a equipe de suporte para comunicar o fim da manutenção mesmo com rollback.
4. Criar issue no Jira com os logs de erro completos antes de qualquer nova tentativa.

O tempo estimado para rollback completo é de 8 a 12 minutos.
