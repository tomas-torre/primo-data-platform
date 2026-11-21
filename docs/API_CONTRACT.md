# Contrato da API utilizado

O coletor utiliza a API pública V2 do Warframe.market.

| Objetivo | Método/caminho | Uso no projeto |
|---|---|---|
| Validar acesso e obter catálogo geral | `GET /v2/items` | Airbyte `check_connection` |
| Descobrir Set e componentes | `GET /v2/item/{slug}/set` | Coletor principal |
| Obter ofertas de um item | `GET /v2/orders/item/{slug}` | Coletor principal e Airbyte |

## Semântica importante

- A resposta é um envelope com `apiVersion`, `data` e `error`.
- `GET /v2/item/{slug}/set` retorna `data.id` e `data.items`.
- `GET /v2/orders/item/{slug}` retorna `data` como lista de objetos `Order`.
- `Order` inclui campos como `id`, `type`, `platinum`, `quantity`, `perTrade`, `visible`, `createdAt`, `updatedAt`, `itemId` e `user`.
- A API descreve o `platinum` como total de moeda da oferta; o projeto preserva o valor recebido e não assume uma regra de preço unitário.
- O endpoint de ofertas retorna ofertas visíveis de usuários não banidos com `lastSeen` nas últimas 48 horas ou sem `lastSeen`; não é um histórico oficial completo de mercado.
- O endpoint `/top` é evitado: retorna no máximo cinco ofertas Buy e cinco Sell, enquanto o projeto precisa preservar a lista de ofertas retornada pelo endpoint por item.

## Operação responsável

- Enviar um `User-Agent` específico e descritivo. Não se passar por navegador.
- A documentação informa limite geral público de 3 requisições por segundo. O cliente deste projeto está configurado e limitado a 2 req/s.
- Usar cache, reduzir chamadas repetidas, respeitar `Retry-After` e backoff.
- A API V2 ainda está em versão abaixo de 1.0; seus contratos podem mudar. Atualizar fixtures e testes quando houver alterações.

Referências oficiais:

- https://docs.warframe.market/docs/api/manifests/
- https://docs.warframe.market/docs/api/orders/
- https://docs.warframe.market/docs/data-models/
- https://docs.warframe.market/docs/rules/overview/
