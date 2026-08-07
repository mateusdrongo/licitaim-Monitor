# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# Dependências de sistema para Playwright / Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl wget gnupg ca-certificates \
        # Chromium deps
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdbus-1-3 libdrm2 libexpat1 libgbm1 \
        libglib2.0-0 libgtk-3-0 libpango-1.0-0 libx11-6 \
        libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 \
        libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 \
        libxrender1 libxss1 libxtst6 xvfb fonts-liberation \
        # Lxml deps
        libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Dependências Python ────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala Chromium para Playwright (headless)
RUN playwright install chromium --with-deps

# ── Código ────────────────────────────────────────────────────────────────────
COPY . .

# ── Variáveis de ambiente padrão ───────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO \
    HEADLESS=true

# ── Targets de execução ───────────────────────────────────────────────────────

# Worker Celery (padrão)
CMD ["celery", "-A", "collector.app.tasks", "worker", \
     "--loglevel=info", "--concurrency=4", "-Q", "celery"]

# Para Beat (agendador):
#   docker run --entrypoint celery <image> -A collector.app.tasks beat --loglevel=info

# Para CLI manual:
#   docker run --entrypoint python <image> -m collector.app.main scrape --source pncp --days 1
