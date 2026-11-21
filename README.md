# primo-data-platform

Plataforma de engenharia de dados para coletar, historizar e analisar ofertas **Buy** e **Sell** de Warframes e armas Prime no Warframe.market.

O projeto foi organizado para demonstrar dois caminhos de implementação que compartilham o mesmo escopo de negócio:

1. **Databricks + PySpark + Delta Lake + Unity Catalog + Jobs** — arquitetura Lakehouse Medallion.
2. **Python + PostgreSQL + Airbyte (conector customizado) + dbt** — arquitetura local/relacional.

A coleta de referência é implementada no pacote Python `src/primo_market`. Ele é utilizado pelo CLI e pelo notebook Bronze do Databricks. O conector Airbyte é uma alternativa autônoma e mais simples, com configuração própria de slugs.

> Importante: este repositório é um scaffold de projeto pronto para configuração e execução controlada. Não contém credenciais, workspace Databricks, cluster, catálogo Unity Catalog, ambiente Airbyte ou deploy no seu GitHub. Esses recursos precisam ser criados/configurados na sua conta. A configuração DAB é um template e deve ser validada no seu workspace antes de produção.

---

## 1. Escopo funcional

- Coletar ofertas Buy e Sell para uma lista selecionada de produtos.
- Iniciar pelo Set de cada produto e descobrir seus componentes pela API.
- Preservar cada oferta individual, sem agregar ou descartar jogadores/ofertas.
- Gravar snapshots por execução, identificados por `execution_id` e `observed_at`.
- Preservar o JSON bruto para auditoria e reprocessamento.
- Gerar métricas de preço por item e execução.
- Comparar melhor oferta de compra e venda por item (spread).

### Produtos iniciais

A configuração `config/selected_products.yml` inicia com:

- Soma Prime — `soma_prime_set` — categoria `weapon`.
- limbo Prime — `limbo_prime_set` — categoria `warframe`.

Os itens negociáveis são descobertos por `/v2/item/{slug}/set`. Assim, não é necessário manter manualmente os slugs de todos os componentes no coletor principal.

Exemplos de componentes esperados:

| Produto | Slugs de referência |
|---|---|
| Soma Prime | `soma_prime_set`, `soma_prime_blueprint`, `soma_prime_barrel`, `soma_prime_receiver`, `soma_prime_stock` |
| limbo Prime | `limbo_prime_set`, `limbo_prime_blueprint`, `limbo_prime_neuroptics_blueprint`, `limbo_prime_chassis_blueprint`, `limbo_prime_systems_blueprint` |

A resposta efetiva da API é a fonte de verdade para a composição do Set; a lista acima é apenas uma referência inicial.

---

## 2. Arquitetura

```text
                         config/selected_products.yml
                                     |
                                     v
                          Warframe.market API V2
                          /v2/item/{slug}/set
                         /v2/orders/item/{slug}
                                     |
                                     v
                           Python ingestion client
                     User-Agent | rate limit | retry
                                     |
                   +-----------------+------------------+
                   |                                    |
                   v                                    v
          Databricks / Lakehouse              PostgreSQL / Airbyte
                   |                                    |
         bronze.raw_api_response                bronze.api_response
                   |                                    |
                   v                                    v
            Silver / PySpark                     dbt staging
     dim_product, dim_item, dim_player                 |
      fact_order_observation                           v
                   |                             dbt intermediate
                   v                                    |
             Gold / PySpark                             v
      fact_item_price_snapshot                     dbt marts
          vw_market_spread                  fact_item_price_snapshot
                   |                              vw_market_spread
                   +-----------------+------------------+
                                     |
                                     v
                                Power BI
```

### Frequência

O intervalo inicial planejado é de **30 minutos**. A frequência fica configurada no Job Databricks e pode ser alterada depois de observar duração, volume e limites da API. Para execuções locais, use Agendador de Tarefas do Windows, cron ou Airflow.

### Política de coleta

O cliente começa em 2 requisições por segundo, abaixo do limite público geral documentado de 3 req/s. Usa `User-Agent` próprio, timeout, retry/backoff para 429/5xx e cabeçalho `Retry-After` quando fornecido. Evite reduzir o intervalo sem justificativa; use cache e não consulte endpoints desnecessariamente.

---

## 3. Estrutura do repositório

```text
primo-data-platform/
├── .github/workflows/             # CI, deploy DEV e PROD
├── airbyte/source-warframe-market/# Source connector Python CDK
├── config/selected_products.yml   # Catálogo de produtos habilitados
├── databricks/
│   ├── databricks.yml              # Bundle: targets DEV/PROD
│   ├── resources/                  # Definição do Job
│   ├── 01_bronze/collect.py         # Ingestão e persistência de JSON bruto
│   ├── 02_silver/normalize.py       # Dimensões e fato de observação
│   └── 03_gold/aggregate.py         # Snapshot agregado e spread
├── dbt/
│   ├── models/staging/             # Leitura do JSONB Bronze
│   ├── models/intermediate/        # Observações normalizadas
│   └── models/marts/               # Métricas analíticas
├── postgres/
│   ├── docker-compose.yml
│   └── init/                       # DDL inicial
├── src/primo_market/               # Cliente API, coletor, normalização e CLI
├── sql/postgres/                   # DDL versionado
├── tests/                          # Testes unitários
├── .env.example                    # Exemplo de variáveis (sem segredo real)
├── pyproject.toml
└── README.md
```

---

## 4. Pré-requisitos

Para rodar o caminho Python/PostgreSQL:

- Python 3.11 ou superior.
- Git.
- Docker Desktop ou Docker Engine.
- Acesso de rede à API pública do Warframe.market.

Para dbt:

- `dbt-core` e `dbt-postgres`.
- Perfil PostgreSQL configurado em `~/.dbt/profiles.yml`.

Para Databricks:

- Workspace com Unity Catalog habilitado.
- Um cluster existente compatível com os notebooks.
- Catálogos `primo_dev` e `primo_prod` (ou nomes ajustados no Bundle).
- Databricks CLI instalado localmente para validar/deployar.

---

## 5. Configuração local — passo a passo

### 5.1 Clonar e preparar ambiente

```bash
git clone https://github.com/SEU_USUARIO/primo-data-platform.git
cd primo-data-platform

# Windows PowerShell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1

# Linux/macOS
# python3.11 -m venv .venv
# source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 5.2 Variáveis de ambiente

```bash
# Windows PowerShell
Copy-Item .env.example .env

# Linux/macOS
# cp .env.example .env
```

Edite `.env` e, no mínimo, configure `WFM_USER_AGENT` com um identificador real e um contato/URL do projeto. O cliente recusa o valor-modelo enquanto o placeholder não for substituído. Não coloque tokens ou senhas em arquivos versionados. O arquivo `.env` está no `.gitignore`.

Variáveis principais:

| Variável | Função | Padrão |
|---|---|---|
| `APP_ENV` | Nome do ambiente | `dev` |
| `WFM_BASE_URL` | URL base | `https://api.warframe.market` |
| `WFM_USER_AGENT` | Identificação da aplicação | Deve ser personalizado |
| `WFM_LANGUAGE` | Idioma do nome dos itens | `en` |
| `WFM_REQUESTS_PER_SECOND` | Limite local do cliente | `2` |
| `WFM_TIMEOUT_SECONDS` | Timeout HTTP | `30` |
| `WFM_MAX_RETRIES` | Retentativas | `5` |
| `SELECTED_PRODUCTS_FILE` | Arquivo de produtos | `config/selected_products.yml` |
| `OUTPUT_DIR` | Saída dos arquivos brutos | `data/raw` |
| `DATABASE_URL` | Conexão PostgreSQL | URL local do exemplo |

### 5.3 Definir produtos monitorados

Edite `config/selected_products.yml`:

```yaml
products:
  - product_slug: soma_prime_set
    product_name: Soma Prime
    category: weapon
    enabled: true
  - product_slug: limbo_prime_set
    product_name: limbo Prime
    category: warframe
    enabled: true
```

Para incluir outro produto, acrescente a raiz do Set e habilite `enabled: true`. Desabilitar um produto não apaga o histórico já coletado.

### 5.4 Subir PostgreSQL local

Na raiz do repositório:

```bash
docker compose -f postgres/docker-compose.yml up -d
docker compose -f postgres/docker-compose.yml ps
```

O banco inicializa com schema `bronze` e as tabelas de execução e resposta bruta. Os valores do exemplo são apenas para desenvolvimento local; troque a senha em qualquer ambiente compartilhado.

### 5.5 Executar a coleta

```bash
primo-market collect
```

A execução:

1. Consulta cada Set habilitado.
2. Expande os itens retornados pela API.
3. Consulta ofertas do Set e de cada componente.
4. Grava cada resposta em `data/raw/execution_date=.../execution_id=.../` como JSONL gzip.
5. Carrega as respostas e logs no PostgreSQL se `DATABASE_URL` estiver definida.

Para coletar apenas em arquivos e não gravar no PostgreSQL:

```bash
primo-market collect --no-postgres
```

Uma execução parcialmente malsucedida persiste os resultados obtidos e os erros em `item_execution_log`, mas termina com código de saída diferente de zero para alertar o agendador.

### 5.6 Conferir dados Bronze

```sql
SELECT * FROM bronze.execution_log ORDER BY started_at DESC;

SELECT execution_id, event_type, resource_slug, observed_at,
       jsonb_typeof(response -> 'data') AS response_data_type
FROM bronze.api_response
ORDER BY observed_at DESC;

SELECT * FROM bronze.item_execution_log
ORDER BY started_at DESC, item_slug;
```

---

## 6. dbt — PostgreSQL

O fluxo principal de dbt transforma as respostas brutas JSONB em modelos analíticos. Não é preciso um segundo coletor se você estiver usando o CLI Python como fonte; Airbyte é uma alternativa de ingestão, não um componente obrigatório em paralelo.

### 6.1 Instalar dependências

```bash
pip install -r requirements-dbt.txt
```

Copie `dbt/profiles.yml.example` para `~/.dbt/profiles.yml` e ajuste host/usuário/senha. No Windows, normalmente o destino é `%USERPROFILE%\.dbt\profiles.yml`.

### 6.2 Validar e executar

```bash
cd dbt
dbt debug
dbt run
dbt test
```

O perfil se chama `primo_market` e o alvo padrão é `dev`. Por padrão, `dbt_project.yml` usa `ingestion_source: python`. Para usar os dados do Airbyte, execute `dbt run --vars '{ingestion_source: airbyte, airbyte_schema: airbyte}'` e depois `dbt test` com a mesma variável. O destino Airbyte precisa gravar `market_order_snapshots` no schema definido em `airbyte_schema`. Para usar `prod`, configure as variáveis `DBT_PROD_HOST`, `DBT_PROD_USER`, `DBT_PROD_PASSWORD`, `DBT_PROD_PORT` e `DBT_PROD_DB`, e execute:

```bash
dbt run --target prod
```

### 6.3 Modelos dbt

| Modelo | Camada | Conteúdo |
|---|---|---|
| `stg_catalog_items` | staging | Itens devolvidos pelo endpoint de Set |
| `stg_api_orders` | staging | Expansão do array de ofertas do JSON bruto (Python ou Airbyte) |
| `dim_product`, `dim_item`, `dim_player` | marts | Dimensões com cadastro mais recente de produto, item e jogador |
| `int_order_observations` | intermediate | Oferta individual com item e jogador |
| `fact_item_price_snapshot` | marts | Estatísticas por execução, item e lado Buy/Sell |
| `vw_market_spread` | marts | Melhor Sell menos melhor Buy |

Os nomes dos schemas gerados pelo dbt incluem o schema configurado no profile e o custom schema (`*_staging`, `*_intermediate`, `*_marts`), conforme o comportamento padrão do dbt. Ajuste `generate_schema_name` se preferir schemas fixos.

---

## 7. Airbyte — conector customizado

O diretório `airbyte/source-warframe-market` contém uma implementação Python CDK para a stream `market_order_snapshots`.

Essa alternativa recebe uma lista de **itens individuais** (`items`) com `item_slug`, `product_slug`, `product_name` e `category`. Ao contrário do coletor principal, este conector não expande automaticamente os Sets; inclua no Airbyte o Set e seus componentes. Ele emite um registro por item/snapshot com o array de ofertas em `response`, inclusive quando o array está vazio.

Build da imagem:

```bash
cd airbyte/source-warframe-market
docker build -t airbyte/source-warframe-market:dev .
```

A imagem deve ser publicada em um registry acessível ao seu deployment Airbyte e registrada como Custom Connector. A especificação fica em `spec.json`. Configure `items` conforme `config/airbyte_items.example.json`, `user_agent` e `requests_per_second`, teste a conexão e então configure a sincronização. No destino PostgreSQL, use o schema/namespace `airbyte` e a tabela `market_order_snapshots`. O conector gera um `execution_id` por execução da stream; `execution_id + item_slug` é a chave do snapshot.

Recomendação de arquitetura: escolha **um** orquestrador de ingestão para cada execução (CLI/Databricks ou Airbyte). Evite que ambos coletem os mesmos slugs ao mesmo tempo, pois isso duplica snapshots e carga na API.

---

## 8. Databricks — Lakehouse Medallion

### 8.1 Catálogos e schemas

O template usa dois catálogos lógicos para separar os dados DEV e PROD. Eles podem ficar no **mesmo Workspace e até no mesmo cluster**; não é necessário duplicar a infraestrutura apenas para ter duas branches:

```sql
CREATE CATALOG IF NOT EXISTS primo_dev;
CREATE CATALOG IF NOT EXISTS primo_prod;

CREATE SCHEMA IF NOT EXISTS primo_dev.bronze;
CREATE SCHEMA IF NOT EXISTS primo_dev.silver;
CREATE SCHEMA IF NOT EXISTS primo_dev.gold;

CREATE SCHEMA IF NOT EXISTS primo_prod.bronze;
CREATE SCHEMA IF NOT EXISTS primo_prod.silver;
CREATE SCHEMA IF NOT EXISTS primo_prod.gold;
```

Os nomes são ajustáveis. As branches Git `develop` e `main` separam o ciclo de código; os targets do Bundle escolhem catálogo e cluster de destino.

### 8.2 Preparar o Workspace

1. Crie um Git Folder (ou diretório Workspace) para o repositório, por exemplo `/Workspace/Shared/primo-data-platform`.
2. Garanta que `src/` e `config/` estejam disponíveis nesse caminho.
3. Ajuste os parâmetros `project_src_path` e `products_file` em `databricks/databricks.yml`, se seu caminho for diferente.
4. Crie/obtenha um cluster existente e configure a variável `DATABRICKS_CLUSTER_ID`.
5. Configure a URL do Workspace em `DATABRICKS_HOST`, o cluster em `DATABRICKS_CLUSTER_ID` e um token por secret.
6. Configure `WFM_USER_AGENT` nas variáveis de ambiente do cluster com o identificador e URL/contato do seu projeto.

### 8.3 Validar e publicar

```bash
cd databricks

# O host, token e cluster devem estar definidos no ambiente.
databricks bundle validate -t dev
databricks bundle deploy -t dev

# Para produção:
databricks bundle validate -t prod
databricks bundle deploy -t prod
```

O Job é criado pausado de propósito. Após conferir o cluster, paths, permissões, variáveis `WFM_*` e tabelas, ative o schedule de 30 minutos no Databricks. Uma execução parcialmente malsucedida mantém os resultados e os logs na Bronze, mas marca a task de coleta como falha para não publicar silenciosamente um ciclo incompleto. Os notebooks estão em `01_bronze`, `02_silver` e `03_gold`.

**Atenção:** a configuração usa um cluster existente porque o tipo de máquina depende do cloud/provedor e da infraestrutura que você já tem. Não há um ID universal de cluster. Também é necessário validar a sintaxe/path do Bundle com sua versão da Databricks CLI e workspace.

---

## 9. Git — branches `develop` e `main`

O repositório usa duas branches principais:

- `develop`: integração e validação em DEV.
- `main`: versão aprovada para PROD.

Branches auxiliares:

- `feature/nome-da-entrega`
- `fix/nome-do-ajuste`
- `hotfix/nome-do-incidente`

Fluxo sugerido:

```text
feature/*  -> Pull Request -> develop -> CI + deploy DEV
                                 |
                       validação funcional
                                 |
                                 v
                       Pull Request -> main -> CI + deploy PROD
```

Criação inicial:

```bash
git init -b main
git add .
git commit -m "chore: initialize primo-data-platform"
git remote add origin https://github.com/SEU_USUARIO/primo-data-platform.git
git push -u origin main

git switch -c develop
git push -u origin develop
```

Recomendação no GitHub:

1. Defina `develop` como branch padrão de trabalho.
2. Proteja `main`: exija Pull Request, checks aprovados e bloqueie push direto.
3. Proteja `develop` com CI e Pull Request para features, conforme o nível de rigor desejado.
4. Crie os GitHub Environments `development` e `production`.
5. Configure os secrets indicados abaixo.

### Secrets dos workflows

| Secret | Uso |
|---|---|
| `DATABRICKS_HOST` | URL do Workspace Databricks |
| `DATABRICKS_TOKEN` | Token/credencial usada pelo deploy |
| `DATABRICKS_CLUSTER_ID` | Cluster existente utilizado pelo Job |

Os workflows usam GitHub Environments separados (`development` e `production`). Configure os três secrets acima em cada Environment; eles podem apontar para o mesmo Workspace/cluster ou para recursos separados, conforme sua necessidade. Configure aprovação manual no Environment `production` para impedir deploy sem revisão.

**Conceito importante:** `develop` e `main` são as duas branches principais de código que você pediu. Branches não isolam dados/infraestrutura por conta própria. Os targets DAB permitem direcionar o mesmo código a catálogos distintos (`primo_dev`/`primo_prod`) no mesmo Workspace; também é possível configurar o mesmo catálogo caso queira somente separar versões de código, mas isso reduz a proteção entre testes e dados de produção.

---

## 10. Modelo de dados e granularidade

### Bronze

| Tabela | Granularidade | Descrição |
|---|---|---|
| `raw_api_response` / `api_response` | Uma resposta da API por execução e recurso | JSON integral, metadados do endpoint, item e instante de observação |
| `execution_log` | Uma linha por execução | Início/fim, status e contagens |
| `item_execution_log` | Uma linha por item consultado em uma execução | Sucesso/falha e quantidade de ofertas |

### Silver

| Tabela | Granularidade | Chave lógica |
|---|---|---|
| `dim_product` | Um produto principal | `product_slug` |
| `dim_item` | Um item negociável (Set ou componente) | `item_slug` |
| `dim_player` | Um jogador | `player_id` |
| `fact_order_observation` | Uma oferta observada para um item em uma execução | `execution_id + order_id + item_slug` |

A mesma oferta pode aparecer em várias execuções; isso é esperado e representa a evolução do mercado. Não sobrescreva uma observação anterior com os valores atuais.

### Gold

| Tabela/view | Granularidade | Medidas |
|---|---|---|
| `fact_item_price_snapshot` | Execução + item + lado Buy/Sell | Contagem, quantidade total, mínimo, mediana, média e máximo do platinum informado na oferta |
| `vw_market_spread` | Execução + item | Melhor Sell, melhor Buy, contagens e spread |

O campo `platinum` é preservado com o significado retornado pela API. A modelagem não calcula preço unitário dividindo por `quantity` ou `perTrade`: esses campos precisam ser interpretados em conjunto com as regras de cada item antes de derivar um preço comparável.

### Definição do spread

`market_spread_platinum = best_sell_platinum - best_buy_platinum`

`best_sell_platinum` é o menor valor de uma oferta Sell e `best_buy_platinum` é o maior valor de uma oferta Buy para o mesmo item e snapshot. Um spread negativo pode ocorrer e não deve ser corrigido silenciosamente.

---

## 11. Regras de qualidade e interpretação

- Coleta bem-sucedida com `data: []` significa zero ofertas visíveis retornadas naquele instante, não falha.
- Falha HTTP/JSON é registrada como falha da coleta do item, e não como zero ofertas.
- Oferta não observada em snapshot posterior não significa necessariamente que foi vendida ou cancelada; significa apenas que não foi retornada naquele snapshot.
- Uma oferta pode mudar de preço, quantidade, status ou deixar de estar visível.
- O endpoint de ofertas devolve ofertas visíveis dentro dos critérios de disponibilidade definidos pela API; não é um histórico oficial completo de transações.
- A API V2 ainda está abaixo de 1.0; monitore mudanças nos contratos e mantenha testes de integração.
- O conector não executa trades nem modifica ordens: apenas lê dados públicos.

---

## 12. Power BI

A especificação de tabelas, relacionamentos, medidas DAX e páginas sugeridas está em [`docs/POWER_BI.md`](docs/POWER_BI.md). A camada Gold foi preparada para relatórios de evolução de preço, spread e liquidez; para detalhamento por jogador, use a Silver/intermediate.

---

## 13. Testes e manutenção

```bash
pytest -q
ruff check src tests
```

Antes de uma alteração de API:

1. Atualize o cliente central `src/primo_market/api.py`.
2. Ajuste fixtures/testes de `tests/`.
3. Valide o coletor contra um slug de baixo volume.
4. Verifique a resposta raw armazenada.
5. Confira a normalização e os modelos dbt/Databricks.

### Próximas melhorias recomendadas

- Testes de contrato com fixtures reais anonimizadas da API.
- Alertas de falha por item e atraso de execução.
- Snapshot de catálogo com histórico de mudanças de metadados.
- Deduplicação e testes de qualidade por chave lógica.
- Histórico de presença/ausência de ofertas, sem atribuir causa indevida.
- Comparativo Set versus componentes usando quantidades necessárias por Set e regras de preço validadas.
- Dashboard Power BI com evolução de preço, liquidez, spread e disponibilidade.
- Evolução de polling para WebSocket apenas se houver necessidade de maior latência e se os termos/limites permitirem.

---

## 14. Referências técnicas

- Warframe.market — documentação API: <https://docs.warframe.market/>
- API V2 — manifests/items/Set: <https://docs.warframe.market/docs/api/manifests/>
- API V2 — orders: <https://docs.warframe.market/docs/api/orders/>
- Data models: <https://docs.warframe.market/docs/data-models/>
- Regras para integrações e rate limits: <https://docs.warframe.market/docs/rules/overview/>
- Databricks Declarative Automation Bundles: <https://docs.databricks.com/aws/en/dev-tools/bundles/>
- Airbyte Python CDK: <https://docs.airbyte.com/platform/connector-development/python-cdk/>
- dbt PostgreSQL: <https://docs.getdbt.com/reference/warehouse-profiles/postgres-profile>
