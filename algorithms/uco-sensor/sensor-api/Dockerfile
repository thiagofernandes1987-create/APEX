# UCO-Sensor API — Dockerfile
# ============================
# Build multi-stage para imagem de produção enxuta.
#
# Uso:
#   docker build -t uco-sensor:latest .
#   docker run -p 8080:8080 -e UCO_ADMIN_KEY=minha_key uco-sensor:latest
#
# Variáveis de ambiente:
#   UCO_PORT       — porta do servidor (default: 8080)
#   UCO_DB_PATH    — caminho do banco SQLite (default: /data/uco_sensor.db)
#   UCO_ADMIN_KEY  — chave de administração para /auth/keys
#   UCO_AUTH       — "1" para habilitar validação de API key (default: 0 = dev mode)
#   UCO_VERBOSE    — "1" para logs detalhados (default: 0)

# ── Stage 1: Build / instalar dependências ───────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Dependências do sistema necessárias para compilar extensões C
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        make \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Imagem de runtime ───────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="APEX Project <apex@example.com>"
LABEL description="UCO-Sensor — Spectral Code Quality API"
LABEL version="0.3.0"

# Copiar dependências instaladas
COPY --from=builder /install /usr/local

WORKDIR /app

# Copiar código do sensor
COPY . /app/

# Criar diretório de dados persistente
RUN mkdir -p /data && chmod 777 /data

# Usuário não-root para segurança
RUN useradd -m -u 1000 uco && chown -R uco:uco /app /data
USER uco

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${UCO_PORT:-8080}/health', timeout=5)"

EXPOSE 8080

ENV UCO_PORT=8080
ENV UCO_DB_PATH=/data/uco_sensor.db
ENV UCO_AUTH=0
ENV UCO_VERBOSE=0
ENV UCO_ADMIN_KEY=""

# Entrypoint via script para expandir variáveis de ambiente
CMD python /app/api/server.py \
    --host 0.0.0.0 \
    --port ${UCO_PORT} \
    --db ${UCO_DB_PATH} \
    $([ "${UCO_AUTH}" = "1" ] && echo "--auth" || echo "--no-auth") \
    $([ "${UCO_VERBOSE}" = "1" ] && echo "--verbose" || true)
