# Camada analítica — Power BI

Este documento descreve uma primeira camada semântica para consumir a Gold do projeto. Os nomes dos schemas variam conforme o target: no Databricks, use `{catalog}.gold`; no PostgreSQL/dbt, use o schema de marts gerado pelo profile (por padrão, `public_marts`).

## Tabelas recomendadas

| Tabela | Uso | Chave
|---|---|---|
| `dim_product` | Produto Prime monitorado | `product_slug`
| `dim_item` | Set ou componente negociável | `item_slug`
| `fact_item_price_snapshot` | Métricas de preço por execução, item e lado | `execution_id + item_slug + order_type`
| `vw_market_spread` | Melhor compra, melhor venda e spread | `execution_id + item_slug`

Para detalhar jogadores e ofertas individuais, conecte também `dim_player` e `int_order_observations` no dbt, ou `silver.dim_player` e `silver.fact_order_observation` no Databricks. A tabela agregada Gold não tem granularidade de jogador.

## Relacionamentos

Crie relacionamentos 1:N, com filtro em direção única:

- `dim_product[product_slug]` → `dim_item[product_slug]`
- `dim_item[item_slug]` → `fact_item_price_snapshot[item_slug]`
- `dim_item[item_slug]` → `vw_market_spread[item_slug]`

Use `observed_at` para o eixo temporal. Se criar uma dimensão calendário, relacione-a às datas de observação (e não às datas de criação da oferta, que representam outro conceito).

## Medidas DAX

Os exemplos abaixo assumem que as tabelas foram importadas com os nomes indicados. Ajuste-os se o conector acrescentar prefixo de schema.

```DAX
Qtd. Ofertas = SUM ( fact_item_price_snapshot[order_count] )

Qtd. Total Anunciada = SUM ( fact_item_price_snapshot[total_quantity] )

Menor Preço Sell =
CALCULATE (
    MIN ( fact_item_price_snapshot[min_order_platinum] ),
    fact_item_price_snapshot[order_type] = "sell"
)

Maior Preço Buy =
CALCULATE (
    MAX ( fact_item_price_snapshot[max_order_platinum] ),
    fact_item_price_snapshot[order_type] = "buy"
)

Média das Ofertas Sell =
CALCULATE (
    AVERAGE ( fact_item_price_snapshot[avg_order_platinum] ),
    fact_item_price_snapshot[order_type] = "sell"
)

Spread de Mercado =
MAX ( vw_market_spread[market_spread_platinum] )

Última Observação = MAX ( fact_item_price_snapshot[observed_at] )
```

`Média das Ofertas Sell` é a média simples das médias por snapshot/item que permanecerem no contexto do visual. Para médias históricas ponderadas ou distribuição por ordem, use `int_order_observations`/`fact_order_observation`; não interprete essa medida como preço unitário por peça.

## Páginas sugeridas

1. **Visão geral:** última observação, quantidade de ofertas Buy/Sell, melhor Sell/Buy e spread por produto.
2. **Histórico:** evolução do menor Sell, maior Buy, média e mediana por item ao longo dos snapshots.
3. **Componentes x Set:** comparar Set com componentes, incluindo `quantity_in_set`; só calcule valor equivalente quando a quantidade e a regra de composição tiverem sido validadas.
4. **Liquidez:** contagem de ofertas e quantidade anunciada por lado, item e tempo.
5. **Ofertas individuais:** tabela detalhada por jogador, tipo, preço, quantidade, status e horário de observação, usando a camada Silver/intermediate.

## Cuidados de interpretação

- Não tratar uma ausência em snapshot posterior como venda ou cancelamento.
- Não misturar médias de itens diferentes sem filtros explícitos.
- O spread é `menor Sell - maior Buy`; não representa lucro garantido nem execução garantida.
- O valor `platinum` é preservado como retornado pela API. Antes de dividir por `quantity` ou `perTrade`, validar a semântica dos campos para cada tipo de item.
- Uma resposta sem ofertas é mantida na Bronze/logs de execução; como não há ordens para agregar, pode não aparecer como linha na tabela Gold.
