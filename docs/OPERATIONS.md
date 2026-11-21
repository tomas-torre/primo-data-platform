# Operação

## Cadência

O alvo inicial é a cada 30 minutos. O endpoint de ofertas deve ser consultado apenas para os itens selecionados. O cliente está limitado a 2 req/s e não deve ser configurado acima do limite público geral documentado.

## Incidentes

| Sintoma | Ação |
|---|---|
| HTTP 429 | Respeitar `Retry-After`, manter/baixar taxa, não aumentar concorrência |
| HTTP 5xx | Retry/backoff; verificar se o serviço está instável |
| 401/403 | Verificar mudança de política, endpoint ou acesso; não tentar contornar controles |
| Catálogo vazio | Conferir slug e formato da resposta; não criar componentes à mão sem validar |
| Zero ofertas | Validar `item_execution_log`: `success` com `order_count=0` é resultado válido |
| Falha parcial | Reprocessar somente itens que falharam em nova execução, preservando o histórico das respostas já obtidas |
| Alteração de schema | Guardar raw, criar fixture de contrato e atualizar normalizadores/modelos |

## Segurança

- Nunca versionar `.env`, tokens, passwords ou credenciais de Databricks.
- Use GitHub Secrets/Environments e secret scope do Databricks.
- Use usuário de banco com permissões mínimas.
- Não use o projeto para criar ordens ou automatizar negociação.
