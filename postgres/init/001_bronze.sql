CREATE SCHEMA IF NOT EXISTS bronze;
CREATE TABLE IF NOT EXISTS bronze.execution_log (
    execution_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    response_count INTEGER NOT NULL,
    item_count INTEGER NOT NULL,
    total_orders INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS bronze.item_execution_log (
    execution_id UUID NOT NULL REFERENCES bronze.execution_log(execution_id),
    item_slug TEXT NOT NULL,
    status TEXT NOT NULL,
    order_count INTEGER,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    error_message TEXT,
    PRIMARY KEY (execution_id, item_slug)
);
CREATE TABLE IF NOT EXISTS bronze.api_response (
    execution_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    resource_slug TEXT NOT NULL,
    product_slug TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    http_status INTEGER NOT NULL,
    response JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (execution_id, event_type, resource_slug)
);
CREATE INDEX IF NOT EXISTS ix_api_response_event_type ON bronze.api_response(event_type);
CREATE INDEX IF NOT EXISTS ix_api_response_observed_at ON bronze.api_response(observed_at);
