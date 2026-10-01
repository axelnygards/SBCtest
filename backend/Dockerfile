# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
# Optional extra CA (only behind TLS-intercepting proxies): docker compose build with
# EXTRA_CA_CERT=/path/ca.crt. Used for this step only, never stored in the image.
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
