# Airbyte custom source

Este conector emite uma linha por item consultado, contendo o snapshot completo do array de ofertas em `response`. Assim, um item com zero ofertas ainda produz uma linha com `response: []`.

Configuração: use `config/airbyte_items.example.json` como exemplo para preencher a propriedade `items` na conexão Airbyte. Cadastre cada Set e componente como um objeto com `item_slug`, `product_slug`, `product_name` e `category`; `item_name` e `item_role` são opcionais, mas úteis para o catálogo dbt.

**Diferença em relação ao coletor principal:** o conector Airbyte não expande automaticamente Sets. A lista de itens é mantida na configuração do Airbyte. O coletor Python principal descobre dinamicamente os componentes com o endpoint de Set.

Build local:

```bash
docker build -t airbyte/source-warframe-market:dev .
```

O conector foi preparado para Python 3.12 e Airbyte Python CDK 7.x. Publique a imagem em um registry acessível ao deployment Airbyte, registre como Custom Connector e execute o teste de conexão antes da primeira sincronização. Configure o destino PostgreSQL no schema/namespace `airbyte` (ou ajuste `airbyte_schema` no dbt).
