# Decisão técnica: autenticação com OIDC

**Data:** 14/11/2025
**Autora:** Larissa Quintela
**Revisão prevista:** 01/02/2026

## Contexto

Hoje o login é um JWT emitido pelo próprio backend e guardado no localStorage do navegador. Isso já deu problema de XSS na tela de configurações, e a equipe de segurança pediu que a gente tire o token de lá. Além disso, cada serviço implementa a própria verificação de assinatura, e isso já causou um bug em que um serviço aceitava token expirado.

## Decisão

Adotar OIDC com Keycloak como provedor de identidade. O backend deixa de emitir token e passa a só validar. A decisão foi tomada numa reunião de arquitetura com o Diego e o time de frontend presentes.

Os parâmetros ficaram assim:

- Access token com validade de 5 minutos.
- Refresh token com rotação: a cada uso o anterior é invalidado, e reuso de um token antigo derruba a sessão inteira.
- O cookie de sessão se chama sid_escolio e sai com as flags HttpOnly, Secure e SameSite=Lax.

Os 5 minutos parecem curtos, mas com refresh silencioso no frontend a experiência do usuário não muda. O custo é mais chamadas ao Keycloak, que aguenta bem esse volume.

## Alternativas rejeitadas

- Manter o JWT no localStorage: rejeitado por causa do XSS, que a gente não consegue eliminar por completo só com sanitização.
- Sessão server-side pura: funcionaria bem para o web, mas o app mobile que está no roadmap precisa de token, então a gente teria que construir duas coisas.

## Impacto

O frontend precisa trocar o fluxo de login inteiro. A estimativa é de 2 sprints. Quem integra com a API antiga tem até o fim de dezembro para migrar, e depois disso a API antiga para de aceitar o JWT do backend.

## Riscos

O Keycloak vira ponto único de falha. A mitigação é rodar em cluster com duas réplicas e fazer backup diário da base. A Larissa também pediu um teste de restauração mensal, que ainda não tem dono.

## Aprovação

Aprovado na reunião de arquitetura. O Diego pediu que o prazo de migração fosse 31/12/2025, e a Larissa concordou, desde que a revisão de 01/02/2026 avalie se o prazo foi cumprido.
