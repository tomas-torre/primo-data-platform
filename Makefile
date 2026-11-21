.PHONY: install test lint postgres-up postgres-down collect dbt-deps dbt-run dbt-test

install:
	python -m pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check src tests

postgres-up:
	docker compose -f postgres/docker-compose.yml up -d

postgres-down:
	docker compose -f postgres/docker-compose.yml down

collect:
	primo-market collect

dbt-deps:
	cd dbt && dbt deps

dbt-run:
	cd dbt && dbt run

dbt-test:
	cd dbt && dbt test
