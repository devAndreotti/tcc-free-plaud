# Política de segurança

O Escólio é um projeto de TCC. Não há garantia de suporte, prazo de correção nem SLA: os relatos são lidos e tratados no ritmo dos mantenedores.

## Versões cobertas

Somente a branch `main`. Não há versões antigas mantidas.

## Como reportar uma vulnerabilidade

O relato privado de vulnerabilidades do GitHub **não está ativado** neste repositório (que é público), e não há e-mail de contato publicado. Por isso:

1. Abra uma issue em <https://github.com/devAndreotti/tcc-free-plaud/issues> **sem detalhes sensíveis** (sem prova de conceito, chaves, caminhos ou dados pessoais). Diga apenas que se trata de uma questão de segurança e peça um canal privado.
2. Os mantenedores combinam o canal na própria issue; os detalhes seguem por lá.

Se o relato privado for ativado no futuro, este arquivo passa a indicá-lo.

## Escopo

O Escólio é um app local-first: notas, índices e bancos ficam na máquina de quem o usa. Não existe servidor próprio do projeto.

- As chaves de API de provedores de resposta (opcionais) ficam na máquina do usuário, em `pipeline/.env`, que está fora do Git (`.gitignore`). Nunca coloque chaves em issues, PRs ou logs.
- Só há tráfego para fora quando o usuário configura um provedor remoto de resposta; com provedor local (por exemplo Ollama), nada sai da máquina.
- Estão no escopo: execução indevida de código ou leitura de arquivos fora do vault por conteúdo de nota (XSS, path traversal), vazamento de chaves ou de dados do usuário, e vulnerabilidades em dependências.

## O que os mantenedores verificam

A esteira de CI (`.github/workflows/quality-gate.yml`) roda a cada alteração:

- `pip-audit` nas dependências Python;
- `npm audit --audit-level=high` nas dependências da UI;
- análise do SonarCloud, com o Quality Gate;
- lint, testes e build.

## Limites conhecidos

- É um projeto acadêmico: não houve auditoria independente nem teste de penetração.
- Os checks acima pegam vulnerabilidades conhecidas e padrões de código; não provam ausência de falhas.
- Conteúdo de notas de terceiros deve ser tratado como não confiável; a interface escapa o texto, mas isso não substitui cautela ao importar arquivos de origem desconhecida.
