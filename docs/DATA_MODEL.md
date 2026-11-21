# Modelo de dados — Primo Data Platform

## Entidades

- **Product**: produto Prime monitorado, como Soma Prime ou limbo Prime.
- **Item**: unidade negociável retornada no Set, seja Set completo ou componente.
- **Player**: conta pública que publicou uma oferta.
- **Order**: oferta Buy ou Sell publicada para um item.
- **Execution/Snapshot**: momento em que as ofertas foram observadas.

## Relacionamentos

```text
Product 1 ─── N Item
Item    1 ─── N Order Observation
Player  1 ─── N Order Observation
Execution 1 ─ N Order Observation
```

## Fato central

`fact_order_observation` não representa uma ordem atual mutável. Representa uma **observação histórica** de uma ordem. A chave lógica é `execution_id + order_id + item_slug`; snapshots sucessivos preservam o histórico de alteração/visibilidade.

## Atributos de oferta

| Campo | Origem | Tratamento |
|---|---|---|
| `order_id` | `Order.id` | Identificador da oferta |
| `order_type` | `Order.type` | `buy` ou `sell` |
| `platinum` | `Order.platinum` | Valor retornado pela API, sem dividir |
| `quantity` | `Order.quantity` | Quantidade na oferta |
| `per_trade` | `Order.perTrade` | Quantidade por troca, quando aplicável |
| `visible` | `Order.visible` | Visibilidade retornada |
| `player_id` | `Order.user.id` | FK para jogador |
| `order_created_at` | `Order.createdAt` | Data de criação |
| `order_updated_at` | `Order.updatedAt` | Última alteração informada |
| `observed_at` | Pipeline | Instante da observação da resposta |

## Ausência de oferta

Uma execução com resposta `data: []` deve ser interpretada como uma consulta bem-sucedida que retornou zero ofertas visíveis. Uma falha HTTP deve permanecer marcada como falha. Não inferir venda, cancelamento ou exclusão apenas com base em uma oferta que não reapareceu em snapshot posterior.
