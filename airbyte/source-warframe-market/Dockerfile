FROM python:3.12-slim
WORKDIR /airbyte/integration_code
COPY source.py main.py spec.json ./
RUN pip install --no-cache-dir "airbyte-cdk>=7.45,<8" "requests>=2.32,<3"
ENV AIRBYTE_ENTRYPOINT="python /airbyte/integration_code/main.py"
ENTRYPOINT ["/bin/sh", "-c", "$AIRBYTE_ENTRYPOINT"]
