# Lembrete: Revisar Configuração de Timeout

Verificar se o `REDIS_TIMEOUT` está corretamente configurado no ambiente de produção. Em staging está em 30s, mas em prod pode estar com o valor padrão (5s), o que explica os erros intermitentes de conexão relatados na semana passada.

Ver variável `REDIS_CONNECT_TIMEOUT` no `.env.production`.
